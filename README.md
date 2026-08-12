# Discord Rich Presence Multiple Platform

$${\color{red}This\ script\ is\ using\ FIFO\ method}$$

A Python application that automatically detects when you're playing supported games and updates your Discord status with rich presence information, including game details, images, and buttons.

## Features

- 🎮 **Multi-Game Support**: Automatically detect and manage Discord Rich Presence for multiple games
- 🔄 **Seamless Switching**: Instantly switches between games when you change windows
- 🌐 **Browser & Desktop Support**: Handles both browser-based games (like Granblue Fantasy) and desktop applications (like NIKKE)
- 🔗 **Custom Buttons**: Display up to 2 buttons per game (Official Site, Wiki links, etc.)
- ⏱️ **Session Timing**: Shows elapsed time since you started playing
- 🛡️ **Smart Detection**: Intelligent window matching to avoid false positives
- 🔄 **Auto-Recovery**: Handles Discord disconnects gracefully

## Installation

### Prerequisites
- Windows OS
- Python
- Discord

### Setup Steps

1. **Clone the repository**
   ```
   git clone https://github.com/FranPratama/Discord-Presence-for-Multiple-Game-Platform.git
   cd Discord-Presence-for-Multiple-Game-Platform
   ```

2. **Install dependencies**
   ```
   pip install -r requirements.txt
   ```

3. **Run the script**
   ```
   python discord-presence.pyw
   ```

## How to Use

### Running Manually
1. Install Discord and Python on your system
2. Run `pip install -r requirements.txt`
3. Execute `python discord-presence.pyw` or double-click `discord-presence.pyw`
4. Open any supported game
5. Your Discord status will update automatically!

### Running at Startup

Follow these steps to run the script automatically when Windows starts:

1. Copy the path to `discord-presence.pyw`
2. Press `Win + R` to open the Run dialog
3. Type `shell:startup` and press Enter
4. A folder will open - paste a shortcut to `discord-presence.pyw` here
5. (Optional) Open Task Manager and verify the script is running and enabled in the Startup tab

## Configuration

### Adding New Games

Edit the `GAMES` list in `discord-presence.pyw`:

```python
{
    "name": "Game Name",
    "client_id": "YOUR_DISCORD_CLIENT_ID",
    "triggers": ["Window Title"],
    "require_browser": "Chrome",  # or None for desktop apps
    "image_key": "game-logo",
    "image_text": "Display Text",
    "details": "Activity Description",
    "buttons": [
        {"label": "Official Site", "url": "https://example.com"},
        {"label": "Wiki", "url": "https://example.com"}
    ]
}
```

### Creating Discord Application IDs

1. Visit [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application"
3. Name your application and create it
4. Go to "OAuth2" → "General"
5. Copy your **Client ID**
6. Add it to the `GAMES` configuration in the script

## How It Works

The script uses a **FIFO (First In, First Out)** method to:

1. Monitor all open window titles in real-time
2. Detect when a supported game is running
3. Connect to Discord using the game's Client ID
4. Update your Discord status with game details, images, and buttons
5. Automatically switch between games when you change windows
6. Clear status when no game is detected

### Detection Logic

- **Browser Games**: Strict matching (requires exact window title or specific prefix) to avoid false triggers from wiki/guide tabs
- **Desktop Apps**: Looser matching with ignored terms to filter unrelated windows

## Files

- `discord-presence.pyw` - Main executable script (production)
- `for-development.py` - Development version for testing
- `requirements.txt` - Python dependencies

## Dependencies

```
PyGetWindow==0.0.9
pypresence==4.6.1
PyRect==0.2.0
```

## Troubleshooting

### Status not updating?
- Ensure Discord is running
- Verify the game window title matches a trigger word
- Check that the Client ID is correct
- Look at console output for error messages

### False positives (unrelated windows triggering status)?
- Add the window title to `ignored_terms` list
- Adjust the `require_browser` setting for browser games

### Discord connection lost?
- Restart Discord
- The script will auto-reconnect
- Check your internet connection

### Still having issues?
- Run `for-development.py` to see console output
- Verify all dependencies installed: `pip install -r requirements.txt`

## Development

For development and debugging:
```
python for-development.py
```

This version displays console output for easier troubleshooting.
