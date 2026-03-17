from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional
import json
from app.database import get_db
from app.models.models import Position, Resume, User, CompanyLink
from app.models.schemas import (
    PositionResponse,
    PositionListResponse,
    PositionCreate
)
from app.services.auth_service import get_current_user
from app.services.llm_service import llm_service
from app.services.vector_service import vector_service

router = APIRouter(prefix="/positions", tags=["positions"])


def to_position_response(
    position: Position,
    job_type: Optional[str] = None,
    similarity_score: Optional[float] = None,
    match_score: Optional[int] = None,
    match_reason: Optional[str] = None
) -> PositionResponse:
    return PositionResponse(
        id=position.id,
        name=position.name,
        location=position.location,
        jd=position.jd,
        salary=position.salary,
        link=position.link,
        company=position.company,
        source=position.source,
        job_type=job_type,
        similarity_score=similarity_score,
        match_score=match_score,
        match_reason=match_reason,
        created_at=position.created_at,
        updated_at=position.updated_at
    )


def build_company_type_map(db: Session) -> dict[str, str]:
    company_links = db.query(CompanyLink).all()
    return {
        (company_link.company_name or "").strip().lower(): company_link.type
        for company_link in company_links
        if company_link.company_name and company_link.type
    }


def build_link_type_rules(db: Session) -> list[tuple[str, str]]:
    company_links = db.query(CompanyLink).all()
    link_rules = [
        ((company_link.link or "").strip().lower(), company_link.type)
        for company_link in company_links
        if company_link.link and company_link.type
    ]
    link_rules.sort(key=lambda item: len(item[0]), reverse=True)
    return link_rules


def resolve_job_type(
    company_name: Optional[str],
    position_link: Optional[str],
    company_type_map: dict[str, str],
    link_type_rules: list[tuple[str, str]]
) -> Optional[str]:
    normalized_link = (position_link or "").strip().lower()
    if normalized_link:
        for link_rule, job_type in link_type_rules:
            if link_rule and (link_rule in normalized_link or normalized_link in link_rule):
                return job_type

    normalized_company = (company_name or "").strip().lower()
    if not normalized_company:
        return None

    exact_match = company_type_map.get(normalized_company)
    if exact_match:
        return exact_match

    for mapped_name, job_type in company_type_map.items():
        if mapped_name in normalized_company or normalized_company in mapped_name:
            return job_type

    return None


def parse_resume_info(parsed_info: Optional[str]) -> dict:
    if not parsed_info:
        return {}

    if isinstance(parsed_info, dict):
        return parsed_info

    try:
        return json.loads(parsed_info)
    except (TypeError, json.JSONDecodeError):
        return {}


def ensure_list(value) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


def build_resume_query_features(resume_info: dict) -> tuple[list[str], list[str], Optional[str]]:
    target_positions = ensure_list(resume_info.get("target_positions"))
    skills = ensure_list(resume_info.get("skills"))

    location = resume_info.get("location")
    if isinstance(location, str):
        location = location.strip() or None
    else:
        location = None

    return target_positions, skills, location


def score_position_by_rules(
    position: Position,
    target_positions: list[str],
    skills: list[str],
    location: Optional[str]
) -> int:
    score = 0
    name_text = (position.name or "").lower()
    jd_text = (position.jd or "").lower()
    location_text = (position.location or "").lower()

    for target in target_positions:
        target_text = target.lower()
        if target_text and target_text in name_text:
            score += 5
        elif target_text and target_text in jd_text:
            score += 3

    for skill in skills[:10]:
        skill_text = skill.lower()
        if skill_text and skill_text in jd_text:
            score += 2

    if location and location.lower() in location_text:
        score += 3

    return score


def build_candidate_query(
    db: Session,
    target_positions: list[str],
    skills: list[str],
    location: Optional[str]
):
    query = db.query(Position)
    filters = []

    for target in target_positions[:5]:
        filters.append(Position.name.contains(target))
        filters.append(Position.jd.contains(target))

    for skill in skills[:8]:
        filters.append(Position.jd.contains(skill))

    if location:
        filters.append(Position.location.contains(location))

    if filters:
        query = query.filter(or_(*filters))

    return query


def load_positions_by_ids(db: Session, position_ids: list[int]) -> list[Position]:
    if not position_ids:
        return []

    positions = db.query(Position).filter(Position.id.in_(position_ids)).all()
    position_map = {position.id: position for position in positions}
    return [position_map[position_id] for position_id in position_ids if position_id in position_map]


def normalize_similarity(distance: Optional[float]) -> float:
    if distance is None:
        return 0.0
    similarity = 1 / (1 + max(distance, 0))
    return round(similarity, 4)


def deduplicate_positions(positions: list[Position]) -> list[Position]:
    seen = set()
    unique_positions = []
    for position in positions:
        key = (
            (position.company or "").strip().lower(),
            (position.name or "").strip().lower(),
            (position.location or "").strip().lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        unique_positions.append(position)
    return unique_positions


def llm_rerank_position(resume_info: dict, position: Position) -> tuple[int, str]:
    prompt = f"""你是招聘匹配助手。请根据简历信息和职位信息，返回 JSON：
{{
  "match_score": 0-100 的整数,
  "match_reason": "不超过60字的中文理由"
}}

简历信息：
{json.dumps(resume_info, ensure_ascii=False)}

职位信息：
{json.dumps({
    "name": position.name,
    "company": position.company,
    "location": position.location,
    "jd": position.jd,
    "salary": position.salary
}, ensure_ascii=False)}

只返回 JSON，不要附加解释。"""

    try:
        response = llm_service.chat(prompt)
        json_start = response.find("{")
        json_end = response.rfind("}") + 1
        if json_start < 0 or json_end <= json_start:
            raise ValueError("LLM 未返回有效 JSON")

        result = json.loads(response[json_start:json_end])
        score = int(result.get("match_score", 0))
        reason = str(result.get("match_reason", "")).strip()
        score = max(0, min(100, score))
        return score, reason or "模型未返回明确理由"
    except Exception:
        return 0, "模型评分失败，已回退到规则召回结果"


@router.get("", response_model=PositionListResponse)
async def get_positions(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    company: Optional[str] = None,
    location: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Position)
    company_type_map = build_company_type_map(db)
    link_type_rules = build_link_type_rules(db)
    
    if company:
        query = query.filter(Position.company.contains(company))
    if location:
        query = query.filter(Position.location.contains(location))
    
    total = query.count()
    positions = query.offset(skip).limit(limit).all()
    
    return PositionListResponse(
        total=total,
        positions=[
            to_position_response(
                position,
                job_type=resolve_job_type(position.company, position.link, company_type_map, link_type_rules)
            )
            for position in positions
        ]
    )


@router.get("/{position_id}", response_model=PositionResponse)
async def get_position(
    position_id: int,
    db: Session = Depends(get_db)
):
    company_type_map = build_company_type_map(db)
    link_type_rules = build_link_type_rules(db)
    position = db.query(Position).filter(Position.id == position_id).first()
    if not position:
        raise HTTPException(status_code=404, detail="职位不存在")
    return to_position_response(
        position,
        job_type=resolve_job_type(position.company, position.link, company_type_map, link_type_rules)
    )


@router.post("", response_model=PositionResponse)
async def create_position(
    position: PositionCreate,
    db: Session = Depends(get_db)
):
    company_type_map = build_company_type_map(db)
    link_type_rules = build_link_type_rules(db)
    db_position = Position(**position.model_dump())
    db.add(db_position)
    db.commit()
    db.refresh(db_position)
    return to_position_response(
        db_position,
        job_type=resolve_job_type(db_position.company, db_position.link, company_type_map, link_type_rules)
    )


@router.post("/rebuild-index")
async def rebuild_position_index(
    db: Session = Depends(get_db)
):
    positions = db.query(Position).all()
    vector_service.rebuild_position_index(positions)
    return {"message": "职位向量索引重建完成", "total": len(positions)}


@router.get("/recommend/{resume_id}", response_model=PositionListResponse)
async def recommend_positions(
    resume_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    company_type_map = build_company_type_map(db)
    link_type_rules = build_link_type_rules(db)
    resume = db.query(Resume).filter(
        Resume.id == resume_id,
        Resume.user_id == current_user.id
    ).first()
    if not resume:
        raise HTTPException(status_code=404, detail="简历不存在")

    resume_info = parse_resume_info(resume.parsed_info)
    if not resume_info:
        raise HTTPException(status_code=400, detail="简历尚未解析出有效结构化信息")

    target_positions, skills, location = build_resume_query_features(resume_info)
    if not target_positions and not skills and not location:
        raise HTTPException(status_code=400, detail="简历缺少可用于推荐的关键信息")

    candidates = []
    vector_similarity_map = {}
    try:
        vector_matches = vector_service.query_positions(resume_info, limit=20)
        vector_position_ids = [item["position_id"] for item in vector_matches]
        vector_similarity_map = {
            item["position_id"]: normalize_similarity(item.get("distance"))
            for item in vector_matches
        }
        candidates = load_positions_by_ids(db, vector_position_ids)
    except Exception:
        candidates = []

    if not candidates:
        candidate_query = build_candidate_query(db, target_positions, skills, location)
        candidates = candidate_query.limit(30).all()

    if not candidates:
        candidates = db.query(Position).limit(20).all()

    candidates = deduplicate_positions(candidates)
    ranked_candidates = sorted(
        candidates,
        key=lambda position: (
            vector_similarity_map.get(position.id, 0),
            score_position_by_rules(position, target_positions, skills, location)
        ),
        reverse=True
    )[:12]

    recommendations = []
    for position in ranked_candidates:
        similarity_score = vector_similarity_map.get(position.id, 0)
        llm_score, llm_reason = llm_rerank_position(resume_info, position)
        final_score = int((similarity_score * 100) * 0.3 + llm_score * 0.7)
        final_score = max(0, min(100, final_score))
        recommendations.append(
            (
                final_score,
                to_position_response(
                    position,
                    job_type=resolve_job_type(position.company, position.link, company_type_map, link_type_rules),
                    similarity_score=similarity_score,
                    match_score=final_score,
                    match_reason=llm_reason
                )
            )
        )

    recommendations.sort(key=lambda item: item[0], reverse=True)
    top_positions = [item[1] for item in recommendations[:10]]

    return PositionListResponse(
        total=len(top_positions),
        positions=top_positions
    )
