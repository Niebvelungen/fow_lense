r"""Generate the extension's own icons (placeholder art, replace with real artwork any time):
a card silhouette under a lens ring. Writes extension/icons/toolbar{16,32,48,128}.png and the
overlay_on / overlay_off SVGs used by the in-player toggle button.

usage: .venv/Scripts/python tools/make_icons.py                      # generated placeholder art
       .venv/Scripts/python tools/make_icons.py --source logo.png    # resize a given PNG (square, RGBA)
"""
import argparse, base64, io, os
from PIL import Image, ImageDraw, ImageOps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'extension', 'icons')
BG = (24, 26, 34, 255)
CARD = (232, 200, 92, 255)      # gold card
CARD_ART = (86, 140, 214, 255)  # blue art panel
RING = (245, 245, 245, 255)


def draw_icon(size):
    s = 8  # supersample
    W = size * s
    im = Image.new('RGBA', (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    r = W * 0.22
    d.rounded_rectangle((0, 0, W - 1, W - 1), radius=r, fill=BG)
    # card, slightly tilted look via a rounded rectangle offset to the lower left
    cw, ch = W * 0.42, W * 0.58
    cx, cy = W * 0.40, W * 0.54
    d.rounded_rectangle((cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2), radius=W * 0.05, fill=CARD)
    d.rounded_rectangle((cx - cw / 2 + W * 0.05, cy - ch / 2 + W * 0.07, cx + cw / 2 - W * 0.05, cy - ch / 2 + W * 0.30),
                        radius=W * 0.02, fill=CARD_ART)
    for i in range(3):  # text lines
        y = cy + ch / 2 - W * 0.19 + i * W * 0.055
        d.rounded_rectangle((cx - cw / 2 + W * 0.05, y, cx + cw / 2 - W * 0.05 - (i == 2) * W * 0.1, y + W * 0.03),
                            radius=W * 0.01, fill=(60, 50, 30, 255))
    # lens ring over the upper right
    lx, ly, lr = W * 0.64, W * 0.36, W * 0.22
    d.ellipse((lx - lr, ly - lr, lx + lr, ly + lr), outline=RING, width=int(W * 0.065))
    d.ellipse((lx - lr * 0.72, ly - lr * 0.72, lx + lr * 0.72, ly + lr * 0.72), fill=(255, 255, 255, 40))
    # handle
    d.line((lx + lr * 0.7, ly + lr * 0.7, W * 0.88, W * 0.86), fill=RING, width=int(W * 0.075))
    return im.resize((size, size), Image.LANCZOS)


OVERLAY_SVG = """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<rect x="3" y="4" width="11" height="16" rx="1.6" fill="{card}" stroke="{stroke}" stroke-width="1.2"/>
<rect x="5" y="6" width="7" height="5" rx="0.8" fill="{art}"/>
<circle cx="16" cy="10" r="4.6" stroke="{stroke}" stroke-width="2" fill="{lens}"/>
<path d="M19.3 13.3 L22 16" stroke="{stroke}" stroke-width="2.2" stroke-linecap="round"/>
</svg>
"""


IMAGE_SVG = """<svg width="24" height="24" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
<image href="data:image/png;base64,{b64}" x="0" y="0" width="24" height="24"/>
</svg>
"""


def png_b64(im):
    buf = io.BytesIO()
    im.save(buf, 'PNG')
    return base64.b64encode(buf.getvalue()).decode('ascii')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', default=None, help='square RGBA PNG to use instead of the generated art')
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    if a.source:
        src = Image.open(a.source).convert('RGBA')
        for size in (16, 32, 48, 128):
            src.resize((size, size), Image.LANCZOS).save(os.path.join(OUT, f'toolbar{size}.png'))
        on = src.resize((48, 48), Image.LANCZOS)
        off = ImageOps.grayscale(on).convert('RGBA')
        off.putalpha(on.split()[3].point(lambda v: int(v * 0.6)))
        open(os.path.join(OUT, 'overlay_on.svg'), 'w', encoding='utf-8').write(IMAGE_SVG.format(b64=png_b64(on)))
        open(os.path.join(OUT, 'overlay_off.svg'), 'w', encoding='utf-8').write(IMAGE_SVG.format(b64=png_b64(off)))
        print('icons written to', OUT, 'from', a.source)
        return
    for size in (16, 32, 48, 128):
        draw_icon(size).save(os.path.join(OUT, f'toolbar{size}.png'))
    on = OVERLAY_SVG.format(card='#e8c85c', stroke='#ffffff', art='#568cd6', lens='rgba(255,255,255,0.18)')
    off = OVERLAY_SVG.format(card='#8a8a8a', stroke='#d0d0d0', art='#6c6c6c', lens='none')
    open(os.path.join(OUT, 'overlay_on.svg'), 'w', encoding='utf-8').write(on)
    open(os.path.join(OUT, 'overlay_off.svg'), 'w', encoding='utf-8').write(off)
    print('icons written to', OUT)


if __name__ == '__main__':
    main()
