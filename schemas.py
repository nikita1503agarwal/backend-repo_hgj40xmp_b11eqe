"""
Database Schemas for Online Exam Proctoring Portal

Each Pydantic model represents a MongoDB collection.
Collection name is the lowercase of the class name.
"""
from typing import List, Optional, Literal, Any
from pydantic import BaseModel, Field, EmailStr
from datetime import datetime


class User(BaseModel):
    email: EmailStr
    name: str
    role: Literal["admin", "instructor", "student"] = "student"
    password_hash: str
    photo_url: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ExamQuestion(BaseModel):
    qid: str
    type: Literal["mcq", "subjective", "coding"] = "mcq"
    prompt: str
    options: Optional[List[str]] = None
    answer: Optional[Any] = None  # instructors can store key for MCQ
    points: int = 1


class Exam(BaseModel):
    title: str
    description: Optional[str] = None
    start_time: datetime
    duration_minutes: int
    created_by: str  # user id (instructor/admin)
    questions: List[ExamQuestion] = []
    allowed_candidates: Optional[List[str]] = None  # list of student user ids/emails
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ProctorEvent(BaseModel):
    exam_id: str
    user_id: str
    event_type: Literal[
        "tab_blur",
        "tab_focus",
        "multi_face",
        "face_mismatch",
        "audio_anomaly",
        "phone_detected",
        "gaze_anomaly",
        "head_pose_anomaly",
        "screen_share",
        "frame_analysis",
        "other"
    ] = "other"
    severity: Literal["low", "medium", "high"] = "low"
    data: Optional[dict] = None
    timestamp: Optional[datetime] = None


class ChatMessage(BaseModel):
    exam_id: str
    user_id: str
    role: Literal["student", "instructor", "system"] = "student"
    message: str
    timestamp: Optional[datetime] = None


class Submission(BaseModel):
    exam_id: str
    user_id: str
    answers: dict  # questionId -> answer value
    attachments: Optional[List[str]] = None  # file paths or URLs
    submitted_at: Optional[datetime] = None


class Evidence(BaseModel):
    exam_id: str
    user_id: str
    kind: Literal["image", "audio", "video", "log"] = "image"
    url: str  # path or S3 URL
    metadata: Optional[dict] = None
    created_at: Optional[datetime] = None


# Minimal schema response helper (read by tooling if needed)
class SchemaInfo(BaseModel):
    collections: List[str]
