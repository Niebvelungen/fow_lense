// Force of Will card catalog. The packaged data/cards.json is the only source:
// a flat list of { id, name, orientation, imageUrl, image, set, tags } built by
// tools/build_arena_json.py from the fowsim database dump.

export const resolveImageUrl = (url) => {
  const value = String(url || "").trim();
  if (!value) return "";
  if (/^(https?:|data:|blob:|chrome-extension:)/i.test(value)) return value;
  if (typeof chrome !== "undefined" && chrome.runtime?.getURL) {
    return chrome.runtime.getURL(value.replace(/^\//, ""));
  }
  return value;
};

const uniqueTags = (values) => {
  const tags = [];
  const seen = new Set();
  for (const value of values || []) {
    const tag = String(value || "").trim().toLowerCase();
    if (!tag || seen.has(tag)) continue;
    seen.add(tag);
    tags.push(tag);
  }
  return tags;
};

export const normalizeCard = (item) => {
  if (!item?.id) return null;
  return {
    id: String(item.id),
    name: item.name || String(item.id),
    orientation: item.orientation || "portrait",
    imageUrl: resolveImageUrl(item.imageUrl),
    image: item.image || "",
    set: item.set || "",
    tags: uniqueTags(item.tags),
  };
};

// Human readable print code, e.g. "EDL-069*" stays as is; FoW ids are already readable.
export const printCode = (id) => String(id || "").toUpperCase();

export const safeCardFileId = (id) => String(id || "unknown").replace(/[<>:"/\\|?*]/g, "_");

export const mergeCards = (...lists) => {
  const byId = new Map();
  for (const list of lists) {
    for (const item of list || []) {
      const card = normalizeCard(item);
      if (!card) continue;
      const prev = byId.get(card.id);
      byId.set(
        card.id,
        prev ? { ...prev, ...card, tags: uniqueTags([...(prev.tags || []), ...card.tags]) } : card
      );
    }
  }
  return [...byId.values()].sort((a, b) => a.name.localeCompare(b.name));
};

export const fetchPackagedCatalog = async () => {
  const response = await fetch(chrome.runtime.getURL("data/cards.json"));
  if (!response.ok) throw new Error("Packaged catalog missing");
  return mergeCards(await response.json());
};

export const fetchAllCards = fetchPackagedCatalog;
