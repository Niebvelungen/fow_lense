export const iou = (a, b) => {
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

export const createDetector = () => {
  return {
    findCardQuads: async () => [],
  };
};

export const frameSignature = (imageData) => {
  const sigW = 32;
  const sigH = 18;
  const { data, width: srcW, height: srcH } = imageData;
  const out = new Uint8Array(sigW * sigH);
  for (let y = 0; y < sigH; y += 1) {
    for (let x = 0; x < sigW; x += 1) {
      const sx = Math.min(srcW - 1, ((x + 0.5) * srcW) / sigW) | 0;
      const sy = Math.min(srcH - 1, ((y + 0.5) * srcH) / sigH) | 0;
      const i = (sy * srcW + sx) * 4;
      out[y * sigW + x] = (data[i] * 0.299 + data[i + 1] * 0.587 + data[i + 2] * 0.114) | 0;
    }
  }
  return out;
};

export const meanAbsDiff = (a, b) => {
  if (!a || !b || a.length !== b.length) return 255;
  let sum = 0;
  for (let i = 0; i < a.length; i += 1) {
    sum += Math.abs(a[i] - b[i]);
  }
  return sum / a.length;
};
