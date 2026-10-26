"""Build optional Java17 QA observer; does not launch/attach/select/create a world."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--jdk', type=Path, default=Path(r'C:\Tools\jdk-25.0.2'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if not any(part.lower() == 'artifacts' for part in output.parts):
        raise SystemExit('Build output must be beneath artifacts')
    classes = output / 'classes'
    classes.mkdir(parents=True, exist_ok=True)
    sources = sorted((ROOT / 'src/main/java').rglob('*.java'))
    result = subprocess.run([str(args.jdk/'bin/javac.exe'), '--release', '17', '-encoding', 'UTF-8',
                             '-d', str(classes), *map(str, sources)], capture_output=True,
                            text=True, encoding='utf-8', errors='replace')
    if result.returncode:
        raise SystemExit(result.stdout + result.stderr)
    entries = {'META-INF/MANIFEST.MF': b'Manifest-Version: 1.0\r\n'
               b'Premain-Class: dev.lanminecraft.cadqa.WorldTypeObserver\r\n'
               b'Agent-Class: dev.lanminecraft.cadqa.WorldTypeObserver\r\n'
               b'Can-Redefine-Classes: false\r\nCan-Retransform-Classes: false\r\n\r\n'}
    for file in classes.rglob('*.class'):
        data = file.read_bytes()
        if int.from_bytes(data[6:8], 'big') != 61:
            raise SystemExit('Observer must use Java17 bytecode')
        entries[file.relative_to(classes).as_posix()] = data
    jar = output / 'cad-world-type-observer-1.20.1-0.1.0.jar'
    with zipfile.ZipFile(jar, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(entries.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, data, compresslevel=9)
    report = {'jar': str(jar), 'sha256': hashlib.sha256(jar.read_bytes()).hexdigest(),
              'javaRelease': 17, 'transformsClasses': False, 'mutatesWorldSelection': False,
              'runtimeVerified': False, 'target': 'Minecraft1.20.1 client SRG/development names'}
    (output/'build-report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
