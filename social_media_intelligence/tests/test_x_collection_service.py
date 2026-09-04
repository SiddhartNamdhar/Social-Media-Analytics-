import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from app.services.x_collection_service import XCollectionService

import asyncio

def test_x_collection_service_deduplication_aggregation():
    """
    Test that XCollectionService correctly aggregates distinct stats
    from the collector, normalizer, and storage without double counting.
    """
    service = XCollectionService()
    
    # We will mock the collector, raw_storage, normalizer, and processed_storage
    mock_collector = MagicMock()
    mock_collector.validate_connection = AsyncMock(return_value=True)
    
    # Create two chunks of data
    chunk1_data = [{"id": "1"}, {"id": "2"}, {"id": "3"}]
    chunk2_data = [{"id": "4"}, {"id": "5"}]
    
    # The collector yields chunk responses
    def mock_collect_stream(**kwargs):
        yield {
            "data": chunk1_data,
            "collection_metadata": {
                "statistics": {
                    "total_records_read": 3,
                    "valid_records": 3,
                    "skipped_records": 0,
                    "duplicate_records": 0
                }
            }
        }
        yield {
            "data": chunk2_data,
            "collection_metadata": {
                "statistics": {
                    "total_records_read": 8,  # total read over both chunks
                    "valid_records": 5,
                    "skipped_records": 1,     # 1 collector skip
                    "duplicate_records": 2    # 2 collector duplicates
                }
            }
        }
    
    mock_collector.collect_stream.side_effect = mock_collect_stream
    
    # Mock normalizer: skip 1 record in chunk 1
    # We will make it raise an exception for {"id": "2"}
    def mock_normalize(raw_data, **kwargs):
        if raw_data["id"] == "2":
            raise Exception("Normalization failed")
        return MagicMock(post_id=raw_data["id"])
    
    service.normalizer.normalize = MagicMock(side_effect=mock_normalize)
    
    # Mock raw storage
    service.raw_storage.save_stream = MagicMock(return_value="/tmp/raw.jsonl")
    
    # Mock processed storage:
    # Chunk 1: 3 raw items -> 2 normalized items (since id:2 skipped) -> save_and_report
    # We mock save_and_report to return 1 added, 1 duplicate
    # Chunk 2: 2 raw items -> 2 normalized items -> save_and_report
    # We mock save_and_report to return 2 added, 0 duplicates
    def mock_save_and_report(normalized_posts):
        if len(normalized_posts) == 2 and normalized_posts[0].post_id == "1":
            # Chunk 1 response
            return {"file_path": "/tmp/processed.jsonl", "added_count": 1, "duplicate_count": 1}
        elif len(normalized_posts) == 2 and normalized_posts[0].post_id == "4":
            # Chunk 2 response
            return {"file_path": "/tmp/processed.jsonl", "added_count": 2, "duplicate_count": 0}
        return {"file_path": "/tmp/processed.jsonl", "added_count": 0, "duplicate_count": 0}

    service.processed_storage.save_and_report = MagicMock(side_effect=mock_save_and_report)
    
    # Run the service with the mocked collector class
    with patch("app.services.x_collection_service.XDatasetCollector", return_value=mock_collector):
        result = asyncio.run(service.collect_and_process(dataset_path="dummy.csv"))
        
        # Exact final summary assertion
        # Total Records = 8 (from final collector stats)
        # Processed Records = 1 (chunk 1) + 2 (chunk 2) = 3
        # Skipped Records = 1 (collector skip) + 1 (normalization skip id:2) = 2
        # Duplicate Records = 2 (collector duplicates) + 1 (chunk 1 storage duplicate) = 3
        
        assert result["total_records"] == 8
        assert result["processed_records"] == 3
        assert result["skipped_records"] == 2
        assert result["duplicate_records"] == 3
