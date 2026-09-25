import { createEngine } from "./lib/engine.js";
import { idMatcherStatus } from "./lib/identify.js";

const engines = new Map();

const engineFor = (tabId) => {
  const key = tabId ?? 0;
  let engine = engines.get(key);
  if (!engine) {
    engine = createEngine();
    engines.set(key, engine);
  }
  return engine;
};

const toPixels = (data) => {
  const source = data.pixels ?? data.buffer;
  if (!source) return new Uint8ClampedArray();
  if (source instanceof Uint8ClampedArray) return source;
  if (source instanceof Uint8Array) {
    return new Uint8ClampedArray(source.buffer, source.byteOffset, source.byteLength);
  }
  if (source instanceof ArrayBuffer) return new Uint8ClampedArray(source);
  if (ArrayBuffer.isView(source)) {
    return new Uint8ClampedArray(source.buffer, source.byteOffset, source.byteLength);
  }
  if (Array.isArray(source)) return new Uint8ClampedArray(source);
  return new Uint8ClampedArray();
};

const handleEngineMessage = async (data, tabId) => {
  const engine = () => engineFor(tabId);
  if (data.type === "fingerprints") {
    engine().setFingerprints(data.fingerprints);
    return { type: "ok" };
  }
  if (data.type === "reset") {
    engine().reset();
    return { type: "ok" };
  }
  if (data.type === "indexState") {
    const status = idMatcherStatus();
    chrome.runtime
      .sendMessage({ type: "indexStatus", phase: status.phase, detail: status.detail })
      .catch(() => {});
    return { type: "indexState", phase: status.phase, detail: status.detail };
  }
  if (data.type === "identify") {
    const width = Number(data.width) || 0;
    const height = Number(data.height) || 0;
    const pixels = toPixels(data);
    const expected = width * height * 4;
    const imageData =
      width > 0 && height > 0 && pixels.length >= expected
        ? new ImageData(pixels.length === expected ? pixels : pixels.slice(0, expected), width, height)
        : null;
    return {
      type: "tracks",
      source: "identify",
      ...(await engine().identifyTrack(data.trackId, imageData, Boolean(data.cropped))),
    };
  }
  if (data.type === "correctTrack") {
    return { type: "tracks", source: "correctTrack", ...engine().correctTrack(data) };
  }
  if (data.type !== "frame") return { type: "ok" };

  const width = Number(data.width) || 0;
  const height = Number(data.height) || 0;
  const pixels = toPixels(data);
  const expected = width * height * 4;
  if (width < 1 || height < 1 || pixels.length < expected) {
    return { type: "tracks", tracks: [], quads: 0, identified: 0 };
  }

  const imageData = new ImageData(pixels.length === expected ? pixels : pixels.slice(0, expected), width, height);
  return {
    type: "tracks",
    source: "frame",
    ...(await engine().processFrame(imageData, Boolean(data.forceReset))),
  };
};

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type !== "engineDirect") return false;
  handleEngineMessage(message.data || {}, sender.tab?.id)
    .then(sendResponse)
    .catch((error) => sendResponse({ type: "error", error: error.message }));
  return true;
});
