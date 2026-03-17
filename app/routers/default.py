from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app.models.schemas import HealthResponse
from app.config import settings

router = APIRouter(tags=["default"])


@router.get("/", response_model=dict)
async def root():
    return {
        "message": f"欢迎使用{settings.APP_NAME} API",
        "version": settings.APP_VERSION,
        "docs": "/docs"
    }


@router.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="healthy",
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION
    )
