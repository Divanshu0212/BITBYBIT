"""
PFI Schemas
"""

from pydantic import BaseModel
from uuid import UUID
from datetime import datetime


class PFIScoreResponse(BaseModel):
    user_id: UUID
    score: int
    rating: int
    rd: int
    volatility: float
    confidence: str
    risk: str

    model_config = {"from_attributes": True}


class PFIHistoryResponse(BaseModel):
    score: int
    rating: int
    event_type: str
    timestamp: datetime

    model_config = {"from_attributes": True}


class LeaderboardEntry(BaseModel):
    user_id: UUID
    score: int
    rating: int
    rd: int
    confidence: str
    risk: str

    model_config = {"from_attributes": True}
