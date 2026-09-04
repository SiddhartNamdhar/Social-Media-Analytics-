import pytest
from app.normalizers.x_normalizer import XNormalizer
from app.exceptions import NormalizationError

def test_missing_timestamp_raises_error():
    normalizer = XNormalizer()
    raw_data = {
        "post_id": "123",
        "author_id": "user1",
        "text": "test"
    }
    
    with pytest.raises(NormalizationError, match="Missing timestamp"):
        normalizer.normalize(raw_data, {"platform": "x", "raw_file": ""})

def test_invalid_timestamp_raises_error():
    normalizer = XNormalizer()
    raw_data = {
        "post_id": "123",
        "author_id": "user1",
        "text": "test",
        "created_at": "invalid date"
    }
    
    with pytest.raises(NormalizationError, match="Could not parse timestamp"):
        normalizer.normalize(raw_data, {"platform": "x", "raw_file": ""})

def test_missing_post_id_generates_hash():
    normalizer = XNormalizer()
    raw_data = {
        "author_id": "user1",
        "text": "test content",
        "created_at": "2026-09-03"
    }
    
    post = normalizer.normalize(raw_data, {"platform": "x", "raw_file": ""})
    assert post.post_id.startswith("x:hash:")

def test_legacy_pdt_timestamp_parsing():
    normalizer = XNormalizer()
    raw_data = {
        "author_id": "user1",
        "text": "test content",
        "created_at": "Mon Apr 06 22:19:49 PDT 2009"
    }
    
    post = normalizer.normalize(raw_data, {"platform": "x", "raw_file": ""})
    assert post.timestamp is not None
    # 22:19:49 PDT (-0700) is 05:19:49 UTC next day
    assert post.timestamp.strftime("%Y-%m-%d %H:%M:%S%z") == "2009-04-07 05:19:49+0000"
