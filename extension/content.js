const TICK_MS = 1000;
const HEARTBEAT_MS = 5000;
const DRIFT_SECONDS = 2;
const VIDEO_SELECTORS = ["#movie_player video", "#shorts-player video"];
const TITLE_SUFFIX = /\s+(?:\|\s+YouTube Music|-\s+YouTube)$/;
const TITLE_COUNTER = /^\(\d+\)\s+/;
const ARTWORK_VIDEO_ID = /\/vi(?:_webp)?\/([\w-]{11})\//;
const ARTIST_SELECTORS = ["ytd-watch-metadata ytd-channel-name a", "ytmusic-player-bar .byline a"];
const ALBUM_SELECTOR = 'ytmusic-player-bar .byline a[href*="browse/MPRE"]';

let lastSent = null;
let lastSentAt = 0;
let reportedGone = true;

function findVideo() {
  for (const selector of VIDEO_SELECTORS) {
    const video = document.querySelector(selector);
    if (video) return video;
  }
  return null;
}

function titleFromDocument() {
  return document.title.replace(TITLE_SUFFIX, "").replace(TITLE_COUNTER, "").trim();
}

function artistFromPage() {
  for (const selector of ARTIST_SELECTORS) {
    const element = document.querySelector(selector);
    if (element && element.textContent.trim()) return element.textContent.trim();
  }
  return "";
}

function albumFromPage() {
  const element = document.querySelector(ALBUM_SELECTOR);
  return element ? element.textContent.trim() : "";
}

function largestArtwork(artwork) {
  let best = null;
  let bestSize = -1;
  for (const image of artwork || []) {
    const size = parseInt((image.sizes || "0").split("x")[0], 10) || 0;
    if (size > bestSize) {
      best = image.src;
      bestSize = size;
    }
  }
  return best;
}

function findVideoId(artwork) {
  const url = new URL(location.href);
  const fromQuery = url.searchParams.get("v");
  if (fromQuery) return fromQuery;
  const shorts = url.pathname.match(/^\/shorts\/([\w-]{11})/);
  if (shorts) return shorts[1];
  const fromArtwork = (artwork || "").match(ARTWORK_VIDEO_ID);
  return fromArtwork ? fromArtwork[1] : null;
}

function snapshot() {
  const video = findVideo();
  if (!video || !(video.duration > 0)) return null;
  const meta = navigator.mediaSession && navigator.mediaSession.metadata;
  const title = ((meta && meta.title) || titleFromDocument()).trim();
  if (!title) return null;
  const artwork = meta ? largestArtwork(meta.artwork) : null;
  const player = document.querySelector("#movie_player");
  return {
    title,
    artist: ((meta && meta.artist) || artistFromPage()).trim(),
    album: (meta && meta.album) || albumFromPage(),
    artwork,
    videoId: findVideoId(artwork),
    host: location.hostname,
    position: video.currentTime,
    duration: video.duration,
    paused: video.paused || video.ended,
    ad: Boolean(player && player.classList.contains("ad-showing")),
    ts: Date.now(),
  };
}

function hasChanged(state, now) {
  if (!lastSent) return true;
  for (const key of ["title", "artist", "album", "artwork", "videoId", "paused", "ad"]) {
    if (state[key] !== lastSent[key]) return true;
  }
  const elapsed = lastSent.paused ? 0 : (now - lastSentAt) / 1000;
  return Math.abs(state.position - (lastSent.position + elapsed)) > DRIFT_SECONDS;
}

function send(payload) {
  try {
    chrome.runtime.sendMessage(payload).catch(() => {});
  } catch {
    clearInterval(timer);
  }
}

function reportGone() {
  if (reportedGone) return;
  reportedGone = true;
  lastSent = null;
  send({ gone: true });
}

function tick() {
  const state = snapshot();
  if (!state) {
    reportGone();
    return;
  }
  const now = Date.now();
  if (hasChanged(state, now) || now - lastSentAt >= HEARTBEAT_MS) {
    lastSent = state;
    lastSentAt = now;
    reportedGone = false;
    send(state);
  }
}

const timer = setInterval(tick, TICK_MS);

for (const name of ["play", "pause", "seeked", "loadedmetadata", "ended"]) {
  document.addEventListener(name, tick, true);
}
document.addEventListener("yt-navigate-finish", tick);
window.addEventListener("pageshow", tick);
window.addEventListener("pagehide", reportGone);

tick();
