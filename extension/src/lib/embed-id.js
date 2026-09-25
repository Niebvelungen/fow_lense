import * as ort from "../../vendor/ort/ort.wasm.min.mjs";

const SIZE = 128;
const MEAN = [0.485, 0.456, 0.406];
const STD = [0.229, 0.224, 0.225];

let sessionPromise = null;

const loadSession = () => {
  if (sessionPromise) return sessionPromise;
  ort.env.wasm.numThreads = 1;
  ort.env.wasm.wasmPaths = chrome.runtime.getURL("vendor/ort/");
  sessionPromise = ort.InferenceSession.create(chrome.runtime.getURL("models/embedder.onnx"), {
    executionProviders: ["wasm"],
  });
  return sessionPromise;
};

const toTensor = (imageData) => {
  const canvas = new OffscreenCanvas(SIZE, SIZE);
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  const source = new OffscreenCanvas(imageData.width, imageData.height);
  source.getContext("2d").putImageData(imageData, 0, 0);
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = "high";
  ctx.drawImage(source, 0, 0, SIZE, SIZE);
  const pixels = ctx.getImageData(0, 0, SIZE, SIZE).data;
  const tensor = new Float32Array(3 * SIZE * SIZE);
  const plane = SIZE * SIZE;
  for (let i = 0; i < plane; i += 1) {
    const r = pixels[i * 4] / 255;
    const g = pixels[i * 4 + 1] / 255;
    const b = pixels[i * 4 + 2] / 255;
    tensor[i] = (r - MEAN[0]) / STD[0];
    tensor[plane + i] = (g - MEAN[1]) / STD[1];
    tensor[plane * 2 + i] = (b - MEAN[2]) / STD[2];
  }
  return tensor;
};

export const embedImage = async (imageData) => {
  const session = await loadSession();
  const tensor = toTensor(imageData);
  const feeds = {
    [session.inputNames[0]]: new ort.Tensor("float32", tensor, [1, 3, SIZE, SIZE]),
  };
  const results = await session.run(feeds);
  return results[session.outputNames[0]].data;
};

export const ensureEmbedder = () => loadSession();
