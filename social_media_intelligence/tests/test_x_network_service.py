import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from app.services.x_network_service import XNetworkService

import asyncio

@patch('app.services.x_network_service.NetworkStorage')
def test_x_network_service_deduplication_aggregation(mock_network_storage_class):
    """
    Test that XNetworkService correctly aggregates distinct stats
    from the collector, normalizer, and storage without double counting.
    """
    service = XNetworkService()
    
    # We will mock the collector, raw_storage, normalizer
    mock_collector = MagicMock()
    mock_collector.validate_connection = AsyncMock(return_value=True)
    
    # Create two chunks of data
    chunk1_data = [{"source": "A", "target": "B"}, {"source": "B", "target": "C"}]
    chunk2_data = [{"source": "C", "target": "D"}]
    
    # The collector yields chunk responses
    def mock_collect_stream(**kwargs):
        yield {
            "data": chunk1_data,
            "collection_metadata": {
                "statistics": {
                    "total_edges_read": 2,
                    "valid_edges": 2,
                    "skipped_edges": 0,
                    "duplicate_edges": 0
                }
            }
        }
        yield {
            "data": chunk2_data,
            "collection_metadata": {
                "statistics": {
                    "total_edges_read": 6,  # total read over both chunks
                    "valid_edges": 3,
                    "skipped_edges": 1,     # 1 collector skip
                    "duplicate_edges": 2    # 2 collector duplicates
                }
            }
        }
    
    mock_collector.collect_stream.side_effect = mock_collect_stream
    
    # Mock normalizer: skip 1 record in chunk 1
    # We will make it raise an exception for {"source": "B", "target": "C"}
    def mock_normalize(raw_data, **kwargs):
        if raw_data["source"] == "B":
            raise Exception("Normalization failed")
        return MagicMock(edge_id=f"{raw_data['source']}-{raw_data['target']}")
    
    service.normalizer.normalize = MagicMock(side_effect=mock_normalize)
    
    # Mock raw storage
    service.raw_storage.save_stream = MagicMock(return_value="/tmp/raw_edges.jsonl")
    
    # Mock processed storage:
    mock_network_storage_instance = mock_network_storage_class.return_value
    
    def mock_save_and_report(normalized_edges):
        if len(normalized_edges) == 1 and normalized_edges[0].edge_id == "A-B":
            # Chunk 1 response
            return {"file_path": "/tmp/processed_edges.jsonl", "added_count": 0, "duplicate_count": 1}
        elif len(normalized_edges) == 1 and normalized_edges[0].edge_id == "C-D":
            # Chunk 2 response
            return {"file_path": "/tmp/processed_edges.jsonl", "added_count": 1, "duplicate_count": 0}
        return {"file_path": "/tmp/processed_edges.jsonl", "added_count": 0, "duplicate_count": 0}

    mock_network_storage_instance.save_and_report.side_effect = mock_save_and_report
    
    # Run the service with the mocked collector class
    with patch("app.services.x_network_service.XNetworkCollector", return_value=mock_collector):
        result = asyncio.run(service.collect_and_process(dataset_path="dummy.edgelist"))
        
        # Exact final summary assertion
        # Total Edges = 6 (from final collector stats)
        # Processed Edges = 0 (chunk 1) + 1 (chunk 2) = 1
        # Skipped Edges = 1 (collector skip) + 1 (normalization skip B-C) = 2
        # Duplicate Edges = 2 (collector duplicates) + 1 (chunk 1 storage duplicate) = 3
        
        assert result["total_edges"] == 6
        assert result["processed_edges"] == 1
        assert result["skipped_edges"] == 2
        assert result["duplicate_edges"] == 3
