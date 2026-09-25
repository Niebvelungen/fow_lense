const TWITCH_HOST = /(^|\.)twitch\.tv$/i;
const TWITCH_SKIP = new Set([
  "activate",
  "clips",
  "dashboard",
  "directory",
  "downloads",
  "drops",
  "friends",
  "inventory",
  "jobs",
  "login",
  "messages",
  "moderator",
  "p",
  "payments",
  "popout",
  "prime",
  "search",
  "settings",
  "signup",
  "store",
  "subscriptions",
  "turbo",
  "videos",
  "wallet",
]);

export const isTwitch = () => TWITCH_HOST.test(location.hostname);

const twitchChannel = (name) => {
  const channel = String(name || "").toLowerCase();
  if (!channel || TWITCH_SKIP.has(channel)) return null;
  return `live:${channel}`;
};

const twitchMediaId = () => {
  const parts = location.pathname.split("/").filter(Boolean);
  if (parts[0] === "videos" && /^\d+$/.test(parts[1] || "")) return `video:${parts[1]}`;
  if (parts[0] === "popout" && parts[1] && parts[2] !== "chat") return twitchChannel(parts[1]);
  if (!parts.length || parts[1] === "clip") return null;
  return twitchChannel(parts[0]);
};

export const getYoutubeVideoId = () => {
  const url = new URL(location.href);
  if (url.pathname === "/watch") return url.searchParams.get("v");
  return null;
};

export const getMediaId = () => (isTwitch() ? twitchMediaId() : getYoutubeVideoId());

const largestTwitchPlayer = () => {
  let best = null;
  let bestArea = 0;
  for (const node of document.querySelectorAll('[data-a-target="video-player"]')) {
    if (!node.querySelector("video")) continue;
    const rect = node.getBoundingClientRect();
    const area = rect.width * rect.height;
    if (area > bestArea) {
      best = node;
      bestArea = area;
    }
  }
  if (best) return best;

  for (const video of document.querySelectorAll("video")) {
    const rect = video.getBoundingClientRect();
    const area = rect.width * rect.height;
    if (area < 240 * 135 || area <= bestArea) continue;
    best = video.parentElement;
    bestArea = area;
  }
  return best;
};

export const findPlayer = () => {
  if (!isTwitch()) return document.querySelector("#movie_player");
  return largestTwitchPlayer();
};

export const findVideo = () => {
  if (isTwitch()) {
    if (!twitchMediaId()) return null;
    return findPlayer()?.querySelector("video") || null;
  }
  return document.querySelector("video.html5-main-video") || document.querySelector("#movie_player video");
};

export const positionPlayer = (player) => {
  if (!isTwitch() || !player) return;
  if (getComputedStyle(player).position === "static") player.style.position = "relative";
};

export const waitForVideo = () => {
  return new Promise((resolve) => {
    const existing = findVideo();
    if (existing) {
      resolve(existing);
      return;
    }

    const timer = window.setInterval(() => {
      const video = findVideo();
      if (!video) return;
      window.clearInterval(timer);
      resolve(video);
    }, 400);
  });
};

export const getVideoRectInPlayer = (video, player) => {
  const elem = video.getBoundingClientRect();
  const playerRect = player.getBoundingClientRect();
  let left = elem.left;
  let top = elem.top;
  let width = elem.width;
  let height = elem.height;

  if (video.videoWidth > 0 && video.videoHeight > 0 && width > 0 && height > 0) {
    const mediaRatio = video.videoWidth / video.videoHeight;
    const elemRatio = width / height;
    if (elemRatio > mediaRatio + 0.02) {
      width = height * mediaRatio;
      left = elem.left + (elem.width - width) / 2;
    } else if (mediaRatio > elemRatio + 0.02) {
      height = width / mediaRatio;
      top = elem.top + (elem.height - height) / 2;
    }
  }

  return {
    left: left - playerRect.left,
    top: top - playerRect.top,
    width,
    height,
  };
};
