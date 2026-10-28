"""Audit actual advancement displays against the shipped Russian resources.

The helper's source resources are deliberately overlaid last for an offline
content check. This does not prove Minecraft's resource-pack priority: the native
client observer separately checks the effective LanguageManager and advancements.
"""
from pathlib import Path
import argparse
import collections
import hashlib
import io
import json
import re
import zipfile

ROOT = Path(__file__).resolve().parents[2]
RESOURCES = ROOT / 'tools/world-type-lock/src/lock/resources'
BUILTIN = Path('builtin/russian-advancements')
CYRILLIC = re.compile('[А-Яа-яЁё]')
ADVANCEMENT = re.compile(r'data/([^/]+)/advancements/(.+)\.json$')
LANGUAGE = re.compile(r'assets/[^/]+/lang/(en_us|ru_ru)\.json$')


def read_json(data):
    # Gson's language loader accepts line breaks inside strings. One unrelated
    # upstream ShoulderSurfing translation contains those, so match its syntax.
    return json.loads(data.decode('utf-8-sig'), strict=False)


def component_parts(component):
    """Yield every literal/translatable component, including nested arguments."""
    if isinstance(component, str):
        yield ('text', component)
    elif isinstance(component, list):
        for value in component:
            yield from component_parts(value)
    elif isinstance(component, dict):
        if 'translate' in component:
            yield ('translate', component['translate'])
        if 'text' in component:
            yield ('text', component['text'])
        for key in ('extra', 'with', 'separator'):
            if key in component:
                yield from component_parts(component[key])


def scan_pack(pack, resources=RESOURCES, vanilla_ru=None, overlay=True):
    """Return source/effective displays, language values and reproducible inputs."""
    pack, resources = Path(pack), Path(resources)
    advancements, source_advancements = {}, {}
    languages = {'en_us': {}, 'ru_ru': {}}
    inputs = {}

    def visit(name, data, source):
        match = LANGUAGE.fullmatch(name)
        if match:
            languages[match[1]].update(read_json(data))
        match = ADVANCEMENT.fullmatch(name)
        if match:
            advancements[match[1] + ':' + match[2]] = read_json(data)

    def archive(archive_file, source):
        for name in sorted(archive_file.namelist()):
            if name.startswith('META-INF/jarjar/') and name.endswith('.jar'):
                with zipfile.ZipFile(io.BytesIO(archive_file.read(name))) as nested:
                    archive(nested, source + '!' + name)
            elif LANGUAGE.fullmatch(name) or ADVANCEMENT.fullmatch(name):
                visit(name, archive_file.read(name), source)

    jars = sorted((pack / 'mods').glob('*.jar'))
    files = [pack / 'minecraft-1.20.1-client.jar', *jars,
             *sorted((pack / 'resourcepacks').glob('*.zip'))]
    for path in files:
        if not path.is_file():
            raise ValueError('Required audit input is missing: ' + path.name)
        data = path.read_bytes()
        inputs[path.relative_to(pack).as_posix()] = hashlib.sha256(data).hexdigest()
        # Baseline is the unmodified authors' content. Reading an already built
        # localization helper here would hide the only intentional JSON override
        # from the gameplay-preservation comparison. Its byte identity is checked
        # independently by build_helper.py --verify-installed.
        if path.name.startswith('cad-world-type-lock-'):
            continue
        with zipfile.ZipFile(io.BytesIO(data)) as opened:
            archive(opened, path.relative_to(pack).as_posix())
    source_advancements.update(advancements)
    if vanilla_ru:
        path = Path(vanilla_ru)
        languages['ru_ru'].update(read_json(path.read_bytes()))
        inputs['minecraft/lang/ru_ru.json'] = hashlib.sha256(path.read_bytes()).hexdigest()
    if overlay:
        # The display-only datapack is registered as mandatory TOP SERVER_DATA.
        # Ordinary mod packs have a different data priority than language packs,
        # and an old world's Enabled list may retain their historical order.
        for layer in (resources, resources / BUILTIN):
            for path in sorted(layer.rglob('*.json')):
                relative = path.relative_to(layer).as_posix()
                if LANGUAGE.fullmatch(relative) or ADVANCEMENT.fullmatch(relative):
                    visit(relative, path.read_bytes(), 'helper-source')
    return advancements, source_advancements, languages, inputs


def audit(pack=ROOT, resources=RESOURCES, vanilla_ru=None):
    effective, original, languages, inputs = scan_pack(pack, resources, vanilla_ru)
    rows, failures = [], []
    for identifier, advancement in sorted(effective.items()):
        display = advancement.get('display')
        if not display:
            continue
        fields = {}
        # Vanilla's ru_ru is a downloaded Mojang asset, not inside client.jar.
        # Do not invent a successful offline check when that input was omitted.
        checked = vanilla_ru is not None or not identifier.startswith('minecraft:')
        for field in ('title', 'description'):
            parts = []
            for kind, value in component_parts(display[field]):
                resolved = (languages['ru_ru'].get(value,
                            languages['en_us'].get(value, value))
                            if kind == 'translate' else value)
                parts.append({'kind': kind, 'value': value, 'ru': resolved})
                if checked and resolved.strip() and not CYRILLIC.search(resolved):
                    failures.append({'id': identifier, 'field': field,
                                     'kind': kind, 'value': value, 'ru': resolved})
            fields[field] = parts
        rows.append({'id': identifier, 'checked': checked, 'display': display,
                     'fields': fields})
    return {'schemaVersion': 1,
            'scope': 'Offline content overlay; native client proves runtime priority',
            'visibleCount': len(rows), 'checkedCount': sum(r['checked'] for r in rows),
            'byNamespace': dict(collections.Counter(r['id'].split(':')[0] for r in rows)),
            'failureCount': len(failures), 'failures': failures,
            'inputSha256': inputs, 'advancements': rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pack', type=Path, default=ROOT)
    parser.add_argument('--resources', type=Path, default=RESOURCES)
    parser.add_argument('--vanilla-ru', type=Path,
                        help='Downloaded Mojang assets object minecraft/lang/ru_ru.json')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.pack, args.resources, args.vanilla_ru)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: report[k] for k in ('visibleCount', 'checkedCount', 'failureCount')}))
    if report['failureCount']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
