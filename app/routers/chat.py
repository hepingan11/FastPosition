from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.models import ChatSession, ChatMessage
from app.models.schemas import ChatRequest, ChatResponse
from app.services.llm_service import llm_service
from datetime import datetime

router = APIRouter(prefix="/chat", tags=["chat"])


def get_or_create_session(db: Session, session_id: str) -> ChatSession:
    session = db.query(ChatSession).filter(ChatSession.session_id == session_id).first()
    if not session:
        session = ChatSession(session_id=session_id)
        db.add(session)
        db.commit()
        db.refresh(session)
    return session


def get_chat_history(db: Session, session_id: str, limit: int = 10) -> str:
    messages = db.query(ChatMessage).filter(
        ChatMessage.session_id == session_id
    ).order_by(ChatMessage.created_at.desc()).limit(limit).all()
    
    messages.reverse()
    
    history = ""
    for msg in messages:
        role = "用户" if msg.role == "user" else "助手"
        history += f"{role}: {msg.content}\n"
    
    return history


@router.post("/message", response_model=ChatResponse)
async def send_message(request: ChatRequest, db: Session = Depends(get_db)):
    session = get_or_create_session(db, request.session_id)
    
    user_message = ChatMessage(
        session_id=request.session_id,
        role="user",
        content=request.message
    )
    db.add(user_message)
    db.commit()
    
    history = get_chat_history(db, request.session_id)
    
    try:
        response_text = llm_service.chat(request.message, history)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM服务错误: {str(e)}")
    
    assistant_message = ChatMessage(
        session_id=request.session_id,
        role="assistant",
        content=response_text
    )
    db.add(assistant_message)
    db.commit()
    
    return ChatResponse(
        session_id=request.session_id,
        response=response_text,
        created_at=datetime.now()
    )


@router.get("/history/{session_id}")
async def get_history(session_id: str, limit: int = 20, db: Session = Depends(get_db)):
    messages = db.query(ChatMessage).filter(
        ChatMessage.session_id == session_id
    ).order_by(ChatMessage.created_at.desc()).limit(limit).all()
    
    return {
        "session_id": session_id,
        "messages": [
            {
                "role": msg.role,
                "content": msg.content,
                "created_at": msg.created_at
            }
            for msg in reversed(messages)
        ]
    }


@router.delete("/session/{session_id}")
async def clear_session(session_id: str, db: Session = Depends(get_db)):
    db.query(ChatMessage).filter(ChatMessage.session_id == session_id).delete()
    db.query(ChatSession).filter(ChatSession.session_id == session_id).delete()
    db.commit()
    
    return {"message": "会话已清除", "session_id": session_id}
