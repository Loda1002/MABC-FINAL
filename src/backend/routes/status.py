# GET /api/status/{job_id} — 진행 상황 폴링.
from fastapi import APIRouter
from ..models import StatusResponse
from .check import _JOB_STORE

router = APIRouter()


@router.get("/status/{job_id}", response_model=StatusResponse)
async def get_status(job_id: str):
    """검수 작업 진행 상황. 프론트엔드가 폴링하여 진행 문구 업데이트."""
    job = _JOB_STORE.get(job_id)
    if job is None:
        return StatusResponse(
            status="error",
            progress="작업 상태를 찾을 수 없습니다.",
            error="존재하지 않는 작업 ID입니다.",
        )

    status = job.get("status", "error")
    progress = job.get("progress", "")
    error = job.get("error")
    results = job.get("results", [])

    if status == "processing":
        return StatusResponse(
            status="processing",
            progress=progress,
            partial_results=[],
        )

    if status == "error":
        return StatusResponse(
            status="error",
            progress=progress or "알 수 없는 오류",
            error=error or "오류가 발생했습니다.",
            partial_results=[],
        )

    # done: results를 CheckResultItem 형태로 변환하여 반환
    partial_items = []
    for r in results:
        if isinstance(r, dict):
            partial_items.append(r)
        else:
            partial_items.append({
                "item": r.item,
                "cited_value": r.cited_value,
                "source_value": r.source_value,
                "judgment": r.judgment,
                "basis": r.basis,
                "correction_suggestion": r.correction_suggestion,
                "verified": r.verified,
                "calculation": r.calculation,
            })

    return StatusResponse(
        status="done",
        progress=progress or "대조 완료",
        partial_results=partial_items,
        error=error,
    )
