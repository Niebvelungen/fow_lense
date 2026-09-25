import { SCENE_CHANGE_MAD } from "./constants.js";
import { frameSignature, meanAbsDiff } from "./detect.js";
import { createTracker } from "./tracker.js";
import { createYoloDetector } from "./yolo.js";
import { ensureIdMatcher } from "./identify.js";

export const createEngine = () => {
  const tracker = createTracker();
  const detector = createYoloDetector();
  let previousSignature = null;
  let fingerprintCount = 0;
  let lastImageData = null;
  ensureIdMatcher().catch(() => {});

  const snapshot = (tracks) => ({
    tracks,
    quads: tracks.length,
    identified: tracks.filter((track) => track.cardId).length,
  });

  return {
    setFingerprints: (fingerprints) => {
      const next = fingerprints || {};
      const nextCount = Object.keys(next).length;
      tracker.setFingerprints(next);
      if (fingerprintCount === 0 && nextCount > 0) {
        tracker.reset();
        previousSignature = null;
      }
      fingerprintCount = nextCount;
    },

    reset: () => {
      tracker.reset();
      previousSignature = null;
      lastImageData = null;
    },

    identifyTrack: async (trackId, imageData, preCropped) => {
      if (imageData && preCropped) {
        return snapshot(await tracker.identifyOne(trackId, imageData, true));
      }
      const frame = imageData || lastImageData;
      if (imageData) lastImageData = imageData;
      return snapshot(await tracker.identifyOne(trackId, frame, false));
    },

    correctTrack: (payload) =>
      snapshot(
        tracker.correctOne(payload.trackId, {
          cardId: payload.cardId,
          name: payload.name,
          imageUrl: payload.imageUrl,
          correctionId: payload.correctionId,
        })
      ),

    processFrame: async (imageData, forceReset) => {
      const signature = frameSignature(imageData);
      const sceneChanged =
        forceReset || meanAbsDiff(previousSignature, signature) > SCENE_CHANGE_MAD;
      previousSignature = signature;
      if (sceneChanged) tracker.reset();

      lastImageData = imageData;
      const quads = await detector.findCardQuads(imageData);
      return snapshot(tracker.update(quads, imageData, false));
    },
  };
};
