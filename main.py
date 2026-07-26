import os
import logging
import sys
from dotenv import load_dotenv
from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import Application, InlineQueryHandler, CommandHandler, ContextTypes
import requests

load_dotenv()

# Set up logging - output to stdout for Railway
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
logger.info(f"Token loaded: {bool(TELEGRAM_BOT_TOKEN)}")

# Odesli API for cross-platform song conversion
ODESLI_API = "https://api.song.link/v1-alpha.1/links"


def convert_song_link(url):
    """
    Convert song link using Odesli API
    Returns tuple: (converted_url, platform_name)
    """
    try:
        logger.info(f"🔄 Converting URL: {url}")
        response = requests.get(
            ODESLI_API,
            params={
                "url": url,
                "userCountry": "US"
            },
            timeout=10
        )
        
        logger.info(f"Odesli response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            logger.debug(f"Odesli response: {data}")
            
            link_by_platform = data.get("linksByPlatform", {})
            logger.info(f"Available platforms: {list(link_by_platform.keys())}")
            
            # If it's Spotify, convert to Apple Music
            if "spotify.com" in url:
                if "appleMusic" in link_by_platform:
                    converted = link_by_platform["appleMusic"]["url"]
                    logger.info(f"✅ Converted Spotify → Apple Music")
                    return converted, "Apple Music"
            
            # If it's Apple Music, convert to Spotify
            elif "music.apple.com" in url:
                if "spotify" in link_by_platform:
                    converted = link_by_platform["spotify"]["url"]
                    logger.info(f"✅ Converted Apple Music → Spotify")
                    return converted, "Spotify"
        
        logger.warning(f"❌ No conversion available - Status: {response.status_code}")
        return None, None
        
    except Exception as e:
        logger.error(f"❌ Error converting: {e}", exc_info=True)
        return None, None


async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline queries from users"""
    try:
        query = update.inline_query.query.strip()
        query_id = update.inline_query.id
        
        logger.info(f"📥 Inline query received (ID: {query_id}): '{query}'")
        
        if not query:
            logger.info("Query empty, returning no results")
            await update.inline_query.answer([], cache_time=0)
            return
        
        # Check if it's a Spotify or Apple Music link
        is_spotify = "spotify.com" in query
        is_apple = "music.apple.com" in query
        
        logger.info(f"Is Spotify: {is_spotify}, Is Apple: {is_apple}")
        
        if not (is_spotify or is_apple):
            logger.info("Not a music link, returning no results")
            await update.inline_query.answer([], cache_time=0)
            return
        
        # Convert the link
        converted_url, platform = convert_song_link(query)
        
        if not converted_url:
            logger.warning("Conversion failed, returning error result")
            results = [
                InlineQueryResultArticle(
                    id="error",
                    title="❌ Could not convert",
                    description="Try a valid Spotify or Apple Music link",
                    input_message_content=InputTextMessageContent(
                        message_text="❌ Couldn't convert that link. Make sure it's a valid Spotify or Apple Music URL."
                    ),
                )
            ]
        else:
            logger.info(f"Conversion successful! Returning result")
            target = "Apple Music" if is_spotify else "Spotify"
            results = [
                InlineQueryResultArticle(
                    id="converted",
                    title=f"🎵 Open on {target}",
                    description="Click to share this link",
                    input_message_content=InputTextMessageContent(
                        message_text=f"🎵 **{target}:**\n{converted_url}"
                    ),
                    url=converted_url,
                )
            ]
        
        logger.info(f"Answering with {len(results)} result(s)")
        await update.inline_query.answer(results, cache_time=300)
        
    except Exception as e:
        logger.error(f"❌ Error in inline_query: {e}", exc_info=True)
        try:
            await update.inline_query.answer([], cache_time=0)
        except:
            pass


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when /start is issued"""
    logger.info("Start command received")
    text = (
        "🎵 **SharingTrack Bot**\n\n"
        "Convert between Spotify and Apple Music!\n\n"
        "**How to use:**\n"
        "Type in any chat:\n"
        "@SharingTrackbot https://open.spotify.com/track/...\n\n"
        "Or:\n"
        "@SharingTrackbot https://music.apple.com/...\n\n"
        "I'll instantly convert it! 🎶"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def test(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Test command"""
    logger.info("Test command received")
    await update.message.reply_text(
        "✅ Bot is working!\n\n"
        "Try using me inline:\n"
        "@SharingTrackbot [spotify_link]\n"
        "@SharingTrackbot [apple_music_link]"
    )


def main() -> None:
    """Start the bot"""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("❌ TELEGRAM_BOT_TOKEN not set!")
        raise ValueError("TELEGRAM_BOT_TOKEN not set in environment variables")
    
    logger.info(f"✅ Token found: {TELEGRAM_BOT_TOKEN[:20]}...")
    logger.info("🤖 Starting SharingTrack Bot...")
    
    # Create the Application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Register handlers
    application.add_handler(InlineQueryHandler(inline_query))
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("test", test))
    
    logger.info("✅ Handlers registered")
    logger.info("🎵 Bot is running and polling...")
    
    # Start the Bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
