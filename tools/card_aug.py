r"""Stream-condition augmentation for Force of Will card images (torch-free, shared by the
embedder trainer and the detector dataset generator)."""
import math, os, random
import numpy as np
import cv2

SIZE = 128


def imread_u(path):
    """cv2.imread that copes with non-ASCII paths on Windows."""
    try:
        buf = np.fromfile(path, dtype=np.uint8)
    except OSError:
        return None
    if buf.size == 0:
        return None
    return cv2.imdecode(buf, cv2.IMREAD_COLOR)


def load_backgrounds(folder, limit=400):
    bgs = []
    if not os.path.isdir(folder):
        return bgs
    for root, _, files in os.walk(folder):
        for f in sorted(files):
            if f.lower().endswith(('.jpg', '.png')):
                im = imread_u(os.path.join(root, f))
                if im is not None:
                    bgs.append(cv2.resize(im, (640, 360), interpolation=cv2.INTER_AREA))
                if len(bgs) >= limit:
                    return bgs
    return bgs


def rand_bg_patch(bgs, w, h, rng):
    if bgs and rng.random() < 0.85:
        bg = bgs[rng.randrange(len(bgs))]
        bh, bw = bg.shape[:2]
        s = rng.uniform(0.15, 0.6)
        pw, ph = max(8, int(bw * s)), max(8, int(bh * s))
        x, y = rng.randrange(0, bw - pw + 1), rng.randrange(0, bh - ph + 1)
        return cv2.resize(bg[y:y + ph, x:x + pw], (w, h), interpolation=cv2.INTER_LINEAR)
    col = np.array([rng.randrange(20, 200) for _ in range(3)], dtype=np.uint8)
    patch = np.full((h, w, 3), col, dtype=np.uint8)
    return patch


def occlude(img, rng):
    """Draw 1-3 dice / counters / finger tips over the card (in place)."""
    h, w = img.shape[:2]
    for _ in range(rng.randrange(1, 4)):
        kind = rng.random()
        cx, cy = rng.randrange(w), rng.randrange(h)
        size = int(min(w, h) * rng.uniform(0.12, 0.32))
        if kind < 0.45:  # die: rounded square with pips
            col = rng.choice([(240, 240, 240), (30, 30, 30), (40, 40, 200), (200, 40, 40), (30, 160, 60), (230, 200, 40)])
            ang = rng.uniform(-40, 40)
            box = cv2.boxPoints(((cx, cy), (size, size), ang)).astype(np.int32)
            cv2.fillPoly(img, [box], col)
            pip = (30, 30, 30) if sum(col) > 400 else (240, 240, 240)
            for _ in range(rng.randrange(1, 7)):
                cv2.circle(img, (cx + rng.randrange(-size // 3, size // 3 + 1), cy + rng.randrange(-size // 3, size // 3 + 1)),
                           max(1, size // 10), pip, -1)
        elif kind < 0.75:  # round counter / token
            col = tuple(rng.randrange(0, 256) for _ in range(3))
            cv2.circle(img, (cx, cy), size // 2, col, -1)
            cv2.circle(img, (cx, cy), size // 2, tuple(max(0, c - 60) for c in col), 1)
        else:  # finger tip / hand edge from a border
            col = (rng.randrange(120, 200), rng.randrange(150, 210), rng.randrange(190, 245))
            side = rng.randrange(4)
            ex, ey = [(0, cy), (w, cy), (cx, 0), (cx, h)][side]
            cv2.ellipse(img, (ex, ey), (int(size * 0.8), int(size * 1.4)), rng.uniform(0, 180), 0, 360, col, -1)


def augment(card, bgs, rng, hard=1.0):
    """card: BGR uint8 full card image. Returns a 128x128 BGR uint8 view."""
    H, W = card.shape[:2]
    # 1. crop region of the card (fractions), sometimes dropping the text box (full-art proxy)
    r = rng.random()
    if r < 0.18:
        x0, y0, x1, y1 = 0.0, 0.0, 1.0, rng.uniform(0.52, 0.72)
    elif r < 0.30:
        x0, y0, x1, y1 = rng.uniform(0, 0.1), rng.uniform(0, 0.08), rng.uniform(0.9, 1), rng.uniform(0.55, 0.8)
    else:
        j = 0.09 * hard
        x0, y0 = rng.uniform(0, j), rng.uniform(0, j)
        x1, y1 = rng.uniform(1 - j, 1), rng.uniform(1 - j, 1)
    crop = np.array(card[int(y0 * H):int(y1 * H), int(x0 * W):int(x1 * W)])  # copy: memmap slices are read-only
    if rng.random() < 0.45 * hard:
        occlude(crop, rng)

    # 2. paste onto background with a loose margin (YOLO box slack) and slight rotation
    ch, cw = crop.shape[:2]
    margin = rng.uniform(0, 0.16 * hard) if rng.random() < 0.6 else 0.0
    mw, mh = int(cw * margin), int(ch * margin)
    canvas = rand_bg_patch(bgs, cw + 2 * mw, ch + 2 * mh, rng)
    canvas[mh:mh + ch, mw:mw + cw] = crop
    if rng.random() < 0.6:
        ang = (rng.uniform(-7, 7) if rng.random() < 0.6 else rng.uniform(-30, 30)) * hard
        ch2, cw2 = canvas.shape[:2]
        M = cv2.getRotationMatrix2D((cw2 / 2, ch2 / 2), ang, 1.0)
        # enlarge the canvas so the rotated card stays inside its (axis aligned) box, fill with background
        cos, sin = abs(M[0, 0]), abs(M[0, 1])
        nw, nh = int(ch2 * sin + cw2 * cos), int(ch2 * cos + cw2 * sin)
        M[0, 2] += nw / 2 - cw2 / 2
        M[1, 2] += nh / 2 - ch2 / 2
        bgfill = rand_bg_patch(bgs, nw, nh, rng)
        rotated = cv2.warpAffine(canvas, M, (nw, nh), borderMode=cv2.BORDER_TRANSPARENT, dst=bgfill.copy())
        canvas = rotated
    if rng.random() < 0.25:  # mild perspective (camera angle)
        h, w = canvas.shape[:2]
        d = 0.06 * hard
        src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
        dst = src + np.float32([[rng.uniform(-d, d) * w, rng.uniform(-d, d) * h] for _ in range(4)])
        canvas = cv2.warpPerspective(canvas, cv2.getPerspectiveTransform(src, dst), (w, h), borderMode=cv2.BORDER_REFLECT)

    # 3. rested / upside-down cards
    rr = rng.random()
    if rr < 0.12:
        canvas = cv2.rotate(canvas, cv2.ROTATE_90_CLOCKWISE)
    elif rr < 0.24:
        canvas = cv2.rotate(canvas, cv2.ROTATE_90_COUNTERCLOCKWISE)
    elif rr < 0.29:
        canvas = cv2.rotate(canvas, cv2.ROTATE_180)

    # 4. resolution loss: downscale to a stream-like size, then to model size
    small = int(rng.uniform(22, 120)) if rng.random() < 0.85 else SIZE
    h, w = canvas.shape[:2]
    sw, sh = max(8, int(small * w / max(w, h))), max(8, int(small * h / max(w, h)))
    canvas = cv2.resize(canvas, (sw, sh), interpolation=rng.choice([cv2.INTER_AREA, cv2.INTER_LINEAR]))
    if rng.random() < 0.6:
        k = rng.choice([3, 3, 5, 5, 7])
        if rng.random() < 0.5:
            canvas = cv2.GaussianBlur(canvas, (k, k), 0)
        else:  # motion blur
            kern = np.zeros((k, k), np.float32)
            if rng.random() < 0.5:
                kern[k // 2, :] = 1
            else:
                kern[:, k // 2] = 1
            canvas = cv2.filter2D(canvas, -1, kern / k)
    canvas = cv2.resize(canvas, (SIZE, SIZE), interpolation=cv2.INTER_LINEAR)

    # 5. photometric: exposure, contrast, colour cast, gamma, saturation, glare, noise, JPEG
    img = canvas.astype(np.float32)
    img = img * rng.uniform(0.6, 1.45) + rng.uniform(-30, 40)
    img = (img - 128) * rng.uniform(0.35 if hard >= 0.9 else 0.6, 1.3) + 128
    img += np.array([rng.uniform(-22, 22) for _ in range(3)], dtype=np.float32)
    if rng.random() < 0.45 * hard:  # camera haze / glare wash-out: blend towards a light grey
        haze = np.array([rng.uniform(170, 255) for _ in range(3)], dtype=np.float32)
        img = img * (1 - (a := rng.uniform(0.15, 0.6))) + haze * a
    if rng.random() < 0.12:  # monochrome chase-card prints: grayscale, sometimes with a slight tint
        g = cv2.cvtColor(np.clip(img, 0, 255).astype(np.uint8), cv2.COLOR_BGR2GRAY).astype(np.float32)
        tint = np.array([rng.uniform(0.9, 1.1) for _ in range(3)], dtype=np.float32)
        img = g[..., None] * tint
    if rng.random() < 0.5:
        hsv = cv2.cvtColor(np.clip(img, 0, 255).astype(np.uint8), cv2.COLOR_BGR2HSV).astype(np.float32)
        hsv[..., 1] *= rng.uniform(0.2 if hard >= 0.9 else 0.5, 1.3)
        hsv[..., 0] = (hsv[..., 0] + rng.uniform(-6, 6)) % 180
        img = cv2.cvtColor(np.clip(hsv, 0, 255).astype(np.uint8), cv2.COLOR_HSV2BGR).astype(np.float32)
    if rng.random() < 0.4:
        g = rng.uniform(0.7, 1.5)
        img = 255.0 * (np.clip(img, 0, 255) / 255.0) ** g
    if rng.random() < 0.3:  # sleeve glare: bright soft band
        yy, xx = np.mgrid[0:SIZE, 0:SIZE].astype(np.float32)
        cx, cy, ang = rng.uniform(0, SIZE), rng.uniform(0, SIZE), rng.uniform(0, math.pi)
        d = (xx - cx) * math.cos(ang) + (yy - cy) * math.sin(ang)
        band = np.exp(-(d ** 2) / (2 * rng.uniform(8, 30) ** 2)) * rng.uniform(40, 120)
        img += band[..., None]
    if rng.random() < 0.5:
        img += np.random.default_rng(rng.randrange(1 << 30)).normal(0, rng.uniform(2, 12), img.shape).astype(np.float32)
    img = np.clip(img, 0, 255).astype(np.uint8)
    if rng.random() < 0.6:
        q = rng.randrange(25, 80)
        ok, enc = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, q])
        if ok:
            img = cv2.imdecode(enc, cv2.IMREAD_COLOR)
    return img


