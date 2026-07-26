import os
import logging
import sys
from dotenv import load_dotenv
from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import Application, InlineQueryHandler, CommandHandler, ContextTypes
import requests

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TELEGRAM_BOT_TOKEN:
    logger.error("❌ TELEGRAM_BOT_TOKEN not set!")
    raise ValueError("TELEGRAM_BOT_TOKEN required")

logger.info(f"✅ Token loaded")

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
        
        logger.info(f"📥 INLINE QUERY: '{query}'")
        
        if not query:
            await update.inline_query.answer([], cache_time=0)
            return
        
        is_spotify = "spotify.com" in query
        is_apple = "music.apple.com" in query
        
        if not (is_spotify or is_apple):
            await update.inline_query.answer([], cache_time=0)
            return
        
        converted_url, platform = convert_song_link(query)
        
        if not converted_url:
            results = [
                InlineQueryResultArticle(
                    id="error",
                    title="❌ Could not convert",
                    description="Invalid link",
                    input_message_content=InputTextMessageContent(
                        message_text="❌ Couldn't convert."
                    ),
                )
            ]
        else:
            target = "Apple Music" if is_spotify else "Spotify"
            results = [
                InlineQueryResultArticle(
                    id="converted",
                    title=f"🎵 {target}",
                    description="Click to share",
                    input_message_content=InputTextMessageContent(
                        message_text=f"🎵 {target}\n{converted_url}"
                    ),
                    url=converted_url,
                )
            ]
        
        await update.inline_query.answer(results, cache_time=300)
        
    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start command"""
    await update.message.reply_text(
        "🎵 **SharingTrack Bot**\n\n"
        "Use me inline: @SharingTrackbot [link]"
    )


async def test(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Test command"""
    logger.info("✅ Test command received")
    await update.message.reply_text("✅ Bot is working!")


def main() -> None:
    """Start the bot"""
    logger.info("🚀 Starting bot with polling...")
    
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    app.add_handler(InlineQueryHandler(inline_query))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("test", test))
    
    logger.info("✅ Handlers registered")
    logger.info("🎵 Bot polling...")
    
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
