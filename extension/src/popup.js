const STORAGE_ENABLED = "fow.enabled";
const STORAGE_INDEX_STATUS = "fow.indexStatus";

const powerBtn = document.getElementById("power");
const powerState = powerBtn.querySelector(".power-state");
const extrasEl = document.getElementById("extras");
const progressEl = document.getElementById("progress");
const progressText = document.getElementById("progress-text");

const renderPower = (on) => {
  const enabled = Boolean(on);
  powerBtn.setAttribute("aria-pressed", enabled ? "true" : "false");
  powerBtn.setAttribute("aria-label", enabled ? "Disable overlay" : "Enable overlay");
  powerState.textContent = enabled ? "Enabled" : "Disabled";
  extrasEl.hidden = !enabled;
};

let overlayOn = false;
let indexStatus = null;

const renderProgress = (status) => {
  const phase = status?.phase || "idle";
  const detail = String(status?.detail || "").trim();
  const show = overlayOn && (phase === "loading" || phase === "error");
  const showDetail = show && Boolean(detail);
  progressEl.hidden = !show;
  progressEl.classList.toggle("is-loading", show && phase !== "error");
  progressEl.classList.toggle("is-error", show && phase === "error");
  progressText.hidden = !showDetail;
  progressText.textContent = showDetail ? detail : "";
};

const load = async () => {
  const local = await chrome.storage.local.get([STORAGE_ENABLED, STORAGE_INDEX_STATUS]);
  overlayOn = local[STORAGE_ENABLED] !== false;
  indexStatus = local[STORAGE_INDEX_STATUS] || null;
  renderPower(overlayOn);
  renderProgress(indexStatus);
};

powerBtn.addEventListener("click", () => {
  const next = powerBtn.getAttribute("aria-pressed") !== "true";
  overlayOn = next;
  renderPower(next);
  renderProgress(indexStatus);
  chrome.storage.local.set({ [STORAGE_ENABLED]: next }).catch(() => {});
});

chrome.storage.onChanged.addListener((changes, area) => {
  if (area !== "local") return;
  if (changes[STORAGE_ENABLED]) {
    overlayOn = changes[STORAGE_ENABLED].newValue !== false;
    renderPower(overlayOn);
    renderProgress(indexStatus);
  }
  if (changes[STORAGE_INDEX_STATUS]) {
    indexStatus = changes[STORAGE_INDEX_STATUS].newValue || null;
    renderProgress(indexStatus);
  }
});

load();
