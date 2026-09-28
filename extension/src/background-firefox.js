// Firefox background page. Firefox has no offscreen documents, but its Manifest V3 background
// is an event page with a DOM, so the engine host that Chrome runs in an offscreen document
// (engine-host.js) is imported here and runs directly in the background page. The message
// protocol with the content script is unchanged; the "ensure/stop engine" messages become
// create/drop of the per-tab engine objects. Firefox unloads this page after ~30 s without
// events, which drops the loaded models just like Chrome closing the idle offscreen document.
// Only referenced by the manifest that tools/export_firefox.py writes; Chrome never loads it.
import { dropAllEngines, dropEngine, handleEngineMessage } from "./engine-host.js";
import { onIdMatcherStatus } from "./lib/identify.js";

const STORAGE_INDEX_STATUS = "fow.indexStatus";

const storeIndexStatus = (phase, detail) =>
  chrome.storage.local
    .set({
      [STORAGE_INDEX_STATUS]: {
        phase: phase || "idle",
        detail: phase === "ready" || phase === "idle" ? "" : detail || "",
      },
    })
    .catch(() => {});

// A page never receives its own runtime.sendMessage, so the matcher's status message from
// identify.js does not reach us here; subscribe to the in-page hook instead.
onIdMatcherStatus(storeIndexStatus);

chrome.tabs.onRemoved.addListener((tabId) => {
  dropEngine(tabId);
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
    storeIndexStatus(message.phase, message.detail).then(() => sendResponse({ ok: true }));
    return true;
  }

  if (message?.type === "ensureEngine") {
    // Creating the tab's engine starts loading the detector, embedder and index right away.
    handleEngineMessage({ type: "indexState" }, sender.tab?.id)
      .then(() => sendResponse({ ok: true }))
      .catch((error) => sendResponse({ type: "error", error: error.message }));
    return true;
  }

  if (message?.type === "engineActive") {
    if (!message.active && sender.tab?.id != null) dropEngine(sender.tab.id);
    sendResponse({ ok: true });
    return true;
  }

  if (message?.type === "engineStop") {
    dropAllEngines();
    sendResponse({ ok: true });
    return true;
  }

  return false;
});
