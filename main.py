import os
import logging
import sys
from dotenv import load_dotenv
from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import Application, InlineQueryHandler, CommandHandler, MessageHandler, ContextTypes, filters
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


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle regular text messages with links"""
    try:
        text = update.message.text.strip()
        logger.info(f"📨 Message: {text}")
        
        if not text:
            return
        
        is_spotify = "spotify.com" in text
        is_apple = "music.apple.com" in text
        
        if not (is_spotify or is_apple):
            await update.message.reply_text("🎵 Send me a Spotify or Apple Music link!")
            return
        
        converted_url, platform = convert_song_link(text)
        
        if not converted_url:
            await update.message.reply_text("❌ Couldn't convert this link. Make sure it's valid.")
        else:
            target = "Apple Music" if is_spotify else "Spotify"
            await update.message.reply_text(
                f"🎵 **{target}**\n{converted_url}",
                parse_mode="Markdown"
            )
        
    except Exception as e:
        logger.error(f"❌ Message handler error: {e}", exc_info=True)
        await update.message.reply_text("❌ Error processing message")


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
            logger.info("Not a music link, returning empty")
            await update.inline_query.answer([], cache_time=0)
            return
        
        converted_url, platform = convert_song_link(query)
        
        if not converted_url:
            logger.warning(f"Conversion failed for: {query}")
            results = [
                InlineQueryResultArticle(
                    id="error",
                    title="❌ Could not convert",
                    description="Invalid or unsupported link",
                    input_message_content=InputTextMessageContent(
                        message_text="❌ Couldn't convert this link."
                    ),
                )
            ]
        else:
            target = "Apple Music" if is_spotify else "Spotify"
            logger.info(f"✅ Inline conversion success: {target}")
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
        logger.error(f"❌ Inline query error: {e}", exc_info=True)
        await update.inline_query.answer([], cache_time=0)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start command"""
    await update.message.reply_text(
        "🎵 **SharingTrack Bot**\n\n"
        "**Two ways to use me:**\n\n"
        "1️⃣ **Send directly** - Send me a Spotify or Apple Music link\n"
        "2️⃣ **Inline** - Type `@SharingTrackbot [link]` in any chat",
        parse_mode="Markdown"
    )


async def test(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Test command"""
    logger.info("✅ Test command received")
    await update.message.reply_text("✅ Bot is working!")


async def post_init(app: Application) -> None:
    """Delete webhook on startup"""
    logger.info("🧹 Cleaning up old webhook...")
    try:
        await app.bot.delete_webhook(drop_pending_updates=True)
        logger.info("✅ Webhook deleted, polling mode ready")
    except Exception as e:
        logger.error(f"Error deleting webhook: {e}")


def main() -> None:
    """Start the bot"""
    logger.info("🚀 Starting bot with polling...")
    
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Handlers (order matters - more specific first)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("test", test))
    app.add_handler(InlineQueryHandler(inline_query))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    app.post_init = post_init
    
    logger.info("✅ Handlers registered")
    logger.info("🎵 Bot polling...")
    
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
