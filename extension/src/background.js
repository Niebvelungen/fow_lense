const OFFSCREEN_URL = "src/engine-host.html";

const hasOffscreen = async () => {
  if (!chrome.runtime.getContexts) return false;
  const contexts = await chrome.runtime.getContexts({
    contextTypes: ["OFFSCREEN_DOCUMENT"],
    documentUrls: [chrome.runtime.getURL(OFFSCREEN_URL)],
  });
  return contexts.length > 0;
};

const ensureOffscreen = async () => {
  if (await hasOffscreen()) return;
  try {
    await chrome.offscreen.createDocument({
      url: OFFSCREEN_URL,
      reasons: ["WORKERS"],
      justification: "Run card detection off the video page",
    });
  } catch (error) {
    if (!String(error.message || error).includes("single offscreen")) {
      throw error;
    }
  }
};

const liveTabs = new Set();

const releaseEngineIfIdle = () => {
  if (liveTabs.size > 0) return;
  chrome.offscreen.closeDocument().catch(() => {});
};

chrome.tabs.onRemoved.addListener((tabId) => {
  if (!liveTabs.delete(tabId)) return;
  releaseEngineIfIdle();
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type === "openPopup") {
    const popupUrl = chrome.runtime.getURL("src/popup.html");
    const openFallback = () => {
      chrome.windows
        .getAll({ populate: true })
        .then((wins) => {
          const existing = wins.find((win) => win.tabs?.some((tab) => tab.url === popupUrl));
          if (existing?.id) {
            chrome.windows.update(existing.id, { focused: true });
            return;
          }
          chrome.windows.create({
            url: popupUrl,
            type: "popup",
            width: 300,
            height: 220,
            focused: true,
          });
        })
        .catch(() => {});
    };
    try {
      const pending = chrome.action.openPopup();
      if (pending?.then) {
        pending.then(() => sendResponse({ ok: true })).catch(() => {
          openFallback();
          sendResponse({ ok: true });
        });
      } else {
        sendResponse({ ok: true });
      }
    } catch {
      openFallback();
      sendResponse({ ok: true });
    }
    return true;
  }

  if (message?.type === "indexStatus") {
    const phase = message.phase || "idle";
    chrome.storage.local
      .set({
        "fow.indexStatus": {
          phase,
          detail: phase === "ready" || phase === "idle" ? "" : message.detail || "",
        },
      })
      .then(() => sendResponse({ ok: true }))
      .catch(() => sendResponse({ ok: false }));
    return true;
  }

  if (message?.type === "ensureEngine") {
    ensureOffscreen()
      .then(() => sendResponse({ ok: true }))
      .catch((error) => sendResponse({ type: "error", error: error.message }));
    return true;
  }

  if (message?.type === "engineActive") {
    const tabId = sender.tab?.id;
    if (tabId != null) {
      if (message.active) liveTabs.add(tabId);
      else liveTabs.delete(tabId);
    }
    releaseEngineIfIdle();
    sendResponse({ ok: true });
    return true;
  }

  if (message?.type === "engineStop") {
    liveTabs.clear();
    chrome.offscreen
      .closeDocument()
      .then(() => sendResponse({ ok: true }))
      .catch(() => sendResponse({ ok: true }));
    return true;
  }

  return false;
});
