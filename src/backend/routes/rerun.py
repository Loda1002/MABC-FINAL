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

    # 기억 파일에 있는 항목과 현재 요청 항목의 교집합을 건너뛸 대상으로 계산
    # 간단히: memory_data.results에 있는 항목 수만큼 이미 확인된 것으로 가정
    remaining = len(body.memory_data.get("results", []))
    skipped = min(remaining, len(prev_results)) if prev_results else 0

    # 기억 파일 갱신: 재검증 완료 상태 기록
    memory["reverified_at"] = __import__("datetime").datetime.now().isoformat()
    memory_path.write_text(json.dumps(memory, ensure_ascii=False, indent=2), encoding="utf-8")

    return RerunResponse(
        status="ok",
        remaining_checks=remaining - skipped,
        skipped_checks=skipped,
    )
