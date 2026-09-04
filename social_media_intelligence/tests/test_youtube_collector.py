import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from googleapiclient.errors import HttpError
import json
import httplib2

from app.collectors.youtube_collector import YouTubeCollector
from app.exceptions import (
    YouTubeConfigurationError,
    YouTubeQuotaExceededError,
    YouTubeVideoNotFoundError
)

def create_mock_http_error(status_code, message, reason=None):
    resp = httplib2.Response({"status": status_code})
    error_dict = {"message": message}
    if reason:
        error_dict["errors"] = [{"reason": reason}]
    content = json.dumps({"error": error_dict}).encode("utf-8")
    return HttpError(resp, content)

def test_missing_api_key(monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "")
    with patch("app.collectors.youtube_collector.settings.YOUTUBE_API_KEY", ""):
        with pytest.raises(YouTubeConfigurationError):
            YouTubeCollector(api_key="")

@pytest.fixture
def mock_youtube_service():
    with patch("app.collectors.youtube_collector.build") as mock_build:
        yield mock_build

import asyncio

def test_search_videos_quota_exceeded():
    """Test that a 403 quota error correctly raises YouTubeQuotaExceededError."""
    # We patch build so it returns a mocked service
    with patch("app.collectors.youtube_collector.build") as mock_build:
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        
        # Setup the mock for search().list().execute()
        mock_search = MagicMock()
        mock_service.search.return_value = mock_search
        mock_list = MagicMock()
        mock_search.list.return_value = mock_list
        
        # Make execute() raise an HttpError with 403 and "quotaExceeded" reason
        mock_list.execute.side_effect = create_mock_http_error(403, "Quota Exceeded", reason="quotaExceeded")
        
        collector = YouTubeCollector(api_key="dummy_key")
        
        # We need to use asyncio.to_thread because the collector uses it
        with pytest.raises(YouTubeQuotaExceededError):
            asyncio.run(collector.search_videos("AI"))

def test_collect_video_comments_disabled():
    """Test that disabled comments return empty list instead of failing."""
    with patch("app.collectors.youtube_collector.build") as mock_build:
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        
        mock_threads = MagicMock()
        mock_service.commentThreads.return_value = mock_threads
        mock_list = MagicMock()
        mock_threads.list.return_value = mock_list
        
        # Make execute() raise an HttpError with 403 and "commentsDisabled"
        mock_list.execute.side_effect = create_mock_http_error(403, "commentsDisabled", reason="commentsDisabled")
        
        collector = YouTubeCollector(api_key="dummy_key")
        
        comments = asyncio.run(collector.collect_video_comments("dummy_video"))
        assert comments == []
