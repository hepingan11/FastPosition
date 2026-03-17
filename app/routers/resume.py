from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
import json
import fitz
from app.database import get_db
from app.models.models import Resume, User
from app.models.schemas import (
    ResumeUploadResponse,
    ResumeResponse,
    ResumeListResponse
)
from app.services.auth_service import get_current_user
from app.services.llm_service import llm_service
from app.services.oss_service import oss_service

router = APIRouter(prefix="/resume", tags=["resume"])

SUPPORTED_RESUME_EXTENSIONS = {".txt", ".pdf"}


def deserialize_parsed_info(parsed_info: Optional[str]) -> Optional[dict]:
    if not parsed_info:
        return None

    if isinstance(parsed_info, dict):
        return parsed_info

    try:
        return json.loads(parsed_info)
    except (TypeError, json.JSONDecodeError):
        return None


def to_resume_response(resume: Resume) -> ResumeResponse:
    return ResumeResponse(
        id=resume.id,
        file_name=resume.file_name,
        file_url=resume.file_url,
        content=resume.content,
        parsed_info=deserialize_parsed_info(resume.parsed_info),
        created_at=resume.created_at
    )


def extract_text_from_file(file_name: Optional[str], content: bytes) -> str:
    if not file_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文件名不能为空"
        )

    lower_name = file_name.lower()

    if lower_name.endswith(".txt"):
        text_content = content.decode("utf-8", errors="ignore").strip()
    elif lower_name.endswith(".pdf"):
        try:
            with fitz.open(stream=content, filetype="pdf") as pdf_document:
                pages = [page.get_text("text") for page in pdf_document]
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"PDF 解析失败: {exc}"
            ) from exc

        text_content = "\n".join(page.strip() for page in pages if page and page.strip())
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"暂不支持该文件格式，仅支持: {', '.join(sorted(SUPPORTED_RESUME_EXTENSIONS))}"
        )

    if not text_content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文件中未提取到有效文本内容"
        )

    return text_content


async def parse_resume_content(content: str) -> Optional[dict]:
    try:
        response = llm_service.analyze_resume(content)
        json_start = response.find("{")
        json_end = response.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            return json.loads(response[json_start:json_end])
        return None
    except Exception:
        return None


@router.post("/upload", response_model=ResumeUploadResponse)
async def upload_resume(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        content = await file.read()
        file_url = oss_service.upload_resume(file.filename, content, current_user.id)
        text_content = extract_text_from_file(file.filename, content)
        parsed_info = await parse_resume_content(text_content)

        db_resume = Resume(
            user_id=current_user.id,
            file_name=file.filename,
            file_url=file_url,
            content=text_content,
            parsed_info=json.dumps(parsed_info, ensure_ascii=False) if parsed_info else None
        )
        db.add(db_resume)
        db.commit()
        db.refresh(db_resume)

        return ResumeUploadResponse(
            id=db_resume.id,
            file_name=db_resume.file_name,
            message="简历上传成功",
            file_url=db_resume.file_url,
            parsed_info=parsed_info
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"上传失败: {exc}") from exc


@router.get("/list", response_model=ResumeListResponse)
async def get_resumes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    resumes = db.query(Resume).filter(Resume.user_id == current_user.id).all()
    return ResumeListResponse(
        total=len(resumes),
        resumes=[to_resume_response(resume) for resume in resumes]
    )


@router.get("/{resume_id}", response_model=ResumeResponse)
async def get_resume(
    resume_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    resume = db.query(Resume).filter(
        Resume.id == resume_id,
        Resume.user_id == current_user.id
    ).first()
    if not resume:
        raise HTTPException(status_code=404, detail="简历不存在")
    return to_resume_response(resume)


@router.delete("/{resume_id}")
async def delete_resume(
    resume_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    resume = db.query(Resume).filter(
        Resume.id == resume_id,
        Resume.user_id == current_user.id
    ).first()
    if not resume:
        raise HTTPException(status_code=404, detail="简历不存在")
    db.delete(resume)
    db.commit()
    return {"message": "删除成功"}
