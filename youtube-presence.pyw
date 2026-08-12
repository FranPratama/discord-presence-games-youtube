import time
import asyncio
import logging
import urllib.request
import urllib.parse
import json
from pypresence import AioPresence, exceptions

# Import foundation to handle Windows background async operations
import winrt.windows.foundation

# winrt lets us talk directly to the Windows 10/11 Media Controls!
from winrt.windows.media.control import \
    GlobalSystemMediaTransportControlsSessionManager, \
    GlobalSystemMediaTransportControlsSessionPlaybackStatus

# ------------------------------------------------------------------
# LOGGING CONFIGURATION
# ------------------------------------------------------------------
logging.basicConfig(
    filename='youtube-presence.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logging.getLogger().addHandler(console)

# ------------------------------------------------------------------
# CONSTANTS
# ------------------------------------------------------------------
POLL_INTERVAL = 3           # Seconds between each media check
SCRUB_THRESHOLD = 5         # Seconds difference to count as a scrub/seek
BLANK_TICK_LIMIT = 2        # Ticks of no media before clearing Discord status
API_TIMEOUT = 5             # Seconds before iTunes API request times out

# --- CONFIGURATION ---
CLIENT_ID = '1478129019701432400'  

# Fallback images using highly reliable static icon URLs
YOUTUBE_MUSIC_LOGO = "https://img.icons8.com/color/512/youtube-music.png"
YOUTUBE_LOGO = "https://img.icons8.com/color/512/youtube-play.png"

# ------------------------------------------------------------------
# ITUNES API CACHE (in-memory)
# ------------------------------------------------------------------
_media_cache = {}

def fetch_media_data(title, artist):
    """
    Checks if the media is a song. 
    If yes, returns YouTube Music branding + Album Art. 
    If no, returns Standard YouTube branding.
    Results are cached in memory to avoid redundant API calls.
    """
    cache_key = f"{title}||{artist}"
    if cache_key in _media_cache:
        return _media_cache[cache_key]
    
    try:
        # Check if we can find this as a song on iTunes
        query = urllib.parse.quote(f"{title} {artist}")
        url = f"https://itunes.apple.com/search?term={query}&entity=song&limit=1"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=API_TIMEOUT) as response:
            data = json.loads(response.read())
            if data['resultCount'] > 0:
                # It's a song! Return YouTube Music branding
                art = data['results'][0]['artworkUrl100'].replace('100x100bb', '512x512bb')
                song_url = f"https://music.youtube.com/search?q={query}"
                result = (art, "YouTube Music", song_url)
                _media_cache[cache_key] = result
                return result
    except Exception as e:
        logging.warning(f"iTunes API lookup failed: {e}")
    
    # If iTunes fails or it's not a song, treat it as a regular YouTube video!
    video_query = urllib.parse.quote(f"{title}")
    video_url = f"https://www.youtube.com/results?search_query={video_query}"
    result = (YOUTUBE_LOGO, "YouTube", video_url)
    _media_cache[cache_key] = result
    return result

# ------------------------------------------------------------------
# HELPER FUNCTIONS
# ------------------------------------------------------------------

async def connect_discord():
    """Establishes a connection to the Discord app asynchronously."""
    try:
        logging.info("Connecting to Discord...")
        RPC = AioPresence(CLIENT_ID)
        await RPC.connect()
        logging.info("Successfully connected to Discord!")
        return RPC
    except Exception as e:
        logging.error(f"Failed to connect to Discord: {e}")
        return None

async def get_media_info():
    """Reads currently playing media directly from Windows."""
    manager = await GlobalSystemMediaTransportControlsSessionManager.request_async()
    session = manager.get_current_session()
    
    if not session:
        return None
        
    props = await session.try_get_media_properties_async()
    
    playback_info = session.get_playback_info()
    status = playback_info.playback_status if playback_info else None
    is_playing = (status == GlobalSystemMediaTransportControlsSessionPlaybackStatus.PLAYING)
    
    timeline = session.get_timeline_properties()
    position_secs = 0
    if timeline:
        position_secs = timeline.position.total_seconds()
        
    return {
        "title": props.title,
        "artist": props.artist,
        "is_playing": is_playing,
        "position": position_secs
    }

async def update_presence(RPC, media, platform, art_url, button_url, is_paused=False, start_time=None):
    """
    Centralized Discord RPC update to eliminate code duplication.
    Handles both playing and paused states.
    """
    artist = media['artist'] if media['artist'] else ("Paused Media" if is_paused else "Playing Media")
    state = f"[Paused] {artist}" if is_paused else artist
    
    btn_label = "Play on YouTube Music" if platform == "YouTube Music" else "Watch on YouTube"
    discord_button = [{"label": btn_label, "url": button_url}]
    
    await RPC.update(
        details=media["title"],
        state=state,
        start=start_time,
        large_image=art_url,
        large_text=platform,
        buttons=discord_button
    )

# ------------------------------------------------------------------
# MAIN LOOP
# ------------------------------------------------------------------

async def main_loop():
    """Main asynchronous loop."""
    RPC = None

    last_title = None
    last_status = None
    last_start_time = 0
    last_position = -1  
    blank_ticks = 0 # Prevents the status from rapidly clearing when changing songs
    
    # Initialize default branding
    current_art_url = YOUTUBE_MUSIC_LOGO 
    current_platform = "YouTube Music"
    current_button_url = "https://music.youtube.com"

    logging.info("Listening for media changes...")

    try:
        while True:
            try:
                # Automatically wait and connect if Discord is closed/starting
                if not RPC:
                    RPC = await connect_discord()
                    if not RPC:
                        await asyncio.sleep(POLL_INTERVAL)
                        continue

                media = await get_media_info()
                current_time = time.time()

                if media and media["title"] and media["title"] != "A site is playing media":
                    blank_ticks = 0 # Reset the blank tracker

                    if media["is_playing"]:
                        if media["title"] != last_title or last_status != "playing":
                            calc_start_time = int(current_time - media["position"])
                            
                            # Smart platform detection when the video/song changes
                            if media["title"] != last_title:
                                current_art_url, current_platform, current_button_url = await asyncio.to_thread(fetch_media_data, media["title"], media["artist"])

                            logging.info(f"▶️ Playing on {current_platform}: {media['title']}")
                            
                            await update_presence(
                                RPC, media, current_platform,
                                current_art_url, current_button_url,
                                is_paused=False, start_time=calc_start_time
                            )
                            
                            last_title = media["title"]
                            last_status = "playing"
                            last_start_time = calc_start_time
                            last_position = media["position"]
                            
                        elif media["position"] != last_position:
                            calc_start_time = int(current_time - media["position"])
                            
                            if abs(calc_start_time - last_start_time) > SCRUB_THRESHOLD:
                                logging.info(f"⏩ Scrubbed on {current_platform}: {media['title']}")
                                
                                await update_presence(
                                    RPC, media, current_platform,
                                    current_art_url, current_button_url,
                                    is_paused=False, start_time=calc_start_time
                                )
                                last_start_time = calc_start_time
                                
                            last_position = media["position"]
                            
                    else:
                        if last_status != "paused" or media["title"] != last_title:
                            
                            if media["title"] != last_title:
                                current_art_url, current_platform, current_button_url = await asyncio.to_thread(fetch_media_data, media["title"], media["artist"])

                            logging.info(f"⏸️ Paused on {current_platform}: {media['title']}")
                            
                            await update_presence(
                                RPC, media, current_platform,
                                current_art_url, current_button_url,
                                is_paused=True
                            )
                            
                            last_title = media["title"]
                            last_status = "paused"
                            last_start_time = 0
                            last_position = media["position"]
                else:
                    if last_title is not None:
                        blank_ticks += 1
                        # Wait for a few ticks before actually clearing the Discord status
                        if blank_ticks >= BLANK_TICK_LIMIT: 
                            logging.info("⏹️ Nothing playing (or invalid data). Clearing status.")
                            await RPC.clear()
                            last_title = None
                            last_status = None
                            last_start_time = 0
                            last_position = -1
            
            except exceptions.ResponseTimeout:
                logging.warning("Discord took too long to respond. Retrying on next tick...")
            except Exception as e:
                # Catch all disconnections (like Discord closing) and prepare to reconnect safely
                logging.warning(f"Discord connection lost ({e}). Reconnecting in background...")
                if RPC:
                    try:
                        RPC.close()
                    except Exception:
                        pass
                RPC = None
                await asyncio.sleep(POLL_INTERVAL)

            await asyncio.sleep(POLL_INTERVAL) 
            
    except KeyboardInterrupt:
        logging.info("Stopping the script. Goodbye!")
        if RPC:
            RPC.close()

if __name__ == '__main__':
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        pass