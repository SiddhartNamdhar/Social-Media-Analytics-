import pytest
import os
import json
from pathlib import Path
from app.storage.network_storage import NetworkStorage
from app.schemas.unified_edge import UnifiedEdge

@pytest.fixture
def dummy_edges():
    return [
        UnifiedEdge(
            edge_id="e1",
            source_user_id="u1",
            target_user_id="u2",
            relationship_type="MENTION",
            platform="x",
            collected_at="2026-09-05T00:00:00Z"
        ),
        UnifiedEdge(
            edge_id="e2",
            source_user_id="u3",
            target_user_id="u4",
            relationship_type="MENTION",
            platform="x",
            collected_at="2026-09-05T00:00:00Z"
        )
    ]

def test_existing_behavior_compatible(monkeypatch, tmp_path):
    # Mock settings to point to tmp_path
    monkeypatch.setattr("app.storage.network_storage.settings.DATA_DIRECTORY", str(tmp_path))
    
    storage = NetworkStorage(platform="x")
    edges = [
        UnifiedEdge(
            edge_id="e1",
            source_user_id="u1",
            target_user_id="u2",
            relationship_type="REPOST",
            platform="x",
            collected_at="2026-09-05T00:00:00Z"
        )
    ]
    
    result = storage.save_and_report(edges)
    
    assert result["added_count"] == 1
    assert result["duplicate_count"] == 0
    
    file_path = result["file_path"]
    assert "x_network" in file_path
    assert os.path.exists(file_path)

def test_different_batch_ids_produce_different_output_files(monkeypatch, tmp_path, dummy_edges):
    monkeypatch.setattr("app.storage.network_storage.settings.DATA_DIRECTORY", str(tmp_path))
    
    storage1 = NetworkStorage(platform="x", batch_id="batch1")
    result1 = storage1.save_and_report([dummy_edges[0]])
    
    storage2 = NetworkStorage(platform="x", batch_id="batch2")
    result2 = storage2.save_and_report([dummy_edges[1]])
    
    path1 = result1["file_path"]
    path2 = result2["file_path"]
    
    assert "batch1" in path1
    assert "batch2" in path2
    assert path1 != path2
    assert os.path.exists(path1)
    assert os.path.exists(path2)

def test_same_batch_id_reuses_the_same_file(monkeypatch, tmp_path, dummy_edges):
    monkeypatch.setattr("app.storage.network_storage.settings.DATA_DIRECTORY", str(tmp_path))
    
    storage1 = NetworkStorage(platform="x", batch_id="batch_same")
    result1 = storage1.save_and_report([dummy_edges[0]])
    
    storage2 = NetworkStorage(platform="x", batch_id="batch_same")
    result2 = storage2.save_and_report([dummy_edges[1]])
    
    path1 = result1["file_path"]
    path2 = result2["file_path"]
    
    assert path1 == path2
    
    with open(path1, 'r') as f:
        lines = f.readlines()
        assert len(lines) == 2

def test_duplicate_edge_detection_works(monkeypatch, tmp_path, dummy_edges):
    monkeypatch.setattr("app.storage.network_storage.settings.DATA_DIRECTORY", str(tmp_path))
    
    storage1 = NetworkStorage(platform="x", batch_id="batch_dup")
    result1 = storage1.save_and_report(dummy_edges)
    
    assert result1["added_count"] == 2
    assert result1["duplicate_count"] == 0
    
    # Try saving the exact same edges again using a new storage instance but same batch
    storage2 = NetworkStorage(platform="x", batch_id="batch_dup")
    result2 = storage2.save_and_report(dummy_edges)
    
    assert result2["added_count"] == 0
    assert result2["duplicate_count"] == 2
