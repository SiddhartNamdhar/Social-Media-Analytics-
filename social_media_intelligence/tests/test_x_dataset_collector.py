import pytest
import tempfile
import json
import gzip
import csv
from pathlib import Path

from app.collectors.x_dataset_collector import XDatasetCollector
from app.exceptions import XDatasetFormatError


@pytest.fixture
def temp_dataset_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


def test_csv_gzip_support(temp_dataset_dir):
    file_path = temp_dataset_dir / "tweets.csv.gz"
    
    with gzip.open(file_path, 'wt', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['id', 'text', 'author_id', 'created_at'])
        writer.writerow(['1', 'hello', 'user1', '2026-09-03'])
        
    collector = XDatasetCollector(str(file_path))
    assert collector.compressed is True
    assert collector.dataset_format == 'csv'
    
    chunks = list(collector.collect_stream())
    data = [item for chunk in chunks for item in chunk['data']]
    assert len(data) == 1
    assert data[0]['post_id'] == '1'


def test_jsonl_gzip_support(temp_dataset_dir):
    file_path = temp_dataset_dir / "tweets.jsonl.gz"
    
    with gzip.open(file_path, 'wt', encoding='utf-8') as f:
        f.write(json.dumps({'id': '1', 'text': 'hello', 'user_id': 'user1', 'created_at': '2026-09-03'}) + '\n')
        
    collector = XDatasetCollector(str(file_path))
    assert collector.compressed is True
    assert collector.dataset_format == 'jsonl'
    
    chunks = list(collector.collect_stream())
    data = [item for chunk in chunks for item in chunk['data']]
    assert len(data) == 1
    assert data[0]['post_id'] == '1'


def test_json_streaming_support(temp_dataset_dir):
    file_path = temp_dataset_dir / "tweets.json"
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump({"data": [{"id": "1", "text": "hello", "created_at": "2026-09-03"}, {"id": "2", "text": "world", "created_at": "2026-09-04"}]}, f)
        
    collector = XDatasetCollector(str(file_path))
    assert collector.compressed is False
    assert collector.dataset_format == 'json'
    
    chunks = list(collector.collect_stream(chunk_size=1))
    data = [item for chunk in chunks for item in chunk['data']]
    assert len(data) == 2
    assert data[0]['post_id'] == '1'
    assert data[1]['post_id'] == '2'

def test_json_gzip_support(temp_dataset_dir):
    file_path = temp_dataset_dir / "tweets.json.gz"
    
    with gzip.open(file_path, 'wt', encoding='utf-8') as f:
        json.dump({"data": [{"id": "1", "text": "hello", "created_at": "2026-09-03"}]}, f)
        
    collector = XDatasetCollector(str(file_path))
    assert collector.compressed is True
    assert collector.dataset_format == 'json'
    
    chunks = list(collector.collect_stream())
    data = [item for chunk in chunks for item in chunk['data']]
    assert len(data) == 1
    assert data[0]['post_id'] == '1'


def test_json_auto_detect_jsonl(temp_dataset_dir):
    """Test that a file with .json extension but JSONL content is auto-detected."""
    file_path = temp_dataset_dir / "wrong_extension.json"
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write('{"id": "1", "text": "t1", "created_at": "2026-09-03"}\n')
        f.write('{"id": "2", "text": "t2", "created_at": "2026-09-04"}\n')
        
    collector = XDatasetCollector(str(file_path))
    chunks = list(collector.collect_stream())
    data = [item for chunk in chunks for item in chunk['data']]
    assert len(data) == 2


def test_json_no_false_jsonl(temp_dataset_dir):
    """Test that pretty-printed JSON is not falsely detected as JSONL."""
    file_path = temp_dataset_dir / "pretty.json"
    
    # First line is `{` which is not a valid JSON dict on its own
    content = """{
        "data": [
            {"id": "1", "text": "t1", "created_at": "2026-09-03"}
        ]
    }"""
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
        
    collector = XDatasetCollector(str(file_path))
    chunks = list(collector.collect_stream())
    data = [item for chunk in chunks for item in chunk['data']]
    assert len(data) == 1
    assert data[0]['post_id'] == '1'


def test_case_insensitive_mapping(temp_dataset_dir):
    """Test that mapping is case-insensitive for headers but _original preserves case."""
    file_path = temp_dataset_dir / "mixed_case.jsonl"
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write('{"TweetId": "1", "TEXT": "t1", "CreatedAt": "2026-09-03"}\n')
        
    collector = XDatasetCollector(str(file_path))
    chunks = list(collector.collect_stream())
    data = [item for chunk in chunks for item in chunk['data']]
    assert len(data) == 1
    assert data[0]['post_id'] == '1'
    assert data[0]['text'] == 't1'
    assert data[0]['created_at'] == '2026-09-03'
    # Original preserves exact case
    assert "TweetId" in data[0]['_original']


def test_validation_rejection(temp_dataset_dir):
    """Test that records missing text or timestamp are skipped."""
    file_path = temp_dataset_dir / "invalid.jsonl"
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write('{"id": "1", "text": "t1", "created_at": "2026-09-03"}\n') # valid
        f.write('{"id": "2", "text": "", "created_at": "2026-09-03"}\n') # missing text
        f.write('{"id": "3", "text": "t3"}\n') # missing timestamp
        
    collector = XDatasetCollector(str(file_path))
    chunks = list(collector.collect_stream())
    data = [item for chunk in chunks for item in chunk['data']]
    assert len(data) == 1
    assert data[0]['post_id'] == '1'
    
    stats = chunks[-1]['collection_metadata']['statistics']
    assert stats['skipped_records'] == 2
