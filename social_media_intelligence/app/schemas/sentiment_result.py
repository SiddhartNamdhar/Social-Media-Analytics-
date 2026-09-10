from pydantic import BaseModel, Field
from datetime import datetime

class SentimentResult(BaseModel):
    platform: str
    post_id: str
    
    sentiment_label: str
    
    probability_negative: float
    probability_neutral: float
    probability_positive: float
    
    model_id: str
    model_revision: str
    precision: str
    processed_at: datetime
