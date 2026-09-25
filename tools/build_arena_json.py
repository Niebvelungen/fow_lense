r"""Build a TCG-Arena style cards.json ({"fow": {"clusters": [{"name", "sets": [{"name", "code", "cards"}]}]}})
from the flat data/cards.json produced by build_cards_json.py.

Card fields match F:\R\TCG-Arena-FoW\cards.json exactly, plus:
  image      basename of the DB's _card_image (e.g. "EDL-069.jpg"), "" when the DB has none
  image_url  full URL on the fowsim S3 bucket, "" when none
ID convention follows the target: the DB's '^' flip-side marker becomes '*'.
"""
import json, os, sys, collections

SRC = sys.argv[1] if len(sys.argv) > 1 else 'data/cards.json'
OUT = sys.argv[2] if len(sys.argv) > 2 else 'data/cards_arena.json'
D = os.path.dirname(SRC)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import IMAGE_BASE_URL  # noqa: E402
S3_BASE = IMAGE_BASE_URL.rsplit('cards/', 1)[0]

def load_tsv(name):
    with open(os.path.join(D, f'cardDatabase_{name}.tsv'), encoding='utf-8') as f:
        cols = f.readline().rstrip('\n').split(',')
        return [dict(zip(cols, l.rstrip('\n').split('\t'))) for l in f if l.strip() and l.strip() != r'\.']

cards = json.load(open(SRC, encoding='utf-8'))
clusters = sorted(load_tsv('cluster'), key=lambda r: int(r['id']))
sets = sorted(load_tsv('set'), key=lambda r: int(r['id']))
cluster_name = {int(r['id']): r['name'] for r in clusters}
set_cluster = {r['code']: cluster_name[int(r['cluster_id'])] for r in sets}
set_name = {r['code']: r['name'] for r in sets}
PROMO = next((r['name'] for r in clusters if r['name'].lower() == 'promo'), 'Promo')

def s(v):
    return '' if v is None else str(v)

def convert(c):
    img = c['image'] or ''
    return {
        'id': c['card_id'].replace('^', '*'),
        'name': c['name'],
        'type': c['types'],
        'race': c['races'],
        'cost': s(c['cost']),
        'colour': c['colours'],
        'ATK': s(c['atk']),
        'DEF': s(c['def']),
        'abilities': c['abilities'],
        'divinity': '' if c['divinity'] is None else ('∞' if c['divinity'] == 'Inf' else int(c['divinity'])),
        'willpower': '' if c['will_power'] is None else int(c['will_power']),
        'flavour': s(c['flavour']),
        'artist': ' / '.join(c['artists']),
        'rarity': s(c['rarity']),
        'fowID': str(c['id']),
        'image': os.path.basename(img),
        'image_url': S3_BASE + img if img else '',
    }

# group: cluster -> set code -> cards
grouped = collections.defaultdict(lambda: collections.defaultdict(list))
for c in cards:
    code = c['set_code']
    if code is None:  # promo / unmatched: synthesise a set from the id prefix
        code = c['card_id'].split('-')[0] if '-' in c['card_id'] else c['card_id']
        cl = PROMO
    else:
        cl = set_cluster[code]
    grouped[cl][code].append(convert(c))

set_order = {r['code']: i for i, r in enumerate(sets)}
cluster_order = {r['name']: i for i, r in enumerate(clusters)}
out = {'fow': {'clusters': []}}
for cl in sorted(grouped, key=lambda n: cluster_order.get(n, 10**6)):
    cl_sets = []
    for code in sorted(grouped[cl], key=lambda k: (set_order.get(k, 10**6), k)):
        cl_sets.append({'name': set_name.get(code, code), 'code': code,
                        'cards': sorted(grouped[cl][code], key=lambda x: x['id'])})
    out['fow']['clusters'].append({'name': cl, 'sets': cl_sets})

with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=1)

n = sum(len(st['cards']) for cl in out['fow']['clusters'] for st in cl['sets'])
print(f"{n} cards, {sum(len(cl['sets']) for cl in out['fow']['clusters'])} sets, {len(out['fow']['clusters'])} clusters -> {OUT}")
for cl in out['fow']['clusters']:
    print(f"  {cl['name']}: {len(cl['sets'])} sets, {sum(len(st['cards']) for st in cl['sets'])} cards")
print('cards without image file:', sum(1 for cl in out['fow']['clusters'] for st in cl['sets'] for c in st['cards'] if not c['image']))
