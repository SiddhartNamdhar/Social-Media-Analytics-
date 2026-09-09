import pytest
import tempfile
import gzip
from pathlib import Path

from app.collectors.x_network_collector import XNetworkCollector


@pytest.fixture
def temp_dataset_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


def test_edgelist_whitespace(temp_dataset_dir):
    file_path = temp_dataset_dir / "network.edgelist"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("userA userB 1672531200 1.5\n")
        f.write("userC userD\n")

    collector = XNetworkCollector(
        str(file_path),
        relationship_type="REPOST",
        timestamp_column=2,
        weight_column=3
    )
    
    chunks = list(collector.collect_stream())
    data = [item for chunk in chunks for item in chunk['data']]
    
    assert len(data) == 2
    assert data[0]["source"] == "userA"
    assert data[0]["target"] == "userB"
    assert data[0]["relationship_type"] == "REPOST"
    assert data[0]["timestamp"] == "1672531200"
    assert data[0]["weight"] == "1.5"

    assert data[1]["source"] == "userC"
    assert data[1]["target"] == "userD"
    assert "timestamp" not in data[1]


def test_edgelist_csv_gz(temp_dataset_dir):
    file_path = temp_dataset_dir / "network.edgelist.gz"
    with gzip.open(file_path, "wt", encoding="utf-8") as f:
        f.write("source,target\n")
        f.write("userA,userB\n")

    collector = XNetworkCollector(
        str(file_path),
        relationship_type="FOLLOW",
        delimiter=",",
        has_header=True
    )
    
    assert collector.compressed is True
    
    chunks = list(collector.collect_stream())
    data = [item for chunk in chunks for item in chunk['data']]
    
    assert len(data) == 1
    assert data[0]["source"] == "userA"
    assert data[0]["target"] == "userB"

def test_edgelist_deduplication(temp_dataset_dir):
    file_path = temp_dataset_dir / "network_dup.edgelist"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("userA userB\n")
        f.write("userA userB\n") # Duplicate
        f.write("userB userA\n") # Not duplicate (reversed)
        f.write("userC userD\n")

    collector = XNetworkCollector(
        str(file_path),
        relationship_type="REPOST"
    )
    
    chunks = list(collector.collect_stream())
    data = [item for chunk in chunks for item in chunk['data']]
    
    assert len(data) == 3
    
    last_metadata = chunks[-1]["collection_metadata"]
    assert last_metadata["statistics"]["duplicate_edges"] == 1
    assert last_metadata["statistics"]["valid_edges"] == 3

def test_relationship_type_differentiates_edges(temp_dataset_dir):
    file_path = temp_dataset_dir / "network_rel.edgelist"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("userA userB\n")
        f.write("userA userB\n")

    collector_mention = XNetworkCollector(
        str(file_path),
        relationship_type="MENTION"
    )
    chunks_mention = list(collector_mention.collect_stream())
    data_mention = [item for chunk in chunks_mention for item in chunk['data']]
    
    collector_reply = XNetworkCollector(
        str(file_path),
        relationship_type="REPLY"
    )
    chunks_reply = list(collector_reply.collect_stream())
    data_reply = [item for chunk in chunks_reply for item in chunk['data']]
    
    assert len(data_mention) == 1
    assert data_mention[0]["relationship_type"] == "MENTION"
    
    assert len(data_reply) == 1
    assert data_reply[0]["relationship_type"] == "REPLY"

def test_duplicate_detection_across_chunks(temp_dataset_dir):
    file_path = temp_dataset_dir / "network_chunks.edgelist"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("userA userB\n")
        f.write("userC userD\n")
        f.write("userE userF\n")
        f.write("userA userB\n") # Duplicate
        f.write("userG userH\n")

    collector = XNetworkCollector(
        str(file_path),
        relationship_type="REPOST"
    )
    
    chunks = list(collector.collect_stream(chunk_size=2))
    data = [item for chunk in chunks for item in chunk['data']]
    
    assert len(data) == 4
    
    last_metadata = chunks[-1]["collection_metadata"]
    assert last_metadata["statistics"]["duplicate_edges"] == 1
    assert last_metadata["statistics"]["valid_edges"] == 4
    assert last_metadata["statistics"]["total_edges_read"] == 5

def test_duplicates_do_not_consume_limit(temp_dataset_dir):
    file_path = temp_dataset_dir / "network_limit.edgelist"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("userA userB\n")
        f.write("userA userB\n") # Duplicate
        f.write("userA userB\n") # Duplicate
        f.write("userC userD\n")
        f.write("userE userF\n")

    collector = XNetworkCollector(
        str(file_path),
        relationship_type="REPOST"
    )
    
    chunks = list(collector.collect_stream(limit=3))
    data = [item for chunk in chunks for item in chunk['data']]
    
    assert len(data) == 3
    
    last_metadata = chunks[-1]["collection_metadata"]
    assert last_metadata["statistics"]["duplicate_edges"] == 2
    assert last_metadata["statistics"]["valid_edges"] == 3
