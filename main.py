import os
import logging
import sys
from dotenv import load_dotenv
from telegram import Update, InlineQueryResultArticle, InputTextMessageContent, BotCommand
from telegram.ext import Application, InlineQueryHandler, CommandHandler, ContextTypes
import requests
from flask import Flask, request
import asyncio

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://sharingtrackbot.railway.app")
PORT = int(os.getenv("PORT", 8000))

logger.info(f"✅ Token: {bool(TELEGRAM_BOT_TOKEN)}")
logger.info(f"Webhook URL: {WEBHOOK_URL}")

ODESLI_API = "https://api.song.link/v1-alpha.1/links"

app = Flask(__name__)
application = None


def convert_song_link(url):
    """Convert song link using Odesli API"""
    try:
        logger.info(f"🔄 Converting: {url}")
        response = requests.get(
            ODESLI_API,
            params={"url": url, "userCountry": "US"},
            timeout=10
        )
        
        logger.info(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            link_by_platform = data.get("linksByPlatform", {})
            logger.debug(f"Available: {list(link_by_platform.keys())}")
            
            if "spotify.com" in url and "appleMusic" in link_by_platform:
                result = link_by_platform["appleMusic"]["url"]
                logger.info(f"✅ Spotify → Apple Music")
                return result, "Apple Music"
            
            elif "music.apple.com" in url and "spotify" in link_by_platform:
                result = link_by_platform["spotify"]["url"]
                logger.info(f"✅ Apple Music → Spotify")
                return result, "Spotify"
        
        logger.warning(f"❌ No conversion available")
        return None, None
        
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return None, None


async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline queries"""
    try:
        query = update.inline_query.query.strip()
        user_id = update.inline_query.from_user.id
        
        logger.info(f"📥 INLINE QUERY from {user_id}: '{query}'")
        
        if not query:
            logger.info("Empty query")
            await update.inline_query.answer([], cache_time=0)
            return
        
        is_spotify = "spotify.com" in query
        is_apple = "music.apple.com" in query
        
        logger.info(f"Spotify: {is_spotify}, Apple: {is_apple}")
        
        if not (is_spotify or is_apple):
            logger.info("Not a music link")
            await update.inline_query.answer([], cache_time=0)
            return
        
        converted_url, platform = convert_song_link(query)
        
        if not converted_url:
            results = [
                InlineQueryResultArticle(
                    id="error",
                    title="❌ Could not convert",
                    description="Invalid Spotify or Apple Music link",
                    input_message_content=InputTextMessageContent(
                        message_text="❌ Couldn't convert. Check the link and try again."
                    ),
                )
            ]
        else:
            target = "Apple Music" if is_spotify else "Spotify"
            results = [
                InlineQueryResultArticle(
                    id="converted",
                    title=f"🎵 {target}",
                    description=f"Click to share {target} link",
                    input_message_content=InputTextMessageContent(
                        message_text=f"🎵 {target}\n{converted_url}"
                    ),
                    url=converted_url,
                )
            ]
            logger.info(f"✅ Returning result")
        
        await update.inline_query.answer(results, cache_time=300)
        
    except Exception as e:
        logger.error(f"❌ Inline error: {e}", exc_info=True)
        try:
            await update.inline_query.answer([], cache_time=0)
        except:
            pass


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start command"""
    logger.info("Start command")
    await update.message.reply_text(
        "🎵 **SharingTrack Bot**\n\n"
        "Use me inline to convert songs!\n\n"
        "Example:\n"
        "@SharingTrackbot https://open.spotify.com/track/...",
        parse_mode="Markdown"
    )


async def test(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Test command"""
    logger.info("Test command")
    await update.message.reply_text("✅ Bot is working!")


@app.route("/webhook", methods=["POST"])
def webhook():
    """Webhook endpoint"""
    try:
        update_data = request.get_json()
        logger.debug(f"Webhook received")
        
        update = Update.de_json(update_data, application.bot)
        
        # Process update in async context
        asyncio.run(application.process_update(update))
        
        return "ok"
    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)
        return "error", 500


@app.route("/health", methods=["GET"])
def health():
    """Health check"""
    return "ok"


async def setup_bot():
    """Setup bot commands and webhook"""
    logger.info("Setting up bot...")
    
    # Set commands
    commands = [
        BotCommand("start", "Start the bot"),
        BotCommand("test", "Test if bot is working"),
    ]
    await application.bot.set_my_commands(commands)
    logger.info("✅ Commands set")
    
    # Set webhook
    webhook_url = f"{WEBHOOK_URL}/webhook"
    await application.bot.set_webhook(webhook_url, drop_pending_updates=True)
    logger.info(f"✅ Webhook set: {webhook_url}")


# Initialize bot on startup
if not TELEGRAM_BOT_TOKEN:
    logger.error("❌ No token!")
    raise ValueError("TELEGRAM_BOT_TOKEN required")

logger.info("🚀 Starting SharingTrack Bot...")

application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

application.add_handler(InlineQueryHandler(inline_query))
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("test", test))

# Setup bot
try:
    asyncio.run(setup_bot())
except Exception as e:
    logger.error(f"Setup error: {e}", exc_info=True)

logger.info("🎵 Bot configured and ready")
