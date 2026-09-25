r"""Write the extension's packaged catalog (extension/data/cards.json) from data/cards_arena.json.
Image URLs come from tools/config.py IMAGE_BASE_URL + the image file name.

usage: python tools/build_catalog.py
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import IMAGE_BASE_URL  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = json.load(open(os.path.join(ROOT, 'data', 'cards_arena.json'), encoding='utf-8'))['fow']
out = []
for cl in src['clusters']:
    for st in cl['sets']:
        for c in st['cards']:
            if not c['image']:
                continue
            tags = [t.lower() for t in c['type']] + [x.lower() for x in c['colour']] + [st['code'].lower(), cl['name'].lower()]
            out.append({'id': c['id'], 'name': c['name'], 'orientation': 'portrait', 'imageUrl': IMAGE_BASE_URL + c['image'],
                        'image': c['image'], 'set': st['code'], 'tags': sorted(set(tags))})
path = os.path.join(ROOT, 'extension', 'data', 'cards.json')
json.dump(out, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
print(len(out), 'cards ->', path)
