# GET /api/download/{type} — 고쳐진 파일 / 기억 파일 다운로드.

import json
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from ..config import UPLOAD_DIR

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


def generate_outputs(results: list[dict], original_text: str, draft_text: str):
    """check 결과를 받아 fixed_draft.txt와 memory.json을 생성하고 경로를 반환."""
    fixed_lines = []
    source_map: dict[str, str] = {}
    for line in original_text.splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            source_map[key.strip()] = val.strip()

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
            for r in results:
                if r.get("item") == key and r.get("judgment") in ("불일치", "값은 있으나 항목 대응이 다름", "원본에 없음"):
                    if r.get("source_value") and r["source_value"] != "None":
                        fixed_val = r["source_value"]
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
