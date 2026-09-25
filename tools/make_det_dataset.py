r"""Synthetic YOLO dataset for card detection: card images pasted onto playmat-like backgrounds
in the layouts a stream shows (table spread, stacks, rested cards, hands, sidebar preview),
with stream-style degradation. Also emits a small set of real frames pseudo-labelled by the
stock Riftbound detector at high confidence (for domain grounding).

usage: .venv/Scripts/python tools/make_det_dataset.py [--n 3000] [--out datasets/cards]
Writes datasets/cards/{images,labels}/{train,val}/... and datasets/cards/cards.yaml
"""
import argparse, json, os, random, sys, math
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from card_aug import imread_u, load_backgrounds  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H = 1280, 720


def playmat(cards, rng, frames):
    """Background: blurred blown-up card art (playmats are art), a plain cloth, or a real frame with no boxes."""
    r = rng.random()
    if r < 0.45:
        art = imread_u(cards[rng.randrange(len(cards))])
        art = art[int(art.shape[0] * 0.1):int(art.shape[0] * 0.6)]
        bg = cv2.resize(art, (W, H), interpolation=cv2.INTER_CUBIC)
        bg = cv2.GaussianBlur(bg, (0, 0), rng.uniform(2, 9))
        bg = (bg.astype(np.float32) * rng.uniform(0.35, 0.8)).astype(np.uint8)
    elif r < 0.92:
        col = np.array([rng.randrange(15, 110) for _ in range(3)], dtype=np.float32)
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        grad = (xx / W * rng.uniform(-40, 40) + yy / H * rng.uniform(-40, 40))[..., None]
        bg = np.clip(col + grad + np.random.default_rng(rng.randrange(1 << 30)).normal(0, 6, (H, W, 3)), 0, 255).astype(np.uint8)
    else:
        f = frames[rng.randrange(len(frames))] if frames else np.full((H, W, 3), 60, np.uint8)
        bg = cv2.resize(f, (W, H))
        bg = cv2.GaussianBlur(bg, (0, 0), rng.uniform(6, 14))  # kill the real cards in it
    return bg


def paste(bg, card, cx, cy, w, h, angle, rng, idmap=None, idx=-1):
    """Paste card rotated by angle (deg) centred at (cx, cy) with size (w, h). Returns axis-aligned box."""
    img = cv2.resize(card, (max(4, int(w)), max(4, int(h))), interpolation=cv2.INTER_AREA)
    if rng.random() < 0.5:
        img = cv2.GaussianBlur(img, (0, 0), rng.uniform(0.3, 1.6))
    img = np.clip(img.astype(np.float32) * rng.uniform(0.7, 1.3) + rng.uniform(-25, 25), 0, 255).astype(np.uint8)
    ih, iw = img.shape[:2]
    diag = int(math.hypot(iw, ih)) + 4
    canvas = np.zeros((diag, diag, 4), np.uint8)
    ox, oy = (diag - iw) // 2, (diag - ih) // 2
    canvas[oy:oy + ih, ox:ox + iw, :3] = img
    canvas[oy:oy + ih, ox:ox + iw, 3] = 255
    M = cv2.getRotationMatrix2D((diag / 2, diag / 2), angle, 1.0)
    rot = cv2.warpAffine(canvas, M, (diag, diag), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0, 0))
    x0, y0 = int(cx - diag / 2), int(cy - diag / 2)
    x1, y1 = x0 + diag, y0 + diag
    sx0, sy0 = max(0, -x0), max(0, -y0)
    sx1, sy1 = diag - max(0, x1 - W), diag - max(0, y1 - H)
    if sx1 <= sx0 or sy1 <= sy0:
        return None
    dst = bg[max(0, y0):max(0, y0) + (sy1 - sy0), max(0, x0):max(0, x0) + (sx1 - sx0)]
    src = rot[sy0:sy1, sx0:sx1]
    a = src[..., 3:4].astype(np.float32) / 255.0
    dst[:] = (src[..., :3] * a + dst * (1 - a)).astype(np.uint8)
    if idmap is not None:
        region = idmap[max(0, y0):max(0, y0) + (sy1 - sy0), max(0, x0):max(0, x0) + (sx1 - sx0)]
        region[src[..., 3] > 127] = idx
    ys, xs = np.where(src[..., 3] > 0)
    if len(xs) == 0:
        return None
    bx0, by0 = max(0, x0) + xs.min(), max(0, y0) + ys.min()
    bx1, by1 = max(0, x0) + xs.max(), max(0, y0) + ys.max()
    return (bx0, by0, bx1, by1)


def scene(cards, rng, frames):
    bg = playmat(cards, rng, frames)
    idmap = np.full((H, W), -1, np.int32)
    boxes, areas = [], []
    # static chrome first: sidebar panel and top bar are part of the background
    sidebar = None
    if rng.random() < 0.35:
        w = rng.uniform(190, 320)
        h = w * 670 / 480
        panel_x = rng.choice([W - w / 2 - rng.uniform(10, 60), w / 2 + rng.uniform(10, 60)])
        cv2.rectangle(bg, (int(panel_x - w / 2 - 30), 0), (int(panel_x + w / 2 + 30), H), (rng.randrange(0, 60),) * 3, -1)
        sidebar = (panel_x, w, h)
    if rng.random() < 0.5:
        cv2.rectangle(bg, (0, 0), (W, rng.randrange(30, 70)), (rng.randrange(0, 80),) * 3, -1)
    layout = rng.random()
    n = rng.randrange(3, 14)
    base_w = rng.uniform(50, 170) if layout < 0.7 else rng.uniform(120, 290)
    for i in range(n):
        card = imread_u(cards[rng.randrange(len(cards))])
        w = base_w * rng.uniform(0.75, 1.25)
        h = w * 670 / 480
        rested = rng.random() < 0.22
        angle = rng.uniform(-6, 6) + (90 if rested else 0) + (180 if rng.random() < 0.08 else 0)
        cx, cy = rng.uniform(w * 0.3, W - w * 0.3), rng.uniform(h * 0.3, H - h * 0.3)
        if boxes and rng.random() < 0.25:  # stack on / next to an existing card
            px0, py0, px1, py1 = boxes[-1]
            cx, cy = (px0 + px1) / 2 + rng.uniform(-w * 0.6, w * 0.6), (py0 + py1) / 2 + rng.uniform(-h * 0.5, h * 0.5)
        b = paste(bg, card, cx, cy, w, h, angle, rng, idmap, len(boxes))
        if b:
            boxes.append(b)
            areas.append(w * h)
    if sidebar:  # large clean preview card on the panel
        panel_x, w, h = sidebar
        card = imread_u(cards[rng.randrange(len(cards))])
        b = paste(bg, card, panel_x, rng.uniform(h / 2 + 20, H - h / 2 - 20), w, h, rng.uniform(-1, 1), rng, idmap, len(boxes))
        if b:
            boxes.append(b)
            areas.append(w * h)
    # occluders: hands / dice / tokens, recorded as -2 in the id map
    occ = np.zeros((H, W), np.uint8)
    for _ in range(rng.randrange(0, 4)):
        col = (rng.randrange(120, 220), rng.randrange(140, 210), rng.randrange(170, 240))
        c = (rng.randrange(W), rng.randrange(H)); ax = (rng.randrange(20, 120), rng.randrange(15, 60)); ang = rng.uniform(0, 180)
        cv2.ellipse(bg, c, ax, ang, 0, 360, col, -1)
        cv2.ellipse(occ, c, ax, ang, 0, 360, 255, -1)
    for _ in range(rng.randrange(0, 6)):
        c = (rng.randrange(W), rng.randrange(H)); r = rng.randrange(6, 18)
        cv2.circle(bg, c, r, tuple(rng.randrange(0, 255) for _ in range(3)), -1)
        cv2.circle(occ, c, r, 255, -1)
    idmap[occ > 0] = -2
    # keep boxes whose card is still at least 35% visible and 30% inside the frame
    counts = np.bincount(idmap[idmap >= 0].ravel(), minlength=len(boxes)) if boxes else []
    clean = []
    for i, (x0, y0, x1, y1) in enumerate(boxes):
        cx0, cy0, cx1, cy1 = max(0, x0), max(0, y0), min(W - 1, x1), min(H - 1, y1)
        if cx1 - cx0 <= 10 or cy1 - cy0 <= 10:
            continue
        inside = (cx1 - cx0) * (cy1 - cy0) / max(1, (x1 - x0) * (y1 - y0))
        visible = counts[i] / max(1.0, areas[i])
        if inside >= 0.3 and visible >= 0.35:
            clean.append((cx0, cy0, cx1, cy1))
    # global degradation
    if rng.random() < 0.5:
        s = rng.uniform(0.35, 0.8)
        bg = cv2.resize(cv2.resize(bg, None, fx=s, fy=s, interpolation=cv2.INTER_AREA), (W, H), interpolation=cv2.INTER_LINEAR)
    bg = np.clip(bg.astype(np.float32) * rng.uniform(0.75, 1.2) + rng.uniform(-15, 15), 0, 255).astype(np.uint8)
    ok, enc = cv2.imencode('.jpg', bg, [cv2.IMWRITE_JPEG_QUALITY, rng.randrange(35, 85)])
    bg = cv2.imdecode(enc, cv2.IMREAD_COLOR)
    return bg, clean


def yolo_label(boxes):
    return "".join(f"0 {(x0 + x1) / 2 / W:.6f} {(y0 + y1) / 2 / H:.6f} {(x1 - x0) / W:.6f} {(y1 - y0) / H:.6f}\n" for x0, y0, x1, y1 in boxes)


def pseudo_label_frames(frames_dir, out_img, out_lbl, conf=0.6, limit=120):
    """Real frames labelled by the stock detector at high confidence (noisy but in-domain)."""
    from test_pipeline import detect, DET_MODEL
    import onnxruntime as ort
    det = ort.InferenceSession(DET_MODEL, providers=['CPUExecutionProvider'])
    n = 0
    for root, _, files in os.walk(frames_dir):
        for f in sorted(files):
            if not f.endswith('.jpg'):
                continue
            bgr = imread_u(os.path.join(root, f))
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            h, w = rgb.shape[:2]
            boxes = [b for b in detect(det, cv2.resize(rgb, (640, int(h * 640 / w)))) if b[4] >= conf]
            if not boxes:
                continue
            tag = os.path.basename(root) + '_' + f
            cv2.imwrite(os.path.join(out_img, tag), bgr)
            with open(os.path.join(out_lbl, tag[:-4] + '.txt'), 'w') as fh:
                fh.write("".join(f"0 {x + bw / 2:.6f} {y + bh / 2:.6f} {bw:.6f} {bh:.6f}\n" for x, y, bw, bh, _ in boxes))
            n += 1
            if n >= limit:
                return n
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=3000)
    ap.add_argument('--out', default='datasets/cards')
    ap.add_argument('--media', default='media/cards')
    ap.add_argument('--frames', default='samples/frames')
    ap.add_argument('--seed', type=int, default=0)
    a = ap.parse_args()
    cards = sorted(os.path.join(a.media, f) for f in os.listdir(a.media) if f.endswith('.jpg'))
    frames = load_backgrounds(a.frames, limit=150)
    for split in ('train', 'val'):
        os.makedirs(os.path.join(a.out, 'images', split), exist_ok=True)
        os.makedirs(os.path.join(a.out, 'labels', split), exist_ok=True)
    rng = random.Random(a.seed)
    for i in range(a.n):
        split = 'val' if i % 10 == 0 else 'train'
        img, boxes = scene(cards, rng, frames)
        name = f"syn{i:05d}"
        cv2.imwrite(os.path.join(a.out, 'images', split, name + '.jpg'), img, [cv2.IMWRITE_JPEG_QUALITY, 90])
        with open(os.path.join(a.out, 'labels', split, name + '.txt'), 'w') as fh:
            fh.write(yolo_label(boxes))
        if i % 500 == 0:
            print(f"{i}/{a.n}", flush=True)
    n_real = pseudo_label_frames(a.frames, os.path.join(a.out, 'images', 'train'), os.path.join(a.out, 'labels', 'train'))
    with open(os.path.join(a.out, 'cards.yaml'), 'w') as fh:
        fh.write(f"path: {os.path.abspath(a.out)}\ntrain: images/train\nval: images/val\nnames:\n  0: card\n")
    print(f"done: {a.n} synthetic scenes + {n_real} pseudo-labelled real frames -> {a.out}")


if __name__ == '__main__':
    main()
