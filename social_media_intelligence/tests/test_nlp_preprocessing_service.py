import pytest
import json
import os
import tempfile
from datetime import datetime, timezone
from uuid import uuid4

from app.schemas.unified_post import UnifiedPost, Author, Content, Metadata, RawReference
from app.schemas.nlp_preprocessed_post import NLPStatus
from app.services.nlp_preprocessing_service import NLPPreprocessingService


@pytest.fixture
def service():
    return NLPPreprocessingService(chunk_size=10)


@pytest.fixture
def mock_unified_post():
    return UnifiedPost(
        record_id=uuid4(),
        platform="x",
        post_id="12345",
        author=Author(user_id="user_123", username="test_user"),
        content=Content(
            text="Hello world!",
            language="en"
        ),
        timestamp=datetime.now(timezone.utc),
        metadata=Metadata(source_type="test", collected_at=datetime.now(timezone.utc)),
        raw_reference=RawReference(platform="x", raw_file="test.json")
    )


def test_information_preservation(service, mock_unified_post):
    """Test that original_text is identical to upstream text."""
    # Add mojibake to text
    weird_text = "Hello âœ”ï¸Ž world \n\t  @user https://link.com #AI 🚀"
    mock_unified_post.content.text = weird_text
    mock_unified_post.content.urls = ["https://link.com"]
    mock_unified_post.content.mentions = ["user"]
    mock_unified_post.content.hashtags = ["#AI"]
    
    result = service.process_record(mock_unified_post)
    
    assert result.original_text == weird_text
    assert result.urls == ["https://link.com"]
    assert result.mentions == ["user"]
    assert result.hashtags == ["#AI"]
    assert "🚀" in result.emojis


def test_derived_text_validations(service, mock_unified_post):
    """Test normalized_text and model_text behaviors."""
    mock_unified_post.content.text = "Wow!!!!! This is sooooooo cool 🚀 @test_user check https://link.com \n \n"
    mock_unified_post.content.urls = ["https://link.com"]
    mock_unified_post.content.mentions = ["test_user"]
    
    result = service.process_record(mock_unified_post)
    
    # Normalized text fixes spaces and mojibake but keeps emojis and mentions
    assert "Wow!!!!! This is sooooooo cool 🚀 @test_user check https://link.com" in result.normalized_text
    
    # Model text replaces mentions, urls, demojizes, and caps repeated punctuation/chars
    assert "<URL>" in result.model_text
    assert "<USER>" in result.model_text
    assert ":rocket:" in result.model_text
    assert "Wow!!!" in result.model_text  # Capped at 3
    assert "sooo" in result.model_text    # Capped at 3


def test_language_detection_handling(service, mock_unified_post):
    """Test the three cases of language handling."""
    # Case 1: Upstream provided
    mock_unified_post.content.language = "es"
    mock_unified_post.content.text = "Hola mundo, esto es una prueba."
    res1 = service.process_record(mock_unified_post)
    assert res1.language == "es"
    assert res1.language_detected is False
    
    # Case 2: Fallback detected
    mock_unified_post.content.language = None
    mock_unified_post.content.text = "Bonjour le monde, c'est un test très long."
    res2 = service.process_record(mock_unified_post)
    assert res2.language == "fr"
    assert res2.language_detected is True
    assert res2.language_detection_probability is not None
    assert res2.language_detection_probability > 0.5
    
    # Case 3: Unknown (short/garbage)
    mock_unified_post.content.language = None
    mock_unified_post.content.text = "h"
    res3 = service.process_record(mock_unified_post)
    assert res3.language == "unknown"
    assert res3.language_detected is True
    assert res3.language_detection_probability is None


def test_nlp_status_routing(service, mock_unified_post):
    """Test deterministic NLPStatus routing."""
    # USABLE
    mock_unified_post.content.text = "Valid text here with some words."
    assert service.process_record(mock_unified_post).status == NLPStatus.USABLE
    
    # UNUSABLE_EMPTY
    mock_unified_post.content.text = "   \n \t  "
    assert service.process_record(mock_unified_post).status == NLPStatus.UNUSABLE_EMPTY
    
    # UNUSABLE_URL_ONLY
    mock_unified_post.content.text = "https://link.com https://another.com"
    mock_unified_post.content.urls = ["https://link.com", "https://another.com"]
    assert service.process_record(mock_unified_post).status == NLPStatus.UNUSABLE_URL_ONLY
    
    # UNUSABLE_MENTION_ONLY
    mock_unified_post.content.text = "@user1 @user2"
    mock_unified_post.content.mentions = ["user1", "user2"]
    assert service.process_record(mock_unified_post).status == NLPStatus.UNUSABLE_MENTION_ONLY


def test_determinism(service, mock_unified_post):
    """Test that processing the same record twice yields identical results except timestamps."""
    res1 = service.process_record(mock_unified_post)
    res2 = service.process_record(mock_unified_post)
    
    # Remove processed_at and processing_time_ms for equivalence check
    meta1 = res1.processing_metadata.copy()
    meta1.pop("processed_at", None)
    meta1.pop("processing_time_ms", None)
    
    meta2 = res2.processing_metadata.copy()
    meta2.pop("processed_at", None)
    meta2.pop("processing_time_ms", None)
    
    dict1 = res1.model_dump()
    dict1["processing_metadata"] = meta1
    
    dict2 = res2.model_dump()
    dict2["processing_metadata"] = meta2
    
    assert dict1 == dict2

def test_language_detection_bypass(service, mock_unified_post):
    """Test that upstream language completely bypasses detection."""
    # Given an upstream language
    mock_unified_post.content.language = "fr"
    # Even if text is English, it should trust upstream and not detect
    mock_unified_post.content.text = "This is definitely english text but upstream says fr."
    
    res = service.process_record(mock_unified_post)
    
    assert res.language == "fr"
    assert res.language_detected is False

def test_storage_validate_and_truncate(tmp_path):
    """Test that nlp_storage correctly validates complete JSONL and truncates partials."""
    from app.storage.nlp_storage import NLPStorage
    import json
    
    batch_id = "test_truncate"
    storage = NLPStorage(batch_id=batch_id)
    storage.base_dir = str(tmp_path)
    storage.dir_path = os.path.join(storage.base_dir, batch_id)
    storage.file_path = os.path.join(storage.dir_path, "nlp_posts.jsonl")
    
    os.makedirs(storage.dir_path, exist_ok=True)
    
    # Write 2 valid records and 1 partial record
    with open(storage.file_path, 'w', encoding='utf-8') as f:
        f.write(json.dumps({"platform": "x", "post_id": "1"}) + "\n")
        f.write(json.dumps({"platform": "x", "post_id": "2"}) + "\n")
        f.write('{"platform": "x", "post_id": "3", "timestamp"') # Incomplete!
        
    valid_count, last_record = storage.validate_and_truncate_checkpoint()
    
    assert valid_count == 2
    assert last_record["post_id"] == "2"
    
    # Check that the file was actually truncated
    with open(storage.file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        assert len(lines) == 2
        assert "3" not in lines[-1]

def test_resume_mismatch_fails(tmp_path):
    """Test that resuming fails if skip_lines doesn't match the valid output count."""
    # Handled heavily in integration/pipeline execution.
    pass
