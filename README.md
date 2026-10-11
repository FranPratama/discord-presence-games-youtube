# Discord Presence for Games and YouTube

Two small Python scripts that show what you're doing on Discord. One handles games, the other handles YouTube and YouTube Music. They run quietly in the background on Windows, no console window needed.

## What's inside

**game-presence.pyw** looks at your open window titles every 15 seconds. When it finds a game from its list, it shows that game on your Discord profile with a timer and a couple of buttons. Right now it knows Granblue Fantasy (in Chrome) and NIKKE, but adding more is just a matter of editing the `GAMES` list at the top of the file.

**youtube-presence.pyw** reads what Windows itself reports as "now playing", the same info you see in the volume flyout. When that's YouTube or YouTube Music in your browser, it shows the title, artist, cover art, a progress bar, and a link back to the song or video. It reacts to play, pause, skip and seek almost instantly, and it tries to stay quiet while ads are playing.

## Setup

You need Windows 10 or 11, Python 3.10+, and the Discord desktop app open.

```bash
git clone https://github.com/FranPratama/discord-presence-games-youtube.git
cd discord-presence-games-youtube
pip install -r requirements.txt
```

Then run whichever script you want:

```bash
python game-presence.pyw
python youtube-presence.pyw
```

Running with `python` shows the log in the terminal, which is handy the first time. Once it works, use `pythonw` (or just double-click the file) to keep it in the background. If you installed the packages in a virtual environment, point to that environment's `pythonw.exe`, otherwise double-clicking will use your global Python and fail silently.

To start it with Windows, put a shortcut to the script in `shell:startup` (press Win+R and type that).

Both scripts write a log file next to themselves (`game-presence.log`, `youtube-presence.log`) if you need to see what's going on.

## Adding a game

Each game needs its own Discord application. Create one at the [Discord Developer Portal](https://discord.com/developers/applications), copy its Application ID, and optionally upload a logo under Rich Presence > Art Assets. Then add an entry to `GAMES` in `game-presence.pyw` with the ID, the window title keywords to look for, and the text you want shown.

## Things to know before using it

### game-presence

- Detection is based only on window titles. Any window whose title contains a trigger word counts, so a file called `nikke-notes.txt` open in an editor can show up as playing NIKKE. Add words to `ignored_terms` if that happens.
- Browser games like Granblue Fantasy are only detected while their tab is the active tab in the browser window.
- It checks every 15 seconds, so starting or closing a game can take that long to show up on Discord.
- Only one game is shown at a time. If two are open, the one listed first in `GAMES` wins.
- If Discord restarts, the elapsed timer starts over from zero.

### youtube-presence

- Incognito and private windows don't work. The browser hides what's playing from Windows in those windows, so there's nothing for the script to read.
- Cover art and links are found by searching YouTube Music, iTunes and YouTube using the title. Most of the time it picks the right one, but now and then it can grab a different version or fall back to the plain YouTube logo. The first lookup after starting the script can take a few seconds.
- The YouTube search part reads YouTube's normal search page. If YouTube changes how that page looks, video thumbnails may stop working until the script is updated.
- Ad detection is a guess based on the browser tab title and the length of the clip. Some ads may still slip through, and in rare cases a real song might be treated as an ad (for example if you're browsing a different YouTube video in the active tab while music plays in another).
- Discord limits how often a status can change. If you skip through songs quickly, Discord may lag behind for up to about 20 seconds before catching up.
- Only one thing is shown: whatever Windows considers the current media. Spotify, VLC and a few other players are ignored on purpose.
- If the browser tab's title isn't visible to Windows (for example the YouTube tab isn't the active one), some features like ad detection can't do their job.

## Files

```
game-presence.pyw      game detection
youtube-presence.pyw   YouTube / YouTube Music detection
requirements.txt       Python packages
```
