# GET /api/status/{job_id} — 진행 상황 폴링.

from fastapi import APIRouter, HTTPException
from ..models import StatusResponse

router = APIRouter()


@router.get("/status/{job_id}", response_model=StatusResponse)
async def get_status(job_id: str):
    """검수 작업 진행 상황. 프론트엔드가 폴링하여 진행 문구 업데이트."""
    # TODO: 실제 작업 상태 저장/조회 (메모리 또는 임시 저장소)
    return StatusResponse(
        status="error",
        progress="작업 상태를 찾을 수 없습니다.",
        error="아직 구현되지 않았습니다.",
    )
