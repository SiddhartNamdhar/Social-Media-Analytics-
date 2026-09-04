import logging
import uuid
from pathlib import Path
from typing import Optional, Dict, Any

from ..collectors.x_network_collector import XNetworkCollector
from ..normalizers.x_network_normalizer import XNetworkNormalizer
from ..storage.raw_storage import RawStorage
from ..storage.network_storage import NetworkStorage
from ..exceptions import StorageError

logger = logging.getLogger(__name__)


class XNetworkService:
    """Service that orchestrates the X network edge collection pipeline."""

    def __init__(self):
        self.normalizer = XNetworkNormalizer()
        # The prompt requested raw network storage to be under raw/x_network
        self.raw_storage = RawStorage(platform="x_network")
        self.network_storage = NetworkStorage(platform="x")

    async def collect_and_process(
        self,
        dataset_path: str,
        relationship_type: str = "UNKNOWN",
        limit: Optional[int] = None,
        delimiter: Optional[str] = None,
        has_header: bool = False,
        source_column: int = 0,
        target_column: int = 1,
        timestamp_column: Optional[int] = None,
        weight_column: Optional[int] = None,
        batch_id: Optional[str] = None
    ) -> Dict[str, Any]:
        
        run_batch_id = batch_id or str(uuid.uuid4())[:8]
        
        collector = XNetworkCollector(
            dataset_path=dataset_path,
            relationship_type=relationship_type,
            limit=limit,
            delimiter=delimiter,
            has_header=has_header,
            source_column=source_column,
            target_column=target_column,
            timestamp_column=timestamp_column,
            weight_column=weight_column,
            batch_id=run_batch_id
        )

        is_valid = await collector.validate_connection()
        if not is_valid:
            return {
                "platform": "x",
                "dataset_type": "network",
                "relationship_type": relationship_type.upper(),
                "total_edges": 0,
                "processed_edges": 0,
                "skipped_edges": 0,
                "duplicate_edges": 0,
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

        for chunk_response in collector.collect_stream(limit=limit, chunk_size=10000):
            raw_data = chunk_response.get('data', [])
            metadata = chunk_response.get('collection_metadata', {})
            statistics = metadata.get('statistics', {})
            
            raw_count = len(raw_data)
            if raw_count > 0:
                logger.info(f"{raw_count} raw edges loaded in current chunk")

            # Raw Storage
            try:
                raw_file = self.raw_storage.save_stream(raw_data, metadata, run_batch_id, is_first_chunk)
                if not raw_output_path:
                    raw_output_path = raw_file
            except StorageError as e:
                logger.error(str(e))
                raise

            # Normalization
            normalized_edges = []
            norm_skipped_count = 0
            raw_reference = {
                "platform": "x",
                "raw_file": raw_output_path or ""
            }

            for item in raw_data:
                try:
                    edge = self.normalizer.normalize(
                        raw_data=item,
                        raw_reference=raw_reference,
                        collection_metadata=metadata
                    )
                    normalized_edges.append(edge)
                except Exception as e:
                    logger.warning(f"Edge skipped during normalization: {str(e)}")
                    norm_skipped_count += 1

            normalized_count = len(normalized_edges)
            if normalized_count > 0:
                logger.info(f"{normalized_count} edges successfully normalized in current chunk")

            # Processed Storage
            if normalized_edges:
                try:
                    processed_result = self.network_storage.save_and_report(normalized_edges)
                    if not processed_output_path:
                        processed_output_path = processed_result.get("file_path")
                except StorageError as e:
                    logger.error(str(e))
                    raise

            # Accumulate stats
            total_processed += processed_result.get("added_count", 0) if normalized_edges else 0
            total_skipped += norm_skipped_count
            total_duplicates += processed_result.get("duplicate_count", 0) if normalized_edges else 0
            
            is_first_chunk = False
            final_metadata = metadata

        final_stats = final_metadata.get('statistics', {}) if 'final_metadata' in locals() else {}
        total_records_read = final_stats.get('total_edges_read', 0)
        
        total_skipped += final_stats.get('skipped_edges', 0)
        total_duplicates += final_stats.get('duplicate_edges', 0)
        rel_type = final_stats.get('relationship_type', relationship_type.upper())
        delim = final_stats.get('delimiter', delimiter)

        return {
            "platform": "x",
            "dataset_type": "network",
            "relationship_type": rel_type,
            "delimiter": delim,
            "total_edges": total_records_read,
            "processed_edges": total_processed,
            "skipped_edges": total_skipped,
            "duplicate_edges": total_duplicates,
            "raw_output_path": raw_output_path,
            "processed_output_path": processed_output_path
        }
