from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime


class UserBase(BaseModel):
    username: str
    email: EmailStr


class UserCreate(UserBase):
    password: str


class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(UserBase):
    id: int
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    session_id: str
    response: str
    created_at: Optional[datetime] = None


class PositionBase(BaseModel):
    name: str
    location: Optional[str] = None
    jd: Optional[str] = None
    salary: Optional[str] = None
    link: Optional[str] = None


class PositionCreate(PositionBase):
    company: Optional[str] = None
    source: Optional[str] = None


class PositionResponse(PositionBase):
    id: int
    company: Optional[str] = None
    source: Optional[str] = None
    job_type: Optional[str] = None
    similarity_score: Optional[float] = None
    match_score: Optional[int] = None
    match_reason: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class PositionListResponse(BaseModel):
    total: int
    positions: List[PositionResponse]


class CompanyLinkBase(BaseModel):
    company_name: str
    link: str
    type: Optional[str] = None


class CompanyLinkCreate(CompanyLinkBase):
    pass


class CompanyLinkUpdate(CompanyLinkBase):
    pass


class CompanyLinkResponse(CompanyLinkBase):
    id: int
    create_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class CompanyLinkBatchCrawlRequest(BaseModel):
    company_link_ids: List[int]


class CompanyLinkCrawlResult(BaseModel):
    company_link_id: int
    company_name: str
    success: bool
    inserted: int = 0
    updated: int = 0
    message: str
    debug_steps: List[str] = []
    page_text_preview: Optional[str] = None
    llm_raw_response: Optional[str] = None
    extracted_positions: List[dict] = []


class CompanyLinkBatchCrawlResponse(BaseModel):
    total: int
    success_count: int
    failure_count: int
    results: List[CompanyLinkCrawlResult]


class CompanyLinkBatchCrawlTaskResponse(BaseModel):
    task_id: str
    status: str


class CompanyLinkBatchCrawlTaskStatus(BaseModel):
    task_id: str
    status: str
    total: int
    completed: int
    success_count: int
    failure_count: int
    current_company_link_id: Optional[int] = None
    current_company_name: Optional[str] = None
    results: List[CompanyLinkCrawlResult]
    error_message: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    app_name: str
    version: str


class ResumeUploadResponse(BaseModel):
    id: int
    file_name: str
    message: str
    file_url: Optional[str] = None
    parsed_info: Optional[dict] = None


class ResumeResponse(BaseModel):
    id: int
    file_name: str
    file_url: Optional[str] = None
    content: Optional[str] = None
    parsed_info: Optional[dict] = None
    created_at: Optional[datetime] = None


class ResumeListResponse(BaseModel):
    resumes: List[ResumeResponse]
    total: int
