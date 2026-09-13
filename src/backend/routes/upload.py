# POST /api/upload — 원본/초안 파일 업로드.

from fastapi import APIRouter, UploadFile, File, HTTPException
from pathlib import Path
import uuid
import shutil

from ..config import UPLOAD_DIR
from ..models import UploadResponse

router = APIRouter()

ALLOWED_EXTENSIONS = {".xlsx", ".xls", ".txt", ".md", ".json"}


def _allowed(filename: str) -> bool:
    ext = Path(filename).suffix.lower()
    return ext in ALLOWED_EXTENSIONS


@router.post("/upload", response_model=UploadResponse)
async def upload_files(
    original: UploadFile = File(...),
    draft: UploadFile = File(...),
):
    """원본 자료 + AI 요약 초안 업로드.

    원본이 없으면 판정하지 않고 원본 업로드를 요청해야 함 (별도 엔드포인트 또는 이 엔드포인트에서 원본 필수).
    이미지/URL/PDF는 받지 않음.
    """
    if not _allowed(original.filename or ""):
        raise HTTPException(
            status_code=400,
            detail=f"원본 파일 확장자가 허용되지 않습니다: {original.filename}. 허용: {ALLOWED_EXTENSIONS}",
        )
    if not _allowed(draft.filename or ""):
        raise HTTPException(
            status_code=400,
            detail=f"초안 파일 확장자가 허용되지 않습니다: {draft.filename}. 허용: {ALLOWED_EXTENSIONS}",
        )

    original_id = uuid.uuid4().hex[:12]
    draft_id = uuid.uuid4().hex[:12]

    orig_path = Path(UPLOAD_DIR) / f"{original_id}_original{ Path(original.filename or 'file').suffix }"
    draft_path = Path(UPLOAD_DIR) / f"{draft_id}_draft{ Path(draft.filename or 'file').suffix }"

    orig_path.parent.mkdir(parents=True, exist_ok=True)

    with orig_path.open("wb") as f:
        shutil.copyfileobj(original.file, f)
    with draft_path.open("wb") as f:
        shutil.copyfileobj(draft.file, f)

    return UploadResponse(
        status="uploaded",
        original_id=original_id,
        draft_id=draft_id,
    )
