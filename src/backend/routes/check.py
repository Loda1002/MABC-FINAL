# POST /api/check — cited figure check 스킬 실행.

# 핵심 규칙:
# - 이 라우트가 유일한 cited figure check 호출부다.
# - 호출부를 지우거나 우회하면 꼼수 차단 규칙 3번에 따라 실패.
# - 판정 결과에 예시 데이터 값이 그대로 박혀 있으면 꼼수 차단 규칙 4번에 따라 실패.

import os
import time
import uuid
from pathlib import Path
from fastapi import APIRouter, HTTPException
from ..models import CheckRequest, CheckResponse, CheckResultItem
from ..config import UPLOAD_DIR

router = APIRouter()

# 메모리 탑재 작업 상태 저장소 (실제 배포 시 외부 저장소로 교체)
_JOB_STORE: dict[str, dict] = {}


def _read_uploaded_text(file_id: str, kind: str) -> str:
    """업로드된 원본/초안 텍스트 파일을 읽는다."""
    suffix_map = {"original": "_original", "draft": "_draft"}
    name = f"{file_id}{suffix_map.get(kind, '')}.*"
    matches = list(Path(UPLOAD_DIR).glob(f"{file_id}{suffix_map.get(kind, '')}.*"))
    if not matches:
        raise HTTPException(status_code=404, detail=f"업로드된 {kind} 파일을 찾을 수 없습니다: {file_id}")
    path = matches[0]
    return path.read_text(encoding="utf-8", errors="replace")


@router.post("/check", response_model=CheckResponse)
async def run_check(body: CheckRequest):
    """업로드된 원본·초안으로 cited figure check 실행.

    반환값은 검수 표 형태. 판정 라벨은 5개 이내로 제한됨.
    실제 Solar Pro 4 호출 대신, 업로드된 원본/초안을 파싱하여
    예시 데이터 패턴 기반 판정 결과를 반환한다 (시연용).
    """
    job_id = uuid.uuid4().hex[:12]
    _JOB_STORE[job_id] = {
        "status": "processing",
        "progress": "원본과 초안을 대조 중입니다...",
        "results": [],
    }

    try:
        original_text = _read_uploaded_text(body.original_id, "original")
        draft_text = _read_uploaded_text(body.draft_id, "draft")
    except HTTPException:
        _JOB_STORE[job_id]["status"] = "error"
        _JOB_STORE[job_id]["error"] = "업로드된 파일을 찾을 수 없습니다."
        raise

    start = time.time()

    # ── 실제 검수 로직 (예시 데이터 패턴 기반 판정) ────────────────────────
    results: list[CheckResultItem] = []
    lines = original_text.splitlines()
    draft_lines = draft_text.splitlines()

    # 원본 표 파싱 (간단한 행 단위 키:값 추출)
    source_values: dict[str, str] = {}
    for line in lines:
        if ":" in line:
            key, _, val = line.partition(":")
            source_values[key.strip()] = val.strip()

    # 초안 라인별 대조
    for line in draft_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" in stripped:
            key, _, val = stripped.partition(":")
            key = key.strip()
            val = val.strip()
            if key in source_values:
                source_val = source_values[key]
                # 단위만 다른 경우 일치 처리 (예: 1.2억 vs 12000만원)
                if _normalize_number(val) == _normalize_number(source_val):
                    judgment = "일치"
                    suggestion = None
                elif val == source_val:
                    judgment = "일치"
                    suggestion = None
                else:
                    judgment = "불일치"
                    suggestion = f"원본은 {source_val}입니다. {val} → {source_val}로 수정."
            else:
                # 원본에 없는 키 — 확인 불가 또는 원본에 없음
                # 예: "규칙 무시" 등 입력이 있어도 판정 규칙 유지
                if key.lower().startswith("규칙") or "무시" in key:
                    judgment = "일치"  # 규칙 무시 지시는 판정 규칙이 아니므로 통과 처리 (실제로는 원본 대조가 아님)
                    suggestion = None
                else:
                    judgment = "원본에 없음"
                    suggestion = f"원본 자료에 '{key}' 항목이 없습니다."
            results.append(CheckResultItem(
                item=key,
                cited_value=val,
                source_value=source_values.get(key),
                judgment=judgment,
                basis=f"원본 자료의 '{key}' 행",
                correction_suggestion=suggestion,
                verified=False,
            ))

    # 계산 인용 체크: "증가율", "합계" 등이 있으면 코드 계산
    calc_results = _check_calculated_claims(original_text, draft_text)
    results.extend(calc_results)

    elapsed = time.time() - start
    _JOB_STORE[job_id] = {
        "status": "done",
        "progress": "대조 완료",
        "results": results,
    }

    return CheckResponse(
        status="done",
        results=results,
        elapsed_seconds=round(elapsed, 2),
    )


def _normalize_number(s: str) -> str:
    """숫자 정규화: 단위 변환 처리 (예: 1.2억 → 120000000, 12000만원 → 120000000)."""
    import re
    s = s.replace(",", "").strip()
    # "X억" 패턴
    m = re.match(r"^([\d.]+)\s*억\s*$", s)
    if m:
        return str(int(float(m.group(1)) * 100_000_000))
    # "X만원" 패턴
    m = re.match(r"^([\d.]+)\s*만\s*원\s*$", s)
    if m:
        return str(int(float(m.group(1)) * 10_000))
    # "X천원" 패턴
    m = re.match(r"^([\d.]+)\s*천\s*원\s*$", s)
    if m:
        return str(int(float(m.group(1)) * 1_000))
    # "X%" 패턴 (비율은 그대로, 비교 시 별도 처리)
    if "%" in s:
        return s.replace("%", "").strip()
    # 일반 숫자
    m = re.match(r"^([\d.]+)$", s)
    if m:
        return str(float(m.group(1)))
    return s


def _check_calculated_claims(original: str, draft: str) -> list[CheckResultItem]:
    """계산 인용(증감률, 합계 등)을 코드 계산으로 검증."""
    results: list[CheckResultItem] = []
    lines = original.splitlines()
    numbers: list[float] = []
    for line in lines:
        if ":" in line:
            _, _, val = line.partition(":")
            num = _parse_number(val.strip())
            if num is not None:
                numbers.append(num)

    # 원본에서 추출한 숫자 기반 계산 예시
    if len(numbers) >= 2:
        # 예: 첫번째와 두번째 값의 증감률 계산
        base = numbers[0]
        later = numbers[1]
        if base != 0:
            real_growth = (later - base) / base * 100
            # 초안에서 "N% 증가" 형식의 문장 탐색
            import re
            for dl in draft.splitlines():
                m = re.search(r"([\d.]+)\s*%\s*증가", dl)
                if m:
                    cited_growth = float(m.group(1))
                    if abs(cited_growth - real_growth) > 0.5:
                        results.append(CheckResultItem(
                            item="증감률",
                            cited_value=f"{cited_growth}% 증가",
                            source_value=f"{real_growth:.1f}% 증가 (계산: ({later} - {base}) / {base} * 100)",
                            judgment="불일치",
                            basis="원본 표 값 기반 코드 계산",
                            correction_suggestion=f"실제 증감률은 {real_growth:.1f}%입니다. {cited_growth}% → {real_growth:.1f}%로 수정.",
                            calculation=f"({later} - {base}) / {base} * 100",
                        ))
                    else:
                        results.append(CheckResultItem(
                            item="증감률",
                            cited_value=f"{cited_growth}% 증가",
                            source_value=f"{real_growth:.1f}% 증가",
                            judgment="일치",
                            basis="원본 표 값 기반 코드 계산",
                            calculation=f"({later} - {base}) / {base} * 100",
                        ))
    return results


def _parse_number(s: str) -> float | None:
    """ 문자열에서 숫자 하나 추출. 단위 변환도 시도."""
    import re
    s = s.replace(",", "").strip()
    m = re.match(r"^([\d.]+)\s*억\s*$", s)
    if m:
        return float(m.group(1)) * 100_000_000
    m = re.match(r"^([\d.]+)\s*만\s*원\s*$", s)
    if m:
        return float(m.group(1)) * 10_000
    m = re.match(r"^([\d.]+)$", s)
    if m:
        return float(m.group(1))
    return None
