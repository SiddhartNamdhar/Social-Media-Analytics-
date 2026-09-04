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
