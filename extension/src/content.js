let isConsumer = false;

const noopAdmin = {
  isOpen: () => false,
  pickerOpen: () => false,
  closePicker() {},
  showBanner() {},
  bindRoot() {},
  mount() {},
  loadStored() {},
  onStorage() {},
  onCaptureTick: (_now, last) => last,
  onCardsOn() {},
  refreshDataset() {},
  startCatalog() {},
  noteLookup() {},
  noteTracks() {},
  onClick() {},
  onKey() {
    return false;
  },
  onRuntimeMessage() {
    return false;
  },
};

let admin = noopAdmin;

const showPageBanner = (text) => {
  if (isConsumer) return;
  admin.showBanner(text);
};

const start = async () => {
  const url = (path) => chrome.runtime.getURL(path);
  ({ IS_CONSUMER: isConsumer } = await import(url("src/lib/build-info.js")));
  const [
    {
      SAMPLE_MS,
      SAMPLE_IDLE_MS,
      SAMPLE_WIDTH,
      IDENTIFY_MS,
      IDENTIFY_IDLE_MS,
      POINTER_STILL_MS,
      IDENTIFY_CROP_EDGE,
      STORAGE_ENABLED,
      STORAGE_SHOW_QUICK_OVERLAY,
    },
    {
      bindTrackIdentify,
      createOverlayRoot,
      refreshHoverZoom,
      renderTracks,
      setOverlayFrame,
      setPointerTrack,
    },
    {
      findPlayer,
      findVideo,
      getMediaId,
      getVideoRectInPlayer,
      isTwitch,
      positionPlayer,
      waitForVideo,
    },
    { frameSignature },
    { createEngineClient },
  ] = await Promise.all([
    import(url("src/lib/constants.js")),
    import(url("src/lib/overlay.js")),
    import(url("src/lib/youtube.js")),
    import(url("src/lib/detect.js")),
    import(url("src/lib/engine-client.js")),
  ]);

  const worker = createEngineClient();
  const sampleCanvas = document.createElement("canvas");
  const sampleCtx = sampleCanvas.getContext("2d", { willReadFrequently: true });
  const identifyCanvas = document.createElement("canvas");
  const identifyCtx = identifyCanvas.getContext("2d", { willReadFrequently: true });

  let video = null;
  let player = null;
  let root = null;
  let currentVideoId = null;
  let lastSampleAt = 0;
  let forceNext = true;
  let latestTracks = [];
  let busy = false;
  let rafId = 0;
  let bannerHoldUntil = 0;
  let lastCaptureCheckAt = 0;
  let pendingCorrect = false;
  let cardsOn = false;
  let extensionOn = false;
  let showQuickOverlay = true;
  let indexPhase = "idle";
  let indexDetail = "";
  let hoveringVideo = false;
  let lastPointer = null;
  let hoverLeaveTimer = 0;
  let lastPointerMoveAt = 0;
  let identifyBusy = new Set();
  let lastIdentifyAt = new Map();

  const holdBanner = (ms) => {
    bannerHoldUntil = Date.now() + ms;
  };

  const syncQuickButton = () => {
    if (!root) return;
    let button = root.querySelector(".rift-quick");
    if (!button) {
      button = document.createElement("button");
      button.type = "button";
      button.className = "rift-quick";
      button.innerHTML = `<img alt="" />`;
      button.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        if (isConsumer && indexPhase === "loading") {
          sendMessage({ type: "openPopup" });
          return;
        }
        setCardsOn(!cardsOn);
      });
      root.appendChild(button);
    }
    const iconVersion = chrome.runtime.getManifest().version;
    const iconFile = cardsOn ? "icons/overlay_on.svg" : "icons/overlay_off.svg";
    const img = button.querySelector("img");
    const iconSrc = `${url(iconFile)}?v=${iconVersion}`;
    if (img && img.getAttribute("src") !== iconSrc) img.src = iconSrc;
    const show = (isConsumer ? extensionOn : showQuickOverlay) && hoveringVideo;
    const iconLoading = isConsumer && cardsOn && indexPhase === "loading";
    button.hidden = !show;
    button.classList.toggle("is-loading", iconLoading);
    button.setAttribute("aria-pressed", cardsOn ? "true" : "false");
    const label = iconLoading
      ? "Show loading details"
      : cardsOn
        ? "Stop overlay"
        : "Start overlay";
    button.setAttribute("aria-label", label);
  };

  const setCardsOn = (on, persist = !isConsumer) => {
    const next = Boolean(on);
    if (isConsumer && next && !extensionOn) return;
    if (next === cardsOn) {
      syncQuickButton();
      return;
    }
    cardsOn = next;
    if (persist) chrome.storage.local.set({ [STORAGE_ENABLED]: cardsOn }).catch(() => {});
    syncQuickButton();
    if (!cardsOn) {
      latestTracks = [];
      identifyBusy.clear();
      lastIdentifyAt.clear();
      pendingCorrect = false;
      admin.closePicker();
      busy = false;
      if (root) {
        for (const node of root.querySelectorAll(".rift-card, .rift-zoom, .rift-debug-svg")) {
          node.remove();
        }
      }
      if (isConsumer) {
        sendMessage({ type: "engineActive", active: false });
        if (!extensionOn) setIndexStatus("idle");
      } else {
        worker.terminate();
      }
      return;
    }
    if (isConsumer) sendMessage({ type: "engineActive", active: true });
    forceNext = true;
    lastSampleAt = 0;
    if (isConsumer) {
      worker.postMessage({ type: "reset" });
      refreshIndexStatus();
    } else {
      admin.onCardsOn();
    }
    if (hoveringVideo) sampleEngine();
  };

  const setIndexStatus = (phase, detail = "") => {
    if (phase === "loading" && indexPhase === "ready") return;
    indexPhase = phase;
    indexDetail = phase === "ready" || phase === "idle" ? "" : detail;
    chrome.storage.local
      .set({
        "fow.indexStatus": {
          phase,
          detail: indexDetail,
        },
      })
      .catch(() => {});
    syncConsumerLoading();
  };

  const refreshIndexStatus = async () => {
    if (!isConsumer || !cardsOn) return;
    try {
      const ensured = await sendMessage({ type: "ensureEngine" });
      if (ensured?.type === "error") throw new Error(ensured.error);
      const result = await sendMessage({ type: "engineDirect", data: { type: "indexState" } });
      if (!cardsOn) return;
      setIndexStatus(result?.phase || "loading", result?.detail || "");
    } catch {
      if (cardsOn) setIndexStatus("loading");
    }
  };

  const sendMessage = (message) => chrome.runtime.sendMessage(message);

  const syncConsumerLoading = () => {
    if (!root) return;
    root.querySelector(".rift-status")?.remove();
    syncQuickButton();
  };

  const resetForVideo = (videoId) => {
    const leavingVideo = isConsumer && cardsOn && currentVideoId != null && videoId !== currentVideoId;
    currentVideoId = videoId;
    latestTracks = [];
    pendingCorrect = false;
    forceNext = true;
    lastIdentifyAt.clear();
    admin.closePicker();
    if (cardsOn && !leavingVideo) worker.postMessage({ type: "reset" });
    if (root) {
      for (const node of root.querySelectorAll(".rift-card, .rift-debug-svg")) {
        node.remove();
      }
    }
    if (leavingVideo) setCardsOn(false);
  };

  const grabTrackCrop = (track, canvas, ctx, maxEdge) => {
    if (!video || video.readyState < 2 || video.videoWidth === 0) return null;
    if (!track || !canvas || !ctx) return null;

    const vw = video.videoWidth;
    const vh = video.videoHeight;
    const sx = Math.max(0, Math.min(vw - 1, track.x * vw));
    const sy = Math.max(0, Math.min(vh - 1, track.y * vh));
    const sw = Math.max(1, Math.min(vw - sx, track.w * vw));
    const sh = Math.max(1, Math.min(vh - sy, track.h * vh));
    if (sw < 2 || sh < 2) return null;

    const scale = Math.min(1, maxEdge / Math.max(sw, sh));
    const width = Math.max(8, Math.round(sw * scale));
    const height = Math.max(8, Math.round(sh * scale));
    if (canvas.width !== width || canvas.height !== height) {
      canvas.width = width;
      canvas.height = height;
    }
    try {
      ctx.drawImage(video, sx, sy, sw, sh, 0, 0, width, height);
      return ctx.getImageData(0, 0, width, height);
    } catch {
      return null;
    }
  };

  const grabIdentifyCrop = (track) =>
    grabTrackCrop(track, identifyCanvas, identifyCtx, IDENTIFY_CROP_EDGE);

  const pointerIsStill = (now) => now - lastPointerMoveAt >= POINTER_STILL_MS;

  const requestIdentify = (trackId) => {
    if (!cardsOn || admin.pickerOpen() || pendingCorrect) return;
    const track = latestTracks.find((item) => item.id === Number(trackId));
    if (!track || track.idSource === "user" || track.cardId) return;
    const id = Number(trackId);
    if (identifyBusy.has(id)) return;
    const now = performance.now();
    const gap = pointerIsStill(now) ? IDENTIFY_IDLE_MS : IDENTIFY_MS;
    if (now - (lastIdentifyAt.get(id) || 0) < gap) return;
    lastIdentifyAt.set(id, now);
    identifyBusy.add(id);
    const crop = grabIdentifyCrop(track);
    if (!crop) {
      worker.postMessage({ type: "identify", trackId });
      return;
    }
    if (!isConsumer) admin.noteLookup();
    worker.postMessage({
      type: "identify",
      trackId,
      width: crop.width,
      height: crop.height,
      buffer: crop.data.buffer,
      cropped: true,
    });
  };

  const PLAYER_CHROME_SEL = [
    ".ytp-chrome-bottom",
    ".ytp-chrome-top",
    ".ytp-progress-bar-container",
    ".ytp-progress-bar",
    ".ytp-chapter-hover-container",
    ".ytp-button",
    ".ytp-popup",
    ".ytp-settings-menu",
    ".ytp-volume-panel",
    ".ytp-time-display",
    ".ytp-tooltip",
    ".ytp-skip-ad",
    ".ytp-skip-ad-button",
    ".ytp-ad-overlay-container",
    ".ytp-ce-element",
    ".ytp-cards-teaser",
    ".ytp-cards-button",
    ".ytp-fullerscreen-edu",
    ".ytp-autonav-endscreen",
    ".ytp-pause-overlay",
  ].join(",");

  const isPlayerChrome = (el) => {
    if (!el || el.nodeType !== 1) return false;
    if (el.closest?.("#rift-page-banner")) return true;
    if (el.closest?.(".rift-correct-pick")) return false;
    return Boolean(el.closest?.(PLAYER_CHROME_SEL));
  };

  const trackAtPoint = (clientX, clientY) => {
    if (!root || !latestTracks.length) return null;
    const rect = root.getBoundingClientRect();
    if (rect.width < 8 || rect.height < 8) return null;
    const nx = (clientX - rect.left) / rect.width;
    const ny = (clientY - rect.top) / rect.height;
    let best = null;
    let bestDist = Infinity;
    for (const track of latestTracks) {
      if (nx < track.x || ny < track.y || nx > track.x + track.w || ny > track.y + track.h) {
        continue;
      }
      const dx = nx - (track.x + track.w / 2);
      const dy = ny - (track.y + track.h / 2);
      const dist = dx * dx + dy * dy;
      if (dist < bestDist) {
        best = track;
        bestDist = dist;
      }
    }
    return best;
  };

  const updatePointerCard = () => {
    if (!root || !lastPointer || !hoveringVideo) {
      if (root) setPointerTrack(root, 0);
      return;
    }
    const under = document.elementFromPoint(lastPointer.x, lastPointer.y);
    if (isPlayerChrome(under)) {
      setPointerTrack(root, 0);
      return;
    }
    const track = trackAtPoint(lastPointer.x, lastPointer.y);
    setPointerTrack(root, track?.id || 0);
    if (track) requestIdentify(track.id);
  };

  const bindOverlay = (nextRoot) => {
    if (root && root !== nextRoot) admin.closePicker();
    root = nextRoot;
    root.classList.toggle("is-twitch", isTwitch());
    if (!isConsumer) admin.bindRoot(root);
    bindTrackIdentify(root, { onHover: requestIdentify });
    syncQuickButton();
  };

  const pointOverVideo = (x, y) => {
    const hit = (rect) =>
      rect &&
      rect.width >= 8 &&
      rect.height >= 8 &&
      x >= rect.left &&
      x <= rect.right &&
      y >= rect.top &&
      y <= rect.bottom;
    if (hit(root?.getBoundingClientRect())) return true;
    if (hit(video?.getBoundingClientRect())) return true;
    return false;
  };

  const isPointerOverVideo = () => {
    if (admin.isOpen()) return false;
    if (root?.querySelector(".rift-correct-pick:not([hidden])")) return true;
    if (lastPointer && pointOverVideo(lastPointer.x, lastPointer.y)) return true;
    if (video?.matches(":hover")) return true;
    if (player?.matches(":hover") && lastPointer && pointOverVideo(lastPointer.x, lastPointer.y)) {
      return true;
    }
    return false;
  };

  const notePointerActivity = () => {
    lastPointerMoveAt = performance.now();
  };

  const setHoveringVideo = (on) => {
    if (on) {
      if (hoverLeaveTimer) {
        window.clearTimeout(hoverLeaveTimer);
        hoverLeaveTimer = 0;
      }
      if (hoveringVideo) return;
      hoveringVideo = true;
      forceNext = true;
      lastSampleAt = 0;
      syncQuickButton();
      sampleEngine();
      return;
    }
    if (!hoveringVideo || hoverLeaveTimer) return;
    hoverLeaveTimer = window.setTimeout(() => {
      hoverLeaveTimer = 0;
      hoveringVideo = false;
      admin.closePicker();
      identifyBusy.clear();
      lastIdentifyAt.clear();
      latestTracks = [];
      if (root) renderTracks(root, []);
      if (cardsOn) worker.postMessage({ type: "reset" });
      syncQuickButton();
    }, 180);
  };

  const syncHoverFromPointer = () => {
    setHoveringVideo(isPointerOverVideo());
  };

  const handlePointerMove = (event) => {
    lastPointer = { x: event.clientX, y: event.clientY };
    if (admin.isOpen()) return;
    notePointerActivity();
    syncHoverFromPointer();
    updatePointerCard();
  };

  const handlePointerLeavePage = () => {
    lastPointer = null;
    lastPointerMoveAt = 0;
    if (admin.pickerOpen() || admin.isOpen()) return;
    setHoveringVideo(false);
  };

  const handleDocClick = (event) => {
    if (isConsumer) return;
    admin.onClick(event);
  };

  const grabSample = () => {
    if (!video || video.readyState < 2 || video.videoWidth === 0) return null;
    const width = SAMPLE_WIDTH;
    const height = Math.max(1, Math.round((video.videoHeight / video.videoWidth) * width));
    if (sampleCanvas.width !== width || sampleCanvas.height !== height) {
      sampleCanvas.width = width;
      sampleCanvas.height = height;
    }
    try {
      sampleCtx.drawImage(video, 0, 0, width, height);
      const imageData = sampleCtx.getImageData(0, 0, width, height);
      return {
        imageData,
        signature: Array.from(frameSignature(imageData)),
      };
    } catch {
      return null;
    }
  };

  const sampleEngine = () => {
    if (!cardsOn || !hoveringVideo) return;
    if (!root || busy || admin.isOpen() || admin.pickerOpen() || pendingCorrect) return;
    const sample = grabSample();
    if (!sample) return;
    busy = true;
    worker.postMessage({
      type: "frame",
      width: sample.imageData.width,
      height: sample.imageData.height,
      buffer: sample.imageData.data.buffer,
      forceReset: forceNext,
    });
    forceNext = false;
  };

  const handleTick = (now) => {
    rafId = window.requestAnimationFrame(handleTick);
    if (!video || !player) return;

    const liveVideo = findVideo();
    if (liveVideo && (liveVideo !== video || !player?.contains(liveVideo))) {
      attachVideo(liveVideo);
      return;
    }

    if (!root || !player.contains(root)) {
      bindOverlay(createOverlayRoot(player));
    }

    const videoId = getMediaId();
    if (videoId !== currentVideoId) resetForVideo(videoId);

    if (!videoId) {
      if (!isTwitch()) showPageBanner("Open a YouTube watch page");
      return;
    }

    setOverlayFrame(root, getVideoRectInPlayer(video, player));
    if (admin.isOpen() || admin.pickerOpen()) return;
    syncHoverFromPointer();
    updatePointerCard();

    if (!isConsumer) lastCaptureCheckAt = admin.onCaptureTick(now, lastCaptureCheckAt);

    if (!hoveringVideo) return;
    if (busy) return;
    const sampleGap = pointerIsStill(now) ? SAMPLE_IDLE_MS : SAMPLE_MS;
    if (now - lastSampleAt < sampleGap && !forceNext) return;
    lastSampleAt = now;
    sampleEngine();
  };

  const handleSeeked = () => {
    forceNext = true;
    lastIdentifyAt.clear();
    worker.postMessage({ type: "reset" });
  };

  const attachVideo = (nextVideo) => {
    if (video) {
      video.removeEventListener("seeked", handleSeeked);
      video.removeEventListener("play", handleSeeked);
    }

    video = nextVideo;
    player = findPlayer();
    if (!player) {
      if (!isTwitch()) showPageBanner("YouTube player not found");
      return;
    }

    positionPlayer(player);
    bindOverlay(createOverlayRoot(player));
    video.addEventListener("seeked", handleSeeked);
    video.addEventListener("play", handleSeeked);
    resetForVideo(getMediaId());
    if (!isConsumer) admin.noteTracks();
  };

  const handleNavigate = () => {
    const nextVideo = findVideo();
    if (nextVideo && nextVideo !== video) {
      attachVideo(nextVideo);
    } else {
      resetForVideo(getMediaId());
    }
    forceNext = true;
  };

  const handleKeyDown = (event) => {
    if (isConsumer) return;
    admin.onKey(event);
  };

  worker.onmessage = (event) => {
    busy = false;
    const message = event.data;
    if (message.type === "error") {
      pendingCorrect = false;
      identifyBusy.clear();
      lastIdentifyAt.clear();
      showPageBanner(message.error);
      return;
    }
    if (message.type !== "tracks" || !root) return;
    if (!cardsOn) return;
    if ((admin.pickerOpen() || pendingCorrect) && (message.source === "frame" || message.source === "identify")) {
      return;
    }
    if (message.source === "correctTrack") pendingCorrect = false;
    if (message.source === "identify") identifyBusy.clear();
    if (message.source === "frame" && !hoveringVideo) return;
    latestTracks = message.tracks || [];
    renderTracks(root, latestTracks);
    updatePointerCard();
    if (isConsumer) {
      syncConsumerLoading();
      return;
    }
    admin.noteTracks();
  };

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (isConsumer) return false;
    if (admin.onRuntimeMessage(message, sendResponse)) return true;
    return false;
  });

  const stored = await chrome.storage.local.get([STORAGE_ENABLED, STORAGE_SHOW_QUICK_OVERLAY]);
  extensionOn = isConsumer ? stored[STORAGE_ENABLED] !== false : stored[STORAGE_ENABLED] === true;
  cardsOn = isConsumer ? false : extensionOn;
  showQuickOverlay = stored[STORAGE_SHOW_QUICK_OVERLAY] !== false;
  chrome.storage.onChanged.addListener((changes, area) => {
    if (area !== "local") return;
    if (!isConsumer) admin.onStorage(changes);
    if (changes[STORAGE_ENABLED]) {
      if (isConsumer) {
        extensionOn = changes[STORAGE_ENABLED].newValue === true;
        if (!extensionOn) setCardsOn(false, false);
        else syncQuickButton();
      } else {
        setCardsOn(changes[STORAGE_ENABLED].newValue === true);
      }
    }
    if (changes[STORAGE_SHOW_QUICK_OVERLAY]) {
      showQuickOverlay = changes[STORAGE_SHOW_QUICK_OVERLAY].newValue !== false;
      syncQuickButton();
    }
    if (isConsumer && changes["fow.indexStatus"]) {
      const next = changes["fow.indexStatus"].newValue;
      indexPhase = next?.phase || "idle";
      indexDetail = next?.detail || "";
      syncConsumerLoading();
    }
  });

  if (isConsumer && !extensionOn) setIndexStatus("idle");
  const nextVideo = await waitForVideo();
  attachVideo(nextVideo);
  if (!isConsumer) {
    await admin.refreshDataset();
    if (cardsOn) await admin.startCatalog();
  }
  syncQuickButton();
  rafId = window.requestAnimationFrame(handleTick);
  document.addEventListener("yt-navigate-finish", handleNavigate);
  window.addEventListener("popstate", handleNavigate);
  window.addEventListener("pointermove", handlePointerMove, { passive: true });
  document.addEventListener("pointerleave", handlePointerLeavePage);
  window.addEventListener("click", handleDocClick, true);
  window.addEventListener("blur", handlePointerLeavePage);
  window.addEventListener("keydown", handleKeyDown, true);
  window.addEventListener("beforeunload", () => {
    window.cancelAnimationFrame(rafId);
    if (isConsumer) sendMessage({ type: "engineActive", active: false });
    else worker.terminate();
  });
};

start().catch((error) => {
  showPageBanner(error.message || "Failed to start");
  console.error("Lens for Force of Will", error);
});
