import sys
import time
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import pygetwindow as gw
from pypresence import Presence, InvalidID, PipeClosed, DiscordNotFound, DiscordError

LOG_PATH = Path(__file__).with_name('game-presence.log')

_log_handlers = [RotatingFileHandler(LOG_PATH, maxBytes=1_000_000, backupCount=3, encoding='utf-8')]
if sys.stderr:
    _log_handlers.append(logging.StreamHandler())

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=_log_handlers
)

POLL_INTERVAL = 15
RECONNECT_DELAY = 10

GAMES = [
    {
        "name": "Granblue Fantasy",
        "client_id": "1460467337718403102",
        "triggers": ["Granblue Fantasy", "グランブルーファンタジー"],
        "require_browser": "Chrome",
        "image_key": "game-logo",
        "image_text": "Granblue Fantasy",
        "details": "Exploring the Sky Realm",
        "buttons": [
            {"label": "Official Site", "url": "http://game.granbluefantasy.jp"},
            {"label": "GBF Community Wiki", "url": "https://gbf.wiki"}
        ]
    },
    {
        "name": "NIKKE",
        "client_id": "1472409955809366047",
        "triggers": ["GODDESS OF VICTORY", "NIKKE"],
        "require_browser": None,
        "ignored_terms": ["Chrome", "Edge", "Firefox", "Opera", "Brave", "Wiki", "Guide"],
        "image_key": "game-logo",
        "image_text": "GODDESS OF VICTORY: NIKKE",
        "details": "Reclaiming the Surface",
        "buttons": [
            {"label": "Official Site", "url": "https://nikke-en.com"},
            {"label": "Strongest Party", "url": "https://gamewith.jp/nikke/article/show/376374"}
        ]
    }
]

def get_active_game():
    try:
        windows = gw.getAllTitles()
    except Exception as e:
        logging.warning(f"Failed to read window titles: {e}")
        return None

    for game in GAMES:
        for title in windows:
            title_lower = title.lower()

            if game["require_browser"]:
                if game["require_browser"].lower() not in title_lower:
                    continue

            for trigger in game["triggers"]:
                trigger_lower = trigger.lower()

                if game["require_browser"]:
                    prefix_match = trigger_lower + " -"
                    if title_lower == trigger_lower or title_lower.startswith(prefix_match):
                        return game

                else:
                    if trigger_lower in title_lower:
                        ignored_list = game.get("ignored_terms", [])
                        if any(term.lower() in title_lower for term in ignored_list):
                            continue
                        return game
    return None

def _close_rpc(rpc, clear=False):
    if not rpc:
        return
    try:
        if clear:
            rpc.clear()
        rpc.close()
    except Exception:
        pass

def main():
    current_rpc = None
    current_client_id = None
    start_time = None

    logging.info("Script started. Searching for games...")

    try:
        while True:
            try:
                active_game = get_active_game()

                if active_game:
                    if active_game['client_id'] != current_client_id:
                        logging.info(f"Detected: {active_game['name']}")
                        _close_rpc(current_rpc)
                        current_rpc = None
                        current_client_id = None

                        rpc = Presence(active_game['client_id'])
                        rpc.connect()
                        current_rpc = rpc
                        current_client_id = active_game['client_id']
                        start_time = int(time.time())

                    current_rpc.update(
                        details=active_game.get('details'),
                        large_image=active_game['image_key'],
                        large_text=active_game['image_text'],
                        buttons=active_game.get('buttons'),
                        start=start_time
                    )

                elif current_rpc:
                    logging.info("Game closed. Clearing status.")
                    _close_rpc(current_rpc, clear=True)
                    current_rpc = None
                    current_client_id = None

                time.sleep(POLL_INTERVAL)

            except (PipeClosed, InvalidID, DiscordNotFound, DiscordError, OSError) as e:
                logging.warning(f"Discord connection lost ({e}). Reconnecting...")
                _close_rpc(current_rpc)
                current_rpc = None
                current_client_id = None
                time.sleep(RECONNECT_DELAY)

            except Exception:
                logging.exception("Unexpected error")
                time.sleep(RECONNECT_DELAY)

    except KeyboardInterrupt:
        logging.info("Script stopped by user. Goodbye!")
    finally:
        _close_rpc(current_rpc, clear=True)

if __name__ == "__main__":
    main()
