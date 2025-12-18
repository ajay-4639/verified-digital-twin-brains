from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class ChatRequest(BaseModel):
    query: str
    conversation_id: Optional[str] = None

class ChatMetadata(BaseModel):
    type: str = "metadata"
    confidence_score: float
    citations: List[str]
    conversation_id: str

class ChatContent(BaseModel):
    type: str = "content"
    content: str

class ChatDone(BaseModel):
    type: str = "done"
    escalated: bool

class IngestionResponse(BaseModel):
    status: str
    chunks_ingested: int
    source_id: str

class SourceSchema(BaseModel):
    id: str
    twin_id: str
    filename: Optional[str]
    file_size: Optional[int]
    status: str
    created_at: Optional[datetime]

class MessageSchema(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    confidence_score: Optional[float]
    citations: Optional[List[str]]
    created_at: Optional[datetime]

class ConversationSchema(BaseModel):
    id: str
    twin_id: str
    user_id: Optional[str]
    created_at: Optional[datetime]

class EscalationSchema(BaseModel):
    id: str
    message_id: str
    status: str
    created_at: datetime
    messages: Optional[MessageSchema] = None

class TwinSettingsUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None

class YouTubeIngestRequest(BaseModel):
    url: str

class PodcastIngestRequest(BaseModel):
    url: str # RSS feed or direct audio link

class XThreadIngestRequest(BaseModel):
    url: str

class KnowledgeProfile(BaseModel):
    total_chunks: int
    total_sources: int
    fact_count: int
    opinion_count: int
    tone_distribution: Dict[str, int]
    top_tone: str
