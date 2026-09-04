import pytest
from app.normalizers.youtube_normalizer import YouTubeNormalizer
from app.exceptions import NormalizationError

def test_normalize_video_raises():
    normalizer = YouTubeNormalizer()
    with pytest.raises(NormalizationError, match="context-only"):
        normalizer.normalize(
            raw_data={"record_type": "video"},
            raw_reference={},
            collection_metadata={}
        )

def test_normalize_comment():
    normalizer = YouTubeNormalizer()
    raw_data = {
        "record_type": "comment",
        "snippet": {
            "videoId": "v123",
            "topLevelComment": {
                "id": "c123",
                "snippet": {
                    "authorChannelId": {"value": "ch1"},
                    "authorDisplayName": "User1",
                    "textOriginal": "Hello #youtube",
                    "publishedAt": "2023-01-01T12:00:00Z",
                    "likeCount": 10
                }
            },
            "totalReplyCount": 2
        }
    }
    
    post = normalizer.normalize(
        raw_data=raw_data,
        raw_reference={"platform": "youtube", "raw_file": "dummy.jsonl"},
        collection_metadata={"collected_at": "2023-01-02T12:00:00Z", "dataset_name": "test"}
    )
    
    assert post.platform == "youtube"
    assert post.post_id == "youtube:comment:c123"
    assert post.author.user_id == "ch1"
    assert post.author.display_name == "User1"
    assert post.content.text == "Hello #youtube"
    assert "youtube" in post.content.hashtags
    assert post.interaction.like_count == 10
    assert post.interaction.reply_count == 2
    assert post.metadata.video_id == "v123"
    assert post.metadata.is_reply is False

def test_normalize_reply():
    normalizer = YouTubeNormalizer()
    raw_data = {
        "record_type": "reply",
        "id": "r123",
        "video_id": "v123",
        "snippet": {
            "parentId": "c123",
            "authorChannelId": {"value": "ch2"},
            "authorDisplayName": "User2",
            "textOriginal": "Reply text @User1",
            "publishedAt": "2023-01-01T13:00:00Z",
            "likeCount": 5
        }
    }
    
    post = normalizer.normalize(
        raw_data=raw_data,
        raw_reference={"platform": "youtube", "raw_file": "dummy.jsonl"},
        collection_metadata={"collected_at": "2023-01-02T12:00:00Z", "dataset_name": "test"}
    )
    
    assert post.platform == "youtube"
    assert post.post_id == "youtube:reply:r123"
    assert post.author.user_id == "ch2"
    assert post.content.text == "Reply text @User1"
    assert post.interaction.like_count == 5
    assert post.interaction.reply_count is None
    assert post.relationships.reply_to_post_id == "youtube:comment:c123"
    assert post.metadata.video_id == "v123"
    assert post.metadata.parent_comment_id == "c123"
    assert post.metadata.is_reply is True
