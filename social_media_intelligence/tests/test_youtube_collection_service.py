import pytest
import tempfile
import os
import json
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio
from app.services.youtube_collection_service import YouTubeCollectionService
from app.collectors.youtube_collector import YouTubeCollector
import httplib2
from googleapiclient.errors import HttpError

@pytest.fixture
def temp_storage_dirs():
    with tempfile.TemporaryDirectory() as raw_dir, tempfile.TemporaryDirectory() as processed_dir:
        yield Path(raw_dir), Path(processed_dir)

def create_mock_http_error(status_code, message, reason=None):
    resp = httplib2.Response({"status": status_code})
    error_dict = {"message": message}
    if reason:
        error_dict["errors"] = [{"reason": reason}]
    content = json.dumps({"error": error_dict}).encode("utf-8")
    return HttpError(resp, content)

@pytest.fixture
def mock_google_api():
    with patch("app.collectors.youtube_collector.build") as mock_build:
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        yield mock_service

def test_collect_by_keyword_orchestration(temp_storage_dirs, mock_google_api):
    raw_dir, processed_dir = temp_storage_dirs
    
    service = YouTubeCollectionService()
    service.raw_storage.base_dir = str(raw_dir)
    service.processed_storage.base_dir = str(processed_dir)
    
    # Mock search
    mock_search = MagicMock()
    mock_google_api.search.return_value = mock_search
    mock_search.list().execute.return_value = {
        "items": [
            {"id": {"videoId": "v1"}, "snippet": {"title": "Test Video 1", "publishedAt": "2023-01-01T00:00:00Z"}},
        ]
    }
    
    # Mock video metadata
    mock_videos = MagicMock()
    mock_google_api.videos.return_value = mock_videos
    mock_videos.list().execute.return_value = {
        "items": [
            {
                "id": "v1", 
                "snippet": {"channelId": "ch1", "title": "Test Video 1", "publishedAt": "2023-01-01T00:00:00Z"},
                "statistics": {"viewCount": "100"}
            }
        ]
    }
    
    # Mock comments
    mock_comments = MagicMock()
    mock_google_api.commentThreads.return_value = mock_comments
    mock_comments.list().execute.return_value = {
        "items": [
            {
                "id": "c1",
                "snippet": {
                    "videoId": "v1",
                    "topLevelComment": {
                        "id": "c1",
                        "snippet": {"textOriginal": "test comment", "authorChannelId": {"value": "ch2"}, "publishedAt": "2023-01-01T01:00:00Z"}
                    },
                    "totalReplyCount": 1
                },
                "replies": {
                    "comments": [
                        {
                            "id": "r1",
                            "snippet": {"textOriginal": "test reply", "authorChannelId": {"value": "ch3"}, "publishedAt": "2023-01-01T02:00:00Z"}
                        }
                    ]
                }
            }
        ]
    }

    result = asyncio.run(service.collect_by_keyword("AI", video_limit=1, comments_per_video=1, include_replies=True))
    
    assert result["videos_found"] == 1
    assert result["comments_collected"] == 1
    assert result["replies_collected"] == 1
    
    # 1 video (skipped by normalizer), 1 comment, 1 reply = 2 normalized posts
    assert result["normalized_posts"] == 2
    assert result["persisted_posts"] == 2
    assert result["normalization_skips"] == 1 # the video record
    
    # Verify actual files were written
    raw_path = Path(result["raw_output_path"])
    processed_path = Path(result["processed_output_path"])
    
    assert raw_path.exists()
    assert processed_path.exists()
    
    # Verify raw JSONL
    with open(raw_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        assert len(lines) == 3 # 3 data rows
        
    # Verify metadata file
    metadata_path = Path(result["metadata_output_path"])
    assert metadata_path.exists()
    
    with open(metadata_path, 'r', encoding='utf-8') as f:
        meta_data = json.load(f)
        assert meta_data["is_final_chunk"] is True
        assert "batch_id" in meta_data["source"]
        
    # Verify processed JSONL
    with open(processed_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        assert len(lines) == 2 # 2 normalized posts
        
        post1 = json.loads(lines[0])
        assert post1["platform"] == "youtube"
        assert post1["post_id"] == "youtube:comment:c1"
        assert post1["raw_reference"]["raw_file"] == str(raw_path).replace("\\", "/") or post1["raw_reference"]["raw_file"] == str(raw_path)


def test_collect_video_orchestration(temp_storage_dirs, mock_google_api):
    raw_dir, processed_dir = temp_storage_dirs
    service = YouTubeCollectionService()
    service.raw_storage.base_dir = str(raw_dir)
    service.processed_storage.base_dir = str(processed_dir)
    
    # Mock video metadata
    mock_videos = MagicMock()
    mock_google_api.videos.return_value = mock_videos
    mock_videos.list().execute.return_value = {
        "items": [
            {
                "id": "v1", 
                "snippet": {"channelId": "ch1", "title": "Test Video 1", "publishedAt": "2023-01-01T00:00:00Z"},
                "statistics": {"viewCount": "100"}
            }
        ]
    }
    
    # Mock comments
    mock_comments = MagicMock()
    mock_google_api.commentThreads.return_value = mock_comments
    mock_comments.list().execute.return_value = {
        "items": [
            {
                "id": "c1",
                "snippet": {
                    "videoId": "v1",
                    "topLevelComment": {
                        "id": "c1",
                        "snippet": {"textOriginal": "test comment", "authorChannelId": {"value": "ch2"}, "publishedAt": "2023-01-01T01:00:00Z"}
                    },
                    "totalReplyCount": 0
                }
            }
        ]
    }

    result = asyncio.run(service.collect_video("v1", comments_limit=1))
    
    assert result["videos_found"] == 1
    assert result["comments_collected"] == 1
    assert result["replies_collected"] == 0
    assert result["persisted_posts"] == 1


def test_collect_channel_orchestration(temp_storage_dirs, mock_google_api):
    raw_dir, processed_dir = temp_storage_dirs
    service = YouTubeCollectionService()
    service.raw_storage.base_dir = str(raw_dir)
    service.processed_storage.base_dir = str(processed_dir)
    
    # Mock channel to get playlist ID
    mock_channels = MagicMock()
    mock_google_api.channels.return_value = mock_channels
    mock_channels.list().execute.return_value = {
        "items": [
            {"contentDetails": {"relatedPlaylists": {"uploads": "PL123"}}}
        ]
    }
    
    # Mock playlist items
    mock_playlistItems = MagicMock()
    mock_google_api.playlistItems.return_value = mock_playlistItems
    mock_playlistItems.list().execute.return_value = {
        "items": [
            {"snippet": {"resourceId": {"videoId": "v1"}, "publishedAt": "2023-01-01T00:00:00Z"}}
        ]
    }
    
    # Mock video metadata
    mock_videos = MagicMock()
    mock_google_api.videos.return_value = mock_videos
    mock_videos.list().execute.return_value = {
        "items": [
            {
                "id": "v1", 
                "snippet": {"channelId": "ch1", "title": "Test Video 1", "publishedAt": "2023-01-01T00:00:00Z"},
                "statistics": {"viewCount": "100"}
            }
        ]
    }
    
    # Mock comments disabled
    mock_comments = MagicMock()
    mock_google_api.commentThreads.return_value = mock_comments
    mock_comments.list().execute.side_effect = create_mock_http_error(403, "commentsDisabled", reason="commentsDisabled")

    result = asyncio.run(service.collect_channel("ch1", video_limit=1, comments_per_video=1))
    
    assert result["videos_found"] == 1
    assert result["comments_collected"] == 0 # Comments disabled, should handle gracefully
    assert result["normalization_skips"] == 1 # The video record itself


def test_youtube_collection_service_empty_result(temp_storage_dirs, mock_google_api):
    raw_dir, processed_dir = temp_storage_dirs
    
    service = YouTubeCollectionService()
    service.raw_storage.base_dir = str(raw_dir)
    service.processed_storage.base_dir = str(processed_dir)
    
    mock_search = MagicMock()
    mock_google_api.search.return_value = mock_search
    # Empty result
    mock_search.list().execute.return_value = {
        "items": []
    }
    
    result = asyncio.run(service.collect_by_keyword("EmptyQuery"))
    
    assert result["normalized_posts"] == 0
    assert result["persisted_posts"] == 0
    assert result["raw_output_path"] is None
    assert result["processed_output_path"] is None
    
    # Even if no data, metadata file should exist
    assert result["metadata_output_path"] is not None
    assert Path(result["metadata_output_path"]).exists()

def test_quota_exhaustion(temp_storage_dirs, mock_google_api):
    raw_dir, processed_dir = temp_storage_dirs
    service = YouTubeCollectionService()
    service.raw_storage.base_dir = str(raw_dir)
    service.processed_storage.base_dir = str(processed_dir)
    
    # Mock search to fail with quotaExceeded
    mock_search = MagicMock()
    mock_google_api.search.return_value = mock_search
    mock_search.list().execute.side_effect = create_mock_http_error(403, "Quota Exceeded", reason="quotaExceeded")
    
    result = asyncio.run(service.collect_by_keyword("AI"))
    
    assert result["status"] == "partial_quota_exhausted"
    assert result["videos_found"] == 0
    assert result["raw_output_path"] is None
    assert Path(result["metadata_output_path"]).exists()
