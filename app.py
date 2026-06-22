"""
app.py — FastAPI Server
Compatible with FastAPI 0.136+ / Starlette 1.x
"""

import uuid
import json
import os
import shutil
from fastapi import FastAPI, Request, HTTPException, Depends, status, UploadFile, File, Form
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel
from openai import AuthenticationError, RateLimitError, APIConnectionError, APITimeoutError

import chatbot
import models
import auth
import rag
from database import engine, get_db

# Create SQLite tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="AI Chatbot",
    description="Conversational AI chatbot with session memory powered by OpenAI.",
    version="1.0.0",
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ── Pydantic Schemas ──────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    persona: str | None = None

class ClearRequest(BaseModel):
    session_id: str



# ── Routes ────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serve the chat UI."""
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"session_id": str(uuid.uuid4())},
    )


@app.post("/chat")
async def chat_endpoint(body: ChatRequest, db: Session = Depends(get_db)):
    """Receive a user message and return the AI reply as a stream (SSE)."""
    session_id = body.session_id or str(uuid.uuid4())

    # Ensure session exists
    session = db.query(models.ChatSession).filter(models.ChatSession.id == session_id).first()
    if not session:
        session = models.ChatSession(id=session_id, user_id=None, title=body.message[:30] + "...")
        db.add(session)
        db.commit()

    def event_stream():
        try:
            for chunk in chatbot.chat_stream(session_id, body.message, body.persona):
                data = json.dumps({"chunk": chunk, "session_id": session_id})
                yield f"data: {data}\n\n"
        except Exception as e:
            error_data = json.dumps({"error": str(e), "session_id": session_id})
            yield f"data: {error_data}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

@app.post("/clear")
async def clear_session(body: ClearRequest, db: Session = Depends(get_db)):
    """Clear conversation history for a session."""
    chatbot.clear_session_db(db, body.session_id)
    return {"message": "Conversation cleared.", "session_id": body.session_id}

@app.get("/history/{session_id}")
async def get_history(session_id: str, db: Session = Depends(get_db)):
    """Return the raw conversation history for a session."""
    session = db.query(models.ChatSession).filter(models.ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    history = chatbot.get_history(session_id)
    return {"session_id": session_id, "history": history}

@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    session_id: str = Form(...),
    db: Session = Depends(get_db)
):
    """Upload a file and index it for RAG."""
    # Ensure session exists
    session = db.query(models.ChatSession).filter(models.ChatSession.id == session_id).first()
    if not session:
        session = models.ChatSession(id=session_id, user_id=None, title=f"Doc: {file.filename}")
        db.add(session)
        db.commit()

    file_path = os.path.join(rag.UPLOAD_DIR, f"{session_id}_{file.filename}")
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # Build FAISS index
    success = rag.build_index_for_session(session_id, file_path)
    if not success:
        raise HTTPException(status_code=400, detail="Could not extract text from file.")
        
    return {"message": "File processed successfully. You can now ask questions about it!"}

@app.get("/health")
async def health():
    return {"status": "ok"}

