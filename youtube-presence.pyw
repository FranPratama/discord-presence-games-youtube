import re
import sys
import time
import asyncio
import logging
import urllib.request
import urllib.parse
import json
from collections import deque
from difflib import SequenceMatcher
from functools import lru_cache, partial
from logging.handlers import RotatingFileHandler
from pathlib import Path
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from pypresence import AioPresence, exceptions
from pypresence.types import ActivityType
import pygetwindow as gw
from ytmusicapi import YTMusic

import winrt.windows.foundation

from winrt.windows.media.control import \
    GlobalSystemMediaTransportControlsSessionManager, \
    GlobalSystemMediaTransportControlsSessionPlaybackStatus

LOG_PATH = Path(__file__).with_name('youtube-presence.log')

_file_handler = RotatingFileHandler(LOG_PATH, maxBytes=1_000_000, backupCount=3, encoding='utf-8')
_file_handler.setLevel(logging.DEBUG)
_log_handlers = [_file_handler]
if sys.stderr:
    _console_handler = logging.StreamHandler()
    _console_handler.setLevel(logging.INFO)
    _log_handlers.append(_console_handler)

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=_log_handlers
)
for _noisy_logger in ("urllib3", "asyncio"):
    logging.getLogger(_noisy_logger).setLevel(logging.WARNING)

RECONNECT_INTERVAL = 3
HEARTBEAT_INTERVAL = 15
EVENT_DEBOUNCE = 0.25
BLANK_GRACE = 4
RATE_LIMIT_COUNT = 4
RATE_LIMIT_WINDOW = 20
AD_RECHECK_INTERVAL = 1
AD_MAX_DURATION = 65
CONFIRM_DELAY = 15
SCRUB_THRESHOLD = 5
API_TIMEOUT = 5
YTMUSIC_TIMEOUT = 6
LOOKUP_DEADLINE = 1.0
MATCH_THRESHOLD = 0.6
DISCORD_TEXT_LIMIT = 128
MEDIA_CACHE_SIZE = 256
YOUTUBE_CANDIDATES = 10

PLACEHOLDER_TITLES = {"A site is playing media"}
IGNORED_APPS = ("spotify", "vlc", "foobar", "musicbee", "aimp", "zunemusic", "itunes", "applemusic")

CLIENT_ID = '1478129019701432400'

YOUTUBE_MUSIC_LOGO = "https://img.icons8.com/color/512/youtube-music.png"
YOUTUBE_LOGO = "https://img.icons8.com/color/512/youtube-play.png"
PAUSED_ICON = "https://img.icons8.com/ios-filled/100/FF0000/circled-pause.png"
PLAYING_ICON = "https://img.icons8.com/ios-filled/100/FF0000/circled-play.png"

def _build_ytmusic_session():
    session = requests.Session()
    adapter = HTTPAdapter(max_retries=Retry(total=2, allowed_methods=None, backoff_factor=0))
    session.mount("https://", adapter)
    session.request = partial(session.request, timeout=YTMUSIC_TIMEOUT)
    return session

_ytmusic = YTMusic(requests_session=_build_ytmusic_session())
_http = _build_ytmusic_session()

YOUTUBE_VIDEO_PATTERN = re.compile(
    r'"videoRenderer":\{"videoId":"([\w-]{11})".*?"title":\{"runs":\[\{"text":"((?:[^"\\]|\\.)*)"'
)

def _normalize(text):
    text = (text or "").lower()
    text = re.sub(r"[\(\[].*?[\)\]]", " ", text)
    text = re.sub(r"\s*-\s*topic\s*$", " ", text)
    text = re.sub(r"vevo\s*$", " ", text)
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())

def _contains_words(haystack, needle):
    return bool(needle) and f" {needle} " in f" {haystack} "

def _is_match(title, artist, found_title, found_artists):
    norm_title = _normalize(title)
    norm_found = _normalize(found_title)
    if not norm_found:
        return False

    title_hit = (
        _contains_words(norm_title, norm_found)
        or SequenceMatcher(None, norm_title, norm_found).ratio() >= MATCH_THRESHOLD
    )

    compact_artist = _normalize(artist).replace(" ", "")
    artist_hit = False
    for name in found_artists:
        norm_name = _normalize(name)
        compact_name = norm_name.replace(" ", "")
        if not compact_name:
            continue
        if (
            (compact_artist and (compact_name in compact_artist or compact_artist in compact_name))
            or _contains_words(norm_title, norm_name)
        ):
            artist_hit = True
            break

    return title_hit and artist_hit

def _upscale_thumbnail(url):
    return re.sub(r"=w\d+-h\d+", "=w544-h544", url)

def _fetch_from_ytmusic(title, artist):
    try:
        query = f"{title} {artist}".strip()
        results = _ytmusic.search(query, filter="songs", limit=1)

        if results:
            song = results[0]
            found_artists = [a.get("name", "") for a in song.get("artists") or []]
            if not _is_match(title, artist, song.get("title", ""), found_artists):
                logging.info(f"YT Music result rejected: {song.get('title')} by {', '.join(found_artists)}")
                return None

            thumbnails = song.get("thumbnails", [])
            art_url = _upscale_thumbnail(thumbnails[-1]["url"]) if thumbnails else YOUTUBE_MUSIC_LOGO

            video_id = song.get("videoId", "")
            if video_id:
                button_url = f"https://music.youtube.com/watch?v={video_id}"
            else:
                encoded_query = urllib.parse.quote(query)
                button_url = f"https://music.youtube.com/search?q={encoded_query}"

            logging.info(f"🎵 YT Music match: {song.get('title', title)}")
            return (art_url, "YouTube Music", button_url)
    except Exception as e:
        logging.warning(f"YT Music API lookup failed: {e}")

    return None

def _fetch_from_itunes(title, artist):
    try:
        query = urllib.parse.quote(f"{title} {artist}")
        url = f"https://itunes.apple.com/search?term={query}&entity=song&limit=1"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=API_TIMEOUT) as response:
            data = json.loads(response.read())
            if data['resultCount'] > 0:
                track = data['results'][0]
                if not _is_match(title, artist, track.get('trackName', ''), [track.get('artistName', '')]):
                    logging.info(f"iTunes result rejected: {track.get('trackName')} by {track.get('artistName')}")
                    return None
                art = track['artworkUrl100'].replace('100x100bb', '512x512bb')
                song_url = f"https://music.youtube.com/search?q={query}"
                logging.info(f"🎵 iTunes fallback match: {title}")
                return (art, "YouTube Music", song_url)
    except Exception as e:
        logging.warning(f"iTunes API lookup failed: {e}")

    return None

def _fetch_from_youtube(title):
    try:
        url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(title)}"
        response = _http.get(url, headers={"Accept-Language": "en"})
        response.raise_for_status()
        norm_title = _normalize(title)
        best_score, video_id, found_title = 0.0, None, None
        for index, match in enumerate(YOUTUBE_VIDEO_PATTERN.finditer(response.text)):
            if index >= YOUTUBE_CANDIDATES:
                break
            candidate_title = json.loads(f'"{match.group(2)}"')
            norm_candidate = _normalize(candidate_title)
            if not norm_candidate:
                continue
            if _contains_words(norm_candidate, norm_title):
                score = 1.0
            else:
                score = SequenceMatcher(None, norm_title, norm_candidate).ratio()
            if score > best_score:
                best_score, video_id, found_title = score, match.group(1), candidate_title
            if score >= 1.0:
                break

        if not video_id:
            return None
        if best_score < MATCH_THRESHOLD:
            logging.info(f"YouTube result rejected: {found_title}")
            return None

        logging.info(f"📺 YouTube video match: {found_title}")
        return (
            f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
            "YouTube",
            f"https://www.youtube.com/watch?v={video_id}"
        )
    except Exception as e:
        logging.warning(f"YouTube video lookup failed: {e}")

    return None

YOUTUBE_TAB_SUFFIX = re.compile(r"\s+(?:\|\s+YouTube Music|-\s+YouTube)(?:\s+-\s+.*)?$")
YOUTUBE_TAB_COUNTER = re.compile(r"^\(\d+\)\s+")
YOUTUBE_MUSIC_GENERIC_TAB = re.compile(r"^(?:\(\d+\)\s+)?YouTube Music(?:\s+-\s+.*)?$")

def _youtube_windows():
    try:
        titles = gw.getAllTitles()
    except Exception:
        return [], False
    tabs = []
    has_generic_tab = False
    for window_title in titles:
        if YOUTUBE_MUSIC_GENERIC_TAB.match(window_title):
            has_generic_tab = True
            continue
        if not YOUTUBE_TAB_SUFFIX.search(window_title):
            continue
        content = YOUTUBE_TAB_COUNTER.sub("", YOUTUBE_TAB_SUFFIX.sub("", window_title)).strip()
        if content and content.lower() not in ("youtube", "youtube music"):
            tabs.append(content)
    return tabs, has_generic_tab

def is_probably_ad(media):
    tabs, has_generic_tab = _youtube_windows()
    if not tabs:
        return has_generic_tab and 0 < media["duration"] <= AD_MAX_DURATION
    norm_title = _normalize(media["title"])
    for tab in tabs:
        norm_tab = _normalize(tab)
        if (
            _contains_words(norm_tab, norm_title)
            or _contains_words(norm_title, norm_tab)
            or SequenceMatcher(None, norm_title, norm_tab).ratio() >= MATCH_THRESHOLD
        ):
            return False
    return True

def youtube_fallback(title):
    video_query = urllib.parse.quote(f"{title}")
    video_url = f"https://www.youtube.com/results?search_query={video_query}"
    return (YOUTUBE_LOGO, "YouTube", video_url)

@lru_cache(maxsize=MEDIA_CACHE_SIZE)
def fetch_media_data(title, artist):
    result = _fetch_from_ytmusic(title, artist)

    if not result:
        result = _fetch_from_itunes(title, artist)

    if not result:
        result = _fetch_from_youtube(title)

    if not result:
        result = youtube_fallback(title)

    return result

def _format_clock(seconds):
    minutes, secs = divmod(int(max(seconds, 0)), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"

def _paused_state(media):
    state = f"⏸ Paused at {_format_clock(media['position'])}"
    if media["duration"] > 0:
        state += f" / {_format_clock(media['duration'])}"
    if media["artist"]:
        state += f" · {media['artist']}"
    return state

def _clip(text):
    text = (text or "").strip()
    if len(text) > DISCORD_TEXT_LIMIT:
        text = text[:DISCORD_TEXT_LIMIT - 1] + "…"
    return text.ljust(2, "​")

def _is_ignored(session):
    app_id = (session.source_app_user_model_id or "").lower()
    return any(name in app_id for name in IGNORED_APPS)

def _pick_session(manager):
    current = manager.get_current_session()
    if current and not _is_ignored(current):
        return current
    for session in manager.get_sessions():
        if not _is_ignored(session):
            return session
    return None

class MediaWatcher:
    def __init__(self, manager, loop, notify):
        self._manager = manager
        self._loop = loop
        self._notify = notify
        self._session_subscriptions = []
        self._on_session_event = lambda sender, args: self._wake()
        self._on_sessions_changed = lambda sender, args: self._loop.call_soon_threadsafe(self._resubscribe)
        self._manager_tokens = (
            manager.add_current_session_changed(self._on_session_event),
            manager.add_sessions_changed(self._on_sessions_changed),
        )
        self._resubscribe()

    def _wake(self):
        self._loop.call_soon_threadsafe(self._notify)

    def _unsubscribe_sessions(self):
        for session, tokens in self._session_subscriptions:
            try:
                session.remove_media_properties_changed(tokens[0])
                session.remove_playback_info_changed(tokens[1])
                session.remove_timeline_properties_changed(tokens[2])
            except Exception:
                pass
        self._session_subscriptions = []

    def _resubscribe(self):
        self._unsubscribe_sessions()
        try:
            for session in self._manager.get_sessions():
                tokens = (
                    session.add_media_properties_changed(self._on_session_event),
                    session.add_playback_info_changed(self._on_session_event),
                    session.add_timeline_properties_changed(self._on_session_event),
                )
                self._session_subscriptions.append((session, tokens))
        except Exception as e:
            logging.warning(f"Failed to subscribe to media sessions: {e}")
        self._notify()

    def close(self):
        self._unsubscribe_sessions()
        try:
            self._manager.remove_current_session_changed(self._manager_tokens[0])
            self._manager.remove_sessions_changed(self._manager_tokens[1])
        except Exception:
            pass

async def connect_discord():
    try:
        logging.info("Connecting to Discord...")
        RPC = AioPresence(CLIENT_ID)
        await RPC.connect()
        logging.info("Successfully connected to Discord!")
        return RPC
    except Exception as e:
        logging.error(f"Failed to connect to Discord: {e}")
        return None

async def get_media_info(manager):
    session = _pick_session(manager)

    if not session:
        return None

    props = await session.try_get_media_properties_async()

    playback_info = session.get_playback_info()
    status = playback_info.playback_status if playback_info else None
    is_playing = (status == GlobalSystemMediaTransportControlsSessionPlaybackStatus.PLAYING)

    timeline = session.get_timeline_properties()
    position_secs = 0
    duration_secs = 0
    reference_time = time.time()
    if timeline:
        position_secs = timeline.position.total_seconds()
        duration_secs = (timeline.end_time - timeline.start_time).total_seconds()
        last_updated = timeline.last_updated_time
        if last_updated and last_updated.year >= 2000:
            reference_time = min(last_updated.timestamp(), reference_time)

    return {
        "title": props.title,
        "artist": props.artist,
        "is_playing": is_playing,
        "position": position_secs,
        "duration": duration_secs,
        "start_time": int(reference_time - position_secs)
    }

def build_presence(media, platform, art_url, button_url, is_paused=False, start_time=None):
    state = _paused_state(media) if is_paused else (media["artist"] or "Playing Media")

    is_music = platform == "YouTube Music"
    btn_label = "Play on YouTube Music" if is_music else "Watch on YouTube"
    discord_button = [{"label": btn_label, "url": button_url}]

    end_time = None
    if start_time and media["duration"] > 0:
        end_time = int(start_time + media["duration"])

    return {
        "activity_type": ActivityType.LISTENING if is_music else ActivityType.WATCHING,
        "name": platform,
        "details": _clip(media["title"]),
        "state": _clip(state),
        "start": start_time,
        "end": end_time,
        "large_image": art_url,
        "small_image": PAUSED_ICON if is_paused else PLAYING_ICON,
        "small_text": "Paused" if is_paused else "Playing",
        "buttons": discord_button
    }

class PresenceSender:
    _NOTHING = object()

    def __init__(self):
        self.reset()

    def reset(self):
        self._sent_at = deque()
        self._pending = self._NOTHING
        self._last_payload = self._NOTHING
        self._confirm_at = None

    def _prune(self, now):
        while self._sent_at and now - self._sent_at[0] >= RATE_LIMIT_WINDOW:
            self._sent_at.popleft()

    async def _send(self, rpc, payload, now):
        if payload is None:
            await rpc.clear()
        else:
            await rpc.update(**payload)
        if self._sent_at and now - self._sent_at[-1] < CONFIRM_DELAY:
            self._confirm_at = now + CONFIRM_DELAY
        self._sent_at.append(now)
        self._last_payload = payload

    async def push(self, rpc, payload):
        self._pending = payload
        await self.flush(rpc)

    async def flush(self, rpc):
        if not rpc:
            return
        now = time.monotonic()
        self._prune(now)
        if len(self._sent_at) >= RATE_LIMIT_COUNT:
            if self._pending is not self._NOTHING:
                logging.debug("Discord rate limit reached, holding latest presence")
            return

        if self._pending is not self._NOTHING:
            payload = self._pending
            self._pending = self._NOTHING
            if payload != self._last_payload:
                await self._send(rpc, payload, now)
            return

        if self._confirm_at is not None and now >= self._confirm_at:
            self._confirm_at = None
            if self._last_payload is not self._NOTHING:
                logging.debug("Re-sending latest presence after burst")
                await self._send(rpc, self._last_payload, now)
                self._confirm_at = None

    def seconds_until_ready(self):
        now = time.monotonic()
        self._prune(now)
        quota_wait = 0
        if len(self._sent_at) >= RATE_LIMIT_COUNT:
            quota_wait = RATE_LIMIT_WINDOW - (now - self._sent_at[0])
        if self._pending is not self._NOTHING:
            return max(0.1, quota_wait)
        if self._confirm_at is not None:
            return max(0.1, self._confirm_at - now, quota_wait)
        return None

async def wait_for_wake(wake, timeout):
    try:
        await asyncio.wait_for(wake.wait(), timeout)
    except asyncio.TimeoutError:
        return
    await asyncio.sleep(EVENT_DEBOUNCE)
    wake.clear()

async def main_loop():
    RPC = None
    manager = await GlobalSystemMediaTransportControlsSessionManager.request_async()
    wake = asyncio.Event()
    watcher = MediaWatcher(manager, asyncio.get_running_loop(), wake.set)
    sender = PresenceSender()

    last_key = None
    last_status = None
    last_start_time = 0
    blank_since = None

    last_ad_key = None
    ad_active = False

    lookup_key = None
    lookup_task = None
    branding_final = False

    current_art_url = YOUTUBE_MUSIC_LOGO
    current_platform = "YouTube Music"
    current_button_url = "https://music.youtube.com"

    logging.info("Listening for media changes...")

    try:
        while True:
            try:
                if not RPC:
                    RPC = await connect_discord()
                    if not RPC:
                        await wait_for_wake(wake, RECONNECT_INTERVAL)
                        continue

                await sender.flush(RPC)

                try:
                    media = await get_media_info(manager)
                except Exception as e:
                    logging.warning(f"Failed to read Windows media info: {e}")
                    await wait_for_wake(wake, RECONNECT_INTERVAL)
                    continue

                ad_active = False
                if media and media["title"] and media["title"] not in PLACEHOLDER_TITLES:
                    blank_since = None

                    media_key = (media["title"], media["artist"] or "")
                    if media_key != last_key:
                        logging.debug(
                            f"Track change: title={media['title']!r} artist={media['artist']!r} "
                            f"duration={media['duration']:.1f} windows={_youtube_windows()!r}"
                        )
                    ad_active = media_key != last_key and is_probably_ad(media)
                    if ad_active:
                        if media_key != last_ad_key:
                            logging.info(f"🚫 Ad playing, clearing status: {media['title']}")
                            last_ad_key = media_key
                            await sender.push(RPC, None)
                            last_key = None
                            last_status = None
                            last_start_time = 0
                    else:
                        last_ad_key = None
                        track_changed = media_key != last_key

                        if media_key != lookup_key:
                            lookup_key = media_key
                            branding_final = False
                            lookup_task = asyncio.create_task(asyncio.to_thread(fetch_media_data, *media_key))
                            lookup_task.add_done_callback(lambda _: wake.set())
                            await asyncio.wait({lookup_task}, timeout=LOOKUP_DEADLINE)

                        branding_refreshed = False
                        if not branding_final:
                            if lookup_task.done():
                                try:
                                    current_art_url, current_platform, current_button_url = lookup_task.result()
                                except Exception as e:
                                    logging.warning(f"Media lookup failed: {e}")
                                    current_art_url, current_platform, current_button_url = youtube_fallback(media["title"])
                                branding_final = True
                                branding_refreshed = True
                            elif track_changed:
                                current_art_url, current_platform, current_button_url = youtube_fallback(media["title"])

                        if media["is_playing"]:
                            scrubbed = (
                                last_status == "playing"
                                and abs(media["start_time"] - last_start_time) > SCRUB_THRESHOLD
                            )

                            if track_changed or last_status != "playing" or branding_refreshed or scrubbed:
                                if scrubbed and not track_changed:
                                    logging.info(f"⏩ Scrubbed on {current_platform}: {media['title']}")
                                elif track_changed or last_status != "playing":
                                    logging.info(f"▶️ Playing on {current_platform}: {media['title']}")
                                else:
                                    logging.info(f"🖼️ Cover updated on {current_platform}: {media['title']}")

                                await sender.push(RPC, build_presence(
                                    media, current_platform,
                                    current_art_url, current_button_url,
                                    is_paused=False, start_time=media["start_time"]
                                ))

                                last_key = media_key
                                last_status = "playing"
                                last_start_time = media["start_time"]

                        else:
                            if track_changed or last_status != "paused" or branding_refreshed:
                                logging.info(f"⏸️ Paused on {current_platform}: {media['title']}")

                                await sender.push(RPC, build_presence(
                                    media, current_platform,
                                    current_art_url, current_button_url,
                                    is_paused=True
                                ))

                                last_key = media_key
                                last_status = "paused"
                                last_start_time = 0
                elif last_key is not None:
                    current_time = time.time()
                    if blank_since is None:
                        blank_since = current_time
                    elif current_time - blank_since >= BLANK_GRACE:
                        logging.info("⏹️ Nothing playing (or invalid data). Clearing status.")
                        await sender.push(RPC, None)
                        last_key = None
                        last_status = None
                        last_start_time = 0
                        blank_since = None

            except exceptions.ResponseTimeout:
                logging.warning("Discord took too long to respond. Retrying on next tick...")
            except (exceptions.PyPresenceException, OSError) as e:
                logging.warning(f"Discord connection lost ({e}). Reconnecting in background...")
                if RPC:
                    try:
                        RPC.close()
                    except Exception:
                        pass
                RPC = None
                sender.reset()
                last_key = None
                last_status = None
            except Exception:
                logging.exception("Unexpected error in main loop")

            if not RPC:
                timeout = RECONNECT_INTERVAL
            elif ad_active:
                timeout = AD_RECHECK_INTERVAL
            elif blank_since is not None:
                timeout = max(0.1, BLANK_GRACE - (time.time() - blank_since))
            else:
                timeout = HEARTBEAT_INTERVAL
            pending_in = sender.seconds_until_ready() if RPC else None
            if pending_in is not None:
                timeout = min(timeout, pending_in)
            await wait_for_wake(wake, timeout)

    finally:
        logging.info("Stopping the script. Goodbye!")
        watcher.close()
        if RPC:
            try:
                await RPC.clear()
                RPC.close()
                await asyncio.sleep(0.1)
            except Exception:
                pass

if __name__ == '__main__':
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        pass
