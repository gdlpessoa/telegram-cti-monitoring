import asyncio
import io
import logging
import os
from datetime import datetime
from pydantic_settings import BaseSettings
from functools import lru_cache
import pytesseract
from PIL import Image
from colorama import Fore, Style, init

from telethon import TelegramClient, events

from database import SessionLocal, init_db
from models import Message
from crud import create_message, create_alert

init(autoreset=True)

class Settings(BaseSettings):
    """
    Application configuration settings loaded from environment variables.
    
    Handles Telegram API credentials, monitoring targets, and alert configuration.
    """
    API_ID: int
    API_HASH: str
    PHONE_NUMBER: str
    TELEGRAM_GROUPS: str
    BRAND_KEYWORDS: str
    ALERT_GROUP_ID: int

    @property
    def MONITOR_GROUPS(self) -> list[str]:
        """Parse comma-separated group names into a list."""
        return [g.strip() for g in self.TELEGRAM_GROUPS.split(',') if g.strip()]

    @property
    def MONITOR_KEYWORDS(self) -> list[str]:
        """Parse comma-separated keywords into a lowercase list."""
        return [k.strip().lower() for k in self.BRAND_KEYWORDS.split(',') if k.strip()]

    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    """Get cached application settings."""
    return Settings()

settings = get_settings()

logging.basicConfig(format='[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s',
                    level=logging.INFO)
log = logging.getLogger(__name__)

def extract_text_from_image(image_bytes: bytes) -> str:
    """
    Extract text from image using OCR.
    
    Args:
        image_bytes: Raw image data
        
    Returns:
        Extracted text in lowercase, empty string on error
    """
    try:
        image = Image.open(io.BytesIO(image_bytes))
        text = pytesseract.image_to_string(image, lang='por')
        if text.strip():
            log.info(f"OCR extracted text: {text[:50].strip()}...")
        return text.lower()
    except Exception as e:
        log.error(f"Error during OCR: {e}")
        return ""

SESSION_DIR = "session"
SESSION_FILE = os.path.join(SESSION_DIR, "telethon.session")
os.makedirs(SESSION_DIR, exist_ok=True)

client = TelegramClient(SESSION_FILE, settings.API_ID, settings.API_HASH)

def check_for_keywords(text_to_check: str) -> list[str]:
    """
    Check if any monitored keywords are present in the given text.
    
    Args:
        text_to_check: Text content to analyze
        
    Returns:
        List of keywords found in the text
    """
    found = []
    for keyword in settings.MONITOR_KEYWORDS:
        if keyword in text_to_check:
            found.append(keyword)
    
    return found

async def send_telegram_alert(chat_name: str, found_keywords: list[str], message_id: int, message_text: str = None):
    """
    Send security alert to the configured Telegram group.
    
    Args:
        chat_name: Name of the source chat
        found_keywords: List of keywords that triggered the alert
        message_id: ID of the message that triggered the alert
        message_text: Optional message content preview
    """
    try:
        keyword_str = ", ".join(found_keywords)
        
        alert_message = f"**POSSIBLE LEAK OR EXPOSURE DETECTED**\n\n"
        alert_message += f"📍 **Group:** {chat_name}\n"
        alert_message += f"🔍 **Keywords:** {keyword_str}\n"
        alert_message += f"📝 **Message ID:** {message_id}\n"
        
        if message_text and len(message_text) > 0:
            preview_text = message_text[:200] + "..." if len(message_text) > 200 else message_text
            alert_message += f"💬 **Content:** {preview_text}\n"
        
        alert_message += f"\n⏰ **Timestamp:** {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
        
        result = await client.send_message(settings.ALERT_GROUP_ID, alert_message)
        log.info(f"Alert sent successfully to group ID {settings.ALERT_GROUP_ID} (Msg ID: {result.id})")
        
    except Exception as e:
        log.error(f"Error sending alert to Telegram: {e}")

@client.on(events.NewMessage(chats=settings.MONITOR_GROUPS))
async def handle_new_message(event):
    """
    Process incoming messages from monitored Telegram groups.
    
    Analyzes message content and images for security keywords,
    saves all messages to database, and triggers alerts when keywords are found.
    """
    message = event.message
    chat = await event.get_chat()
    chat_name = getattr(chat, 'title', 'Private Channel')
    
    log.info(f"New message from '{chat_name}'")
    
    db = SessionLocal()
    
    try:
        text_to_check = ""
        ocr_text = ""
        
        if message.text:
            text_to_check += message.text.lower()

        if message.photo:
            log.info("Downloading image for OCR analysis...")
            image_bytes = await message.download_media(file=bytes)
            ocr_text = extract_text_from_image(image_bytes)
            text_to_check += " " + ocr_text

        db_message = Message(
            telegram_message_id=message.id,
            chat_name=chat_name,
            content=message.text,
            has_image=(message.photo is not None),
            ocr_text=ocr_text.strip() if ocr_text else None
        )
        saved_msg = create_message(db, db_message)
        log.info(f"Message {saved_msg.id} saved to database.")

        found_keywords = check_for_keywords(text_to_check)
        
        if found_keywords:
            keyword_str = ", ".join(found_keywords)
            
            print(Fore.RED + Style.BRIGHT + "=========================================")
            print(Fore.RED + Style.BRIGHT + f"!!! POSSIBLE LEAK OR EXPOSURE DETECTED !!!")
            print(Fore.YELLOW + f"Group:    {chat_name} (Msg ID: {saved_msg.id})")
            print(Fore.YELLOW + f"Keywords: {keyword_str}")
            print(Fore.RED + Style.BRIGHT + "=========================================" + Style.RESET_ALL)
            
            create_alert(db, message=saved_msg, keyword=keyword_str)
            log.warning(f"Alert saved to database for message {saved_msg.id}.")
            
            await send_telegram_alert(
                chat_name=chat_name,
                found_keywords=found_keywords,
                message_id=saved_msg.id,
                message_text=message.text
            )

    except Exception as e:
        log.error(f"Error processing message {message.id}: {e}")
        db.rollback()
    finally:
        db.close()

async def main():
    """
    Main application entry point.
    
    Initializes database, starts Telegram client, and begins monitoring.
    """
    log.info("Initializing database...")
    init_db()
    
    log.info(f"Configurations loaded:")
    log.info(f"  - Groups to monitor: {settings.MONITOR_GROUPS}")
    log.info(f"  - Keywords: {settings.MONITOR_KEYWORDS}")
    log.info(f"  - Alert group ID: {settings.ALERT_GROUP_ID}")
    
    log.info("Starting Telethon client...")
    await client.start(phone=settings.PHONE_NUMBER)
    log.info(f"Client started! Monitoring {len(settings.MONITOR_GROUPS)} group(s).")
    
    log.info("=== AVAILABLE DIALOGS ===")
    async for dialog in client.iter_dialogs():
        if dialog.is_channel or dialog.is_group:
            log.info(f"  - {dialog.name} (ID: {dialog.id}) - Type: {'Channel' if dialog.is_channel else 'Group'}")
    log.info("=== END OF LIST ===")
    
    log.info("Waiting for new messages... (Press Ctrl+C to stop)")
    
    await client.run_until_disconnected()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Shutting down...")