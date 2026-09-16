# MABC-FINAL 백엔드 요청/응답 모델.

from pydantic import BaseModel, Field
from typing import Optional


# ── upload ──────────────────────────────────────────────────────────────────

class UploadResponse(BaseModel):
    status: str = "uploaded"
    original_id: str = ""
    draft_id: str = ""


# ── check ───────────────────────────────────────────────────────────────────

class CheckRequest(BaseModel):
    original_id: str
    draft_id: str


class CheckResultItem(BaseModel):
    """검수 표 한 행. 인용 수치 하나당 하나."""
    item: str                       # 인용된 항목/수치 설명
    cited_value: str               # 초안에서 인용된 값 (문자열 보존)
    source_value: Optional[str]    # 원본에서 확인한 대응 값
    judgment: str                   # 5라벨: 일치/불일치/값은 있으나 항목 대응이 다름/원본에 없음/확인 불가
    basis: str                     # 근거: 원본 표의 행/열 라벨, 단위, 기준 시점 등
    correction_suggestion: Optional[str] = None  # 수정 제안
    verified: bool = False         # 사용자가 확인했는지 여부
    calculation: Optional[str] = None  # 계산 인용인 경우 계산식
    judgment_reason: Optional[str] = None  # 판정 이유


class CheckResponse(BaseModel):
    status: str = "done"            # "processing" | "done" | "error"
    results: list[CheckResultItem] = []
    elapsed_seconds: float = 0.0
    error: Optional[str] = None
    # Vercel 서버리스 무상태 대응: 생성된 파일 내용을 응답에 포함
    fixed_text: Optional[str] = None          # 고쳐진 초안 텍스트
    memory_data: Optional[dict] = None        # 기억 파일(memory.json) 내용


# ── download ────────────────────────────────────────────────────────────────

class DownloadMeta(BaseModel):
    filename: str
    content_type: str


class DownloadFixedRequest(BaseModel):
    accepted_items: list[str] | None = None
    results: list[dict] | None = None
    memory_data: dict | None = None
    original_text: str | None = None
    draft_text: str | None = None


class DownloadFixedResponse(BaseModel):
    fixed_text: str


# ── rerun ───────────────────────────────────────────────────────────────────

class RerunRequest(BaseModel):
    memory_data: dict               # 기억 파일 내용 (json)


class RerunResponse(BaseModel):
    status: str = "ok"
    remaining_checks: int = 0
    skipped_checks: int = 0


# ── example ─────────────────────────────────────────────────────────────────

class ExampleResponse(BaseModel):
    original_text: str = ""             # 예시 원본 (텍스트 표/md 형식)
    draft_text: str = ""               # 예시 초안
    memory_json: dict = {}             # 예시 기억 파일 내용
    expected_results: list[dict] = []  # 기대 판정 결과 요약 (사람 읽을 수 있는 형태)


# ── status ──────────────────────────────────────────────────────────────────

class StatusResponse(BaseModel):
    status: str = "processing"     # "processing" | "done" | "error"
    progress: str = ""
    partial_results: list[CheckResultItem] = []
    error: Optional[str] = None
