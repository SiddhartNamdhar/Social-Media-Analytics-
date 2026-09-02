import pytest
from datetime import datetime, timezone
from app.normalizers.telegram_normalizer import TelegramNormalizer
from app.schemas.unified_post import UnifiedPost

def test_telegram_normalizer():
    # 1. Arrange
    normalizer = TelegramNormalizer()
    
    raw_data = {
        "message_id": 456,
        "chat_id": -100123456789,
        "sender_id": None, # Channel post
        "text": "Hello #AI world! Visit https://example.com @elonmusk",
        "date": "2026-09-02T10:30:00+00:00",
        "edit_date": None,
        "views": 500,
        "forwards": 10,
        "message_type": "text",
        "reply_to_msg_id": 450,
        "reply_to_peer_id": None,
        "forward_info": None
    }
    
    collection_metadata = {
        "platform": "telegram",
        "collected_at": "2026-09-02T10:35:00+00:00",
        "source": {
            "channel": "@example_channel",
            "chat_id": -100123456789,
            "title": "Example Channel",
            "username": "example_channel",
            "entity_type": "channel"
        }
    }
    
    raw_reference = {
        "platform": "telegram",
        "raw_file": "data/raw/telegram/2026-09-02/collection_123.json"
    }

    # 2. Act
    post = normalizer.normalize(raw_data, raw_reference, collection_metadata)

    # 3. Assert
    assert isinstance(post, UnifiedPost)
    
    # Telegram ID Standard
    assert post.post_id == "telegram:-100123456789:456"
    assert post.platform == "telegram"
    
    # Text
    assert post.content.text == "Hello #AI world! Visit https://example.com @elonmusk"
    
    # Engagement Mapping
    assert post.interaction.view_count == 500
    assert post.interaction.share_count == 10
    
    # Relationships mapping
    assert post.relationships.reply_to_post_id == "telegram:-100123456789:450"
    
    # Entity Extraction
    assert "AI" in post.content.hashtags
    assert "elonmusk" in post.content.mentions
    assert "https://example.com" in post.content.urls
    
    # Timestamps
    assert post.timestamp.isoformat() == "2026-09-02T10:30:00+00:00"
    assert post.metadata.collected_at.isoformat() == "2026-09-02T10:35:00+00:00"
    
    assert post.author.entity_type == "channel"
