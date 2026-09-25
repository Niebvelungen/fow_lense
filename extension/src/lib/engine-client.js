
const toPixelArray = (source) => {
  if (source instanceof Uint8Array || source instanceof Uint8ClampedArray) {
    return Array.from(source);
  }
  if (source instanceof ArrayBuffer) return Array.from(new Uint8Array(source));
  return [];
};

const toFramePayload = (data) => {
  if (data?.type !== "frame" && data?.type !== "identify") return data;
  return {
    type: data.type,
    trackId: data.trackId,
    width: data.width,
    height: data.height,
    pixels: toPixelArray(data.pixels ?? data.buffer),
    cropped: Boolean(data.cropped),
    forceReset: Boolean(data.forceReset),
  };
};

export const createEngineClient = () => {
  let onmessage = null;
  let ready = null;

  const ensureEngine = () => {
    if (!ready) {
      ready = chrome.runtime
        .sendMessage({ type: "ensureEngine" })
        .then((result) => {
          if (result?.type === "error") throw new Error(result.error);
          return true;
        })
        .catch((error) => {
          ready = null;
          throw error;
        });
    }
    return ready;
  };

  const sendDirect = (payload) =>
    chrome.runtime.sendMessage({ type: "engineDirect", data: payload });

  const send = async (payload) => {
    await ensureEngine();

    try {
      const result = await sendDirect(payload);
      if (result !== undefined) return result;
    } catch (error) {
    }

    ready = null;
    await ensureEngine();
    return sendDirect(payload);
  };

  return {
    set onmessage(handler) {
      onmessage = handler;
    },

    postMessage: (data) => {
      const payload = toFramePayload(data);
      send(payload)
        .then((result) => {
          if (result) onmessage?.({ data: result });
        })
        .catch((error) => {
          onmessage?.({ data: { type: "error", error: error.message } });
        });
    },

    terminate: () => {
      ready = null;
      chrome.runtime.sendMessage({ type: "engineStop" }).catch(() => {});
    },
  };
};
