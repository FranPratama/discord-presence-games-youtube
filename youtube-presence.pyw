import time
import asyncio
from pypresence import AioPresence, exceptions
import urllib.request
import urllib.parse
import json

# Import foundation to handle Windows background async operations
import winrt.windows.foundation

# winrt lets us talk directly to the Windows 10/11 Media Controls!
from winrt.windows.media.control import \
    GlobalSystemMediaTransportControlsSessionManager, \
    GlobalSystemMediaTransportControlsSessionPlaybackStatus

# --- CONFIGURATION ---
CLIENT_ID = '1478129019701432400'  

# Fallback images using highly reliable static icon URLs
YOUTUBE_MUSIC_LOGO = "https://img.icons8.com/color/512/youtube-music.png"
YOUTUBE_LOGO = "https://img.icons8.com/color/512/youtube-play.png"

def fetch_media_data(title, artist):
    """
    Checks if the media is a song. 
    If yes, returns YouTube Music branding + Album Art. 
    If no, returns Standard YouTube branding.
    """
    try:
        # Check if we can find this as a song on iTunes
        query = urllib.parse.quote(f"{title} {artist}")
        url = f"https://itunes.apple.com/search?term={query}&entity=song&limit=1"
        req = urllib.request.Request(url)
        # Added timeout=5 to prevent the script from freezing if the network is slow
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read())
            if data['resultCount'] > 0:
                # It's a song! Return YouTube Music branding
                art = data['results'][0]['artworkUrl100'].replace('100x100bb', '512x512bb')
                song_url = f"https://music.youtube.com/search?q={query}"
                return art, "YouTube Music", song_url
    except Exception:
        pass
    
    # If iTunes fails or it's not a song, treat it as a regular YouTube video!
    video_query = urllib.parse.quote(f"{title}")
    video_url = f"https://www.youtube.com/results?search_query={video_query}"
    return YOUTUBE_LOGO, "YouTube", video_url

async def connect_discord():
    """Establishes a connection to the Discord app asynchronously."""
    try:
        print("Connecting to Discord...")
        RPC = AioPresence(CLIENT_ID)
        await RPC.connect()
        print("Successfully connected to Discord!")
        return RPC
    except Exception as e:
        print(f"Failed to connect to Discord: {e}")
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
    # Removed duration_secs as we don't need the end time anymore
    if timeline:
        position_secs = timeline.position.total_seconds()
        
    return {
        "title": props.title,
        "artist": props.artist,
        "is_playing": is_playing,
        "position": position_secs
    }

async def main_loop():
    """Main asynchronous loop."""
    # We remove the instant-quit logic here so it can wait for Discord
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

    print("Listening for media changes...")

    try:
        while True:
            try:
                # Automatically wait and connect if Discord is closed/starting
                if not RPC:
                    RPC = await connect_discord()
                    if not RPC:
                        await asyncio.sleep(5)
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

                            artist_text = media['artist'] if media['artist'] else "Playing Media"
                            print(f"▶️ Playing on {current_platform}: {media['title']}")
                            
                            # Build the dynamic button
                            btn_label = "Play on YouTube Music" if current_platform == "YouTube Music" else "Watch on YouTube"
                            discord_button = [{"label": btn_label, "url": current_button_url}]
                            
                            # Removed 'end' parameter so the timer doesn't cap/freeze!
                            await RPC.update(
                                details=media["title"],
                                state=artist_text,
                                start=calc_start_time,
                                large_image=current_art_url,
                                large_text=current_platform,
                                buttons=discord_button
                            )
                            
                            last_title = media["title"]
                            last_status = "playing"
                            last_start_time = calc_start_time
                            last_position = media["position"]
                            
                        elif media["position"] != last_position:
                            calc_start_time = int(current_time - media["position"])
                            
                            if abs(calc_start_time - last_start_time) > 5:
                                print(f"⏩ Scrubbed on {current_platform}: {media['title']}")
                                artist_text = media['artist'] if media['artist'] else "Playing Media"
                                
                                btn_label = "Play on YouTube Music" if current_platform == "YouTube Music" else "Watch on YouTube"
                                discord_button = [{"label": btn_label, "url": current_button_url}]
                                
                                await RPC.update(
                                    details=media["title"],
                                    state=artist_text,
                                    start=calc_start_time,
                                    large_image=current_art_url,
                                    large_text=current_platform,
                                    buttons=discord_button
                                )
                                last_start_time = calc_start_time
                                
                            last_position = media["position"]
                            
                    else:
                        if last_status != "paused" or media["title"] != last_title:
                            
                            if media["title"] != last_title:
                                current_art_url, current_platform, current_button_url = await asyncio.to_thread(fetch_media_data, media["title"], media["artist"])

                            artist_text = media['artist'] if media['artist'] else "Paused Media"
                            print(f"⏸️ Paused on {current_platform}: {media['title']}")
                            
                            btn_label = "Play on YouTube Music" if current_platform == "YouTube Music" else "Watch on YouTube"
                            discord_button = [{"label": btn_label, "url": current_button_url}]
                            
                            await RPC.update(
                                details=media["title"],
                                state=f"[Paused] {artist_text}",
                                large_image=current_art_url,
                                large_text=current_platform,
                                buttons=discord_button
                            )
                            
                            last_title = media["title"]
                            last_status = "paused"
                            last_start_time = 0
                            last_position = media["position"]
                else:
                    if last_title is not None:
                        blank_ticks += 1
                        # Wait for a few ticks before actually clearing the Discord status
                        if blank_ticks >= 2: 
                            print("⏹️ Nothing playing (or invalid data). Clearing status.")
                            await RPC.clear()
                            last_title = None
                            last_status = None
                            last_start_time = 0
                            last_position = -1
            
            except exceptions.ResponseTimeout:
                print("⚠️ Discord took too long to respond. Retrying on next tick...")
            except Exception as e:
                # Catch all disconnections (like Discord closing) and prepare to reconnect safely
                print(f"⚠️ Discord connection lost ({e}). Reconnecting in background...")
                if RPC:
                    try:
                        RPC.close()
                    except:
                        pass
                RPC = None
                await asyncio.sleep(5)

            await asyncio.sleep(3) 
            
    except KeyboardInterrupt:
        print("\nStopping the script. Goodbye!")
        if RPC:
            RPC.close()

if __name__ == '__main__':
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        pass