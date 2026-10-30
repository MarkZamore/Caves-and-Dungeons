"""Validate the Caves key-only preset against its exact source-name stock.

Uses conservative UNIVERSAL contexts and the actual Forge47.4 comparator rule.
It permits only unchanged author collision pairs, with no changed binding waived.
A full current client inventory/apply/restart is a separate check.
"""
from pathlib import Path
import itertools,json,re,hashlib,sys
from conflict_model import native_same
HERE=Path(__file__).resolve().parent
PACK=HERE.parent.parent
LINE=re.compile(r"^key_(?P<name>[^:]+):(?P<key>[^:]+)(?::(?P<mod>SHIFT|CONTROL|ALT))?$")

def read(text):
    rows={}
    for raw in text.splitlines():
        s=raw.split("  #",1)[0].strip()
        if not s or s.startswith('#'):continue
        m=LINE.fullmatch(s)
        if not m:raise ValueError("Not a key-only row: "+s)
        n=m['name']
        if n in rows:raise ValueError("Duplicate mapping: "+n)
        rows[n]=m['key']+(':'+m['mod'] if m['mod'] else '')
    return rows

def pairs(rows):
    active={n:v for n,v in rows.items() if v.split(':')[0]!='key.keyboard.unknown'}
    found=set()
    for a,b in itertools.combinations(active,2):
        def val(n):
            key,*mod=active[n].split(':')
            return 'UNIVERSAL',mod[0] if mod else 'NONE',key
        if native_same(val(a),val(b)) or native_same(val(b),val(a)):found.add(tuple(sorted((a,b))))
    return found

def check():
    stock=json.loads((HERE/'stock.json').read_text(encoding='utf-8'))
    if '--skip-jar-check' not in sys.argv:
        current={p.name:p for p in (PACK/'mods').glob('*.jar')}
        if set(current)!=set(stock['sourceJars']):raise ValueError('Source JAR set differs from frozen stock')
        for name,p in current.items():
            digest=hashlib.sha256()
            with p.open('rb') as stream:
                for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
            if digest.hexdigest()!=stock['sourceJars'][name]:raise ValueError('Source JAR SHA differs: '+name)
    rows=read((PACK/'launcher/controls-preset.txt').read_text(encoding='utf-8'))
    if set(rows)!=set(stock['expectedNames']):raise ValueError('Names differ from audited stock')
    baseline=stock['baselineBindings']
    introduced=pairs(rows)-pairs(baseline)
    if introduced:raise ValueError('New conservative native conflicts: '+str(sorted(introduced)))
    changed={n for n,v in rows.items() if baseline.get(n)!=v}
    if any({a,b}&changed for a,b in pairs(rows)):raise ValueError('Changed binding still conflicts')
    for name,key in {'key.ftbquests.quests':'grave.accent','key.curios.open.desc':'g','key.special_ability':'c','key.glowroot.drill_activate':'j','keybind.sophisticatedbackpacks.open_backpack':'b'}.items():
        if rows[name]!='key.keyboard.'+key:raise ValueError('Required useful action changed: '+name)
    active=sum(v!='key.keyboard.unknown' for v in rows.values())
    print(f'{len(rows)} names, {active} enabled, {len(rows)-active} unbound;0introducedconservativeconflicts;unchangedauthorGUIpairs={len(pairs(rows))}')
    return True

if __name__=='__main__':check()
