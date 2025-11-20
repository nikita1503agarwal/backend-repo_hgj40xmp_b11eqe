import os
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr

from database import create_document, get_documents, db

app = FastAPI(title="Online Exam Proctoring API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------
# Models (request payloads)
# -----------------------------
class CreateUser(BaseModel):
    email: EmailStr
    name: str
    role: str = "student"  # admin|instructor|student
    password_hash: str
    photo_url: Optional[str] = None


class CreateExamQuestion(BaseModel):
    qid: str
    type: str = "mcq"  # mcq|subjective|coding
    prompt: str
    options: Optional[List[str]] = None
    answer: Optional[Any] = None
    points: int = 1


class CreateExam(BaseModel):
    title: str
    description: Optional[str] = None
    start_time: datetime
    duration_minutes: int
    created_by: str
    questions: List[CreateExamQuestion] = []
    allowed_candidates: Optional[List[str]] = None


class ProctorEventIn(BaseModel):
    exam_id: str
    user_id: str
    event_type: str
    severity: str = "low"
    data: Optional[Dict[str, Any]] = None


class ChatMessageIn(BaseModel):
    exam_id: str
    user_id: str
    role: str = "student"
    message: str


class SubmissionIn(BaseModel):
    exam_id: str
    user_id: str
    answers: Dict[str, Any]
    attachments: Optional[List[str]] = None


# -----------------------------
# Health and Utilities
# -----------------------------
@app.get("/")
def read_root():
    return {"message": "Online Exam Proctoring API Running"}


@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}


@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


# -----------------------------
# Users
# -----------------------------
@app.post("/api/users")
def create_user(payload: CreateUser):
    existing = get_documents("user", {"email": payload.email})
    if existing:
        raise HTTPException(status_code=409, detail="User already exists")
    user_dict = payload.model_dump()
    user_dict["created_at"] = datetime.now(timezone.utc)
    user_dict["updated_at"] = datetime.now(timezone.utc)
    _id = create_document("user", user_dict)
    return {"id": _id}


# -----------------------------
# Exams
# -----------------------------
@app.post("/api/exams")
def create_exam(payload: CreateExam):
    exam = payload.model_dump()
    exam["created_at"] = datetime.now(timezone.utc)
    exam["updated_at"] = datetime.now(timezone.utc)
    _id = create_document("exam", exam)
    return {"id": _id}


@app.get("/api/exams")
def list_exams(created_by: Optional[str] = None, candidate: Optional[str] = None):
    filt: Dict[str, Any] = {}
    if created_by:
        filt["created_by"] = created_by
    if candidate:
        filt["allowed_candidates"] = {"$in": [candidate]}
    items = get_documents("exam", filt)
    return {"items": items}


# -----------------------------
# Proctoring Events & Summary
# -----------------------------
@app.post("/api/proctor/events")
def log_proctor_event(payload: ProctorEventIn):
    data = payload.model_dump()
    data["timestamp"] = datetime.now(timezone.utc)
    _id = create_document("proctorevent", data)
    return {"id": _id}


@app.get("/api/proctor/summary")
def proctor_summary(
    exam_id: str = Query(...),
    user_id: str = Query(...)
):
    events = get_documents("proctorevent", {"exam_id": exam_id, "user_id": user_id})

    # Count by type and severity
    by_type: Dict[str, int] = {}
    score = 0
    weights = {
        "tab_blur": 1,
        "multi_face": 5,
        "face_mismatch": 8,
        "audio_anomaly": 4,
        "phone_detected": 6,
        "gaze_anomaly": 3,
        "head_pose_anomaly": 3,
        "screen_share": 7,
        "frame_analysis": 2,
        "other": 1
    }
    sev_multiplier = {"low": 1, "medium": 2, "high": 3}

    for e in events:
        et = e.get("event_type", "other")
        sev = e.get("severity", "low")
        by_type[et] = by_type.get(et, 0) + 1
        score += weights.get(et, 1) * sev_multiplier.get(sev, 1)

    level = "low"
    if score >= 50:
        level = "high"
    elif score >= 20:
        level = "medium"

    return {
        "counts": by_type,
        "total_events": len(events),
        "suspicion_score": score,
        "suspicion_level": level
    }


# -----------------------------
# Chat
# -----------------------------
@app.post("/api/chat")
def send_chat_message(payload: ChatMessageIn):
    msg = payload.model_dump()
    msg["timestamp"] = datetime.now(timezone.utc)
    _id = create_document("chatmessage", msg)
    return {"id": _id}


@app.get("/api/chat")
def list_chat_messages(exam_id: str, limit: int = 100):
    items = get_documents("chatmessage", {"exam_id": exam_id}, limit=limit)
    return {"items": items}


# -----------------------------
# Submissions
# -----------------------------
@app.post("/api/submissions")
def submit_answers(payload: SubmissionIn):
    sub = payload.model_dump()
    sub["submitted_at"] = datetime.now(timezone.utc)
    _id = create_document("submission", sub)
    return {"id": _id}


# -----------------------------
# Mock ML analysis endpoint (for demo)
# -----------------------------
class FrameIn(BaseModel):
    exam_id: str
    user_id: str
    image_b64: str  # base64 image frame


@app.post("/api/ml/analyze-frame")
def analyze_frame(_: FrameIn):
    # For demo, return a benign analysis
    return {
        "faces": 1,
        "face_match": True,
        "phone_detected": False,
        "gaze_anomaly": False,
        "head_pose_anomaly": False,
        "suspected": False
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
