const sampleBilinear = (data, width, height, x, y) => {
  const x0 = Math.max(0, Math.min(width - 2, Math.floor(x)));
  const y0 = Math.max(0, Math.min(height - 2, Math.floor(y)));
  const fx = x - x0;
  const fy = y - y0;
  const i00 = (y0 * width + x0) * 4;
  const i10 = i00 + 4;
  const i01 = i00 + width * 4;
  const i11 = i01 + 4;
  return [
    data[i00] * (1 - fx) * (1 - fy) +
      data[i10] * fx * (1 - fy) +
      data[i01] * (1 - fx) * fy +
      data[i11] * fx * fy,
    data[i00 + 1] * (1 - fx) * (1 - fy) +
      data[i10 + 1] * fx * (1 - fy) +
      data[i01 + 1] * (1 - fx) * fy +
      data[i11 + 1] * fx * fy,
    data[i00 + 2] * (1 - fx) * (1 - fy) +
      data[i10 + 2] * fx * (1 - fy) +
      data[i01 + 2] * (1 - fx) * fy +
      data[i11 + 2] * fx * fy,
  ];
};

const lerp = (a, b, t) => ({ x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t });

export const extractRect = (source, rect, destW, destH) => {
  const { data, width, height } = source;
  const out = new Uint8ClampedArray(destW * destH * 4);
  const corners = rect.corners;

  for (let y = 0; y < destH; y += 1) {
    for (let x = 0; x < destW; x += 1) {
      let sx;
      let sy;
      if (corners?.length === 4) {
        const u = (x + 0.5) / destW;
        const v = (y + 0.5) / destH;
        const top = lerp(
          { x: corners[0].x * width, y: corners[0].y * height },
          { x: corners[1].x * width, y: corners[1].y * height },
          u
        );
        const bottom = lerp(
          { x: corners[3].x * width, y: corners[3].y * height },
          { x: corners[2].x * width, y: corners[2].y * height },
          u
        );
        const p = lerp(top, bottom, v);
        sx = p.x;
        sy = p.y;
      } else {
        const cos = Math.cos(rect.angle || 0);
        const sin = Math.sin(rect.angle || 0);
        const u = (x / destW - 0.5) * rect.rw;
        const vv = (y / destH - 0.5) * rect.rh;
        sx = rect.cx + u * cos - vv * sin;
        sy = rect.cy + u * sin + vv * cos;
      }
      const rgb = sampleBilinear(data, width, height, sx, sy);
      const i = (y * destW + x) * 4;
      out[i] = rgb[0];
      out[i + 1] = rgb[1];
      out[i + 2] = rgb[2];
      out[i + 3] = 255;
    }
  }

  return new ImageData(out, destW, destH);
};
