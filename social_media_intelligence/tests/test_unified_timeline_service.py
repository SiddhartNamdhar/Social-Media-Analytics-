import pytest
import os
import json
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from unittest.mock import patch, MagicMock

from app.services.unified_timeline_service import UnifiedTimelineService
from app.schemas.unified_post import UnifiedPost, Author, Content, InteractionMetrics, Relationships, Metadata, RawReference, EntityType

def create_dummy_post(platform, post_id, timestamp):
    return UnifiedPost(
        platform=platform,
        post_id=post_id,
        author=Author(entity_type=EntityType.USER, user_id=f"u_{post_id}"),
        content=Content(text=f"Hello from {platform} at {timestamp}"),
        timestamp=timestamp,
        metadata=Metadata(source_type="test", collected_at="2026-09-05T00:00:00Z"),
        raw_reference=RawReference(platform=platform, raw_file="none")
    )

@pytest.fixture
def dummy_jsonl_files(tmp_path):
    # File 1: X records
    file1 = tmp_path / "x.jsonl"
    with open(file1, 'w') as f:
        # We write out of order to ensure sorting works
        f.write(create_dummy_post("x", "1", "2026-09-05T10:05:00Z").model_dump_json() + '\n')
        f.write(create_dummy_post("x", "3", "2026-09-05T12:00:00Z").model_dump_json() + '\n')
        f.write(create_dummy_post("x", "2", "2026-09-05T07:00:00Z").model_dump_json() + '\n')
        
    # File 2: Telegram records
    file2 = tmp_path / "telegram.jsonl"
    with open(file2, 'w') as f:
        f.write(create_dummy_post("telegram", "1", "2026-09-05T09:30:00Z").model_dump_json() + '\n')
        f.write(create_dummy_post("telegram", "2", "2026-09-05T08:00:00Z").model_dump_json() + '\n')
        # Same timestamp as another record for tie-breaking
        f.write(create_dummy_post("telegram", "3", "2026-09-05T07:00:00Z").model_dump_json() + '\n')

    # File 3: YouTube records
    file3 = tmp_path / "youtube.jsonl"
    with open(file3, 'w') as f:
        f.write(create_dummy_post("youtube", "1", "2026-09-05T11:00:00Z").model_dump_json() + '\n')
        
    # File 4: Invalid/Deduplication records
    file4 = tmp_path / "mixed.jsonl"
    with open(file4, 'w') as f:
        # Invalid schema (not UnifiedPost)
        f.write('{"invalid_field": "yes"}\n')
        # Duplicate of x:1
        f.write(create_dummy_post("x", "1", "2026-09-05T10:05:00Z").model_dump_json() + '\n')
        # Same post_id=1 but platform=youtube (should NOT be duplicate)
        f.write(create_dummy_post("youtube", "1", "2026-09-05T13:00:00Z").model_dump_json() + '\n')

    return [str(file1), str(file2), str(file3), str(file4)]


def test_unified_timeline_integration(dummy_jsonl_files, monkeypatch, tmp_path):
    service = UnifiedTimelineService()
    # Override output dir to tmp_path
    monkeypatch.setattr(service, "base_output_dir", str(tmp_path / "unified"))
    
    stats = service.build_timeline(
        input_paths=dummy_jsonl_files,
        batch_id="test_batch",
        chunk_size=10  # Enough to fit in one chunk for basic tests
    )
    
    # Assertions on stats
    assert stats["total_records_read"] == 10
    assert stats["invalid_records"] == 1
    assert stats["valid_records"] == 9
    assert stats["duplicate_records"] == 2
    assert stats["final_timeline_records"] == 7
    
    assert stats["records_by_platform"]["x"] == 3
    assert stats["records_by_platform"]["telegram"] == 3
    assert stats["records_by_platform"]["youtube"] == 1
    
    # Wait, the second youtube:1 is post_id="1", platform="youtube".
    # The first youtube:1 in file3 is also post_id="1", platform="youtube".
    # So it should be a duplicate!
    
    assert os.path.exists(stats["output_path"])
    
    # Check chronological ordering and tie-breakers
    with open(stats["output_path"], 'r') as f:
        lines = f.readlines()
        
    assert len(lines) == 7
    
    timestamps = [json.loads(line)["timestamp"] for line in lines]
    assert timestamps == sorted(timestamps)
    
    # Ensure the tie-breaker records are both present (telegram:3 and x:2 both have 07:00:00Z)
    assert timestamps[0] == "2026-09-05T07:00:00Z"
    assert timestamps[1] == "2026-09-05T07:00:00Z"
    
def test_external_merge_sort(monkeypatch, tmp_path):
    """
    Explicit test for external merge sort with chunk_size=2.
    Input order:
    10:00 X
    08:00 Telegram
    11:00 YouTube
    07:00 X
    09:00 Telegram
    """
    service = UnifiedTimelineService()
    monkeypatch.setattr(service, "base_output_dir", str(tmp_path / "unified"))
    
    input_file = tmp_path / "input.jsonl"
    with open(input_file, 'w') as f:
        f.write(create_dummy_post("x", "1", "2026-09-05T10:00:00Z").model_dump_json() + '\n')
        f.write(create_dummy_post("telegram", "1", "2026-09-05T08:00:00Z").model_dump_json() + '\n')
        f.write(create_dummy_post("youtube", "1", "2026-09-05T11:00:00Z").model_dump_json() + '\n')
        f.write(create_dummy_post("x", "2", "2026-09-05T07:00:00Z").model_dump_json() + '\n')
        f.write(create_dummy_post("telegram", "2", "2026-09-05T09:00:00Z").model_dump_json() + '\n')

    # Mock the temporary file creation to verify multiple chunks are made
    original_tempfile = NamedTemporaryFile
    chunk_files_created = []

    def mock_tempfile(*args, **kwargs):
        tf = original_tempfile(*args, **kwargs)
        chunk_files_created.append(tf.name)
        return tf

    with patch('app.services.unified_timeline_service.NamedTemporaryFile', side_effect=mock_tempfile):
        stats = service.build_timeline(
            input_paths=[str(input_file)],
            batch_id="test_merge",
            chunk_size=2
        )
        
    # We have 5 valid records, chunk_size=2 -> 3 chunks expected
    assert len(chunk_files_created) == 3
    assert stats["total_records_read"] == 5
    assert stats["valid_records"] == 5
    assert stats["final_timeline_records"] == 5

    # Check output is completely sorted
    with open(stats["output_path"], 'r') as f:
        lines = f.readlines()
        
    timestamps = [json.loads(line)["timestamp"] for line in lines]
    expected_order = [
        "2026-09-05T07:00:00Z",
        "2026-09-05T08:00:00Z",
        "2026-09-05T09:00:00Z",
        "2026-09-05T10:00:00Z",
        "2026-09-05T11:00:00Z"
    ]
    assert timestamps == expected_order
