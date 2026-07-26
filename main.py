import os
import logging
from dotenv import load_dotenv
from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import Application, InlineQueryHandler, ContextTypes
import requests
from urllib.parse import urlparse

load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("8895183093:AAHKyVBtVJQ9Ca7xlKj-gq0Aa7-yb85Iiz8")

# Odesli API for cross-platform song conversion
ODESLI_API = "https://api.song.link/v1-alpha.1/links"


def extract_song_id(url):
    """Extract song ID from Spotify or Apple Music URL"""
    if "spotify.com" in url:
        parts = url.split("/")
        return parts[-1].split("?")[0], "spotify"
    elif "music.apple.com" in url:
        parts = url.split("/")
        return parts[-1].split("?")[0], "apple"
    return None, None


def convert_song_link(url, target_platform):
    """
    Convert song link using Odesli API
    target_platform: 'spotify' or 'apple'
    """
    try:
        # Use Odesli to convert
        response = requests.get(
            ODESLI_API,
            params={
                "url": url,
                "userCountry": "US"
            },
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            link_by_platform = data.get("linksByPlatform", {})
            
            if target_platform == "spotify" and "spotify" in link_by_platform:
                return link_by_platform["spotify"]["url"]
            elif target_platform == "appleMusic" and "appleMusic" in link_by_platform:
                return link_by_platform["appleMusic"]["url"]
        
        return None
    except Exception as e:
        logger.error(f"Error converting song: {e}")
        return None


async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline queries from users"""
    query = update.inline_query.query.strip()
    
    if not query:
        return
    
    # Check if it's a Spotify or Apple Music link
    is_spotify = "spotify.com" in query
    is_apple = "music.apple.com" in query
    
    if not (is_spotify or is_apple):
        return
    
    # Determine target platform
    target = "apple" if is_spotify else "spotify"
    target_display = "Apple Music" if is_spotify else "Spotify"
    
    # Convert the link
    converted_url = convert_song_link(query, "appleMusic" if target == "apple" else "spotify")
    
    if not converted_url:
        results = [
            InlineQueryResultArticle(
                id="error",
                title="❌ Could not convert link",
                description=f"Try sharing a valid Spotify or Apple Music link",
                input_message_content=InputTextMessageContent(
                    message_text="Sorry, I couldn't convert that link. Make sure it's a valid Spotify or Apple Music URL."
                ),
            )
        ]
    else:
        results = [
            InlineQueryResultArticle(
                id="converted",
                title=f"🎵 Open on {target_display}",
                description="Click to share the converted link",
                input_message_content=InputTextMessageContent(
                    message_text=f"🎵 **{target_display} Link:**\n{converted_url}"
                ),
                url=converted_url,
            )
        ]
    
    await update.inline_query.answer(results, cache_time=60)


def main() -> None:
    """Start the bot"""
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN not set in environment variables")
    
    # Create the Application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Register inline query handler
    application.add_handler(InlineQueryHandler(inline_query))
    
    logger.info("🤖 Bot started! Use @your_bot_username inline queries to convert songs.")
    
    # Start the Bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
