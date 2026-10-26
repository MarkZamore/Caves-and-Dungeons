"""Build explicit fixture-only native client checks; does not attach or launch."""
import argparse
from pathlib import Path
import subprocess
import zipfile

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--jdk', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--revision', type=int, default=1)
    p.add_argument('--agent', choices=('checks', 'title-stop', 'server-stop'), default='checks')
    a = p.parse_args()
    out = a.output.resolve()
    if not any(x.lower() == 'artifacts' for x in out.parts):
        raise ValueError('Build output must stay inside artifacts')
    out.mkdir(parents=True, exist_ok=True)
    classes = out / 'classes'; classes.mkdir(exist_ok=True)
    sources = sorted((Path(__file__).parent / 'src').rglob('*.java'))
    if not 1 <= a.revision <= 99:
        raise ValueError('QA revision must be between 1 and 99')
    agent_class = {'checks': 'ClientChecks', 'title-stop': 'NativeClientStop', 'server-stop': 'NativeStop'}[a.agent]
    if a.agent == 'checks' and a.revision > 1:
        agent_class += 'R' + str(a.revision)
        original = next(f for f in sources if f.name == 'ClientChecks.java')
        generated = out / 'generated' / (agent_class + '.java')
        generated.parent.mkdir(exist_ok=True)
        generated.write_text(original.read_text(encoding='utf-8').replace('public final class ClientChecks {', 'public final class ' + agent_class + ' {'), encoding='utf-8')
        sources = [f for f in sources if f != original] + [generated]
    cmd = [str(a.jdk / 'bin/javac.exe' if (a.jdk / 'bin/javac.exe').exists() else a.jdk / 'bin/javac'), '--release', '17', '-encoding', 'UTF-8', '-d', str(classes), *map(str, sources)]
    subprocess.run(cmd, check=True)
    jar = out / ({'checks':'cad-native-client-checks', 'title-stop':'cad-native-title-stop', 'server-stop':'cad-native-server-stop'}[a.agent] + '-1.0.0.jar')
    manifest = ('Manifest-Version: 1.0\r\nAgent-Class: dev.lanminecraft.cadqa.' + agent_class + '\r\nCan-Redefine-Classes: false\r\nCan-Retransform-Classes: false\r\n\r\n').encode()
    with zipfile.ZipFile(jar, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name, data in [('META-INF/MANIFEST.MF', manifest)] + [(f.relative_to(classes).as_posix(), f.read_bytes()) for f in sorted(classes.rglob('*.class'))]:
            info = zipfile.ZipInfo(name, (1980,1,1,0,0,0)); info.compress_type=zipfile.ZIP_DEFLATED; info.external_attr=0o644 << 16
            z.writestr(info, data)
    print(jar)

if __name__ == '__main__': main()
