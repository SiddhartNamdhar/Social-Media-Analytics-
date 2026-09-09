from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from .unified_post import RawReference


class NLPStatus(str, Enum):
    USABLE = "usable"
    PARTIALLY_USABLE = "partially_usable"
    UNUSABLE_EMPTY = "unusable_empty"
    UNUSABLE_URL_ONLY = "unusable_url_only"
    UNUSABLE_MENTION_ONLY = "unusable_mention_only"
    UNUSABLE_ERROR = "unusable_error"


class NLPPreprocessedPost(BaseModel):
    # Identifiers
    record_id: UUID
    platform: str
    post_id: str
    timestamp: datetime
    source_reference: RawReference
    
    # Text Representations
    original_text: str               # Never overwritten
    normalized_text: str             # ftfy + NFKC + whitespace cleaned
    model_text: str                  # <URL>, <USER>, demojized, capped punctuation
    
    # Extracted Components
    urls: List[str] = Field(default_factory=list)
    mentions: List[str] = Field(default_factory=list)
    hashtags: List[str] = Field(default_factory=list)
    emojis: List[str] = Field(default_factory=list)
    
    # Language
    language: str
    language_detected: bool          
    language_detection_probability: Optional[float] = None
    
    # Status and Metadata
    status: NLPStatus
    preprocessing_version: str
    processing_metadata: Dict[str, Any] = Field(default_factory=dict)
