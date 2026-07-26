import os
import logging
from dotenv import load_dotenv
from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import Application, InlineQueryHandler, ContextTypes
import requests

load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Odesli API for cross-platform song conversion
ODESLI_API = "https://api.song.link/v1-alpha.1/links"


def convert_song_link(url):
    """
    Convert song link using Odesli API
    Returns the converted link or None if failed
    """
    try:
        logger.info(f"Converting URL: {url}")
        response = requests.get(
            ODESLI_API,
            params={
                "url": url,
                "userCountry": "US"
            },
            timeout=10
        )
        
        logger.info(f"Odesli API response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            link_by_platform = data.get("linksByPlatform", {})
            
            # If it's Spotify, convert to Apple Music
            if "spotify" in url and "appleMusic" in link_by_platform:
                converted = link_by_platform["appleMusic"]["url"]
                logger.info(f"Converted Spotify to Apple Music: {converted}")
                return converted, "appleMusic"
            
            # If it's Apple Music, convert to Spotify
            elif "music.apple.com" in url and "spotify" in link_by_platform:
                converted = link_by_platform["spotify"]["url"]
                logger.info(f"Converted Apple Music to Spotify: {converted}")
                return converted, "spotify"
        
        logger.warning(f"No conversion available for URL")
        return None, None
        
    except Exception as e:
        logger.error(f"Error converting song: {e}", exc_info=True)
        return None, None


async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline queries from users"""
    try:
        query = update.inline_query.query.strip()
        
        if not query:
            await update.inline_query.answer([], cache_time=0)
            return
        
        logger.info(f"Inline query received: {query}")
        
        # Check if it's a Spotify or Apple Music link
        is_spotify = "spotify.com" in query
        is_apple = "music.apple.com" in query
        
        if not (is_spotify or is_apple):
            logger.info("Query is not a Spotify or Apple Music link")
            await update.inline_query.answer([], cache_time=0)
            return
        
        # Convert the link
        converted_url, platform = convert_song_link(query)
        
        if not converted_url:
            logger.warning("Failed to convert link")
            results = [
                InlineQueryResultArticle(
                    id="error",
                    title="❌ Could not convert link",
                    description="Make sure it's a valid Spotify or Apple Music link",
                    input_message_content=InputTextMessageContent(
                        message_text="Sorry, I couldn't convert that link. Try a valid Spotify or Apple Music URL."
                    ),
                )
            ]
        else:
            target_display = "Apple Music" if is_spotify else "Spotify"
            results = [
                InlineQueryResultArticle(
                    id="converted",
                    title=f"🎵 {target_display}",
                    description="Click to share the converted link",
                    input_message_content=InputTextMessageContent(
                        message_text=f"🎵 **{target_display}:**\n{converted_url}"
                    ),
                    url=converted_url,
                )
            ]
        
        await update.inline_query.answer(results, cache_time=60)
        logger.info(f"Answered inline query with {len(results)} result(s)")
        
    except Exception as e:
        logger.error(f"Error in inline_query handler: {e}", exc_info=True)
        await update.inline_query.answer([], cache_time=0)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    await update.message.reply_text(
        "🎵 MusicBot - Convert between Spotify and Apple Music!\n\n"
        "Use me inline:\n"
        "@MusicBot spotify_link\n"
        "@MusicBot apple_music_link\n\n"
        "I'll convert it to the other platform!"
    )


def main() -> None:
    """Start the bot"""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set in environment variables")
        raise ValueError("TELEGRAM_BOT_TOKEN not set in environment variables")
    
    logger.info(f"Bot token found: {TELEGRAM_BOT_TOKEN[:10]}...")
    
    # Create the Application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Register handlers
    application.add_handler(InlineQueryHandler(inline_query))
    application.add_handler(application.add_handler(__import__("telegram.ext").CommandHandler("start", start)))
    
    logger.info("🤖 Bot started and polling...")
    
    # Start the Bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
