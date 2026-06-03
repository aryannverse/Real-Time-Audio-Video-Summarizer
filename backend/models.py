import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from sqlalchemy import Column, String, DateTime, Text
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

class TaskModel(Base):
    __tablename__ = 'tasks'
    task_id = Column(String(50), primary_key=True, index=True)
    file_name = Column(String(255), nullable=False)
    status = Column(String(50), default='pending', nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)
    transcript = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    key_points = Column(Text, nullable=True)
    action_items = Column(Text, nullable=True)
    discussion_topics = Column(Text, nullable=True)
    logs = Column(Text, default='', nullable=False)
    error_message = Column(String(500), nullable=True)

class StructuredSummary(BaseModel):
    summary: str = Field(description='A concise but comprehensive high-level summary of the entire audio/video content (2-4 sentences).')
    key_points: List[str] = Field(description='A list of the main takeaways, critical concepts, or key ideas discussed.')
    action_items: List[str] = Field(description='Checklist of explicit actions, tasks, or follow-ups identified in the meeting or lecture.')
    discussion_topics: List[str] = Field(description='List of core topics or categories covered during the session.')

class TaskCreate(BaseModel):
    file_name: str

class TaskURLCreate(BaseModel):
    url: str

class TranscriptSegment(BaseModel):
    start: float
    end: float
    text: str

class TaskResponse(BaseModel):
    task_id: str
    file_name: str
    status: str
    created_at: datetime.datetime
    updated_at: datetime.datetime
    transcript: Optional[List[TranscriptSegment]] = None
    summary: Optional[str] = None
    key_points: Optional[List[str]] = None
    action_items: Optional[List[str]] = None
    discussion_topics: Optional[List[str]] = None
    logs: str
    error_message: Optional[str] = None

    class Config:
        from_attributes = True