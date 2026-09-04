import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timezone

from .base_normalizer import BaseNormalizer
from ..schemas.unified_post import (
    UnifiedPost, Author, Content, InteractionMetrics,
    Relationships, Metadata, RawReference, EntityType, PublicMetrics
)
from ..utils.entity_extractor import EntityExtractor
from ..utils.datetime_utils import ensure_utc, get_utc_now
from ..exceptions import NormalizationError

logger = logging.getLogger(__name__)

# Common Twitter datetime formats to try during parsing
TWITTER_DATE_FORMATS = [
    "%a %b %d %H:%M:%S %z %Y",    # Wed Sep 03 12:30:00 +0000 2026
    "%Y-%m-%dT%H:%M:%S.%fZ",       # 2026-09-03T12:30:00.000Z
    "%Y-%m-%dT%H:%M:%SZ",          # 2026-09-03T12:30:00Z
    "%Y-%m-%d %H:%M:%S",           # 2026-09-03 12:30:00
    "%Y-%m-%d",                     # 2026-09-03
]


class XNormalizer(BaseNormalizer[UnifiedPost]):
    """Normalize raw X/Twitter dataset records into UnifiedPost objects."""

    def normalize(
        self,
        raw_data: Dict[str, Any],
        raw_reference: Dict[str, str],
        collection_metadata: Optional[Dict[str, Any]] = None
    ) -> UnifiedPost:
        """Normalize a mapped X dataset record into a UnifiedPost."""
        try:
            collection_metadata = collection_metadata or {}
            source_info = collection_metadata.get('source', {})
            
            # Post ID
            post_id_raw = raw_data.get('post_id')
            if post_id_raw is not None:
                post_id_str = str(post_id_raw)
                post_id = f"x:{post_id_str}" if not post_id_str.startswith("x:") else post_id_str
            else:
                import hashlib
                text = str(raw_data.get('text', ''))
                created_at = str(raw_data.get('created_at', ''))
                author_id_str = str(raw_data.get('author_id', ''))
                hash_input = f"{text}|{created_at}|{author_id_str}"
                digest = hashlib.sha256(hash_input.encode('utf-8')).hexdigest()[:16]
                post_id = f"x:hash:{digest}"
                post_id_raw = post_id

            # Author
            author_id = raw_data.get('author_id')
            username = raw_data.get('username')
            display_name = raw_data.get('display_name')
            
            author = Author(
                entity_type=EntityType.USER,
                user_id=str(author_id) if author_id else "unknown",
                username=str(username) if username else None,
                display_name=str(display_name) if display_name else None,
                public_metrics=PublicMetrics()
            )

            # Content
            text = str(raw_data.get('text', ''))
            
            hashtags = self._parse_list_field(raw_data.get('hashtags'))
            if not hashtags:
                hashtags = EntityExtractor.extract_hashtags(text)
            
            mentions = self._parse_list_field(raw_data.get('mentions'))
            if not mentions:
                mentions = EntityExtractor.extract_mentions(text)
            
            urls = self._parse_list_field(raw_data.get('urls'))
            if not urls:
                urls = EntityExtractor.extract_urls(text)
            
            # Deduplicate while preserving order
            hashtags = list(dict.fromkeys(hashtags))
            mentions = list(dict.fromkeys(mentions))
            urls = list(dict.fromkeys(urls))
            
            language = raw_data.get('language')
            
            content = Content(
                text=text,
                language=str(language) if language else None,
                hashtags=hashtags,
                mentions=mentions,
                urls=urls
            )

            # Timestamp
            timestamp = self._parse_timestamp(raw_data.get('created_at'))

            # Interaction Metrics
            interaction = InteractionMetrics(
                like_count=self._safe_int(raw_data.get('like_count')),
                reply_count=self._safe_int(raw_data.get('reply_count')),
                share_count=self._safe_int(raw_data.get('retweet_count')),
                quote_count=self._safe_int(raw_data.get('quote_count')),
                view_count=self._safe_int(raw_data.get('view_count')),
            )

            # Relationships
            relationships = Relationships()
            reply_to = raw_data.get('reply_to_status_id')
            if reply_to is not None:
                reply_to_str = str(reply_to).strip()
                if reply_to_str and reply_to_str.lower() not in ('none', 'nan', ''):
                    relationships.reply_to_post_id = f"x:{reply_to_str}"

            # Metadata
            collected_at_str = collection_metadata.get('collected_at')
            try:
                collected_at = ensure_utc(datetime.fromisoformat(collected_at_str)) if collected_at_str else get_utc_now()
            except Exception:
                collected_at = get_utc_now()

            dataset_name = source_info.get('source_name') or source_info.get('dataset_file')

            metadata = Metadata(
                source_type="dataset",
                collected_at=collected_at,
                message_type="post",
                dataset_name=str(dataset_name) if dataset_name else None,
                original_post_id=str(post_id_raw) if post_id_raw else None,
            )

            raw_ref = RawReference(
                platform=raw_reference.get('platform', 'x'),
                raw_file=raw_reference.get('raw_file', '')
            )

            return UnifiedPost(
                platform="x",
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
            raise NormalizationError(f"Failed to normalize X post data: {str(e)}")

    # =========================================================================
    # Helper methods
    # =========================================================================

    @staticmethod
    def _parse_timestamp(value: Any) -> datetime:
        """Parse a timestamp from various common formats used in X datasets."""
        if value is None:
            raise NormalizationError("Missing timestamp")
        
        value_str = str(value).strip()
        if not value_str or value_str.lower() in ('none', 'nan', 'nat'):
            raise NormalizationError("Missing timestamp")
            
        # Replace common legacy timezone abbreviations to UTC offsets
        tz_replacements = {
            " PDT ": " -0700 ",
            " PST ": " -0800 ",
            " EDT ": " -0400 ",
            " EST ": " -0500 "
        }
        for tz_str, offset in tz_replacements.items():
            if tz_str in value_str:
                value_str = value_str.replace(tz_str, offset)
        
        # Try unix timestamp (int or float)
        try:
            ts = float(value_str)
            # Distinguish seconds vs milliseconds
            if ts > 1e12:
                ts = ts / 1000.0
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            return dt
        except (ValueError, OverflowError, OSError):
            pass
        
        # Try ISO format first (most common)
        try:
            dt = datetime.fromisoformat(value_str.replace('Z', '+00:00'))
            return ensure_utc(dt)
        except (ValueError, AttributeError):
            pass
        
        # Try known Twitter date formats
        for fmt in TWITTER_DATE_FORMATS:
            try:
                dt = datetime.strptime(value_str, fmt)
                return ensure_utc(dt)
            except ValueError:
                continue
        
        # Could not parse — strict rejection per requirements
        raise NormalizationError(f"Could not parse timestamp: '{value_str}'")

    @staticmethod
    def _safe_int(value: Any) -> Optional[int]:
        """Safely convert a value to an integer. Returns None on failure."""
        if value is None:
            return None
        
        value_str = str(value).strip()
        if not value_str or value_str.lower() in ('none', 'nan', 'null', ''):
            return None
        
        try:
            return int(float(value_str))
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _parse_list_field(value: Any) -> List[str]:
        """Parse a field that may be a list, JSON string, or comma-separated string."""
        if value is None:
            return []
        
        if isinstance(value, list):
            return [str(v) for v in value if v]
        
        value_str = str(value).strip()
        if not value_str or value_str.lower() in ('none', 'nan', '[]', ''):
            return []
        
        # Try JSON array
        try:
            parsed = json.loads(value_str)
            if isinstance(parsed, list):
                return [str(v) for v in parsed if v]
        except (json.JSONDecodeError, TypeError):
            pass
        
        # Comma-separated fallback
        return [item.strip() for item in value_str.split(',') if item.strip()]


# Required import for _parse_list_field JSON parsing
import json
