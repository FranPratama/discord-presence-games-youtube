# 🎮 Discord Rich Presence — Multi Platform

Custom Discord Rich Presence for **Games** and **YouTube / YouTube Music**, running silently in background on Windows.

## ✨ Features

| Script | What it does |
|---|---|
| `game-presence.pyw` | Detects active games via window title → shows game status on Discord |
| `youtube-presence.pyw` | Reads Windows media session → shows YouTube/YT Music with album art |

**Highlights:**
- 🔄 Auto-switch between multiple games
- 🎵 Smart YouTube vs YouTube Music detection (via iTunes API)
- 🖼️ Album art fetched automatically
- ⏸️ Pause/play/scrub detection for media
- 🛡️ Auto-reconnect on Discord crash
- 📝 Logs to file for easy debugging

## 🚀 Quick Start

```bash
git clone https://github.com/FranPratama/Discord-Presence-for-Multiple-Game-Platform.git
cd Discord-Presence-for-Multiple-Game-Platform
pip install -r requirements.txt
```

Run either script by double-clicking the `.pyw` file, or:

```bash
python game-presence.pyw       # For games
python youtube-presence.pyw    # For YouTube / YT Music
```

> **Tip:** `.pyw` files run without a console window — perfect for background use.

### Auto-Start on Boot

1. Press `Win + R` → type `shell:startup` → Enter
2. Paste a shortcut to the `.pyw` file you want

## ⚙️ Configuration

### Adding a New Game

Edit the `GAMES` list in `game-presence.pyw`:

```python
{
    "name": "Your Game",
    "client_id": "YOUR_DISCORD_APP_ID",
    "triggers": ["Window Title Keyword"],
    "require_browser": None,          # Set to "Chrome" for browser games
    "ignored_terms": ["Wiki", "Guide"], # Optional: prevent false positives
    "image_key": "game-logo",
    "image_text": "Your Game",
    "details": "Playing...",
    "buttons": [
        {"label": "Official Site", "url": "https://example.com"}
    ]
}
```

### Getting a Discord Application ID

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. **New Application** → name it → copy the **Client ID**
3. *(Optional)* Upload a logo under **Rich Presence → Art Assets** with the key `game-logo`

## 🔧 Troubleshooting

| Problem | Fix |
|---|---|
| Status not showing | Make sure Discord is open and Client ID is correct |
| Wrong game detected | Add false-positive keywords to `ignored_terms` |
| Connection lost | Script auto-reconnects — just wait a few seconds |
| Need debug logs | Check `game-presence.log` or `youtube-presence.log` |

## 📁 Project Structure

```
├── game-presence.pyw       # Game detection & Discord RPC
├── youtube-presence.pyw    # Media detection & Discord RPC
├── requirements.txt        # Python dependencies
├── .gitignore
└── README.md
```

## 📦 Dependencies

```
pypresence        — Discord RPC connection
PyGetWindow       — Window title detection (game-presence)
winrt-*           — Windows Media API (youtube-presence)
```

Install all at once: `pip install -r requirements.txt`
