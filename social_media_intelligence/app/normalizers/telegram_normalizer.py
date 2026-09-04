from typing import Dict, Any
from datetime import datetime

from .base_normalizer import BaseNormalizer
from ..schemas.unified_post import (
    UnifiedPost, Author, Content, InteractionMetrics, 
    Relationships, Metadata, RawReference, EntityType, PublicMetrics
)
from ..utils.entity_extractor import EntityExtractor
from ..utils.datetime_utils import get_utc_now, ensure_utc
from ..exceptions import NormalizationError

class TelegramNormalizer(BaseNormalizer[UnifiedPost]):
    def normalize(self, raw_data: Dict[str, Any], raw_reference: Dict[str, str], collection_metadata: Dict[str, Any]) -> UnifiedPost:
        """Normalize a raw Telegram message dictionary into a UnifiedPost."""
        try:
            chat_id = raw_data.get('chat_id')
            message_id = raw_data.get('message_id')
            
            if chat_id is None or message_id is None:
                raise ValueError("Missing chat_id or message_id")
                
            post_id = f"telegram:{chat_id}:{message_id}"
            
            source_metadata = collection_metadata.get('source', {})
            
            # Author Resolution
            sender_id = raw_data.get('sender_id')
            if sender_id:
                user_id_str = str(sender_id)
                entity_t = EntityType.USER
            else:
                user_id_str = str(chat_id)
                entity_t = EntityType.CHANNEL if source_metadata.get('entity_type') == 'channel' else EntityType.UNKNOWN

            author = Author(
                entity_type=entity_t,
                user_id=user_id_str,
                username=source_metadata.get('username') if not sender_id else None,
                display_name=source_metadata.get('title') if not sender_id else None,
                public_metrics=PublicMetrics()
            )

            # Content Construction
            text = raw_data.get('text', "")
            content = Content(
                text=text,
                hashtags=EntityExtractor.extract_hashtags(text),
                mentions=EntityExtractor.extract_mentions(text),
                urls=EntityExtractor.extract_urls(text)
            )

            # Timestamp
            date_str = raw_data.get('date')
            try:
                # expecting ISO format string
                timestamp = ensure_utc(datetime.fromisoformat(date_str)) if date_str else get_utc_now()
            except Exception:
                timestamp = get_utc_now()

            # Interaction
            interaction = InteractionMetrics(
                view_count=raw_data.get('views'),
                share_count=raw_data.get('forwards')
            )

            # Relationships
            relationships = Relationships()
            
            reply_to_msg_id = raw_data.get('reply_to_msg_id')
            if reply_to_msg_id is not None:
                relationships.reply_to_post_id = f"telegram:{chat_id}:{reply_to_msg_id}"
                
            fwd_info = raw_data.get('forward_info')
            if fwd_info:
                orig_channel_id = fwd_info.get('original_channel_id')
                # Without original message ID we can't fully construct forwarded_from_post_id reliably based on requirement:
                # "Only construct this ID when both values are known. Otherwise use: null"
                # If Telethon exposes original_msg_id, it is fwd.channel_post
                # Since we didn't extract 'original_message_id' in raw explicitly because it's not always there,
                # we set to None unless provided. (Normally fwd.channel_post for channels).
                pass

            # Metadata
            collected_at_str = collection_metadata.get('collected_at')
            try:
                collected_at = ensure_utc(datetime.fromisoformat(collected_at_str)) if collected_at_str else get_utc_now()
            except Exception:
                collected_at = get_utc_now()

            metadata = Metadata(
                source_type="message",
                conversation_id=str(chat_id),
                collected_at=collected_at,
                original_message_id=message_id,
                chat_id=chat_id,
                message_type=raw_data.get('message_type')
            )
            
            raw_ref = RawReference(
                platform=raw_reference.get('platform', 'telegram'),
                raw_file=raw_reference.get('raw_file', '')
            )
            
            return UnifiedPost(
                platform="telegram",
                post_id=post_id,
                author=author,
                content=content,
                timestamp=timestamp,
                interaction=interaction,
                relationships=relationships,
                metadata=metadata,
                raw_reference=raw_ref
            )
        except Exception as e:
            raise NormalizationError(f"Failed to normalize post data: {str(e)}")
