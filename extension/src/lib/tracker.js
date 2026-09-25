import { MATCH_IOU, TRACK_MAX_MISSES } from "./constants.js";
import { identifyCrop } from "./identify.js";
import { iou } from "./detect.js";

const findBestQuad = (track, quads, used) => {
  let best = null;
  let bestIou = MATCH_IOU;

  for (let i = 0; i < quads.length; i += 1) {
    if (used.has(i)) continue;
    const overlap = iou(track, quads[i]);
    if (overlap > bestIou) {
      bestIou = overlap;
      best = i;
    }
  }

  return best;
};

const applyQuad = (track, quad) => {
  track.x = quad.x;
  track.y = quad.y;
  track.w = quad.w;
  track.h = quad.h;
  track.cx = quad.cx;
  track.cy = quad.cy;
  track.rw = quad.rw;
  track.rh = quad.rh;
  track.angle = quad.angle;
  track.visiblePart = quad.visiblePart;
  track.orientation = quad.orientation;
  track.corners = quad.corners;
  if (quad.detectScore != null) track.detectScore = quad.detectScore;
};

export const createTracker = () => {
  let tracks = [];
  let nextId = 1;
  let fingerprints = {};

  const identifyTrack = async (track, imageData, quad) => {
    if (track.idSource === "user") return;
    const result = await identifyCrop(imageData, quad);
    track.lastGrid = result.layout || track.lastGrid;

    track.guessName = result.guess?.name || null;
    track.guessUrl = result.guess?.imageUrl || null;
    track.top = result.top || [];
    const idScore = result.guess?.score ?? result.score ?? null;
    if (idScore != null) track.idScore = idScore;
    if (!track.guessedCardId) {
      track.guessedCardId = result.guess?.cardId || result.cardId || null;
      track.guessedName = result.guess?.name || result.name || null;
      track.guessedImageUrl = result.guess?.imageUrl || result.imageUrl || null;
      track.guessedScore = result.guess?.score ?? result.score ?? null;
    }

    if (result.status === "match") {
      track.cardId = result.cardId;
      track.name = result.name;
      track.imageUrl = result.imageUrl;
      track.label = result.name;
      track.visiblePart = result.part || "full";
      track.partX = result.partX ?? 0;
      track.partY = result.partY ?? 0;
      track.partW = result.partW ?? 1;
      track.partH = result.partH ?? 1;
      track.rejected = false;
      return;
    }

    track.cardId = null;
    track.imageUrl = null;
    track.rejected = result.status !== "empty";
    if (result.status === "empty") {
      track.label = "no index";
      track.name = null;
      return;
    }
    if (result.status === "upside-down") {
      track.label = "upside-down";
      track.name = null;
      return;
    }
    track.label = result.guess?.name ? `maybe ${result.guess.name}` : "no match";
    track.name = null;
  };

  const snapshot = () => tracks.map((track) => ({ ...track }));

  const WHOLE_IMAGE = {
    x: 0,
    y: 0,
    w: 1,
    h: 1,
    cx: 0.5,
    cy: 0.5,
    angle: 0,
    corners: null,
  };

  return {
    setFingerprints: (next) => {
      fingerprints = next || {};
    },

    reset: () => {
      tracks = [];
    },

    update: (quads, imageData, forceReset) => {
      if (forceReset) tracks = [];

      const used = new Set();

      for (const track of tracks) {
        const matchIndex = findBestQuad(track, quads, used);
        if (matchIndex === null) {
          track.misses += 1;
          continue;
        }

        used.add(matchIndex);
        const quad = quads[matchIndex];
        applyQuad(track, quad);
        track.misses = 0;
      }

      tracks = tracks.filter((track) => track.misses < TRACK_MAX_MISSES);

      for (let i = 0; i < quads.length; i += 1) {
        if (used.has(i)) continue;
        const quad = quads[i];
        const track = {
          id: nextId,
          correctionId: `c${Date.now()}-${nextId}`,
          misses: 0,
          cardId: null,
          name: null,
          imageUrl: null,
          lastGrid: null,
          rejected: false,
          label: "card",
          guessName: null,
          guessUrl: null,
          guessedCardId: null,
          guessedName: null,
          guessedImageUrl: null,
          guessedScore: null,
          idSource: null,
        };
        nextId += 1;
        applyQuad(track, quad);
        tracks.push(track);
      }

      return snapshot();
    },

    identifyOne: async (trackId, imageData, preCropped) => {
      const track = tracks.find((item) => item.id === Number(trackId));
      if (!track || !imageData) return snapshot();
      await identifyTrack(track, imageData, preCropped ? WHOLE_IMAGE : track);
      return snapshot();
    },

    correctOne: (trackId, card) => {
      const track = tracks.find((item) => item.id === Number(trackId));
      if (!track || !card?.cardId) return snapshot();
      if (card.correctionId) track.correctionId = card.correctionId;
      else if (!track.correctionId) track.correctionId = `c${Date.now()}-${track.id}`;
      if (!track.guessedCardId && !track.guessedName) {
        track.guessedCardId = track.cardId || null;
        track.guessedName = track.name || track.guessName || null;
        track.guessedImageUrl = track.imageUrl || track.guessUrl || null;
        track.guessedScore = track.guessedScore ?? null;
      }
      track.cardId = card.cardId;
      track.name = card.name || card.cardId;
      track.imageUrl = card.imageUrl || "";
      track.label = track.name;
      track.idSource = "user";
      track.rejected = false;
      return snapshot();
    },
  };
};
