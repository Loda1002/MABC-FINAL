# POST /api/rerun — 기억 파일 재업로드 → 재검증 대상 축소.

import json
from pathlib import Path
from fastapi import APIRouter, HTTPException
from ..models import RerunRequest, RerunResponse
from ..config import UPLOAD_DIR

router = APIRouter()


@router.post("/rerun", response_model=RerunResponse)
async def rerun(body: RerunRequest):
    """기억 파일(memory.json)을 다시 올려 재검증 대상 축소.

    이전 버전 검수에서 이미 확인된 항목은 재검증에서 제외.
    재검증 대상 건수와 건너뛴 건수를 반환한다.
    """
    memory_path = Path(UPLOAD_DIR) / "memory.json"
    if not memory_path.exists():
        # 기억 파일이 없으면 모든 항목을 재검증 대상으로 간주
        return RerunResponse(
            status="ok",
            remaining_checks=len(body.memory_data.get("results", [])),
            skipped_checks=0,
        )

    memory = json.loads(memory_path.read_text(encoding="utf-8"))
    prev_results = memory.get("results", [])

    # item 기준으로 교집합을 계산해 이미 확인된 항목 건너뜀
    body_items = {
        r.get("item")
        for r in body.memory_data.get("results", [])
        if r.get("item")
    }
    prev_items = {r.get("item") for r in prev_results if r.get("item")}
    skipped = len(body_items & prev_items)
    remaining = len(body_items) - skipped

    # 기억 파일 갱신: 재검증 완료 상태 기록
    memory["reverified_at"] = __import__("datetime").datetime.now().isoformat()
    memory_path.write_text(json.dumps(memory, ensure_ascii=False, indent=2), encoding="utf-8")

    return RerunResponse(
        status="ok",
        remaining_checks=remaining,
        skipped_checks=skipped,
    )
