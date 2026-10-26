"""Build the reproducible pack helper; optionally run real Minecraft/Forge native audits.

The ordinary build downloads only two SHA256-pinned public Forge/Mixin dependencies.
It never installs the output, edits a lock, launches Minecraft, or attaches to a JVM.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent
VERSION = '1.0.0'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_snapshot():
    files = [ROOT/'README.md', ROOT/'LICENSE', ROOT/'build-dependencies.json',
             ROOT/'build_helper.py', ROOT/'build_observer.py']
    files += [path for path in (ROOT/'src').rglob('*') if path.is_file()]
    return {path.relative_to(ROOT).as_posix(): sha(path) for path in files if path.is_file()}


def executable(jdk, name):
    return jdk / 'bin' / (name + ('.exe' if os.name == 'nt' else ''))


def run(command, cwd=ROOT):
    process = subprocess.run(list(map(str, command)), cwd=cwd, capture_output=True,
                             text=True, encoding='utf-8', errors='replace')
    if process.stdout.strip(): print(process.stdout.strip()[-8000:])
    if process.stderr.strip(): print(process.stderr.strip()[-8000:], file=sys.stderr)
    if process.returncode: raise SystemExit(process.returncode)
    return (process.stdout + process.stderr).strip()


def arguments_file(path, values):
    path.write_text('\n'.join('"'+str(value).replace('\\', '/')+'"' for value in values)+'\n', encoding='utf-8')
    return '@'+str(path)


def native_classpath(shared):
    libraries = shared/'libraries'
    paths = [libraries/'net/minecraftforge/forge/1.20.1-47.3.7/forge-1.20.1-47.3.7-client.jar',
             libraries/'net/minecraft/client/1.20.1-20230612.114412/client-1.20.1-20230612.114412-srg.jar',
             libraries/'net/minecraft/client/1.20.1-20230612.114412/client-1.20.1-20230612.114412-extra.jar',
             libraries/'net/minecraftforge/forge/1.20.1-47.3.7/forge-1.20.1-47.3.7-universal.jar']
    paths += sorted((libraries/'net/minecraftforge').rglob('*1.20.1-47.3.7*.jar'))
    for version in ['1.20.1', '1.20.1-forge-47.3.7']:
        descriptor = shared/'versions'/version/(version+'.json')
        if not descriptor.is_file(): raise SystemExit('Exact native runtime is not prepared: '+version)
        for library in json.loads(descriptor.read_text(encoding='utf-8'))['libraries']:
            relative = library.get('downloads', {}).get('artifact', {}).get('path')
            if not relative:
                parts = library['name'].split(':')
                filename = parts[1]+'-'+parts[2]+('-'+parts[3] if len(parts)>3 else '')+'.jar'
                relative = '/'.join([parts[0].replace('.', '/'), parts[1], parts[2], filename])
            path = libraries/relative
            if path.is_file(): paths.append(path)
    for required in paths[:4]:
        if not required.is_file(): raise SystemExit('Native audit input is missing: '+str(required))
    return list(dict.fromkeys(paths))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--jdk', type=Path)
    parser.add_argument('--native-shared', type=Path)
    parser.add_argument('--native-java', type=Path)
    parser.add_argument('--verify-installed', type=Path,
                        help='Fail unless this existing JAR has exactly the rebuilt bytes')
    args = parser.parse_args()
    output = args.output.resolve()
    if not any(part.lower() == 'artifacts' for part in output.parts):
        raise SystemExit('Build output must be beneath artifacts')
    jdk = (args.jdk or Path(os.environ.get('JAVA_HOME', r'C:\Tools\jdk-25.0.2'))).resolve()
    compiler = executable(jdk, 'javac')
    if not compiler.is_file(): raise SystemExit('A JDK25.0.2 compiler is required: '+str(compiler))
    compiler_version = run([compiler, '-version'])
    if '25.0.2' not in compiler_version:
        raise SystemExit('Use JDK25.0.2 for byte-identical local/CI compilation')
    output.mkdir(parents=True, exist_ok=True)
    snapshot = source_snapshot()
    source_digest = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
    build = output/('build-'+source_digest[:16])
    classes = build/'classes'
    classes.mkdir(parents=True, exist_ok=True)
    dependencies = []
    pins = json.loads((ROOT/'build-dependencies.json').read_text())['compile']
    for pin in pins:
        candidate = args.native_shared/'libraries'/pin['path'] if args.native_shared else None
        if candidate is None or not candidate.is_file():
            candidate = output/'dependencies'/pin['fileName']
            if not candidate.is_file():
                candidate.parent.mkdir(parents=True, exist_ok=True)
                request = urllib.request.Request(pin['url'], headers={'User-Agent': 'LANMinecraft-pack-build'})
                with urllib.request.urlopen(request, timeout=120) as response:
                    candidate.write_bytes(response.read())
        if sha(candidate) != pin['sha256']:
            raise SystemExit('Pinned build dependency SHA256 mismatch: '+pin['fileName'])
        dependencies.append(candidate.resolve())
    source_files = sorted((ROOT/'src/lock/java').rglob('*.java'))
    classpath = os.pathsep.join(map(str, dependencies))
    run([compiler, arguments_file(build/'javac.args', [
        '--release', '17', '-g:none', '-encoding', 'UTF-8', '-proc:none',
        '-classpath', classpath, '-d', classes, *source_files])])
    entries = {
        'META-INF/MANIFEST.MF': b'Manifest-Version: 1.0\r\nFMLModType: MOD\r\n'
            b'MixinConfigs: cad_world_type_lock.mixins.json\r\n\r\n',
        'META-INF/LICENSE': (ROOT/'LICENSE').read_text(encoding='utf-8').replace('\r\n', '\n').encode(),
    }
    for directory in [classes, ROOT/'src/lock/resources']:
        for path in sorted(directory.rglob('*')):
            if not path.is_file(): continue
            relative = path.relative_to(directory).as_posix()
            data = path.read_bytes()
            if path.suffix == '.class':
                if int.from_bytes(data[6:8], 'big') != 61: raise SystemExit('Non-Java17 helper class: '+relative)
            else:
                data = data.decode('utf-8').replace('\r\n', '\n').encode('utf-8')
            entries[relative] = data
    jar = output/('cad-world-type-lock-'+VERSION+'.jar')
    # STORED avoids zlib-version differences. Canonical platform/time/order make
    # the exact output reproducible on Windows and Linux with the pinned JDK.
    with zipfile.ZipFile(jar, 'w', compression=zipfile.ZIP_STORED) as archive:
        for name, data in sorted(entries.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o644 << 16
            info.compress_type = zipfile.ZIP_STORED
            archive.writestr(info, data)
    if args.verify_installed:
        if not args.verify_installed.is_file() or sha(args.verify_installed) != sha(jar):
            raise SystemExit('Installed helper does not match its reproducible sources')
    report = {'schemaVersion': 1, 'modId': 'cad_world_type_lock', 'version': VERSION,
              'presetId': 'caves_and_dungeons:modded_mines', 'minecraftVersion': '1.20.1',
              'forgeVersion': '47.3.7', 'javaRelease': 17, 'compiler': compiler_version,
              'jar': str(jar), 'sha256': sha(jar), 'sizeBytes': jar.stat().st_size,
              'nativeVerified': False, 'runtimeVerified': False, 'visualVerified': False,
              'compileDependencies': pins, 'sourceSnapshot': snapshot}
    if args.native_shared:
        if not args.native_java or not args.native_java.is_file():
            raise SystemExit('--native-java must point to the prepared Java17 runtime')
        paths = native_classpath(args.native_shared.resolve())
        tests = build/'native-test-classes'
        tests.mkdir(parents=True, exist_ok=True)
        native_sources = sorted((ROOT/'src/native-test/java').rglob('*.java'))
        if not native_sources: raise SystemExit('Native audit sources are missing')
        native_cp = os.pathsep.join(map(str, [classes, *paths]))
        run([compiler, arguments_file(build/'javac-native-tests.args', [
            '--release', '17', '-g:none', '-encoding', 'UTF-8', '-proc:none',
            '-classpath', native_cp, '-d', tests, *native_sources])])
        services = ROOT/'src/native-test/resources'
        if services.is_dir():
            for path in services.rglob('*'):
                if path.is_file():
                    target = tests/path.relative_to(services)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(path, target)
        execution_cp = os.pathsep.join(map(str, [tests, classes, ROOT/'src/lock/resources', *paths]))
        # Vanilla codec bootstrap cannot mix raw Forge access-transformed classes
        # without ModLauncher. Use its genuine SRG classes first for this test;
        # the Mixin placement test separately requires exact Forge bytes first.
        codec_cp = os.pathsep.join(map(str, [tests, classes, ROOT/'src/lock/resources',
                                           paths[1], paths[0], *paths[2:]]))
        resources = run([args.native_java, '-Xmx512M', '-cp', codec_cp,
                         'dev.lanminecraft.cadlock.test.NativeResourcesTest', ROOT/'src/lock/resources'], cwd=build)
        mixins = run([args.native_java, '-Xmx512M', '-cp', execution_cp,
                      'dev.lanminecraft.cadlock.test.MixinTransformTest', build/'native-mixin-proof'], cwd=build)
        report.update(nativeVerified=True, nativeResourceProof=resources, nativeMixinProof=mixins)
    final_snapshot = source_snapshot()
    if snapshot != final_snapshot:
        raise SystemExit('Helper sources changed during build; wait for their owner and rerun')
    (output/'build-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({key: report[key] for key in ['jar', 'sha256', 'sizeBytes', 'nativeVerified', 'runtimeVerified']}))


if __name__ == '__main__':
    main()
