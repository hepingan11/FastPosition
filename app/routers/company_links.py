from datetime import datetime
import asyncio
import traceback

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.models.models import CompanyLink, Position
from app.models.schemas import (
    CompanyLinkBatchCrawlRequest,
    CompanyLinkBatchCrawlResponse,
    CompanyLinkBatchCrawlTaskResponse,
    CompanyLinkBatchCrawlTaskStatus,
    CompanyLinkCreate,
    CompanyLinkCrawlResult,
    CompanyLinkResponse,
    CompanyLinkUpdate,
)
from app.services.auth_service import get_current_user
from app.services.crawl_task_service import crawl_task_service
from app.services.job_crawler_service import job_crawler_service
from app.services.vector_service import vector_service

router = APIRouter(prefix="/company-links", tags=["company-links"])


def format_exception_message(exc: Exception) -> tuple[str, list[str]]:
    exc_type = type(exc).__name__
    exc_message = str(exc).strip() or repr(exc)
    traceback_lines = traceback.format_exc().strip().splitlines()
    debug_steps = [f"Exception type: {exc_type}"]
    if exc_message:
        debug_steps.append(f"Exception message: {exc_message}")
    if traceback_lines:
        debug_steps.extend(traceback_lines[-5:])
    return f"{exc_type}: {exc_message}", debug_steps


def crawl_callback(task_id: str, company_link_id: int, company_name: str):
    def callback(debug_steps: list[str]) -> None:
        crawl_task_service.update_live_steps(task_id, company_link_id, company_name, debug_steps)

    return callback


async def execute_crawl_task(task_id: str, company_link_ids: list[int]) -> None:
    db = SessionLocal()
    try:
        crawl_task_service.mark_running(task_id)
        company_links = db.query(CompanyLink).filter(CompanyLink.id.in_(company_link_ids)).all()
        company_link_map = {item.id: item for item in company_links}
        has_success = False

        for company_link_id in company_link_ids:
            company_link = company_link_map.get(company_link_id)
            if not company_link:
                crawl_task_service.append_result(
                    task_id,
                    CompanyLinkCrawlResult(
                        company_link_id=company_link_id,
                        company_name="Unknown company",
                        success=False,
                        message="Company link does not exist",
                        debug_steps=["Company link record was not found"],
                    ).model_dump(),
                )
                continue

            crawl_task_service.mark_company_started(task_id, company_link.id, company_link.company_name)
            try:
                crawl_result = await asyncio.to_thread(
                    job_crawler_service.prepare_crawl_result,
                    company_link,
                    crawl_callback(task_id, company_link.id, company_link.company_name),
                )
                positions = crawl_result.get("extracted_positions", [])
                inserted, updated = job_crawler_service.upsert_positions(db, company_link, positions)
                result = CompanyLinkCrawlResult(
                    company_link_id=company_link.id,
                    company_name=company_link.company_name,
                    success=True,
                    inserted=inserted,
                    updated=updated,
                    message=crawl_result["message"],
                    debug_steps=crawl_result.get("debug_steps", []),
                    page_text_preview=crawl_result.get("page_text_preview"),
                    llm_raw_response=crawl_result.get("llm_raw_response"),
                    extracted_positions=crawl_result.get("extracted_positions", []),
                )
                crawl_task_service.append_result(task_id, result.model_dump())
                has_success = True
            except Exception as exc:
                error_message, error_steps = format_exception_message(exc)
                result = CompanyLinkCrawlResult(
                    company_link_id=company_link.id,
                    company_name=company_link.company_name,
                    success=False,
                    message=error_message,
                    debug_steps=error_steps,
                )
                crawl_task_service.append_result(task_id, result.model_dump())

        db.commit()
        if has_success:
            positions = db.query(Position).all()
            vector_service.rebuild_position_index(positions)
        crawl_task_service.mark_finished(task_id)
    except Exception as exc:
        db.rollback()
        crawl_task_service.mark_failed(task_id, str(exc).strip() or repr(exc))
    finally:
        db.close()


@router.get("/", response_model=list[CompanyLinkResponse])
async def get_company_links(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return db.query(CompanyLink).offset(skip).limit(limit).all()


@router.post("/batch-crawl", response_model=CompanyLinkBatchCrawlResponse)
async def batch_crawl_company_links(
    request: CompanyLinkBatchCrawlRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not request.company_link_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Please select at least one company link")

    task_id = crawl_task_service.create_task(request.company_link_ids)
    await execute_crawl_task(task_id, request.company_link_ids)
    task = crawl_task_service.get_task(task_id)
    return CompanyLinkBatchCrawlResponse(
        total=task["total"],
        success_count=task["success_count"],
        failure_count=task["failure_count"],
        results=[CompanyLinkCrawlResult(**item) for item in task["results"]],
    )


@router.post("/batch-crawl/start", response_model=CompanyLinkBatchCrawlTaskResponse)
async def start_batch_crawl(
    request: CompanyLinkBatchCrawlRequest,
    current_user=Depends(get_current_user),
):
    if not request.company_link_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Please select at least one company link")

    task_id = crawl_task_service.create_task(request.company_link_ids)
    asyncio.create_task(execute_crawl_task(task_id, request.company_link_ids))
    return CompanyLinkBatchCrawlTaskResponse(task_id=task_id, status="pending")


@router.get("/batch-crawl/{task_id}", response_model=CompanyLinkBatchCrawlTaskStatus)
async def get_batch_crawl_task(task_id: str, current_user=Depends(get_current_user)):
    task = crawl_task_service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Crawl task does not exist")
    return CompanyLinkBatchCrawlTaskStatus(
        task_id=task["task_id"],
        status=task["status"],
        total=task["total"],
        completed=task["completed"],
        success_count=task["success_count"],
        failure_count=task["failure_count"],
        current_company_link_id=task.get("current_company_link_id"),
        current_company_name=task.get("current_company_name"),
        results=[CompanyLinkCrawlResult(**item) for item in task["results"]],
        error_message=task.get("error_message"),
    )


@router.get("/{company_link_id}", response_model=CompanyLinkResponse)
async def get_company_link(
    company_link_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    company_link = db.query(CompanyLink).filter(CompanyLink.id == company_link_id).first()
    if not company_link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company link does not exist")
    return company_link


@router.post("/", response_model=CompanyLinkResponse)
async def create_company_link(
    company_link: CompanyLinkCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    db_company_link = CompanyLink(**company_link.dict())
    db_company_link.create_at = datetime.now()
    db.add(db_company_link)
    db.commit()
    db.refresh(db_company_link)
    return db_company_link


@router.put("/{company_link_id}", response_model=CompanyLinkResponse)
async def update_company_link(
    company_link_id: int,
    company_link: CompanyLinkUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    db_company_link = db.query(CompanyLink).filter(CompanyLink.id == company_link_id).first()
    if not db_company_link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company link does not exist")
    for key, value in company_link.dict().items():
        setattr(db_company_link, key, value)
    db.commit()
    db.refresh(db_company_link)
    return db_company_link


@router.delete("/{company_link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_company_link(
    company_link_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    db_company_link = db.query(CompanyLink).filter(CompanyLink.id == company_link_id).first()
    if not db_company_link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company link does not exist")
    db.delete(db_company_link)
    db.commit()
    return
