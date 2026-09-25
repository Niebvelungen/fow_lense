import { CAPTURE_MAX_EDGE } from "./constants.js";

export const captureVideoFrame = (video, maxEdge = CAPTURE_MAX_EDGE) => {
  if (!video?.videoWidth) return null;

  const scale = Math.min(1, maxEdge / Math.max(video.videoWidth, video.videoHeight));
  const width = Math.round(video.videoWidth * scale);
  const height = Math.round(video.videoHeight * scale);
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  canvas.getContext("2d").drawImage(video, 0, 0, width, height);
  try {
    return {
      dataUrl: canvas.toDataURL("image/jpeg", 0.85),
      width,
      height,
      mime: "image/jpeg",
    };
  } catch (error) {
    return null;
  }
};

export const signatureDistance = (signature, known) => {
  if (!signature?.length) return 0;
  if (!known.length) return 999;
  let best = Infinity;
  for (const other of known) {
    if (!other?.length || other.length !== signature.length) continue;
    let sum = 0;
    for (let i = 0; i < signature.length; i += 1) {
      sum += Math.abs(signature[i] - other[i]);
    }
    best = Math.min(best, sum / signature.length);
  }
  return best;
};

export const isUniqueSignature = (signature, known, threshold) => {
  return signatureDistance(signature, known) >= threshold;
};
