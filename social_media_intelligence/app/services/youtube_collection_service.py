import logging
import uuid
from typing import Optional, Dict, Any

from ..collectors.youtube_collector import YouTubeCollector
from ..normalizers.youtube_normalizer import YouTubeNormalizer
from ..storage.raw_storage import RawStorage
from ..storage.processed_storage import ProcessedStorage
from ..exceptions import StorageError

logger = logging.getLogger(__name__)

class YouTubeCollectionService:
    """Service that orchestrates YouTube data collection pipeline."""

    def __init__(self):
        self.normalizer = YouTubeNormalizer()
        self.raw_storage = RawStorage(platform="youtube")
        self.processed_storage = ProcessedStorage(platform="youtube")

    async def _process_collection_result(self, result: Dict[str, Any], query_or_id: str) -> Dict[str, Any]:
        """Process collected raw records into normalized posts and save them."""
        metadata = result.get('collection_metadata', {})
        raw_data = result.get('data', [])
        run_batch_id = metadata.get("source", {}).get("batch_id")
        collection_type = metadata.get("collection_type", "unknown")
        
        # 1. Raw Storage
        metadata["is_final_chunk"] = True
        try:
            raw_output_path = self.raw_storage.save_stream(raw_data, metadata, run_batch_id, is_first_chunk=True)
            # Ensure we don't return raw_output_path if no data was written
            if not raw_data:
                raw_output_path = None
                
            # Compute metadata output path for auditability
            import os
            from ..utils.datetime_utils import get_utc_now
            date_str = get_utc_now().strftime("%Y-%m-%d")
            metadata_output_path = os.path.join(self.raw_storage.base_dir, date_str, run_batch_id, f"collection_{run_batch_id}_metadata.json")
        except StorageError as e:
            logger.error(str(e))
            raise

        # 2. Normalization
        normalized_posts = []
        norm_skipped_count = 0
        raw_reference = {
            "platform": "youtube",
            "raw_file": raw_output_path or ""
        }

        for item in raw_data:
            try:
                post = self.normalizer.normalize(
                    raw_data=item,
                    raw_reference=raw_reference,
                    collection_metadata=metadata
                )
                normalized_posts.append(post)
            except Exception as e:
                # Videos throw NormalizationError to skip intentionally, which is fine
                # Or other malformed data
                logger.debug(f"Record skipped during normalization: {str(e)}")
                norm_skipped_count += 1

        # 3. Processed Storage
        processed_output_path = None
        total_processed = 0
        total_duplicates = 0
        
        if normalized_posts:
            try:
                processed_result = self.processed_storage.save_and_report(normalized_posts)
                processed_output_path = processed_result.get("file_path")
                total_processed = processed_result.get("added_count", 0)
                total_duplicates = processed_result.get("duplicate_count", 0)
            except StorageError as e:
                logger.error(str(e))
                raise

        stats = metadata.get("statistics", {})
        
        return {
            "platform": "youtube",
            "collection_type": collection_type,
            "query_or_id": query_or_id,
            "videos_found": stats.get("videos_found", 0),
            "videos_processed": stats.get("videos_processed", 0),
            "comments_collected": stats.get("comments_collected", 0),
            "replies_collected": stats.get("replies_collected", 0),
            "normalized_posts": len(normalized_posts),
            "persisted_posts": total_processed,
            "collector_duplicates": 0,  # YouTube collector doesn't deduplicate in memory currently
            "storage_duplicates": total_duplicates,
            "normalization_skips": norm_skipped_count,
            "skipped_videos": stats.get("skipped_videos", 0),
            "raw_output_path": raw_output_path,
            "processed_output_path": processed_output_path,
            "metadata_output_path": metadata_output_path,
            "status": metadata.get("status", "success")
        }

    async def collect_by_keyword(
        self,
        query: str,
        video_limit: int = 2,
        comments_per_video: int = 10,
        include_replies: bool = False,
        batch_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Collect videos and comments by keyword."""
        collector = YouTubeCollector()
        is_valid = await collector.validate_connection()
        if not is_valid:
            return {"error": "YouTube API validation failed. Check API key."}
            
        result = await collector.collect_by_keyword(
            query=query,
            video_limit=video_limit,
            comments_per_video=comments_per_video,
            include_replies=include_replies,
            batch_id=batch_id
        )
        return await self._process_collection_result(result, query)

    async def collect_video(
        self,
        video_id: str,
        comments_limit: int = 100,
        include_replies: bool = False,
        batch_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Collect comments for a specific video."""
        collector = YouTubeCollector()
        is_valid = await collector.validate_connection()
        if not is_valid:
            return {"error": "YouTube API validation failed. Check API key."}
            
        result = await collector.collect_video(
            video_id=video_id,
            comments_limit=comments_limit,
            include_replies=include_replies,
            batch_id=batch_id
        )
        return await self._process_collection_result(result, video_id)

    async def collect_channel(
        self,
        channel_id: str,
        video_limit: int = 5,
        comments_per_video: int = 10,
        include_replies: bool = False,
        batch_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Collect videos and comments for a specific channel."""
        collector = YouTubeCollector()
        is_valid = await collector.validate_connection()
        if not is_valid:
            return {"error": "YouTube API validation failed. Check API key."}
            
        result = await collector.collect_channel(
            channel_id=channel_id,
            video_limit=video_limit,
            comments_per_video=comments_per_video,
            include_replies=include_replies,
            batch_id=batch_id
        )
        return await self._process_collection_result(result, channel_id)
