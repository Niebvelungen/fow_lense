r"""Offline replica of the extension's recognition chain, for testing on a video file.

Per sampled frame: YOLO detector (640 letterbox, conf 0.25, NMS 0.45) -> crop each box from the
full-res frame -> embed (128x128 squash, ImageNet norm) -> cosine match against the index built by
build_index.py -> accept if score >= 0.42 and margin >= 0.02. Writes annotated frames and a JSON
summary.

usage: .venv/Scripts/python tools/test_pipeline.py VIDEO [--every 20] [--start 60] [--max-frames 12]
           [--out results/<video-stem>] [--sample-width 480]
"""
import argparse, json, os, sys, time
import numpy as np
import cv2
import onnxruntime as ort

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DET_MODEL = os.path.join(ROOT, "extension/models/card-detector.onnx")
EMB_MODEL = os.path.join(ROOT, "extension/models/embedder.onnx")
INDEX_NPZ = os.path.join(ROOT, "data/index_embeddings.npz")

MODEL_SIZE, CONF, NMS_IOU = 640, 0.25, 0.45
EMB_SIZE = 128
MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)
EMBED_ACCEPT, EMBED_MARGIN = 0.8, 0.05
CROP_EDGE = 320


def letterbox(rgb):
    h, w = rgb.shape[:2]
    scale = min(MODEL_SIZE / w, MODEL_SIZE / h)
    dw, dh = int(round(w * scale)), int(round(h * scale))
    canvas = np.full((MODEL_SIZE, MODEL_SIZE, 3), 114, dtype=np.uint8)
    px, py = (MODEL_SIZE - dw) // 2, (MODEL_SIZE - dh) // 2
    canvas[py:py + dh, px:px + dw] = cv2.resize(rgb, (dw, dh), interpolation=cv2.INTER_LINEAR)
    tensor = canvas.astype(np.float32).transpose(2, 0, 1)[None] / 255.0
    return tensor, scale, px, py


def iou(a, b):
    ix = max(0, min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = a[2] * a[3] + b[2] * b[3] - inter
    return inter / union if union > 0 else 0


def nms(boxes):
    boxes = sorted(boxes, key=lambda b: -b[4])
    keep = []
    for b in boxes:
        if all(iou(b, k) <= NMS_IOU for k in keep):
            keep.append(b)
    return keep


def detect(session, rgb):
    tensor, scale, px, py = letterbox(rgb)
    out = session.run(None, {session.get_inputs()[0].name: tensor})[0]
    if out.ndim == 3 and out.shape[2] == 5:
        rows = out[0]
    else:
        rows = out[0].T  # (5, N) -> (N, 5)
    h, w = rgb.shape[:2]
    boxes = []
    for cx, cy, bw, bh, score in rows:
        if score < CONF:
            continue
        x = (cx - bw / 2 - px) / scale / w
        y = (cy - bh / 2 - py) / scale / h
        ww, hh = bw / scale / w, bh / scale / h
        if ww < 0.004 or hh < 0.004:
            continue
        x, y = max(0, min(1, x)), max(0, min(1, y))
        ww, hh = max(0, min(1 - x, ww)), max(0, min(1 - y, hh))
        boxes.append(tuple(float(v) for v in (x, y, ww, hh, score)))
    return nms(boxes)


def crop_box(rgb, box):
    h, w = rgb.shape[:2]
    x, y, bw, bh, _ = box
    x0, y0 = int(x * w), int(y * h)
    x1, y1 = max(x0 + 2, int((x + bw) * w)), max(y0 + 2, int((y + bh) * h))
    crop = rgb[y0:y1, x0:x1]
    scale = min(1.0, CROP_EDGE / max(crop.shape[0], crop.shape[1], 1))
    if scale < 1:
        crop = cv2.resize(crop, (max(16, int(crop.shape[1] * scale)), max(16, int(crop.shape[0] * scale))), interpolation=cv2.INTER_AREA)
    return crop


AUTOCONTRAST = False


def autocontrast(rgb):
    """Per-channel 2-98 percentile stretch to undo camera haze."""
    out = rgb.astype(np.float32)
    for ch in range(3):
        lo, hi = np.percentile(out[..., ch], (2, 98))
        if hi - lo > 5:
            out[..., ch] = (out[..., ch] - lo) * (255.0 / (hi - lo))
    return np.clip(out, 0, 255).astype(np.uint8)


def embed(session, crops):
    batch = []
    for c in crops:
        if AUTOCONTRAST:
            c = autocontrast(c)
        r = cv2.resize(c, (EMB_SIZE, EMB_SIZE), interpolation=cv2.INTER_CUBIC).astype(np.float32) / 255.0
        batch.append(((r - MEAN) / STD).transpose(2, 0, 1))
    if not batch:
        return np.zeros((0, 256), dtype=np.float32)
    out = session.run(None, {session.get_inputs()[0].name: np.stack(batch).astype(np.float32)})[0]
    return out / np.maximum(np.linalg.norm(out, axis=1, keepdims=True), 1e-8)


class Index:
    def __init__(self, path):
        z = np.load(path, allow_pickle=False)
        self.emb = z["emb"].astype(np.float32)
        self.owner = z["owner"]
        self.ids = z["ids"]
        self.names = z["names"]
        self.n = len(self.ids)

    def match(self, q, top=5):
        sims = self.emb @ q
        per_card = np.full(self.n, -1.0, dtype=np.float32)
        np.maximum.at(per_card, self.owner, sims)
        order = np.argsort(-per_card)[:top]
        ranked = [{"id": str(self.ids[i]), "name": str(self.names[i]), "score": float(per_card[i])} for i in order]
        best, second = ranked[0], ranked[1]["score"] if len(ranked) > 1 else -1
        accepted = best["score"] >= EMBED_ACCEPT and best["score"] - second >= EMBED_MARGIN
        return accepted, ranked


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--every", type=float, default=20.0, help="seconds between sampled frames")
    ap.add_argument("--start", type=float, default=60.0)
    ap.add_argument("--max-frames", type=int, default=12)
    ap.add_argument("--sample-width", type=int, default=640, help="width the detector sees (extension uses 640)")
    ap.add_argument("--out", default=None)
    ap.add_argument("--index", default=INDEX_NPZ)
    ap.add_argument("--det-model", default=DET_MODEL)
    ap.add_argument("--emb-model", default=EMB_MODEL)
    ap.add_argument("--autocontrast", action="store_true")
    a = ap.parse_args()

    global AUTOCONTRAST
    AUTOCONTRAST = a.autocontrast
    out_dir = a.out or os.path.join(ROOT, "results", os.path.splitext(os.path.basename(a.video))[0])
    os.makedirs(out_dir, exist_ok=True)
    det = ort.InferenceSession(a.det_model, providers=["CPUExecutionProvider"])
    emb = ort.InferenceSession(a.emb_model, providers=["CPUExecutionProvider"])
    index = Index(a.index)
    print(f"index: {index.n} cards, {len(index.emb)} embeddings")

    cap = cv2.VideoCapture(a.video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"video: {a.video} {int(cap.get(3))}x{int(cap.get(4))} {fps:.1f}fps {total / fps:.0f}s")

    summary = []
    t = a.start
    n = 0
    while n < a.max_frames and t * fps < total:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(t * fps))
        ok, bgr = cap.read()
        if not ok:
            break
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        h, w = rgb.shape[:2]
        sample = cv2.resize(rgb, (a.sample_width, int(h * a.sample_width / w)), interpolation=cv2.INTER_AREA)
        t0 = time.time()
        boxes = detect(det, sample)
        t_det = time.time() - t0
        crops = [crop_box(rgb, b) for b in boxes]
        t0 = time.time()
        vecs = embed(emb, crops)
        t_emb = time.time() - t0

        frame_res = {"t": t, "boxes": [], "det_ms": round(t_det * 1000), "emb_ms": round(t_emb * 1000)}
        vis = bgr.copy()
        for i, (b, q) in enumerate(zip(boxes, vecs)):
            accepted, ranked = index.match(q)
            best = ranked[0]
            frame_res["boxes"].append({"box": [round(v, 4) for v in b[:4]], "det": round(b[4], 3),
                                       "accepted": accepted, "top": ranked[:3]})
            x0, y0 = int(b[0] * w), int(b[1] * h)
            x1, y1 = int((b[0] + b[2]) * w), int((b[1] + b[3]) * h)
            color = (0, 200, 0) if accepted else (0, 140, 255)
            cv2.rectangle(vis, (x0, y0), (x1, y1), color, 2)
            label = f"{best['name'][:26]} {best['score']:.2f}" + ("" if accepted else " ?")
            cv2.putText(vis, label, (x0, max(12, y0 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 3)
            cv2.putText(vis, label, (x0, max(12, y0 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)
            cv2.imwrite(os.path.join(out_dir, f"t{int(t):05d}_crop{i}.jpg"), cv2.cvtColor(crops[i], cv2.COLOR_RGB2BGR))
        cv2.imwrite(os.path.join(out_dir, f"t{int(t):05d}.jpg"), vis, [cv2.IMWRITE_JPEG_QUALITY, 85])
        summary.append(frame_res)
        acc = sum(1 for x in frame_res["boxes"] if x["accepted"])
        print(f"t={t:6.0f}s  boxes={len(boxes):2d}  accepted={acc:2d}  det {t_det * 1000:.0f}ms  emb {t_emb * 1000:.0f}ms  "
              + ", ".join(f"{x['top'][0]['name'][:18]}({x['top'][0]['score']:.2f})" for x in frame_res["boxes"][:4]))
        t += a.every
        n += 1

    json.dump(summary, open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    nb = sum(len(f["boxes"]) for f in summary)
    na = sum(1 for f in summary for x in f["boxes"] if x["accepted"])
    print(f"\n{len(summary)} frames, {nb} boxes, {na} accepted matches -> {out_dir}")


if __name__ == "__main__":
    main()
