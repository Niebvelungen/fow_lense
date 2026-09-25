import { IMAGE_FALLBACK_BASE_URL } from "./constants.js";

const CONFIDENT_SCORE = 0.5;
const HOVER_ZOOM_WIDTH = 437;
const HOVER_ZOOM_MAX_HEIGHT = 676;
const HOVER_ZOOM_MAX_VIEW_FRACTION = 0.5;
const HOVER_ZOOM_GUTTER = 20;
const HOVER_ZOOM_RIGHT_ZONE = 0.7;
const BOX_FADE_MS = 300;

const zoomWidthForImage = (img, maxWidth, maxHeight) => {
  const nw = img?.naturalWidth || 0;
  const nh = img?.naturalHeight || 0;
  const ratio = nw > 0 && nh > 0 ? nw / nh : 63 / 88;
  let width = nw > nh ? HOVER_ZOOM_WIDTH * ratio : HOVER_ZOOM_WIDTH;
  const heightLimit = Math.min(maxHeight, HOVER_ZOOM_MAX_HEIGHT);
  if (width / ratio > heightLimit) width = heightLimit * ratio;
  return Math.max(1, Math.min(maxWidth, width));
};

const lockZoomArt = (zoom, img, maxWidth, maxHeight) => {
  const nw = img?.naturalWidth || 0;
  const nh = img?.naturalHeight || 0;
  const width = zoomWidthForImage(img, maxWidth, maxHeight);
  const heightRatio = nw > 0 && nh > 0 ? nh / nw : 88 / 63;
  zoom.style.width = `${width}px`;
  zoom.style.maxHeight = "none";
  zoom.style.setProperty("--rift-art-ratio", nw > 0 && nh > 0 ? `${nw} / ${nh}` : "63 / 88");
  zoom._riftArtWidth = width;
  zoom._riftArtHeight = width * heightRatio;
};

let showCardDetails = false;

export const setShowCardDetails = (on, root) => {
  showCardDetails = Boolean(on);
  const target = root || document.getElementById("rift-overlay-root");
  target?.classList.toggle("show-details", showCardDetails);
};

export const createOverlayRoot = (player) => {
  const stale = player.querySelector(".html5-video-container #rift-overlay-root");
  if (stale) stale.remove();

  const existing = player.querySelector(":scope > #rift-overlay-root");
  if (existing) return existing;

  const root = document.createElement("div");
  root.id = "rift-overlay-root";
  root.setAttribute("aria-live", "polite");
  root.classList.toggle("show-details", showCardDetails);
  player.appendChild(root);
  return root;
};

export const setOverlayFrame = (root, rect) => {
  root.style.left = `${rect.left}px`;
  root.style.top = `${rect.top}px`;
  root.style.width = `${rect.width}px`;
  root.style.height = `${rect.height}px`;
};

export const renderStatus = (root, text) => {
  if (!root) return;
  let status = root.querySelector(".rift-status");
  if (!status) {
    status = document.createElement("div");
    status.className = "rift-status";
    status.setAttribute("role", "status");
    root.appendChild(status);
  }
  status.textContent = text;
};

const handleCardFocus = (event) => {
  const card = event.currentTarget;
  const root = card.closest("#rift-overlay-root");
  if (root?.querySelector(".rift-correct-pick:not([hidden])")) return;
  if (!card.dataset.imageUrl && !card.dataset.top) return;
  showZoom(card);
};

const handleCardBlur = (event) => {
  hideZoom(event.currentTarget);
};

const handleCardKeyDown = (event) => {
  if (event.key === "Escape") {
    event.currentTarget.blur();
  }
};

const zoomArtHtml =
  '<div class="rift-zoom-art"><img class="rift-zoom-img" alt="" /></div>' +
  '<p class="rift-zoom-note" hidden>LOW CONFIDENCE</p>' +
  '<p class="rift-zoom-name"></p>' +
  '<ol class="rift-zoom-alts"></ol>';

const whenImageReady = (img) => {
  if (!img?.src) return Promise.resolve();
  const decode = () => (img.decode ? img.decode().catch(() => {}) : Promise.resolve());
  if (img.complete && img.naturalWidth > 0) return decode();
  return new Promise((resolve) => {
    const done = () => {
      img.removeEventListener("load", done);
      img.removeEventListener("error", done);
      decode().then(resolve);
    };
    img.addEventListener("load", done);
    img.addEventListener("error", done);
  });
};

const cardZoomMeta = (cardEl) => {
  let rows = [];
  try {
    rows = JSON.parse(cardEl.dataset.top || "[]");
  } catch {
    rows = [];
  }
  return {
    imageUrl: cardEl.dataset.imageUrl || rows[0]?.imageUrl || "",
    trackId: cardEl.dataset.trackId || "",
    name: cardEl.dataset.name || rows[0]?.name || "",
    detectScore: cardEl.dataset.detectScore,
    idScore: cardEl.dataset.idScore,
    rows,
  };
};

const lowConfidence = (findScore, idScore) => {
  const find = Number(findScore);
  const id = Number(idScore);
  if (Number.isFinite(find) && find < CONFIDENT_SCORE) return true;
  if (Number.isFinite(id) && id < CONFIDENT_SCORE) return true;
  return false;
};

const fillZoomMeta = (zoom, meta) => {
  const img = zoom.querySelector("img");
  const name = zoom.querySelector(".rift-zoom-name");
  const alts = zoom.querySelector(".rift-zoom-alts");
  if (img) img.alt = meta.name;
  if (name) name.textContent = meta.name;
  const note = zoom.querySelector(".rift-zoom-note");
  if (note) note.hidden = !lowConfidence(meta.detectScore, meta.idScore);
  if (alts) {
    alts.innerHTML = meta.rows
      .map((row) => {
        const pct = Math.max(0, Math.round((1 - Number(row.dist || 1)) * 100));
        return `<li>${row.name} · ${pct}% · ${row.turn}°</li>`;
      })
      .join("");
  }
};

const revealZoom = (zoom) => {
  if (!zoom.isConnected || zoom.classList.contains("is-leaving")) return;
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      if (zoom.isConnected && !zoom.classList.contains("is-leaving")) {
        zoom.classList.add("is-visible");
      }
    });
  });
};

const dismissZoom = (zoom) => {
  if (!zoom || zoom.classList.contains("is-leaving")) return;
  zoom.classList.remove("is-live", "is-visible");
  zoom.classList.add("is-leaving");
  window.clearTimeout(zoom._riftHide);
  zoom._riftHide = window.setTimeout(() => zoom.remove(), BOX_FADE_MS);
};

export const hideHoverZoom = (root) => {
  if (!root) return;
  for (const zoom of root.querySelectorAll(".rift-zoom")) {
    dismissZoom(zoom);
  }
};

const createZoom = (root) => {
  const zoom = document.createElement("div");
  zoom.className = "rift-zoom";
  zoom.innerHTML = zoomArtHtml;
  root.appendChild(zoom);
  return zoom;
};

const showZoom = (cardEl) => {
  const root = cardEl.closest("#rift-overlay-root");
  if (!root) return;

  const meta = cardZoomMeta(cardEl);
  const live = root.querySelector(".rift-zoom.is-live");
  if (live && live._riftTargetUrl === meta.imageUrl && live._riftTargetTrack === meta.trackId) {
    fillZoomMeta(live, meta);
    if (meta.imageUrl) placeHoverZoom(root, live, cardEl, live.querySelector("img"));
    return;
  }

  if (!meta.imageUrl) {
    hideHoverZoom(root);
    return;
  }

  for (const zoom of root.querySelectorAll(".rift-zoom.is-live")) {
    dismissZoom(zoom);
  }

  const zoom = createZoom(root);
  zoom.classList.add("is-live");
  zoom._riftTargetUrl = meta.imageUrl;
  zoom._riftTargetTrack = meta.trackId;
  fillZoomMeta(zoom, meta);
  const img = zoom.querySelector("img");
  img.onerror = () => {
    const file = meta.imageUrl.split("/").pop();
    const fallback = IMAGE_FALLBACK_BASE_URL + file;
    if (!file || img.src === fallback || img.src.startsWith(IMAGE_FALLBACK_BASE_URL)) return;
    img.onerror = null;
    img.src = fallback;
  };
  img.src = meta.imageUrl;
  whenImageReady(img).then(() => {
    if (!zoom.isConnected || !zoom.classList.contains("is-live")) return;
    placeHoverZoom(root, zoom, cardEl, img);
    revealZoom(zoom);
  });
};

const clampRange = (value, min, max) => {
  if (max < min) return (min + max) / 2;
  return Math.max(min, Math.min(max, value));
};

const placeHoverZoom = (root, zoom, cardEl, sizeImg) => {
  const rootRect = root.getBoundingClientRect();
  const cardRect = cardEl.getBoundingClientRect();
  if (rootRect.width < 1 || rootRect.height < 1) return;

  const gutter = HOVER_ZOOM_GUTTER;
  const visibleWidth = Math.min(rootRect.right, window.innerWidth) - Math.max(rootRect.left, 0);
  const visibleHeight = Math.min(rootRect.bottom, window.innerHeight) - Math.max(rootRect.top, 0);
  const viewCap = Math.min(window.innerWidth, rootRect.width) * HOVER_ZOOM_MAX_VIEW_FRACTION;
  const maxZoomWidth = Math.max(1, Math.min(visibleWidth - gutter * 2, viewCap));
  const maxZoomHeight = Math.max(1, visibleHeight - gutter * 2);
  const artImg = sizeImg || zoom.querySelector("img");
  if (artImg?.naturalWidth) {
    lockZoomArt(zoom, artImg, maxZoomWidth, maxZoomHeight);
  } else {
    lockZoomArt(zoom, null, maxZoomWidth, maxZoomHeight);
  }
  const zoomWidth = zoom._riftArtWidth || zoom.offsetWidth || HOVER_ZOOM_WIDTH;
  const zoomHeight = zoom.offsetHeight || zoom._riftArtHeight || HOVER_ZOOM_MAX_HEIGHT;

  const minX = Math.max(rootRect.left, 0) + gutter;
  const maxX = Math.min(rootRect.right, window.innerWidth) - zoomWidth - gutter;
  const minY = Math.max(rootRect.top, 0) + gutter;
  const maxY = Math.min(rootRect.bottom, window.innerHeight) - zoomHeight - gutter;

  const cardCenter = (cardRect.left + cardRect.width / 2 - rootRect.left) / rootRect.width;
  const preferLeft = cardCenter >= HOVER_ZOOM_RIGHT_ZONE;
  const rightOfCard = cardRect.right + gutter;
  const leftOfCard = cardRect.left - zoomWidth - gutter;
  const fits = (viewLeft) => viewLeft >= minX && viewLeft <= maxX;

  let viewLeft = preferLeft ? leftOfCard : rightOfCard;
  if (!fits(viewLeft)) {
    const other = preferLeft ? rightOfCard : leftOfCard;
    if (fits(other)) viewLeft = other;
  }

  const viewTop = cardRect.top + (cardRect.height - zoomHeight) / 2;

  zoom.style.left = `${clampRange(viewLeft, minX, maxX) - rootRect.left}px`;
  zoom.style.top = `${clampRange(viewTop, minY, maxY) - rootRect.top}px`;
};

const hideZoom = (cardEl) => {
  hideHoverZoom(cardEl.closest("#rift-overlay-root"));
};

export const setPointerTrack = (root, trackId) => {
  if (!root) return null;
  let matched = null;
  const id = Number(trackId);
  for (const card of root.querySelectorAll(".rift-card")) {
    const on = Number(card.dataset.trackId) === id;
    card.classList.toggle("is-pointer", on);
    if (on) matched = card;
  }
  refreshHoverZoom(root);
  return matched;
};

export const bindTrackIdentify = (root, { onHover, onCorrect } = {}) => {
  if (root.dataset.identifyBound === "1") return;
  root.dataset.identifyBound = "1";
  root._riftOnHover = onHover;
  root._riftOnCorrect = onCorrect;
};

export const refreshHoverZoom = (root) => {
  if (root.querySelector(".rift-correct-pick:not([hidden])")) return;
  const focused = root.querySelector(".rift-card.is-pointer, .rift-card:focus");
  if (focused?.dataset.imageUrl || focused?.dataset.top) {
    showZoom(focused);
    return;
  }
  hideHoverZoom(root);
};

export const renderTracks = (root, tracks) => {
  const used = new Set();

  for (const track of tracks) {
    const id = `rift-card-${track.id}`;
    used.add(id);
    let card = root.querySelector(`#${id}`);
    const isNew = !card;
    if (!card) {
      card = document.createElement("button");
      card.id = id;
      card.type = "button";
      card.className = "rift-card";
      card.innerHTML = '<img class="rift-card-img" alt="" /><span class="rift-card-label"></span>';
      card.addEventListener("mouseenter", handleCardFocus);
      card.addEventListener("mouseleave", handleCardBlur);
      card.addEventListener("focus", handleCardFocus);
      card.addEventListener("blur", handleCardBlur);
      card.addEventListener("keydown", handleCardKeyDown);
      root.appendChild(card);
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          if (card.isConnected && card.dataset.leaving !== "1") {
            card.classList.add("is-visible", "can-move");
          }
        });
      });
    }

    const named = Boolean(track.cardId);
    const label = track.label || track.name || "card";
    const zoomName = named ? track.name : track.guessName ? `maybe ${track.guessName}` : label;
    const zoomUrl = named ? track.imageUrl : track.guessUrl || "";
    card.dataset.leaving = "";
    card.dataset.trackId = String(track.id);
    card.dataset.correctionId = track.correctionId || "";
    card.dataset.name = zoomName;
    card.dataset.imageUrl = zoomUrl;
    card.dataset.detectScore = track.detectScore == null ? "" : String(track.detectScore);
    card.dataset.idScore = track.idScore == null ? "" : String(track.idScore);
    card.dataset.top = JSON.stringify(track.top || []);
    card.classList.toggle("is-unknown", !named);
    card.classList.toggle("is-corrected", track.idSource === "user");
    if (!isNew) card.classList.add("is-visible", "can-move");
    card.setAttribute("aria-label", named ? `${track.name}, Force of Will card` : `Unidentified card, ${label}`);
    card.style.left = `${track.x * 100}%`;
    card.style.top = `${track.y * 100}%`;
    card.style.width = `${track.w * 100}%`;
    card.style.height = `${track.h * 100}%`;

    const img = card.querySelector("img");
    const tag = card.querySelector(".rift-card-label");
    img.removeAttribute("src");
    img.alt = "";
    tag.textContent = "";
  }

  for (const card of root.querySelectorAll(".rift-card")) {
    if (used.has(card.id)) continue;
    if (card.dataset.leaving === "1") continue;
    card.dataset.leaving = "1";
    card.classList.remove("is-visible");
    window.setTimeout(() => {
      if (card.dataset.leaving === "1") card.remove();
    }, BOX_FADE_MS);
  }

  refreshHoverZoom(root);
};
