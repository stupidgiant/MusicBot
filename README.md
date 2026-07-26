# MusicBot 🎵

A simple Telegram bot that converts Spotify links to Apple Music and vice versa using inline queries.

## Features

- **Inline Query Support**: Type `@bot_username spotify_link` or `@bot_username apple_music_link` in any chat
- **Bidirectional Conversion**: Spotify ↔ Apple Music
- **24/7 Uptime**: Runs on Railway
- **Simple & Fast**: Uses Odesli API for instant conversions

## Setup

### Local Development

1. **Clone the repo**
   ```bash
   git clone https://github.com/stupidgiant/MusicBot.git
   cd MusicBot
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Create `.env` file** (copy from `.env.example`)
   ```bash
   cp .env.example .env
   ```

5. **Add your Telegram bot token**
   - Create a bot with [@BotFather](https://t.me/BotFather) on Telegram
   - Copy the token and paste it in `.env`:
   ```
   TELEGRAM_BOT_TOKEN=your_token_here
   ```

6. **Run the bot locally**
   ```bash
   python main.py
   ```

### Railway Deployment

1. **Push to GitHub** (make sure your repo is on GitHub)
   ```bash
   git add .
   git commit -m "Initial commit"
   git push origin main
   ```

2. **Go to [railway.app](https://railway.app)**
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Connect your GitHub account and select `stupidgiant/MusicBot`

3. **Add Environment Variables**
   - Go to the project settings
   - Add variable: `TELEGRAM_BOT_TOKEN` = your bot token from @BotFather

4. **Deploy**
   - Railway will automatically build and deploy when you push to GitHub
   - Check logs to confirm it's running

## How to Use

1. **Get your bot username** from the setup message or @BotFather
2. **In any Telegram chat**, type:
   ```
   @your_bot_username https://open.spotify.com/track/...
   ```
   or
   ```
   @your_bot_username https://music.apple.com/...
   ```
3. **Select the result** to share the converted link

## Tech Stack

- **Python 3.11**
- **python-telegram-bot**: Telegram bot framework
- **Odesli API**: Cross-platform song link conversion
- **Railway**: Hosting

## File Structure

```
MusicBot/
├── main.py                 # Main bot logic
├── requirements.txt        # Python dependencies
├── Dockerfile             # Container image
├── railway.json          # Railway config
├── .env.example          # Environment template
└── README.md             # This file
```

## Troubleshooting

**Bot not responding?**
- Check bot is running: `python main.py`
- Verify `TELEGRAM_BOT_TOKEN` is correct in `.env`
- Check Railway logs if deployed

**Link conversion failing?**
- Make sure URL is a valid Spotify or Apple Music link
- Odesli API might have rate limits (free tier is generous)

## License

MIT

## Author

[@stupidgiant](https://github.com/stupidgiant)
