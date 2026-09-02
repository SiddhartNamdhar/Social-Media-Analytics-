import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

from ..collectors.telegram_collector import TelegramCollector
from ..normalizers.telegram_normalizer import TelegramNormalizer
from ..storage.raw_storage import RawStorage
from ..storage.processed_storage import ProcessedStorage
from ..exceptions import StorageError, NormalizationError

logger = logging.getLogger(__name__)

class TelegramCollectionService:
    def __init__(self):
        self.collector = TelegramCollector()
        self.normalizer = TelegramNormalizer()
        self.raw_storage = RawStorage(platform="telegram")
        self.processed_storage = ProcessedStorage(platform="telegram")

    async def collect_and_process(
        self,
        channel: str,
        limit: int = 100,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        keywords: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Full pipeline:
        Collect -> Save Raw -> Normalize -> Save Processed -> Return Summary
        """
        
        # 1. Collection
        raw_collection = await self.collector.collect(
            channel=channel,
            limit=limit,
            start_date=start_date,
            end_date=end_date,
            keywords=keywords
        )
        
        raw_data = raw_collection.get('data', [])
        metadata = raw_collection.get('collection_metadata', {})
        
        raw_count = len(raw_data)
        logger.info(f"{raw_count} raw messages collected from {channel}")

        if not raw_data:
            return {
                "platform": "telegram",
                "channel": channel,
                "raw_records_collected": 0,
                "records_normalized": 0,
                "records_skipped": 0,
                "raw_file": None,
                "processed_file": None
            }
            
        # 2. Raw Storage
        try:
            raw_file = self.raw_storage.save(raw_data, metadata)
            logger.info(f"Raw data saved to {raw_file}")
        except StorageError as e:
            logger.error(str(e))
            raise

        # 3. Normalization
        logger.info("Normalizing messages")
        normalized_posts = []
        skipped_count = 0
        raw_reference = {
            "platform": "telegram",
            "raw_file": raw_file
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
                logger.warning(f"Message skipped due to validation/normalization issues: {str(e)}")
                skipped_count += 1
                
        normalized_count = len(normalized_posts)
        logger.info(f"{normalized_count} messages successfully normalized")
        if skipped_count:
            logger.warning(f"{skipped_count} messages skipped")

        # 4. Processed Storage
        processed_file = None
        if normalized_posts:
            try:
                processed_file = self.processed_storage.save(normalized_posts)
                logger.info(f"Processed data saved to {processed_file}")
            except StorageError as e:
                logger.error(str(e))
                raise

        return {
            "platform": "telegram",
            "channel": channel,
            "raw_records_collected": raw_count,
            "records_normalized": normalized_count,
            "records_skipped": skipped_count,
            "raw_file": raw_file,
            "processed_file": processed_file
        }
