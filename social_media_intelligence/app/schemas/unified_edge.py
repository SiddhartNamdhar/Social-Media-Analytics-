"""
Unified Edge Schema for Social Media Intelligence Network Datasets.
"""
from typing import Optional
from datetime import datetime
from enum import Enum
from pydantic import BaseModel
from .unified_post import RawReference


class RelationshipType(str, Enum):
    FOLLOW = "FOLLOW"
    REPLY = "REPLY"
    MENTION = "MENTION"
    REPOST = "REPOST"
    QUOTE = "QUOTE"
    FORWARD = "FORWARD"
    UNKNOWN = "UNKNOWN"


class UnifiedEdge(BaseModel):
    edge_id: str
    platform: str = "x"
    
    source_user_id: str
    target_user_id: str
    
    source_post_id: Optional[str] = None
    target_post_id: Optional[str] = None
    
    relationship_type: RelationshipType
    
    timestamp: Optional[datetime] = None
    
    weight: float = 1.0
    
    dataset_name: Optional[str] = None
    collected_at: datetime
    raw_reference: Optional[RawReference] = None
