r"""Join the extracted cardDatabase_* TSVs (PostgreSQL COPY text format) into data/cards.json."""
import json, os, sys, collections
D = sys.argv[1] if len(sys.argv) > 1 else 'data'

ESC = {'n': '\n', 't': '\t', 'r': '\r', 'b': '\b', 'f': '\f', 'v': '\v', '\\': '\\'}

def unescape(v):
    if v == r'\N':
        return None
    out = []; i = 0
    while i < len(v):
        c = v[i]
        if c == '\\' and i + 1 < len(v):
            out.append(ESC.get(v[i + 1], v[i + 1])); i += 2
        else:
            out.append(c); i += 1
    return ''.join(out)

def load(name):
    with open(os.path.join(D, f'cardDatabase_{name}.tsv'), encoding='utf-8') as f:
        cols = f.readline().rstrip('\n').split(',')
        rows = []
        for line in f:
            line = line.rstrip('\n')
            if not line or line == r'\.':
                continue
            rows.append(dict(zip(cols, map(unescape, line.split('\t')))))
    return rows

def by_id(rows):
    return {int(r['id']): r for r in rows}

def m2m(rows, left, right):
    d = collections.defaultdict(list)
    for r in rows:
        d[int(r[left])].append(int(r[right]))
    return d

cards = load('card'); abil_text = by_id(load('abilitytext'))
types = by_id(load('type')); colours = by_id(load('cardcolour')); races = by_id(load('race'))
artists = by_id(load('cardartist')); sets = load('set'); clusters = by_id(load('cluster'))
formats = by_id(load('format'))
c_types = m2m(load('card_types'), 'card_id', 'type_id')
c_col = m2m(load('card_colours'), 'card_id', 'cardcolour_id')
c_race = m2m(load('card_races'), 'card_id', 'race_id')
c_art = m2m(load('card_artists'), 'card_id', 'cardartist_id')
banned = m2m(load('bannedcard'), 'card_id', 'format_id')
abilities = collections.defaultdict(list)
for r in load('cardability'):
    abilities[int(r['card_id'])].append((int(r['position']), int(r['ability_text_id'])))
rulings = collections.defaultdict(list)
for r in load('ruling'):
    rulings[int(r['card_id'])].append({'text': r['text'], 'company_confirmed': r['company_confirmed'] == 't'})
set_by_code = {s['code']: s for s in sets}

out = []
for c in cards:
    cid = int(c['id']); code = c['card_id']
    # longest set code that prefixes the card id (handles ABC-SD04-001 vs ABC)
    set_code = max((k for k in set_by_code if code.startswith(k + '-')), key=len, default=None)
    s = set_by_code.get(set_code)
    out.append({
        'id': cid, 'card_id': code, 'name': c['name'], 'name_plain': c['name_without_punctuation'],
        'set_code': set_code, 'set_name': s['name'] if s else None,
        'cluster': clusters[int(s['cluster_id'])]['name'] if s else None,
        'rarity': c['rarity'], 'cost': c['cost'],
        'atk': int(c['ATK']) if c['ATK'] is not None else None,
        'def': int(c['DEF']) if c['DEF'] is not None else None,
        'divinity': c['divinity'], 'will_power': c['will_power'],
        'types': [types[t]['name'] for t in c_types.get(cid, [])],
        'colours': [colours[t]['db_representation'] for t in c_col.get(cid, [])],
        'races': [races[t]['name'] for t in c_race.get(cid, [])],
        'artists': [artists[t]['name'] for t in c_art.get(cid, [])],
        'abilities': [abil_text[a]['text'] for _, a in sorted(abilities.get(cid, []))],
        'flavour': c['flavour'], 'image': c['_card_image'],
        'rulings': rulings.get(cid, []),
        'banned_in': [formats[f]['name'] for f in banned.get(cid, [])],
    })
out.sort(key=lambda x: x['card_id'])
with open(os.path.join(D, 'cards.json'), 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print(len(out), 'cards written')
print('sets:', len(sets), '| cards without matching set:', sum(1 for c in out if c['set_name'] is None))
print('image path patterns:', collections.Counter((c['image'] or 'NULL').split('/')[0] for c in out))
print('cards with no image:', sum(1 for c in out if not c['image']))
print(json.dumps(next(c for c in out if c['card_id'] == 'EDL-069'), ensure_ascii=False, indent=1))
