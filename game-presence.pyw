import time
import sys
from pypresence import Presence, InvalidID, PipeClosed, DiscordNotFound, DiscordError

# ------------------------------------------------------------------
# MULTI-GAME CONFIGURATION
# ------------------------------------------------------------------

# Max 2 buttons per game
GAMES = [
    # --- GAME 1: GRANBLUE FANTASY ---
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
    
    # --- GAME 2: NIKKE ---
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

# ------------------------------------------------------------------
# LOGIC
# ------------------------------------------------------------------

def get_active_game():
    try:
        import pygetwindow as gw
        windows = gw.getAllTitles()
    except:
        return None

    for game in GAMES:
        for title in windows:
            title_lower = title.lower()
            
            # 1. Browser Requirement Check
            if game["require_browser"]:
                if game["require_browser"].lower() not in title_lower:
                    continue

            # 2. Trigger Word Check
            for trigger in game["triggers"]:
                trigger_lower = trigger.lower()
                
                # Logic for Browser Games (Strict matching to avoid Wikis)
                if game["require_browser"]:
                    prefix_match = trigger_lower + " -"
                    if title_lower == trigger_lower or title_lower.startswith(prefix_match):
                        return game
                
                # Logic for Desktop Apps (Looser matching)
                else:
                    if trigger_lower in title_lower:
                        ignored_list = game.get("ignored_terms", [])
                        if any(term.lower() in title_lower for term in ignored_list):
                            continue
                        return game
    return None

def main():
    current_rpc = None
    current_client_id = None
    start_time = None

    print("Script started. Searching for games...")

    while True:
        try:
            active_game = get_active_game()
            
            if active_game:
                
                # Check if it need to switch games (e.g. from GBF to Nikke)
                if active_game['client_id'] != current_client_id:
                    print(f"Detected: {active_game['name']}")
                    
                    # Close old connection if it exists
                    if current_rpc:
                        try:
                            current_rpc.close()
                        except:
                            pass
                    
                    # Connect to new ID
                    current_client_id = active_game['client_id']
                    current_rpc = Presence(current_client_id)
                    current_rpc.connect()
                    start_time = time.time() # Reset timer for new game
                
                # Update Status
                current_rpc.update(
                    details=active_game.get('details'),
                    large_image=active_game['image_key'],
                    large_text=active_game['image_text'],
                    buttons=active_game.get('buttons'),
                    start=start_time
                )
                
            else:
                # --- NO GAME FOUND ---
                if current_rpc and current_client_id:
                    print("Game closed. Clearing status.")
                    try:
                        current_rpc.clear()
                        current_rpc.close()
                    except:
                        pass
                    current_rpc = None
                    current_client_id = None

            time.sleep(15)

        except (PipeClosed, InvalidID, ConnectionError, DiscordNotFound, DiscordError, FileNotFoundError):
            # Discord crashed or restarted, reset everything
            current_rpc = None
            current_client_id = None
            time.sleep(10)
            
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()