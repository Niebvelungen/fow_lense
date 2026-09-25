import * as ort from "../../vendor/ort/ort.wasm.min.mjs";

const MODEL_SIZE = 640;
const CONF = 0.25;
const NMS_IOU = 0.45;

let sessionPromise = null;

const boxIou = (a, b) => {
  const ax2 = a.x + a.w;
  const ay2 = a.y + a.h;
  const bx2 = b.x + b.w;
  const by2 = b.y + b.h;
  const ix = Math.max(0, Math.min(ax2, bx2) - Math.max(a.x, b.x));
  const iy = Math.max(0, Math.min(ay2, by2) - Math.max(a.y, b.y));
  const inter = ix * iy;
  const union = a.w * a.h + b.w * b.h - inter;
  return union <= 0 ? 0 : inter / union;
};

const toQuad = (x, y, w, h, score) => {
  const nx = Math.max(0, Math.min(1, x));
  const ny = Math.max(0, Math.min(1, y));
  const nw = Math.max(0, Math.min(1 - nx, w));
  const nh = Math.max(0, Math.min(1 - ny, h));
  return {
    x: nx,
    y: ny,
    w: nw,
    h: nh,
    cx: nx + nw / 2,
    cy: ny + nh / 2,
    rw: nw,
    rh: nh,
    angle: 0,
    visiblePart: "full",
    orientation: nh >= nw ? "portrait" : "landscape",
    corners: [
      { x: nx, y: ny },
      { x: nx + nw, y: ny },
      { x: nx + nw, y: ny + nh },
      { x: nx, y: ny + nh },
    ],
    detectScore: score,
  };
};

const nms = (boxes) => {
  const order = boxes
    .map((box, index) => index)
    .sort((a, b) => boxes[b].score - boxes[a].score);
  const keep = [];
  const dead = new Set();
  for (const i of order) {
    if (dead.has(i)) continue;
    keep.push(boxes[i]);
    for (const j of order) {
      if (j === i || dead.has(j)) continue;
      if (boxIou(boxes[i], boxes[j]) > NMS_IOU) dead.add(j);
    }
  }
  return keep;
};

const letterbox = (imageData) => {
  const canvas = new OffscreenCanvas(MODEL_SIZE, MODEL_SIZE);
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  ctx.fillStyle = "rgb(114, 114, 114)";
  ctx.fillRect(0, 0, MODEL_SIZE, MODEL_SIZE);

  const scale = Math.min(MODEL_SIZE / imageData.width, MODEL_SIZE / imageData.height);
  const drawW = imageData.width * scale;
  const drawH = imageData.height * scale;
  const padX = (MODEL_SIZE - drawW) / 2;
  const padY = (MODEL_SIZE - drawH) / 2;

  const source = new OffscreenCanvas(imageData.width, imageData.height);
  source.getContext("2d").putImageData(imageData, 0, 0);
  ctx.drawImage(source, padX, padY, drawW, drawH);

  const pixels = ctx.getImageData(0, 0, MODEL_SIZE, MODEL_SIZE).data;
  const plane = MODEL_SIZE * MODEL_SIZE;
  const tensor = new Float32Array(plane * 3);
  for (let i = 0; i < plane; i += 1) {
    const p = i * 4;
    tensor[i] = pixels[p] / 255;
    tensor[plane + i] = pixels[p + 1] / 255;
    tensor[plane * 2 + i] = pixels[p + 2] / 255;
  }
  return { tensor, scale, padX, padY };
};

const parseOutput = (output, imageData, scale, padX, padY) => {
  const data = output.data;
  const dims = output.dims;
  const rowsFirst = dims.length === 3 && dims[2] === 5;
  const count = rowsFirst ? dims[1] : dims[2];
  const boxes = [];

  for (let i = 0; i < count; i += 1) {
    const cx = rowsFirst ? data[i * 5] : data[i];
    const cy = rowsFirst ? data[i * 5 + 1] : data[count + i];
    const bw = rowsFirst ? data[i * 5 + 2] : data[count * 2 + i];
    const bh = rowsFirst ? data[i * 5 + 3] : data[count * 3 + i];
    const score = rowsFirst ? data[i * 5 + 4] : data[count * 4 + i];
    if (score < CONF) continue;

    const x = (cx - bw / 2 - padX) / scale / imageData.width;
    const y = (cy - bh / 2 - padY) / scale / imageData.height;
    const w = bw / scale / imageData.width;
    const h = bh / scale / imageData.height;
    if (w < 0.004 || h < 0.004) continue;
    boxes.push({ x, y, w, h, score });
  }

  return nms(boxes).map((box) => toQuad(box.x, box.y, box.w, box.h, box.score));
};

const loadSession = () => {
  if (sessionPromise) return sessionPromise;
  ort.env.wasm.numThreads = 1;
  ort.env.wasm.wasmPaths = chrome.runtime.getURL("vendor/ort/");
  sessionPromise = ort.InferenceSession.create(chrome.runtime.getURL("models/card-detector.onnx"), {
    executionProviders: ["wasm"],
  });
  return sessionPromise;
};

export const createYoloDetector = () => {
  return {
    findCardQuads: async (imageData) => {
      if (!imageData?.width || !imageData?.height) return [];
      const session = await loadSession();
      const { tensor, scale, padX, padY } = letterbox(imageData);
      const feeds = { [session.inputNames[0]]: new ort.Tensor("float32", tensor, [1, 3, MODEL_SIZE, MODEL_SIZE]) };
      const results = await session.run(feeds);
      const output = results[session.outputNames[0]];
      return parseOutput(output, imageData, scale, padX, padY);
    },
  };
};
