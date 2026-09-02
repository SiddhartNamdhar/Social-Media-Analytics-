"""
Unified Post Schema for Social Media Intelligence.
"""
from typing import List, Optional
from datetime import datetime
from uuid import UUID, uuid4
from enum import Enum
from pydantic import BaseModel, Field


class EntityType(str, Enum):
    USER = "user"
    CHANNEL = "channel"
    GROUP = "group"
    UNKNOWN = "unknown"


class PublicMetrics(BaseModel):
    followers: Optional[int] = None
    following: Optional[int] = None
    posts: Optional[int] = None


class Author(BaseModel):
    entity_type: EntityType = EntityType.UNKNOWN
    user_id: str
    username: Optional[str] = None
    display_name: Optional[str] = None
    profile_description: Optional[str] = None
    declared_location: Optional[str] = None
    verified: Optional[bool] = None
    public_metrics: PublicMetrics = Field(default_factory=PublicMetrics)


class Content(BaseModel):
    text: str
    language: Optional[str] = None
    hashtags: List[str] = Field(default_factory=list)
    mentions: List[str] = Field(default_factory=list)
    urls: List[str] = Field(default_factory=list)


class InteractionMetrics(BaseModel):
    like_count: Optional[int] = None
    reply_count: Optional[int] = None
    share_count: Optional[int] = None
    view_count: Optional[int] = None


class Relationships(BaseModel):
    reply_to_post_id: Optional[str] = None
    reply_to_user_id: Optional[str] = None
    repost_of_post_id: Optional[str] = None
    quoted_post_id: Optional[str] = None
    forwarded_from_post_id: Optional[str] = None


class Metadata(BaseModel):
    source_type: str
    conversation_id: str
    collected_at: datetime
    original_message_id: int
    chat_id: int
    message_type: Optional[str] = None


class RawReference(BaseModel):
    platform: str
    raw_file: str


class UnifiedPost(BaseModel):
    record_id: UUID = Field(default_factory=uuid4)
    platform: str
    post_id: str
    project_id: Optional[str] = None
    author: Author
    content: Content
    timestamp: datetime
    interaction: InteractionMetrics = Field(default_factory=InteractionMetrics)
    relationships: Relationships = Field(default_factory=Relationships)
    metadata: Metadata
    raw_reference: RawReference
