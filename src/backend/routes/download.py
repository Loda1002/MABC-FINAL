# GET /api/download/{type} — 고쳐진 파일 / 기억 파일 다운로드.
import json
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from ..config import UPLOAD_DIR
from ..models import DownloadFixedRequest, DownloadFixedResponse

router = APIRouter()


def _ensure_memory_file(results: list[dict], fixed_text: str) -> Path:
    """기억 파일(memory.json)을 생성."""
    memory = {
        "version": "1.0",
        "generated_at": __import__("datetime").datetime.now().isoformat(),
        "results": results,
        "fixed_text": fixed_text,
    }
    path = Path(UPLOAD_DIR) / "memory.json"
    path.write_text(json.dumps(memory, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _ensure_fixed_file(fixed_text: str) -> Path:
    """고쳐진 초안 파일을 생성."""
    path = Path(UPLOAD_DIR) / "fixed_draft.txt"
    path.write_text(fixed_text, encoding="utf-8")
    return path


@router.get("/download/{file_type}")
async def download_file(file_type: str):
    """type: 'fixed' (고쳐진 초안), 'memory' (기억 파일 json)"""
    if file_type == "fixed":
        path = Path(UPLOAD_DIR) / "fixed_draft.txt"
        if not path.exists():
            raise HTTPException(status_code=404, detail="고쳐진 파일이 아직 생성되지 않았습니다.")
        return FileResponse(path, filename="mabc_fixed_draft.txt", media_type="text/plain")
    elif file_type == "memory":
        path = Path(UPLOAD_DIR) / "memory.json"
        if not path.exists():
            raise HTTPException(status_code=404, detail="기억 파일이 아직 생성되지 않았습니다.")
        return FileResponse(path, filename="mabc_memory.json", media_type="application/json")
    else:
        raise HTTPException(status_code=400, detail=f"알 수 없는 다운로드 유형: {file_type}. 'fixed' 또는 'memory'.")


def generate_outputs(results: list[dict], original_text: str, draft_text: str, accepted_items: set[str] | None = None):
    """check 결과를 받아 fixed_draft.txt와 memory.json을 생성하고 경로를 반환.

    accepted_items가 주어지면 해당 항목만 원본 값으로 교체한다.
    accepted_items가 없으면 기존 동작(비일치 전체 교체)을 유지한다(하위 호환).
    results가 비어 있어도 original_text에서 추출한 source_map로 교체할 수 있다.
    """
    accepted: set[str] | None = accepted_items  # None이면 전체 교체, set()이면 전체 교체, 비어있지 않으면 해당 항목만 교체
    fixed_lines = []
    source_map: dict[str, str] = {}
    for line in original_text.splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            source_map[key.strip()] = val.strip()

    # results가 비어 있으면, 원본 텍스트의 source_map만으로 accepted_items 교체를 수행한다.
    if not results:
        results = [
            {
                "item": key,
                "judgment": "불일치",
                "source_value": val,
                "cited_value": "",
                "basis": "",
                "correction_suggestion": "",
                "verified": False,
            }
            for key, val in source_map.items()
        ]

    # results 각 항목에 source_value가 비어 있으면 원본 텍스트 source_map에서 채운다.
    for r in results:
        if not r.get("source_value"):
            item = r.get("item")
            if item and item in source_map:
                r["source_value"] = source_map[item]

    for line in draft_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            fixed_lines.append(line)
            continue
        if ":" in stripped:
            key, _, val = stripped.partition(":")
            key = key.strip()
            val = val.strip()
            fixed_val = val
            # 교체 조건: (1) accepted_items에 포함되어 있고, (2) 불일치 판정이며, (3) source_value가 실제 값일 때
            # accepted가 비어있지 않은 집합이고 그 안에 key가 없으면 건너뛰고, None/빈 집합이면 전체 교체
            for r in results:
                if r.get("item") == key and r.get("judgment") == "불일치":
                    if accepted and key not in accepted:
                        break
                    sv = r.get("source_value")
                    if sv and isinstance(sv, str) and sv.strip():
                        raw = sv.strip()
                        # source_value가 "key: value" 형태로 들어와 있을 수 있으므로,
                        # 콜론이 있으면 값 부분만 취한다 (중복 키 출력 방지).
                        if ":" in raw:
                            _, _, raw = raw.partition(":")
                        fixed_val = raw.strip()
                    break
            if fixed_val != val:
                fixed_lines.append(f"{key}: {fixed_val}")
            else:
                fixed_lines.append(line)
        else:
            fixed_lines.append(line)

    fixed_text = "\n".join(fixed_lines)
    _ensure_fixed_file(fixed_text)
    _ensure_memory_file(results, fixed_text)
    return fixed_text


@router.post("/download/fixed")
async def download_fixed(body: DownloadFixedRequest):
    """POST /api/download/fixed — 사용자가 승인한 항목만 원본 값으로 교체한 고정본 반환.

    요청 바디 (다음 중 하나 사용, 우선순위 순):
      - memory_data 전체: check 응답의 memory_data를 그대로 전달
        - results, accepted_items, original_text, draft_text를 모두 포함할 수 있음
        - accepted_items만 있고 results가 있으면 results 기준으로 교체
      - accepted_items + results만 직접 전달 (original_text/draft_text는 자율)

    response: {"fixed_text": "..."}
    """
    memory_data = body.memory_data
    results = body.results
    accepted_items_explicit = body.accepted_items
    original_text = body.original_text
    draft_text = body.draft_text
    accepted: set[str] = set()

    # 1) memory_data 우선 처리
    if memory_data:
        mresults = memory_data.get("results")
        if mresults is not None:
            results = mresults
        accepted |= set(memory_data.get("accepted_items", []))
        if accepted_items_explicit:
            accepted |= set(accepted_items_explicit)
        if original_text is None:
            original_text = memory_data.get("original_text") or memory_data.get("original")
            if not original_text:
                raise HTTPException(
                    status_code=400,
                    detail="memory_data에 original_text 또는 original 필드가 필요합니다.",
                )
        if draft_text is None:
            draft_text = memory_data.get("draft_text") or memory_data.get("draft")
            if not draft_text:
                raise HTTPException(
                    status_code=400,
                    detail="memory_data에 draft_text 또는 draft 필드가 필요합니다.",
                )
        if not results:
            results = []
        # accepted_items가 비어 있으면 교체 없이 초안 그대로 반환
        if not accepted and original_text and draft_text:
            # accepted_items가 없지만 텍스트가 있으면 초안 그대로 반환 (200)
            fixed_text = draft_text or ""
            return DownloadFixedResponse(fixed_text=fixed_text)
        if not accepted:
            # accepted_items도 없고, replacement할 근거가 부족하면 400
            raise HTTPException(
                status_code=400,
                detail="'accepted_items'에 하나 이상의 항목을 지정하거나 memory_data에 accepted_items를 포함해야 합니다.",
            )
        fixed_text = generate_outputs(results, original_text or "", draft_text or "", accepted)
        return DownloadFixedResponse(fixed_text=fixed_text)

    # 2) results + accepted_items 조합
    if accepted_items_explicit is None:
        # accepted_items도 memory_data도 없으면 400
        raise HTTPException(
            status_code=400,
            detail="'accepted_items'가 필요합니다. (memory_data 없이 요청 시)",
        )
    accepted = set(accepted_items_explicit)
    if not accepted:
        # accepted_items가 빈 배열이면 400
        raise HTTPException(
            status_code=400,
            detail="'accepted_items'에 하나 이상의 항목을 지정해야 합니다.",
        )
    if not original_text:
        # accepted_items는 있으나 original_text가 없으면 400
        raise HTTPException(
            status_code=400,
            detail="'accepted_items'를 사용할 때는 'original_text'가 필요합니다.",
        )
    if results is None:
        results = []
    fixed_text = generate_outputs(results, original_text or "", draft_text or "", accepted)
    return DownloadFixedResponse(fixed_text=fixed_text)


def _extract_original_from_memory(memory_data: dict) -> str | None:
    """memory_data에서 원본 텍스트를 꺼내려 시도한다. 없을 수 있으므로 None 반환."""
    # memory.json은 보통 results + fixed_text만 저장한다.
    # 원본/초안 텍스트를 함께 저장한 커스텀 필드가 있으면 그것을 사용.
    return memory_data.get("original_text") or memory_data.get("original")


def _extract_draft_from_memory(memory_data: dict) -> str | None:
    """memory_data에서 초안 텍스트를 꺼내려 시도한다. 없을 수 있으므로 None 반환."""
    return memory_data.get("draft_text") or memory_data.get("draft")
