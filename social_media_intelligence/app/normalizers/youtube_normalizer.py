import logging
from typing import Any, Dict, List
from datetime import datetime
from uuid import uuid4

from .base_normalizer import BaseNormalizer
from ..schemas.unified_post import UnifiedPost, Author, EntityType, Content, InteractionMetrics, Relationships, Metadata
from ..utils.datetime_utils import parse_utc_timestamp
from ..utils.entity_extractor import EntityExtractor
from ..exceptions import NormalizationError

logger = logging.getLogger(__name__)

class YouTubeNormalizer(BaseNormalizer[UnifiedPost]):
    """Normalizes raw YouTube API records into UnifiedPost format."""

    def normalize(self, raw_data: Dict[str, Any], raw_reference: Dict[str, str], collection_metadata: Dict[str, Any]) -> UnifiedPost:
        try:
            record_type = raw_data.get("record_type")
            
            # For this milestone, we only normalize comments and replies. Videos remain raw/context-only.
            if record_type == "video":
                raise NormalizationError("Video records are currently treated as context-only and not normalized as UnifiedPosts.")
            elif record_type == "comment":
                return self._normalize_comment(raw_data, raw_reference, collection_metadata)
            elif record_type == "reply":
                return self._normalize_reply(raw_data, raw_reference, collection_metadata)
            else:
                raise NormalizationError(f"Unsupported YouTube record_type: {record_type}")

        except NormalizationError:
            raise
        except Exception as e:
            raise NormalizationError(f"Failed to normalize YouTube record: {e}")

    def _normalize_comment(self, raw_data: Dict[str, Any], raw_reference: Dict[str, str], collection_metadata: Dict[str, Any]) -> UnifiedPost:
        """Normalize a top-level comment thread or comment."""
        # raw_data could be a commentThread resource or a comment resource.
        # commentThreads have a snippet.topLevelComment structure.
        
        snippet = raw_data.get("snippet", {})
        
        # If it's a commentThread, the actual comment is inside topLevelComment
        if "topLevelComment" in snippet:
            comment_resource = snippet["topLevelComment"]
            is_thread = True
            total_reply_count = snippet.get("totalReplyCount", 0)
        else:
            comment_resource = raw_data
            is_thread = False
            total_reply_count = 0
            
        comment_snippet = comment_resource.get("snippet", {})
        
        post_id = f"youtube:comment:{comment_resource.get('id')}"
        video_id = raw_data.get("video_id") or snippet.get("videoId") or comment_snippet.get("videoId")
        
        # Author details
        author_channel_id = comment_snippet.get("authorChannelId", {}).get("value", "unknown")
        author_display_name = comment_snippet.get("authorDisplayName", "unknown")
        
        author = Author(
            entity_type=EntityType.USER,
            user_id=author_channel_id,
            username=author_display_name,
            display_name=author_display_name
        )
        
        # Content
        text_original = comment_snippet.get("textOriginal", "")
        hashtags = EntityExtractor.extract_hashtags(text_original)
        mentions = EntityExtractor.extract_mentions(text_original)
        urls = EntityExtractor.extract_urls(text_original)
        
        content = Content(
            text=text_original,
            hashtags=hashtags,
            mentions=mentions,
            urls=urls
        )
        
        # Timestamps
        published_at_str = comment_snippet.get("publishedAt")
        if not published_at_str:
            raise NormalizationError("Missing publishedAt timestamp")
            
        try:
            timestamp = parse_utc_timestamp(published_at_str)
        except ValueError as e:
            raise NormalizationError(f"Invalid timestamp '{published_at_str}': {e}")
            
        # Interactions
        like_count = comment_snippet.get("likeCount", 0)
        interaction = InteractionMetrics(
            like_count=int(like_count),
            reply_count=int(total_reply_count) if is_thread else None
        )
        
        # Metadata
        metadata = Metadata(
            source_type="youtube",
            collected_at=parse_utc_timestamp(collection_metadata.get("collected_at")),
            dataset_name=collection_metadata.get("dataset_name"),
            message_type="comment",
            video_id=video_id,
            youtube_channel_id=comment_snippet.get("channelId"),
            is_reply=False
        )
        
        return UnifiedPost(
            record_id=uuid4(),
            platform="youtube",
            post_id=post_id,
            author=author,
            content=content,
            timestamp=timestamp,
            interaction=interaction,
            metadata=metadata,
            raw_reference=raw_reference
        )

    def _normalize_reply(self, raw_data: Dict[str, Any], raw_reference: Dict[str, str], collection_metadata: Dict[str, Any]) -> UnifiedPost:
        """Normalize a comment reply."""
        # Replies are always just comment resources
        snippet = raw_data.get("snippet", {})
        
        post_id = f"youtube:reply:{raw_data.get('id')}"
        video_id = raw_data.get("video_id") or snippet.get("videoId")
        parent_id = snippet.get("parentId")
        
        # Author details
        author_channel_id = snippet.get("authorChannelId", {}).get("value", "unknown")
        author_display_name = snippet.get("authorDisplayName", "unknown")
        
        author = Author(
            entity_type=EntityType.USER,
            user_id=author_channel_id,
            username=author_display_name,
            display_name=author_display_name
        )
        
        # Content
        text_original = snippet.get("textOriginal", "")
        hashtags = EntityExtractor.extract_hashtags(text_original)
        mentions = EntityExtractor.extract_mentions(text_original)
        urls = EntityExtractor.extract_urls(text_original)
        
        content = Content(
            text=text_original,
            hashtags=hashtags,
            mentions=mentions,
            urls=urls
        )
        
        # Timestamps
        published_at_str = snippet.get("publishedAt")
        if not published_at_str:
            raise NormalizationError("Missing publishedAt timestamp")
            
        try:
            timestamp = parse_utc_timestamp(published_at_str)
        except ValueError as e:
            raise NormalizationError(f"Invalid timestamp '{published_at_str}': {e}")
            
        # Interactions
        like_count = snippet.get("likeCount", 0)
        interaction = InteractionMetrics(
            like_count=int(like_count)
        )
        
        # Relationships
        relationships = Relationships()
        if parent_id:
            relationships.reply_to_post_id = f"youtube:comment:{parent_id}"
            
        # Metadata
        metadata = Metadata(
            source_type="youtube",
            collected_at=parse_utc_timestamp(collection_metadata.get("collected_at")),
            dataset_name=collection_metadata.get("dataset_name"),
            message_type="reply",
            video_id=video_id,
            youtube_channel_id=snippet.get("channelId"),
            parent_comment_id=parent_id,
            is_reply=True
        )
        
        return UnifiedPost(
            record_id=uuid4(),
            platform="youtube",
            post_id=post_id,
            author=author,
            content=content,
            timestamp=timestamp,
            interaction=interaction,
            relationships=relationships,
            metadata=metadata,
            raw_reference=raw_reference
        )
