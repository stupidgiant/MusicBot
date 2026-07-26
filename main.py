import os
import logging
import sys
from dotenv import load_dotenv
from telegram import Update, InlineQueryResultArticle, InputTextMessageContent, BotCommand
from telegram.ext import Application, InlineQueryHandler, CommandHandler, ContextTypes
from telegram.constants import ChatAction
import requests

load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
logger.info(f"✅ Token loaded: {bool(TELEGRAM_BOT_TOKEN)}")

ODESLI_API = "https://api.song.link/v1-alpha.1/links"


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
            
            # Spotify → Apple Music
            if "spotify.com" in url and "appleMusic" in link_by_platform:
                result = link_by_platform["appleMusic"]["url"]
                logger.info(f"✅ Spotify → Apple Music")
                return result, "Apple Music"
            
            # Apple Music → Spotify
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
        await update.inline_query.answer([], cache_time=0)


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


async def post_init(application: Application) -> None:
    """Set bot commands after startup"""
    logger.info("Setting bot commands...")
    commands = [
        BotCommand("start", "Start the bot"),
        BotCommand("test", "Test if bot is working"),
    ]
    await application.bot.set_my_commands(commands)
    logger.info("✅ Commands set")


def main() -> None:
    """Start the bot"""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("❌ No token!")
        raise ValueError("TELEGRAM_BOT_TOKEN required")
    
    logger.info("🚀 Starting SharingTrack Bot...")
    
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    app.add_handler(InlineQueryHandler(inline_query))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("test", test))
    
    app.post_init = post_init
    
    logger.info("🎵 Bot running and polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
