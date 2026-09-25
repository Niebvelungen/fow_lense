r"""Fine-tune a YOLOv8n single-class card detector on datasets/cards and export it to ONNX in the
layout src/lib/yolo.js expects: input [1,3,640,640] in 0..1, output [1,5,8400] (cx,cy,w,h,score).

usage: .venv/Scripts/python tools/train_detector.py [--epochs 40] [--batch 16] [--model yolov8n.pt]
       .venv/Scripts/python tools/train_detector.py --export-only runs/detector/weights/best.pt
"""
import argparse, os, shutil
import numpy as np


def export(weights, out_path):
    from ultralytics import YOLO
    import onnxruntime as ort
    model = YOLO(weights)
    onnx_path = model.export(format='onnx', imgsz=640, opset=17, simplify=True, dynamic=False, nms=False)
    shutil.copy(onnx_path, out_path)
    sess = ort.InferenceSession(out_path, providers=['CPUExecutionProvider'])
    inp, outp = sess.get_inputs()[0], sess.get_outputs()[0]
    y = sess.run(None, {inp.name: np.zeros((1, 3, 640, 640), np.float32)})[0]
    print(f"exported {out_path}: input {inp.name} {inp.shape}, output {outp.name} {list(y.shape)}, "
          f"{os.path.getsize(out_path) / 1e6:.1f} MB")
    assert list(y.shape) == [1, 5, 8400], "unexpected output layout for yolo.js"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', default='datasets/cards/cards.yaml')
    ap.add_argument('--model', default='yolov8n.pt')
    ap.add_argument('--epochs', type=int, default=40)
    ap.add_argument('--batch', type=int, default=16)
    ap.add_argument('--out', default='runs/detector')
    ap.add_argument('--export-only', default=None)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    onnx_out = os.path.join(a.out, 'card-detector.onnx')
    if a.export_only:
        export(a.export_only, onnx_out)
        return

    from ultralytics import YOLO
    model = YOLO(a.model)
    model.train(
        data=a.data, imgsz=640, epochs=a.epochs, batch=a.batch, workers=6,
        project=os.path.dirname(a.out) or '.', name=os.path.basename(a.out), exist_ok=True,
        # cards are rectangles; keep geometry realistic, no vertical flips
        degrees=5, scale=0.5, translate=0.1, fliplr=0.0, flipud=0.0, mosaic=1.0, close_mosaic=8,
        hsv_h=0.02, hsv_s=0.5, hsv_v=0.4, patience=15, cos_lr=True, plots=False, verbose=False,
    )
    export(os.path.join(a.out, 'weights', 'best.pt'), onnx_out)


if __name__ == '__main__':
    main()
