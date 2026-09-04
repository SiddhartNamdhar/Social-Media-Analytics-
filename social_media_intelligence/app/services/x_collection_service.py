import logging
import uuid
from pathlib import Path
from typing import Optional, Dict, Any

from ..collectors.x_dataset_collector import XDatasetCollector
from ..normalizers.x_normalizer import XNormalizer
from ..storage.raw_storage import RawStorage
from ..storage.processed_storage import ProcessedStorage
from ..exceptions import StorageError

logger = logging.getLogger(__name__)


class XCollectionService:
    """Service that orchestrates the full X dataset collection pipeline.
    
    Flow: Read Dataset Stream -> Save Raw Chunk -> Normalize -> Save Processed Chunk -> Return Summary
    """

    def __init__(self):
        self.normalizer = XNormalizer()
        self.raw_storage = RawStorage(platform="x")
        self.processed_storage = ProcessedStorage(platform="x")

    async def collect_and_process(
        self,
        dataset_path: str,
        limit: Optional[int] = None,
        source_name: Optional[str] = None,
        batch_id: Optional[str] = None,
        dataset_format: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Full pipeline:
        Read Dataset -> Save Raw -> Normalize -> Save Processed -> Return Summary
        """
        # Generate a batch ID for this collection run if not provided
        run_batch_id = batch_id or str(uuid.uuid4())[:8]
        
        # 1. Create collector and collect
        collector = XDatasetCollector(
            dataset_path=dataset_path,
            dataset_format=dataset_format,
            limit=limit,
            source_name=source_name,
            batch_id=run_batch_id
        )

        is_valid = await collector.validate_connection()
        if not is_valid:
            return {
                "platform": "x",
                "dataset": str(dataset_path),
                "total_records": 0,
                "processed_records": 0,
                "skipped_records": 0,
                "duplicate_records": 0,
                "raw_output_path": None,
                "processed_output_path": None,
                "error": "Dataset file is not accessible"
            }

        total_processed = 0
        total_skipped = 0
        total_duplicates = 0
        total_records_read = 0
        
        raw_output_path = None
        processed_output_path = None
        
        is_first_chunk = True

        for chunk_response in collector.collect_stream(limit=limit, chunk_size=5000):
            raw_data = chunk_response.get('data', [])
            metadata = chunk_response.get('collection_metadata', {})
            statistics = metadata.get('statistics', {})
            
            raw_count = len(raw_data)
            if raw_count > 0:
                logger.info(f"{raw_count} raw records loaded in current chunk")

            # 2. Raw Storage (Streaming)
            try:
                raw_file = self.raw_storage.save_stream(raw_data, metadata, run_batch_id, is_first_chunk)
                if not raw_output_path:
                    raw_output_path = raw_file
            except StorageError as e:
                logger.error(str(e))
                raise

            # 3. Normalization
            normalized_posts = []
            norm_skipped_count = 0
            raw_reference = {
                "platform": "x",
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
                    logger.warning(f"Record skipped during normalization: {str(e)}")
                    norm_skipped_count += 1

            normalized_count = len(normalized_posts)
            if normalized_count > 0:
                logger.info(f"{normalized_count} records successfully normalized in current chunk")

            # 4. Processed Storage
            if normalized_posts:
                try:
                    processed_result = self.processed_storage.save_and_report(normalized_posts)
                    if not processed_output_path:
                        processed_output_path = processed_result.get("file_path")
                except StorageError as e:
                    logger.error(str(e))
                    raise

            # Accumulate stats from this chunk's normalization and storage
            total_processed += processed_result.get("added_count", 0) if normalized_posts else 0
            total_skipped += norm_skipped_count
            total_duplicates += processed_result.get("duplicate_count", 0) if normalized_posts else 0
            
            is_first_chunk = False
            final_metadata = metadata

        # Final collector stats are returned in the last chunk
        final_stats = final_metadata.get('statistics', {}) if 'final_metadata' in locals() else {}
        total_records_read = final_stats.get('total_records_read', 0)
        
        # Add collector-level skipped and duplicate counts to the totals
        total_skipped += final_stats.get('skipped_records', 0)
        total_duplicates += final_stats.get('duplicate_records', 0)
        
        return {
            "platform": "x",
            "dataset": Path(dataset_path).name,
            "total_records": total_records_read,
            "processed_records": total_processed,
            "skipped_records": total_skipped,
            "duplicate_records": total_duplicates,
            "raw_output_path": raw_output_path,
            "processed_output_path": processed_output_path
        }
