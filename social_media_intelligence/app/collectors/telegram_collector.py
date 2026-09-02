import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from telethon import TelegramClient
from telethon.tl.types import (
    Channel, User, Chat, 
    Message, MessageMediaDocument, MessageMediaPhoto
)
from telethon.errors import (
    SessionPasswordNeededError, 
    ChannelPrivateError,
    UsernameInvalidError
)

from .base_collector import BaseCollector
from ..config import settings
from ..exceptions import (
    ConfigurationError, 
    TelegramConnectionError, 
    TelegramCollectionError,
    TelegramChannelNotFoundError
)
from ..utils.datetime_utils import ensure_utc

logger = logging.getLogger(__name__)

class TelegramCollector(BaseCollector):
    def __init__(self):
        self.api_id = settings.TELEGRAM_API_ID
        self.api_hash = settings.TELEGRAM_API_HASH
        self.phone = settings.TELEGRAM_PHONE
        
        if not self.api_id or not self.api_hash:
            raise ConfigurationError("Telegram API ID and Hash must be provided.")
            
        self.client = TelegramClient(
            settings.TELEGRAM_SESSION_NAME, 
            int(self.api_id), 
            self.api_hash
        )

    async def validate_connection(self) -> bool:
        """Validate connection and authentication."""
        try:
            await self.client.connect()
            if not await self.client.is_user_authorized():
                if not self.phone:
                    raise ConfigurationError("Phone number required for authentication.")
                await self.client.send_code_request(self.phone)
                # Note: In a fully automated env, handling 2FA or code requires user input.
                # Since this is a test/validate method, we'll just return False if it requires auth.
                logger.warning("Authentication required. Please run interactive login.")
                return False
            return True
        except Exception as e:
            raise TelegramConnectionError(f"Failed to connect to Telegram: {str(e)}")

    async def _resolve_entity(self, channel: str):
        """Resolve the channel to get its metadata."""
        try:
            entity = await self.client.get_entity(channel)
            metadata = {
                "channel": channel,
                "chat_id": getattr(entity, 'id', None),
                "title": getattr(entity, 'title', None),
                "username": getattr(entity, 'username', None),
                "entity_type": "channel" if isinstance(entity, Channel) else ("group" if isinstance(entity, Chat) else "unknown")
            }
            if hasattr(entity, 'about'):
                metadata['about'] = entity.about
            return entity, metadata
        except (ValueError, UsernameInvalidError):
            raise TelegramChannelNotFoundError(f"Channel {channel} not found or invalid.")
        except ChannelPrivateError:
            raise TelegramChannelNotFoundError(f"Channel {channel} is private or inaccessible.")
        except Exception as e:
            raise TelegramConnectionError(f"Failed to resolve channel {channel}: {str(e)}")

    def _message_to_dict(self, msg: Message, chat_id: int) -> Dict[str, Any]:
        """Convert a Telethon Message object to a raw JSON-serializable dictionary."""
        
        msg_type = "service"
        if not msg.action:
            has_text = bool(msg.message)
            has_media = bool(msg.media)
            if has_text and has_media:
                msg_type = "text+media"
            elif has_media:
                msg_type = "media"
            elif has_text:
                msg_type = "text"

        raw_dict = {
            "message_id": msg.id,
            "chat_id": chat_id,
            "sender_id": msg.sender_id,
            "text": msg.message or "",
            "date": ensure_utc(msg.date).isoformat() if msg.date else None,
            "edit_date": ensure_utc(msg.edit_date).isoformat() if getattr(msg, 'edit_date', None) else None,
            "views": getattr(msg, 'views', None),
            "forwards": getattr(msg, 'forwards', None),
            "message_type": msg_type
        }

        # Relationships (Reply)
        if hasattr(msg, 'reply_to') and msg.reply_to:
            raw_dict["reply_to_msg_id"] = msg.reply_to.reply_to_msg_id
            raw_dict["reply_to_peer_id"] = getattr(msg.reply_to, 'reply_to_peer_id', None)
        else:
            raw_dict["reply_to_msg_id"] = None
            raw_dict["reply_to_peer_id"] = None

        # Relationships (Forward)
        fwd_info = None
        if hasattr(msg, 'fwd_from') and msg.fwd_from:
            fwd = msg.fwd_from
            fwd_info = {
                "original_date": ensure_utc(fwd.date).isoformat() if getattr(fwd, 'date', None) else None,
                "original_sender_id": getattr(fwd.from_id, 'user_id', None) if getattr(fwd, 'from_id', None) else None,
                "original_channel_id": getattr(fwd.from_id, 'channel_id', None) if getattr(fwd, 'from_id', None) else None,
            }
        
        raw_dict["forward_info"] = fwd_info

        return raw_dict

    async def collect(
        self,
        channel: str,
        limit: int = 100,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        keywords: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Collect messages from a Telegram channel."""
        logger.info(f"Initializing collection for channel {channel}")
        
        if not self.client.is_connected():
            await self.client.connect()

        if not await self.client.is_user_authorized():
            raise TelegramConnectionError("User not authorized. Please run interactive login to create a session.")
            
        entity, source_metadata = await self._resolve_entity(channel)
        chat_id = source_metadata['chat_id']
        
        start_date = ensure_utc(start_date) if start_date else None
        end_date = ensure_utc(end_date) if end_date else None
        
        # Lowercase keywords for case-insensitive matching
        keywords_lower = [k.lower() for k in keywords] if keywords else []

        raw_messages = []
        try:
            logger.info(f"Collecting up to {limit} messages from {channel}")
            
            # Note: iter_messages yields from newest to oldest
            async for msg in self.client.iter_messages(entity, limit=limit):
                if not isinstance(msg, Message):
                    # We might want to handle service messages, but standard allows mostly real texts or media
                    pass
                
                msg_date = ensure_utc(msg.date)
                
                if end_date and msg_date > end_date:
                    continue
                if start_date and msg_date < start_date:
                    break # Since it yields from newest, if we hit older than start_date, we stop
                    
                text = msg.message or ""
                
                if keywords_lower:
                    if not text:
                        continue # No text to match keywords
                    text_lower = text.lower()
                    if not any(k in text_lower for k in keywords_lower):
                        continue
                        
                raw_dict = self._message_to_dict(msg, chat_id)
                raw_messages.append(raw_dict)
                
        except Exception as e:
            logger.error(f"Error during message collection: {str(e)}")
            raise TelegramCollectionError(f"Failed to collect messages: {str(e)}")

        now = ensure_utc(datetime.now())

        return {
            "collection_metadata": {
                "platform": "telegram",
                "collected_at": now.isoformat(),
                "source": source_metadata,
                "filters": {
                    "keywords": keywords,
                    "start_date": start_date.isoformat() if start_date else None,
                    "end_date": end_date.isoformat() if end_date else None,
                    "limit": limit
                }
            },
            "data": raw_messages
        }
