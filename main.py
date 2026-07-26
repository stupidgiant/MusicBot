import os
import logging
import sys
import json
import re
from urllib.parse import parse_qs, urlparse
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import Application, InlineQueryHandler, CommandHandler, MessageHandler, ContextTypes, filters
import aiohttp
import asyncio
from typing import Optional, Tuple

load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# File logging for errors
error_handler = logging.FileHandler('errors.log')
error_handler.setLevel(logging.ERROR)
error_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
error_handler.setFormatter(error_formatter)
logger.addHandler(error_handler)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TELEGRAM_BOT_TOKEN:
    logger.error("❌ TELEGRAM_BOT_TOKEN not set!")
    raise ValueError("TELEGRAM_BOT_TOKEN required")
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_URL = "https://api.spotify.com/v1"
ITUNES_API_URL = "https://itunes.apple.com"

logger.info("✅ Token loaded")

ODESLI_API = "https://api.song.link/v1-alpha.1/links"
METRICS_FILE = "metrics.json"
MAX_RETRIES = 2
TIMEOUT = 10


# ============ METRICS ============
class MetricsTracker:
    """Track bot usage and errors"""
    
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.load()
    
    def load(self) -> None:
        """Load metrics from file"""
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r') as f:
                    data = json.load(f)
                    self.conversions = data.get('conversions', 0)
                    self.errors = data.get('errors', 0)
                    self.users = set(data.get('users', []))
            except Exception as e:
                logger.error(f"Error loading metrics: {e}")
                self.conversions = 0
                self.errors = 0
                self.users = set()
        else:
            self.conversions = 0
            self.errors = 0
            self.users = set()
    
    def save(self) -> None:
        """Save metrics to file"""
        try:
            with open(self.filepath, 'w') as f:
                json.dump({
                    'conversions': self.conversions,
                    'errors': self.errors,
                    'users': list(self.users),
                    'last_updated': datetime.now().isoformat()
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving metrics: {e}")
    
    def add_conversion(self, user_id: int) -> None:
        """Track successful conversion"""
        self.conversions += 1
        self.users.add(str(user_id))
        self.save()
    
    def add_error(self) -> None:
        """Track error"""
        self.errors += 1
        self.save()
    
    def get_stats(self) -> dict:
        """Get current stats"""
        return {
            'conversions': self.conversions,
            'errors': self.errors,
            'unique_users': len(self.users)
        }


metrics = MetricsTracker(METRICS_FILE)


# ============ ASYNC HTTP CLIENT ============
class OdesliClient:
    """Async Odesli API client with retry logic"""
    
    def __init__(self, timeout: int = TIMEOUT, max_retries: int = MAX_RETRIES):
        self.timeout = timeout
        self.max_retries = max_retries
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        connector = aiohttp.TCPConnector(limit=10, limit_per_host=5)
        self.session = aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=self.timeout))
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def convert(self, url: str) -> Optional[Tuple[str, str]]:
        """Convert link with retry logic"""
        for attempt in range(self.max_retries + 1):
            try:
                logger.info(f"🔄 Converting (attempt {attempt + 1}): {url}")
                
                if not self.session:
                    raise RuntimeError("Session not initialized")
                
                async with self.session.get(
                    ODESLI_API,
                    params={"url": url, "userCountry": "US"}
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return self._parse_response(url, data)
                    elif response.status == 404:
                        logger.warning(f"Song not found on API: {url}")
                        return None, None
                    else:
                        logger.warning(f"API returned {response.status}")
                        
            except asyncio.TimeoutError:
                logger.warning(f"Timeout on attempt {attempt + 1}")
                if attempt < self.max_retries:
                    await asyncio.sleep(1)  # Wait before retry
                    continue
            except aiohttp.ClientError as e:
                logger.warning(f"Network error: {e}")
                if attempt < self.max_retries:
                    await asyncio.sleep(1)
                    continue
            except Exception as e:
                logger.error(f"Unexpected error: {e}", exc_info=True)
                return None, None
        
        logger.error(f"Failed to convert after {self.max_retries + 1} attempts")
        return None, None
    
    @staticmethod
    def _parse_response(url: str, data: dict) -> Optional[Tuple[str, str]]:
        """Parse Odesli API response"""
        try:
            link_by_platform = data.get("linksByPlatform", {})
            
            is_spotify = "spotify.com" in url or data.get("entityUniqueId", "").startswith("SPOTIFY_")
            if is_spotify and "appleMusic" in link_by_platform:
                result = link_by_platform["appleMusic"]["url"]
                logger.info("✅ Spotify → Apple Music")
                return result, "Apple Music"
            
            elif "music.apple.com" in url and "spotify" in link_by_platform:
                result = link_by_platform["spotify"]["url"]
                logger.info("✅ Apple Music → Spotify")
                return result, "Spotify"
            
            logger.warning("No conversion available for this platform")
            return None, None
        except Exception as e:
            logger.error(f"Error parsing response: {e}")
            return None, None


MUSIC_URL_RE = re.compile(r"https?://[^\s<>()]+")

def extract_music_url(text: str) -> Optional[str]:
    """Extract a URL from text that may also mention the bot."""
    match = MUSIC_URL_RE.search(text)
    return match.group(0).rstrip(".,!?;:)]}") if match else None
class MusicCatalogClient:
    """Convert links using Spotify's API and Apple's public iTunes catalog."""

    def __init__(self, timeout: int = TIMEOUT):
        self.timeout = timeout
        self.session: Optional[aiohttp.ClientSession] = None
        self.spotify_token: Optional[str] = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout))
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def _json(self, method: str, url: str, **kwargs) -> dict:
        if not self.session:
            raise RuntimeError("Session not initialized")
        async with self.session.request(method, url, **kwargs) as response:
            if response.status >= 400:
                body = await response.text()
                raise RuntimeError(f"Catalog request failed ({response.status}): {body[:200]}")
            return await response.json()

    async def _get_spotify_token(self) -> str:
        if self.spotify_token:
            return self.spotify_token
        client_id = os.getenv("SPOTIFY_CLIENT_ID")
        client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
        if not client_id or not client_secret:
            raise RuntimeError("Missing SPOTIFY_CLIENT_ID or SPOTIFY_CLIENT_SECRET")
        data = await self._json(
            "POST", SPOTIFY_TOKEN_URL, data={"grant_type": "client_credentials"},
            auth=aiohttp.BasicAuth(client_id, client_secret),
        )
        self.spotify_token = data["access_token"]
        return self.spotify_token

    async def _spotify_request(self, path: str, params: dict | None = None) -> dict:
        token = await self._get_spotify_token()
        return await self._json(
            "GET", f"{SPOTIFY_API_URL}{path}", params=params,
            headers={"Authorization": f"Bearer {token}"},
        )

    @staticmethod
    def _spotify_track_id(url: str) -> Optional[str]:
        match = re.search(r"spotify\.com/track/([A-Za-z0-9]+)", url)
        return match.group(1) if match else None

    @staticmethod
    def _apple_track_id(url: str) -> Optional[str]:
        parsed = urlparse(url)
        query_id = parse_qs(parsed.query).get("i", [None])[0]
        if query_id and query_id.isdigit():
            return query_id
        for part in reversed(parsed.path.split("/")):
            if part.isdigit():
                return part
        return None

    @staticmethod
    def _normalize(value: str) -> str:
        return re.sub(r"[^a-z0-9]", "", value.lower())

    async def _itunes_search(self, title: str, artist: str) -> Optional[str]:
        data = await self._json(
            "GET", f"{ITUNES_API_URL}/search",
            params={"term": f"{artist} {title}", "country": os.getenv("ITUNES_COUNTRY", "us"),
                    "media": "music", "entity": "song", "limit": 10},
        )
        title_key, artist_key = self._normalize(title), self._normalize(artist)
        best_result, best_score = None, -1
        for result in data.get("results", []):
            candidate_title = self._normalize(result.get("trackName", ""))
            candidate_artist = self._normalize(result.get("artistName", ""))
            score = 0
            if candidate_title == title_key:
                score += 4
            elif title_key in candidate_title or candidate_title in title_key:
                score += 2
            if candidate_artist == artist_key:
                score += 3
            elif artist_key in candidate_artist or candidate_artist in artist_key:
                score += 1
            if score > best_score:
                best_result, best_score = result, score
        return best_result.get("trackViewUrl") if best_result and best_score >= 4 else None

    async def _itunes_lookup(self, track_id: str) -> Optional[dict]:
        data = await self._json(
            "GET", f"{ITUNES_API_URL}/lookup",
            params={"id": track_id, "country": os.getenv("ITUNES_COUNTRY", "us")},
        )
        return next((item for item in data.get("results", []) if item.get("kind") == "song"), None)

    async def _spotify_search(self, title: str, artist: str) -> Optional[str]:
        data = await self._spotify_request(
            "/search", {"q": f'track:"{title}" artist:"{artist}"', "type": "track", "limit": 5},
        )
        tracks = data.get("tracks", {}).get("items", [])
        return tracks[0].get("external_urls", {}).get("spotify") if tracks else None

    async def convert(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        spotify_id = self._spotify_track_id(url)
        if spotify_id:
            track = await self._spotify_request(f"/tracks/{spotify_id}")
            artist = ", ".join(item["name"] for item in track.get("artists", []))
            return await self._itunes_search(track["name"], artist), "Apple Music"
        apple_id = self._apple_track_id(url)
        if apple_id:
            track = await self._itunes_lookup(apple_id)
            if not track:
                return None, None
            return await self._spotify_search(track["trackName"], track["artistName"]), "Spotify"
        return None, None

# ============ UTILITIES ============
def clean_music_url(url: str) -> str:
    """Normalize a URL without removing Apple Music's required ?i= song ID."""
    url = url.rstrip("/")
    logger.debug(f"🧹 Cleaned URL: {url}")
    return url


# ============ HANDLERS ============
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle regular text messages with links"""
    try:
        text = update.message.text.strip() if update.message.text else ""
        user_id = update.effective_user.id
        logger.info(f"📨 Message from {user_id}: {text}")
        
        if not text:
            return
        
        url = extract_music_url(text)
        is_spotify = bool(url and ("spotify.com" in url or "spotify.link" in url))
        is_apple = bool(url and "music.apple.com" in url)
        
        if not (is_spotify or is_apple):
            await update.message.reply_text("🎵 Send me a Spotify or Apple Music link!")
            return
        
        await update.message.reply_text("⏳ Converting...")
        
        url = clean_music_url(url)
        async with MusicCatalogClient() as client:
            converted_url, platform = await client.convert(url)
        
        if not converted_url:
            logger.warning(f"Conversion failed for user {user_id}")
            metrics.add_error()
            await update.message.reply_text(
                "❌ Couldn't convert this link.\n\n"
                "Make sure:\n"
                "✅ It's a valid Spotify or Apple Music link\n"
                "✅ The song exists on both platforms\n"
                "✅ Try a different song"
            )
        else:
            target = "Apple Music" if is_spotify else "Spotify"
            metrics.add_conversion(user_id)
            await update.message.reply_text(
                f"🎵 **{target}**\n{converted_url}",
                parse_mode="Markdown"
            )
        
    except Exception as e:
        logger.error(f"❌ Message handler error: {e}", exc_info=True)
        metrics.add_error()
        await update.message.reply_text("❌ Error processing message")


async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline queries"""
    try:
        query = update.inline_query.query.strip() if update.inline_query.query else ""
        user_id = update.effective_user.id
        logger.info(f"📥 Inline query from {user_id}: {query}")
        
        if not query:
            await update.inline_query.answer([], cache_time=0)
            return
        
        url = extract_music_url(query)
        is_spotify = bool(url and ("spotify.com" in url or "spotify.link" in url))
        is_apple = bool(url and "music.apple.com" in url)
        
        if not (is_spotify or is_apple):
            await update.inline_query.answer([], cache_time=0)
            return
        
        url = clean_music_url(url)
        async with MusicCatalogClient() as client:
            converted_url, platform = await client.convert(url)
        
        if not converted_url:
            logger.warning(f"Inline conversion failed for user {user_id}")
            metrics.add_error()
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
            metrics.add_conversion(user_id)
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
        metrics.add_error()
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


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show bot statistics"""
    stats_data = metrics.get_stats()
    await update.message.reply_text(
        f"📊 **Bot Stats**\n\n"
        f"✅ Conversions: {stats_data['conversions']}\n"
        f"❌ Errors: {stats_data['errors']}\n"
        f"👥 Unique Users: {stats_data['unique_users']}",
        parse_mode="Markdown"
    )


async def post_init(app: Application) -> None:
    """Initialize bot on startup"""
    logger.info("🧹 Cleaning up old webhook...")
    try:
        await app.bot.delete_webhook(drop_pending_updates=False)
        logger.info("✅ Webhook deleted, polling mode ready")
    except Exception as e:
        logger.error(f"Error deleting webhook: {e}")


def main() -> None:
    """Start the bot"""
    logger.info("🚀 Starting SharingTrack Bot with polling...")
    logger.info(f"📊 Current stats: {metrics.get_stats()}")
    
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Handlers (order matters - more specific first)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("test", test))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(InlineQueryHandler(inline_query))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    app.post_init = post_init
    
    logger.info("✅ Handlers registered")
    logger.info("🎵 Bot polling...")
    
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
