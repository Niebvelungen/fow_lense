r"""Score an embedder + index against the hand-labelled crops in data/labels/crops.jsonl.

Reports top-1 / top-5 accuracy on legible crops, accuracy split by tag (dice / rotated / rested),
and a threshold sweep showing, for each acceptance score, how many correct labels are shown and
how many wrong ones slip through (on all crops, including unknown / not_card, which must be rejected).

usage: .venv/Scripts/python tools/eval_labels.py [--emb-model extension/models/embedder.onnx]
           [--index data/index_embeddings.npz] [--labels data/labels/crops.jsonl]
"""
import argparse, json, os, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import numpy as np
import cv2
import onnxruntime as ort

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_pipeline import Index, embed, EMB_MODEL, INDEX_NPZ, EMBED_MARGIN  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_labels(path, tags_valid_from=0, video=None, exclude_video=None):
    recs, order = {}, []
    for line in open(path, encoding='utf-8'):
        if line.strip():
            r = json.loads(line)
            if r['crop'] not in recs:
                order.append(r['crop'])
            recs[r['crop']] = r
    out = []
    for i, crop in enumerate(order):
        r = recs[crop]
        if video and r['video'] != video:
            continue
        if exclude_video and r['video'] == exclude_video:
            continue
        tags = {'rotated' if t == 'rested' else t for t in r.get('tags', [])}
        r['tags'] = sorted(tags) if i >= tags_valid_from else []
        r['tags_known'] = i >= tags_valid_from
        out.append(r)
    return out


def crop_path(rec):
    folder, name = rec['crop'].split('/', 1)
    return os.path.join(ROOT, 'results', folder, name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--emb-model', default=EMB_MODEL)
    ap.add_argument('--index', default=INDEX_NPZ)
    ap.add_argument('--labels', default=os.path.join(ROOT, 'data', 'labels', 'crops.jsonl'))
    ap.add_argument('--tags-valid-from', type=int, default=280, help='tags on the first N labelled crops are ignored')
    ap.add_argument('--video', default=None, help='only crops from this video')
    ap.add_argument('--exclude-video', default=None)
    a = ap.parse_args()
    recs = [r for r in load_labels(a.labels, a.tags_valid_from, a.video, a.exclude_video) if os.path.exists(crop_path(r))]
    if not recs:
        sys.exit('no labelled crops found')
    sess = ort.InferenceSession(a.emb_model, providers=['CPUExecutionProvider'])
    index = Index(a.index)
    # flip sides share an index entry; map any catalog id to the index id via image
    cards = json.load(open(os.path.join(ROOT, 'extension', 'data', 'cards.json'), encoding='utf-8'))
    img_of = {c['id']: c['image'] for c in cards}
    idx_of_img = {str(im): str(i) for i, im in zip(index.ids, np.load(a.index)['images'])}
    def canon(cid):
        return idx_of_img.get(img_of.get(cid, ''), cid)

    crops = [cv2.cvtColor(cv2.imread(crop_path(r)), cv2.COLOR_BGR2RGB) for r in recs]
    vecs = embed(sess, crops)
    rows = []
    for r, q in zip(recs, vecs):
        _, ranked = index.match(q, top=5)
        best, second = ranked[0], ranked[1]['score'] if len(ranked) > 1 else -1
        truth = canon(r['card_id']) if r['card_id'] not in ('unknown', 'not_card') else None
        rows.append({'truth': truth, 'tags': set(r.get('tags', [])), 'tags_known': r.get('tags_known', True), 'best': best['id'], 'score': best['score'],
                     'margin': best['score'] - second, 'top5': [x['id'] for x in ranked]})

    legible = [x for x in rows if x['truth']]
    print(f"{len(rows)} labelled crops: {len(legible)} legible, {len(rows) - len(legible)} unknown/not a card")
    if legible:
        top1 = np.mean([x['best'] == x['truth'] for x in legible])
        top5 = np.mean([x['truth'] in x['top5'] for x in legible])
        print(f"legible: top-1 {top1:.1%}  top-5 {top5:.1%}")
        known = [x for x in legible if x['tags_known']]
        for tag in ('dice', 'rotated'):
            sub = [x for x in known if tag in x['tags']]
            if sub:
                print(f"  {tag:8s} n={len(sub):3d}  top-1 {np.mean([x['best'] == x['truth'] for x in sub]):.1%}")
        plain = [x for x in known if not x['tags']]
        if plain:
            print(f"  {'plain':8s} n={len(plain):3d}  top-1 {np.mean([x['best'] == x['truth'] for x in plain]):.1%}")
    print("\nthreshold sweep (margin >= %.2f):  shown-correct / legible   wrong-shown / all" % EMBED_MARGIN)
    for th in (0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9):
        shown = [x for x in rows if x['score'] >= th and x['margin'] >= EMBED_MARGIN]
        correct = sum(1 for x in shown if x['truth'] == x['best'])
        wrong = len(shown) - correct
        print(f"  {th:.2f}:  {correct:3d}/{len(legible):3d} correct shown   {wrong:3d}/{len(rows):3d} wrong shown")


if __name__ == '__main__':
    main()
