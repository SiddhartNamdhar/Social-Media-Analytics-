import asyncio
import logging
import uuid
from typing import Optional, List, Dict, Any, Generator

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .base_collector import BaseCollector
from ..config import settings
from ..exceptions import (
    YouTubeConfigurationError,
    YouTubeQuotaExceededError,
    YouTubeAPIError,
    YouTubeVideoNotFoundError,
    YouTubeChannelNotFoundError
)
from ..utils.datetime_utils import get_utc_now

logger = logging.getLogger(__name__)

class YouTubeCollector(BaseCollector):
    """Collector for official YouTube Data API v3."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.YOUTUBE_API_KEY
        if not self.api_key:
            raise YouTubeConfigurationError("YouTube API key is missing. Set YOUTUBE_API_KEY in .env")
        
        self.youtube = build('youtube', 'v3', developerKey=self.api_key)
        self._video_cache: Dict[str, Dict[str, Any]] = {}
    
    def _handle_http_error(self, e: HttpError, context: str):
        if e.resp.status == 403:
            import json
            reasons = []
            try:
                # the content attribute is usually bytes, but we can also check error_details
                content_str = e.content.decode('utf-8') if isinstance(e.content, bytes) else str(e.content)
                err_data = json.loads(content_str)
                errors = err_data.get("error", {}).get("errors", [])
                reasons = [err.get("reason") for err in errors]
            except Exception as ex:
                logger.debug(f"Could not parse HttpError content: {ex}")
                
            if "quotaExceeded" in reasons or "rateLimitExceeded" in reasons:
                raise YouTubeQuotaExceededError(f"YouTube Quota exceeded during {context}: {e}")
        
        if e.resp.status == 404:
            if "video" in context.lower():
                raise YouTubeVideoNotFoundError(f"Video not found during {context}: {e}")
            if "channel" in context.lower():
                raise YouTubeChannelNotFoundError(f"Channel not found during {context}: {e}")
                
        raise YouTubeAPIError(f"YouTube API Error during {context}: {e}")

    async def validate_connection(self) -> bool:
        """Validate connection by making a small quota-friendly API request."""
        try:
            # We fetch a very well known channel (e.g. YouTube Creators) ID just to test key
            # Cost is usually 1 quota point
            def _test_call():
                return self.youtube.channels().list(
                    part='id',
                    id='UCkRfArvrzheW2E7b6SVT7vQ',
                    maxResults=1
                ).execute()
                
            await asyncio.to_thread(_test_call)
            return True
        except HttpError as e:
            logger.error(f"YouTube connection validation failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error validating YouTube connection: {e}")
            return False

    async def collect(self, *args, **kwargs):
        """Deprecated generic collect. Use specific async collect_* methods instead."""
        raise NotImplementedError("Use specific collect_by_keyword, collect_channel, etc. instead.")

    async def _fetch_video_metadata(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Fetch video metadata with in-memory caching."""
        if video_id in self._video_cache:
            return self._video_cache[video_id]

        def _call():
            return self.youtube.videos().list(
                part="snippet,statistics",
                id=video_id
            ).execute()

        try:
            response = await asyncio.to_thread(_call)
            items = response.get("items", [])
            if not items:
                raise YouTubeVideoNotFoundError(f"Video {video_id} not found or is private.")
            video = items[0]
            self._video_cache[video_id] = video
            return video
        except HttpError as e:
            self._handle_http_error(e, f"fetch metadata for video {video_id}")
        return None

    async def search_videos(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Search public videos by keyword."""
        videos = []
        next_page_token = None
        max_results = min(limit, settings.YOUTUBE_MAX_RESULTS)
        
        while len(videos) < limit:
            def _call(token):
                return self.youtube.search().list(
                    part="snippet",
                    q=query,
                    type="video",
                    maxResults=max_results,
                    pageToken=token,
                    regionCode=settings.YOUTUBE_DEFAULT_REGION_CODE,
                    relevanceLanguage=settings.YOUTUBE_DEFAULT_LANGUAGE
                ).execute()
            
            try:
                response = await asyncio.to_thread(_call, next_page_token)
                items = response.get("items", [])
                
                for item in items:
                    item["record_type"] = "video"
                    videos.append(item)
                    if len(videos) >= limit:
                        break
                        
                next_page_token = response.get("nextPageToken")
                if not next_page_token or not items:
                    break
            except HttpError as e:
                self._handle_http_error(e, f"search_videos({query})")
                
        return videos

    async def collect_video(
        self,
        video_id: str,
        comments_limit: int = 10,
        include_replies: bool = False,
        batch_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Orchestrated helper to collect a specific video and its comments."""
        run_batch_id = batch_id or str(uuid.uuid4())[:8]
        now = get_utc_now().isoformat()
        
        metadata = {
            "platform": "youtube",
            "collection_type": "video",
            "collected_at": now,
            "query": video_id,
            "source": {
                "batch_id": run_batch_id
            },
            "statistics": {
                "videos_found": 0,
                "videos_processed": 0,
                "comments_collected": 0,
                "replies_collected": 0,
                "skipped_videos": 0,
                "skipped_records": 0
            }
        }
        
        all_records = []
        try:
            video_meta = await self._fetch_video_metadata(video_id)
            if video_meta:
                video_meta["record_type"] = "video"
                # Need an id for normalizer, which fetch_metadata already includes as string
                all_records.append(video_meta)
                metadata["statistics"]["videos_found"] = 1
                metadata["statistics"]["videos_processed"] = 1
                
                if comments_limit > 0:
                    comments = await self.collect_video_comments(
                        video_id, 
                        limit=comments_limit, 
                        include_replies=include_replies
                    )
                    for c in comments:
                        if c.get("record_type") == "comment":
                            metadata["statistics"]["comments_collected"] += 1
                        elif c.get("record_type") == "reply":
                            metadata["statistics"]["replies_collected"] += 1
                    all_records.extend(comments)
                    
        except YouTubeVideoNotFoundError:
            metadata["statistics"]["skipped_videos"] += 1
            logger.warning(f"Video {video_id} skipped: not found or private.")
        except YouTubeQuotaExceededError as e:
            metadata["status"] = "partial_quota_exhausted"
            logger.error(f"Quota exceeded during video collection: {e}")
        except Exception as e:
            logger.error(f"Error collecting video {video_id}: {e}")
            raise
            
        return {
            "collection_metadata": metadata,
            "data": all_records
        }

    async def _search_channel_videos(self, channel_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Collect videos from a public channel using the uploads playlist."""
        # First, get the uploads playlist ID
        def _get_channel():
            return self.youtube.channels().list(
                part="contentDetails",
                id=channel_id
            ).execute()
            
        try:
            channel_res = await asyncio.to_thread(_get_channel)
            items = channel_res.get("items", [])
            if not items:
                raise YouTubeChannelNotFoundError(f"Channel {channel_id} not found.")
            uploads_playlist_id = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
        except HttpError as e:
            self._handle_http_error(e, f"get channel uploads playlist for {channel_id}")

        videos = []
        next_page_token = None
        max_results = min(limit, settings.YOUTUBE_MAX_RESULTS)
        
        while len(videos) < limit:
            def _get_playlist_items(token):
                return self.youtube.playlistItems().list(
                    part="snippet,contentDetails",
                    playlistId=uploads_playlist_id,
                    maxResults=max_results,
                    pageToken=token
                ).execute()
                
            try:
                res = await asyncio.to_thread(_get_playlist_items, next_page_token)
                items = res.get("items", [])
                
                for item in items:
                    item["record_type"] = "video"
                    videos.append(item)
                    if len(videos) >= limit:
                        break
                        
                next_page_token = res.get("nextPageToken")
                if not next_page_token or not items:
                    break
            except HttpError as e:
                self._handle_http_error(e, f"get playlist items for {uploads_playlist_id}")

        return videos

    async def collect_channel(
        self,
        channel_id: str,
        video_limit: int = 5,
        comments_per_video: int = 10,
        include_replies: bool = False,
        batch_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Orchestrated helper to collect a channel's videos and their comments."""
        run_batch_id = batch_id or str(uuid.uuid4())[:8]
        now = get_utc_now().isoformat()
        
        metadata = {
            "platform": "youtube",
            "collection_type": "channel",
            "collected_at": now,
            "query": channel_id,
            "source": {
                "batch_id": run_batch_id
            },
            "statistics": {
                "videos_found": 0,
                "videos_processed": 0,
                "comments_collected": 0,
                "replies_collected": 0,
                "skipped_videos": 0,
                "skipped_records": 0
            }
        }
        
        all_records = []
        
        # 1. Search videos
        try:
            videos = await self._search_channel_videos(channel_id, limit=video_limit)
            metadata["statistics"]["videos_found"] = len(videos)
        except YouTubeQuotaExceededError as e:
            metadata["status"] = "partial_quota_exhausted"
            logger.error(f"Quota exceeded during channel search: {e}")
            return {"collection_metadata": metadata, "data": all_records}
        except YouTubeChannelNotFoundError as e:
            logger.warning(f"Channel not found: {e}")
            return {"collection_metadata": metadata, "data": all_records}
        except Exception as e:
            logger.error(f"Channel search failed: {e}")
            raise
            
        # 2. Collect comments for each video
        for v in videos:
            all_records.append(v)
            video_id = v["snippet"]["resourceId"]["videoId"] if "resourceId" in v.get("snippet", {}) else v.get("id")
            
            if not video_id:
                metadata["statistics"]["skipped_videos"] += 1
                continue
                
            try:
                # Eagerly cache the metadata
                v_meta = await self._fetch_video_metadata(video_id)
                if v_meta:
                    v["video_metadata"] = v_meta
                    
                metadata["statistics"]["videos_processed"] += 1
                
                if comments_per_video > 0:
                    comments = await self.collect_video_comments(
                        video_id, 
                        limit=comments_per_video, 
                        include_replies=include_replies
                    )
                    
                    for c in comments:
                        if c.get("record_type") == "comment":
                            metadata["statistics"]["comments_collected"] += 1
                        elif c.get("record_type") == "reply":
                            metadata["statistics"]["replies_collected"] += 1
                            
                    all_records.extend(comments)
                    
            except YouTubeVideoNotFoundError:
                metadata["statistics"]["skipped_videos"] += 1
                logger.warning(f"Video {video_id} skipped: not found or private.")
            except YouTubeQuotaExceededError as e:
                metadata["status"] = "partial_quota_exhausted"
                logger.error(f"Quota exceeded during collection: {e}")
                break
            except Exception as e:
                logger.error(f"Error collecting video {video_id}: {e}")
                raise
                
        return {
            "collection_metadata": metadata,
            "data": all_records
        }

    async def collect_comment_replies(self, parent_comment_id: str, video_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Collect replies to a specific top-level comment."""
        replies = []
        next_page_token = None
        max_results = min(limit, settings.YOUTUBE_MAX_RESULTS)
        
        while len(replies) < limit:
            def _call(token):
                return self.youtube.comments().list(
                    part="snippet",
                    parentId=parent_comment_id,
                    maxResults=max_results,
                    pageToken=token
                ).execute()
                
            try:
                res = await asyncio.to_thread(_call, next_page_token)
                items = res.get("items", [])
                
                for item in items:
                    item["record_type"] = "reply"
                    item["video_id"] = video_id
                    replies.append(item)
                    if len(replies) >= limit:
                        break
                        
                next_page_token = res.get("nextPageToken")
                if not next_page_token or not items:
                    break
            except HttpError as e:
                self._handle_http_error(e, f"get replies for comment {parent_comment_id}")
                
        return replies

    async def collect_video_comments(self, video_id: str, limit: int = 50, include_replies: bool = False) -> List[Dict[str, Any]]:
        """Collect top-level video comments and optionally replies."""
        comments = []
        next_page_token = None
        max_results = min(limit, settings.YOUTUBE_MAX_RESULTS)
        
        while len(comments) < limit:
            def _call(token):
                return self.youtube.commentThreads().list(
                    part="snippet,replies",
                    videoId=video_id,
                    maxResults=max_results,
                    pageToken=token,
                    textFormat="plainText"
                ).execute()
                
            try:
                res = await asyncio.to_thread(_call, next_page_token)
                items = res.get("items", [])
                
                for item in items:
                    item["record_type"] = "comment"
                    item["video_id"] = video_id
                    
                    # Flatten the top-level comment structure slightly for easier processing later,
                    # but preserve original payload as well
                    comments.append(item)
                    
                    # Automatically collect replies if requested
                    if include_replies:
                        total_reply_count = item["snippet"].get("totalReplyCount", 0)
                        if total_reply_count > 0:
                            parent_id = item["id"]
                            # If they are already in the payload (up to 5):
                            if "replies" in item and len(item["replies"].get("comments", [])) == total_reply_count:
                                for r in item["replies"]["comments"]:
                                    r["record_type"] = "reply"
                                    r["video_id"] = video_id
                                    comments.append(r)
                            else:
                                # Fetch remaining replies
                                fetched_replies = await self.collect_comment_replies(
                                    parent_id, video_id, limit=total_reply_count
                                )
                                comments.extend(fetched_replies)
                                
                    if len([c for c in comments if c.get("record_type") == "comment"]) >= limit:
                        break
                        
                next_page_token = res.get("nextPageToken")
                if not next_page_token or not items:
                    break
            except HttpError as e:
                if e.resp.status == 403:
                    import json
                    reasons = []
                    try:
                        content_str = e.content.decode('utf-8') if isinstance(e.content, bytes) else str(e.content)
                        err_data = json.loads(content_str)
                        errors = err_data.get("error", {}).get("errors", [])
                        reasons = [err.get("reason") for err in errors]
                    except Exception as ex:
                        logger.debug(f"Could not parse HttpError content for commentsDisabled: {ex}")
                        
                    if "commentsDisabled" in reasons:
                        logger.warning(f"Comments are disabled for video {video_id}.")
                        return comments
                
                self._handle_http_error(e, f"get comments for video {video_id}")
                
        return comments

    async def collect_by_keyword(self, query: str, video_limit: int = 2, comments_per_video: int = 10, include_replies: bool = False, batch_id: Optional[str] = None) -> Dict[str, Any]:
        """Orchestrated helper to collect videos and their comments for a keyword."""
        run_batch_id = batch_id or str(uuid.uuid4())[:8]
        now = get_utc_now().isoformat()
        
        metadata = {
            "platform": "youtube",
            "collection_type": "keyword",
            "collected_at": now,
            "query": query,
            "source": {
                "batch_id": run_batch_id
            },
            "statistics": {
                "videos_found": 0,
                "videos_processed": 0,
                "comments_collected": 0,
                "replies_collected": 0,
                "skipped_videos": 0,
                "skipped_records": 0
            }
        }
        
        all_records = []
        
        # 1. Search videos
        try:
            videos = await self.search_videos(query, limit=video_limit)
            metadata["statistics"]["videos_found"] = len(videos)
        except YouTubeQuotaExceededError as e:
            metadata["status"] = "partial_quota_exhausted"
            logger.error(f"Quota exceeded during search: {e}")
            return {"collection_metadata": metadata, "data": all_records}
        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise
            
        # 2. Collect comments for each video
        for v in videos:
            all_records.append(v)
            video_id = v["id"]["videoId"] if isinstance(v.get("id"), dict) else v.get("id")
            
            if not video_id:
                metadata["statistics"]["skipped_videos"] += 1
                continue
                
            try:
                # Eagerly cache the metadata
                v_meta = await self._fetch_video_metadata(video_id)
                if v_meta:
                    v["video_metadata"] = v_meta
                    
                metadata["statistics"]["videos_processed"] += 1
                
                if comments_per_video > 0:
                    comments = await self.collect_video_comments(
                        video_id, 
                        limit=comments_per_video, 
                        include_replies=include_replies
                    )
                    
                    for c in comments:
                        if c.get("record_type") == "comment":
                            metadata["statistics"]["comments_collected"] += 1
                        elif c.get("record_type") == "reply":
                            metadata["statistics"]["replies_collected"] += 1
                            
                    all_records.extend(comments)
                    
            except YouTubeVideoNotFoundError:
                metadata["statistics"]["skipped_videos"] += 1
                logger.warning(f"Video {video_id} skipped: not found or private.")
            except YouTubeQuotaExceededError as e:
                metadata["status"] = "partial_quota_exhausted"
                logger.error(f"Quota exceeded during collection: {e}")
                break
            except Exception as e:
                logger.error(f"Error collecting video {video_id}: {e}")
                raise
                
        return {
            "collection_metadata": metadata,
            "data": all_records
        }
