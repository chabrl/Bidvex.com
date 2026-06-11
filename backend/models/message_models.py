"""
Message Models
"""

from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from datetime import datetime, timezone
import uuid


class MessageCreate(BaseModel):
    receiver_id: str
    content: str
    listing_id: Optional[str] = None
    # iter301 — explicit reply target. When set (and the sender is a
    # participant), the message lands in this exact thread instead of a
    # recomputed pair/listing id. Keeps legacy pair-id threads working.
    conversation_id: Optional[str] = None


class Message(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    conversation_id: str
    sender_id: str
    receiver_id: str
    listing_id: Optional[str] = None
    content: str
    is_read: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
