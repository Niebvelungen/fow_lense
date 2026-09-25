"""Side-by-side sheet: for each detected box in a frame, the crop and its top-3 index matches."""
import json, os, sys, cv2, numpy as np
res_dir, t = sys.argv[1], int(sys.argv[2])
summary = json.load(open(os.path.join(res_dir, 'summary.json'), encoding='utf-8'))
frame = next(f for f in summary if int(f['t']) == t)
cards = {c['id']: c for c in json.load(open('extension/data/cards.json', encoding='utf-8'))}
H, W = 180, 130
rows = []
for i, b in enumerate(frame['boxes']):
    crop = cv2.imread(os.path.join(res_dir, f"t{t:05d}_crop{i}.jpg"))
    tiles = [cv2.resize(crop, (W, H))]
    for m in b['top']:
        img_name = cards.get(m['id'], {}).get('image')
        im = cv2.imread(f"media/cards/{img_name}") if img_name else None
        tile = cv2.resize(im, (W, H)) if im is not None else np.zeros((H, W, 3), np.uint8)
        cv2.putText(tile, f"{m['score']:.2f}", (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 3)
        cv2.putText(tile, f"{m['score']:.2f}", (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
        tiles.append(tile)
    row = np.concatenate(tiles, axis=1)
    tag = ("OK " if b['accepted'] else "?  ") + f"det {b['det']:.2f}"
    cv2.putText(row, tag, (4, H - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 3)
    cv2.putText(row, tag, (4, H - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
    rows.append(row)
half = (len(rows) + 1) // 2
left = np.concatenate(rows[:half], axis=0)
right = np.concatenate(rows[half:], axis=0) if rows[half:] else np.zeros_like(left)
if right.shape[0] < left.shape[0]:
    right = np.concatenate([right, np.zeros((left.shape[0] - right.shape[0], right.shape[1], 3), np.uint8)], axis=0)
out = os.path.join(res_dir, f"sheet_t{t:05d}.jpg")
cv2.imwrite(out, np.concatenate([left, np.full((left.shape[0], 8, 3), 80, np.uint8), right], axis=1), [cv2.IMWRITE_JPEG_QUALITY, 85])
print(out)
