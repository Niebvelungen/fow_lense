import { resolveImageUrl } from "./catalog.js";
import { extractRect } from "./crop.js";
import { embedImage, ensureEmbedder } from "./embed-id.js";
import { loadIdIndex } from "./id-index.js";

export const EMBED_ACCEPT = 0.7;
export const EMBED_MARGIN = 0.05;
const CROP_EDGE = 320;

let index = null;
let loadPromise = null;
let matcherPhase = "idle";
let matcherDetail = "";

const cropFromQuad = (imageData, quad) => {
  const rect = {
    cx: (quad.cx ?? quad.x + quad.w / 2) * imageData.width,
    cy: (quad.cy ?? quad.y + quad.h / 2) * imageData.height,
    rw: quad.rw ?? quad.w * imageData.width,
    rh: quad.rh ?? quad.h * imageData.height,
    angle: quad.angle || 0,
    corners: quad.corners,
  };
  const scale = Math.min(1, CROP_EDGE / Math.max(rect.rw, rect.rh, 1));
  const destW = Math.max(16, Math.round(rect.rw * scale));
  const destH = Math.max(16, Math.round(rect.rh * scale));
  return extractRect(imageData, rect, destW, destH);
};

const WHOLE = {
  x: 0,
  y: 0,
  w: 1,
  h: 1,
  cx: 0.5,
  cy: 0.5,
  angle: 0,
  corners: null,
};

const dot = (a, b) => {
  let sum = 0;
  for (let i = 0; i < a.length; i += 1) sum += a[i] * b[i];
  return sum;
};

const scoreEmbedding = (query, idIndex) => {
  const perCard = new Float32Array(idIndex.cards.length);
  perCard.fill(-1);
  for (let i = 0; i < idIndex.E.length; i += 1) {
    const sim = dot(query, idIndex.E[i]);
    const owner = idIndex.EOwner[i];
    if (sim > perCard[owner]) perCard[owner] = sim;
  }
  const ranked = [];
  for (let i = 0; i < perCard.length; i += 1) {
    if (perCard[i] < 0) continue;
    const card = idIndex.cards[i];
    ranked.push({
      cardId: card.id,
      name: card.name,
      imageUrl: resolveImageUrl(card.imageUrl),
      dist: 1 - perCard[i],
      score: perCard[i],
    });
  }
  ranked.sort((a, b) => b.score - a.score);
  return ranked;
};

const toResult = (ranked) => {
  const top = ranked.slice(0, 5);
  const best = top[0] || null;
  const second = top[1]?.score ?? -1;
  const guess = best
    ? {
        cardId: best.cardId,
        name: best.name,
        imageUrl: best.imageUrl,
        dist: best.dist,
        score: best.score,
      }
    : null;
  const accepted =
    Boolean(best) &&
    best.score >= EMBED_ACCEPT &&
    best.score - second >= EMBED_MARGIN;
  if (!accepted) {
    return { status: best ? "none" : "empty", guess, top, part: "full" };
  }
  return {
    status: "match",
    guess,
    top,
    cardId: best.cardId,
    name: best.name,
    imageUrl: best.imageUrl,
    dist: best.dist,
    score: best.score,
    part: "full",
    partX: 0,
    partY: 0,
    partW: 1,
    partH: 1,
  };
};

const publishMatcher = (phase, detail = "") => {
  matcherPhase = phase;
  matcherDetail = detail;
  chrome.runtime
    .sendMessage({ type: "indexStatus", phase, detail })
    .catch(() => {});
};

export const idMatcherStatus = () => ({
  phase: matcherPhase,
  detail: matcherPhase === "ready" || matcherPhase === "idle" ? "" : matcherDetail,
});

export const ensureIdMatcher = async () => {
  if (index) {
    matcherPhase = "ready";
    matcherDetail = "";
    return index;
  }
  if (!loadPromise) {
    loadPromise = (async () => {
      publishMatcher("loading", "Loading recognition model");
      await ensureEmbedder();
      publishMatcher("loading", "Loading card index");
      index = await loadIdIndex(chrome.runtime.getURL("models/id-index.bin"));
      publishMatcher("ready");
      return index;
    })().catch((error) => {
      loadPromise = null;
      publishMatcher("error", error?.message || "Card index failed to load");
      throw error;
    });
  }
  return loadPromise;
};

export const identifyCrop = async (imageData, quad) => {
  try {
    await ensureIdMatcher();
  } catch {
    return { status: "empty" };
  }
  if (!index?.cards?.length || !imageData) return { status: "empty" };
  const image = cropFromQuad(imageData, quad);
  const query = await embedImage(image);
  return toResult(scoreEmbedding(query, index));
};

export const identifyImage = (imageData) => identifyCrop(imageData, WHOLE);
