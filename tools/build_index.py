r"""Build the extension's card index (models/id-index.bin) by embedding every card image
with the packaged embedding ONNX model, mirroring the preprocessing in src/lib/embed-id.js.

usage: .venv/Scripts/python tools/build_index.py [--cards extension/data/cards.json]
           [--media media/cards] [--model extension/models/embAll2_mnv3s128.onnx]
           [--out extension/models/id-index.bin] [--npy data/index_embeddings.npz]

Cards that share one image file (flip cards: EDL-069 and EDL-069*) become a single index
entry, otherwise the two identical embeddings would tie and the margin test would reject both.
"""
import argparse, json, os, struct, sys, time
import numpy as np
from PIL import Image, ImageFilter
import onnxruntime as ort

SIZE = 128
MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)
MAGIC = b"FOWIDX01"

# (x0, y0, x1, y1) fractions of the card image, plus optional blur radius (stream softness)
VARIANTS = [
    ((0.00, 0.00, 1.00, 1.00), 0.0),   # full card
    ((0.03, 0.03, 0.97, 0.97), 0.0),   # tight box
    ((0.07, 0.07, 0.93, 0.93), 0.0),   # tighter box
    ((0.00, 0.03, 0.94, 1.00), 0.0),   # box shifted
    ((0.06, 0.00, 1.00, 0.97), 0.0),   # box shifted the other way
    ((0.00, 0.00, 1.00, 0.65), 0.0),   # art-focused (full-art prints differ below)
    ((0.05, 0.00, 0.95, 0.55), 0.0),   # art-focused, tighter
    ((0.00, 0.00, 1.00, 1.00), 1.2),   # full card, softened like a compressed stream
]


def to_tensor(img):
    """PIL RGB -> float32 CHW normalised like embed-id.js toTensor (squash to 128x128)."""
    img = img.resize((SIZE, SIZE), Image.BICUBIC)
    arr = np.asarray(img, dtype=np.float32) / 255.0
    arr = (arr - MEAN) / STD
    return arr.transpose(2, 0, 1)


def variants_of(img):
    w, h = img.size
    for (x0, y0, x1, y1), blur in VARIANTS:
        crop = img.crop((int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h)))
        if blur:
            crop = crop.filter(ImageFilter.GaussianBlur(blur))
        yield to_tensor(crop)


def embed_batch(session, name, batch):
    out = session.run(None, {name: np.stack(batch).astype(np.float32)})[0]
    return out.reshape(len(batch), -1)


def write_index(path, entries, emb, emb_dim):
    heap = bytearray()
    offsets = []

    def put(s):
        off = len(heap)
        heap.extend(s.encode("utf-8") + b"\0")
        return off

    for e in entries:
        offsets.append((put(e["id"]), put(e["name"]), put(e["imageUrl"]), put(e["group"])))

    n_cards = len(entries)
    n_emb = emb.shape[0]
    header = bytearray(64)
    header[0:8] = MAGIC
    struct.pack_into("<7I", header, 8, 1, n_cards, 0, 0, n_emb, emb_dim, SIZE)
    struct.pack_into("<2f", header, 56, 0.0, 1.0)

    cards = bytearray()
    for e, (a, b, c, d) in zip(entries, offsets):
        cards += struct.pack("<10I", a, b, c, d, 0, 0, 0, 0, e["nEmb"], e["embIndex"])

    with open(path, "wb") as f:
        f.write(header)
        f.write(cards)
        f.write(heap)
        f.write(np.ascontiguousarray(emb, dtype="<f4").tobytes())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cards", default="extension/data/cards.json")
    ap.add_argument("--media", default="media/cards")
    ap.add_argument("--model", default="extension/models/embAll2_mnv3s128.onnx")
    ap.add_argument("--out", default="extension/models/id-index.bin")
    ap.add_argument("--npy", default="data/index_embeddings.npz")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    cards = json.load(open(a.cards, encoding="utf-8"))
    by_image = {}
    for c in cards:
        if not c.get("image"):
            continue
        by_image.setdefault(c["image"], []).append(c)
    images = sorted(by_image)
    if a.limit:
        images = images[: a.limit]
    missing = [i for i in images if not os.path.exists(os.path.join(a.media, i))]
    if missing:
        print(f"warning: {len(missing)} images missing locally, e.g. {missing[:5]}", file=sys.stderr)
        images = [i for i in images if i not in set(missing)]

    so = ort.SessionOptions()
    so.intra_op_num_threads = os.cpu_count() or 4
    session = ort.InferenceSession(a.model, so, providers=["CPUExecutionProvider"])
    inp = session.get_inputs()[0]
    print("model input", inp.name, inp.shape, "| output", session.get_outputs()[0].shape)
    batch_ok = not isinstance(inp.shape[0], int) or inp.shape[0] != 1

    entries, tensors, owners = [], [], []
    for idx, image in enumerate(images):
        group = by_image[image]
        front = sorted(group, key=lambda c: (c["id"].count("*"), c["id"]))[0]
        names = []
        for c in group:
            if c["name"] not in names:
                names.append(c["name"])
        entries.append({
            "id": front["id"],
            "name": " // ".join(names),
            "imageUrl": front["imageUrl"],
            "group": front.get("set", ""),
            "nEmb": len(VARIANTS),
            "embIndex": idx * len(VARIANTS),
        })
        img = Image.open(os.path.join(a.media, image)).convert("RGB")
        for t in variants_of(img):
            tensors.append(t)
            owners.append(idx)

    print(f"{len(entries)} index cards from {len(cards)} catalog rows, {len(tensors)} embeddings to compute")
    t0 = time.time()
    emb = np.zeros((len(tensors), 0), dtype=np.float32)
    chunks = []
    bs = 64 if batch_ok else 1
    for i in range(0, len(tensors), bs):
        chunks.append(embed_batch(session, inp.name, tensors[i:i + bs]))
        if (i // bs) % 200 == 0:
            print(f"  {i}/{len(tensors)}  {time.time() - t0:.0f}s", flush=True)
    emb = np.concatenate(chunks, axis=0)
    norms = np.linalg.norm(emb, axis=1)
    print(f"embedding dim {emb.shape[1]}, output norm mean {norms.mean():.4f} min {norms.min():.4f} max {norms.max():.4f}")
    if abs(norms.mean() - 1.0) > 0.01:
        print("model output is not unit length; normalising (JS compares by raw dot product, so queries must be normalised too)")
        emb = emb / np.maximum(norms[:, None], 1e-8)

    write_index(a.out, entries, emb, emb.shape[1])
    np.savez_compressed(a.npy, emb=emb, owner=np.array(owners, dtype=np.int32),
                        ids=np.array([e["id"] for e in entries]), names=np.array([e["name"] for e in entries]),
                        images=np.array(images))
    print(f"wrote {a.out} ({os.path.getsize(a.out) / 1e6:.1f} MB) and {a.npy} in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
