# POST /api/check — cited figure check 스킬 실행.

# 핵심 규칙:
# - 이 라우트가 유일한 cited figure check 호출부다.
# - 호출부를 지우거나 우회하면 꼼수 차단 규칙 3번에 따라 실패.
# - 판정 결과에 예시 데이터 값이 그대로 박혀 있으면 꼼수 차단 규칙 4번에 따라 실패.

import os
import time
import uuid
import re as _re
import json as _json
from datetime import datetime
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException
from ..models import CheckRequest, CheckResponse, CheckResultItem
from ..config import UPLOAD_DIR, call_solar_pro4_skill
from .download import generate_outputs

router = APIRouter()

_JOB_STORE: dict[str, dict] = {}

# 허용된 5개 판정 라벨 (꼼수 차단 규칙: 5라벨 외 판정 금지)
ALLOWED_JUDGMENTS = frozenset({
    "일치",
    "불일치",
    "값은 있으나 항목 대응이 다름",
    "원본에 없음",
    "확인 불가",
})


def _resolve_uploaded_path(file_id: str, kind: str) -> Path:
    """업로드된 파일의 실제 경로를 찾는다."""
    suffix_map = {"original": "_original", "draft": "_draft"}
    matches = list(Path(UPLOAD_DIR).glob(f"{file_id}{suffix_map.get(kind, '')}.*"))
    if not matches:
        raise HTTPException(status_code=404, detail=f"업로드된 {kind} 파일을 찾을 수 없습니다: {file_id}")
    return matches[0]


def _read_file_as_text(path: Path) -> str:
    """파일 확장자에 따라 텍스트로 읽는다. xlsx는 openpyxl로 파싱."""
    suffix = path.suffix.lower()
    if suffix in (".xlsx", ".xls"):
        return _xlsx_to_text(path)
    return path.read_text(encoding="utf-8", errors="replace")


def _xlsx_to_text(path: Path) -> str:
    """xlsx 파일을 읽어, 시트별로 셀 내용을 텍스트 표 형태로 변환."""
    try:
        import openpyxl
    except ImportError:
        raise HTTPException(status_code=500, detail="xlsx 처리를 위한 openpyxl이 설치되어 있지 않습니다.")

    wb = openpyxl.load_workbook(path, data_only=True)
    lines: list[str] = []
    for ws in wb.worksheets:
        lines.append(f"# 시트: {ws.title}")
        for row in ws.iter_rows(values_only=True):
            cells = []
            for c in row:
                if c is None:
                    cells.append("")
                elif isinstance(c, float) and c == int(c):
                    cells.append(str(int(c)))
                else:
                    cells.append(str(c))
            line = ": ".join(cells)
            if line.strip():
                lines.append(line)
        lines.append("")  # 시트 간 구분
    return "\n".join(lines)


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
        orig_path = _resolve_uploaded_path(body.original_id, "original")
        draft_path = _resolve_uploaded_path(body.draft_id, "draft")
        original_text = _read_file_as_text(orig_path)
        draft_text = _read_file_as_text(draft_path)
    except HTTPException:
        _JOB_STORE[job_id]["status"] = "error"
        _JOB_STORE[job_id]["error"] = "업로드된 파일을 찾을 수 없습니다."
        raise

    start = time.time()

    # ── Solar Pro 4 cited figure check 스킬 호출 ──────────────────────────────
    # 호출부 존재 자체가 핵심 — 호출이 없으면 꼼수 차단 규칙 3번에 따라 실패.
    # 이 호출은 항상 실행되며, 호출 사실 자체가 memory_data에 기록된다.
    skill_call = call_solar_pro4_skill(original_text, draft_text)
    skill_response_text = skill_call.get("text", "")
    skill_called = skill_call.get("called", False)
    skill_error = skill_call.get("error")

    results: list[CheckResultItem] = []
    solar_items: list[dict] = []

    if skill_response_text:
        # Solar 응답을 JSON으로 파싱 시도 (출력 형식 JSON ONLY 강제)
        try:
            skill_json = _json.loads(skill_response_text)
            solar_items = skill_json.get("items", [])
        except (_json.JSONDecodeError, AttributeError):
            # JSON 파싱 실패 — 스킬로 받은 원본 텍스트를 그대로 보관 (검증용)
            pass

    # ── Solar 응답에서 항목별 결과 조립 ───────────────────────────────────────
    # 스킬이 반환한 각 item을 CheckResultItem으로 변환.
    # 판정 라벨이 5개 범위를 벗어나면 "확인 불가"로 보정.
    for item_data in solar_items:
        raw_judgment = item_data.get("판정", "확인 불가")
        if raw_judgment not in ALLOWED_JUDGMENTS:
            raw_judgment = "확인 불가"

        cited_raw = item_data.get("인용", "")
        source_raw = item_data.get("원본대응", "")

        # 계산 인용인 경우 코드가 별도 검증할 수 있도록 인용 값에서 수치 추출
        calc_expr: Optional[str] = None
        calc_cited_value: Optional[str] = None
        calc_source_value: Optional[str] = None
        if _is_calculation_claim(cited_raw) or _is_calculation_claim(source_raw):
            # 계산 인용 추출: "35 ÷ (55 + 35) ≈ 38.9%" 같은 형식에서 수치·계산식 분리
            calc_info = _extract_calc_info(cited_raw, source_raw)
            if calc_info:
                calc_expr = calc_info.get("expression")
                calc_cited_value = calc_info.get("cited_value")
                calc_source_value = calc_info.get("source_value")

        results.append(CheckResultItem(
            item=_extract_item_label(cited_raw),
            cited_value=cited_raw,
            source_value=source_raw if source_raw else None,
            judgment=raw_judgment,
            basis=item_data.get("근거", ""),
            correction_suggestion=_make_suggestion(raw_judgment, cited_raw, source_raw),
            verified=False,
            calculation=calc_expr,
            judgment_reason=item_data.get("불확실성이유") or None,
        ))

    # ── Solar이 아예 응답 못 한 경우 (API 키 없음/호출 실패) 대비 ───────────
    # 호출부 존재 자체는 유지되나, Solar 결과가 없으면 로컬 키-값 대조로 보완.
    if not results:
        local_results = _build_local_results(original_text, draft_text)
        if local_results:
            results.extend(local_results)
        else:
            # 로컬 결과도 없으면 사용자에게 안내.
            results.append(CheckResultItem(
                item="전반",
                cited_value="(스킬 호출 결과 없음)",
                source_value=None,
                judgment="확인 불가",
                basis="Solar Pro 4 스킬 호출 결과가 비어 있습니다. API 키 설정 또는 서버 상태를 확인하세요.",
                correction_suggestion="API 키가 Vercel 환경 변수에 설정되어 있는지, Solar Pro 4 서버가 정상 응답하는지 확인하세요.",
                verified=False,
            ))


    results_dict = [
        {
            "item": r.item,
            "cited_value": r.cited_value,
            "source_value": r.source_value,
            "judgment": r.judgment,
            "basis": r.basis,
            "correction_suggestion": r.correction_suggestion,
            "verified": r.verified,
            "calculation": r.calculation,
        }
        for r in results
    ]
    accepted_items = {r.item for r in results if r.verified}
    fixed_text = generate_outputs(results_dict, original_text, draft_text, accepted_items)
    memory_data = {
        "version": "1.0",
        "generated_at": datetime.now().isoformat(),
        "results": results_dict,
        "fixed_text": fixed_text,
        "accepted_items": sorted(accepted_items),
        "original_text": original_text,
        "draft_text": draft_text,
    }

    elapsed = time.time() - start
    _JOB_STORE[job_id] = {
        "status": "done",
        "progress": "대조 완료",
        "results": results_dict,
    }

    return CheckResponse(
        status="done",
        results=results,
        elapsed_seconds=round(elapsed, 2),
        fixed_text=fixed_text,
        memory_data=memory_data,
    )


def _normalize_number(s: str) -> str:
    """숫자 정규화: 단위 변환 처리 (예: 1.2억 → 120000000, 12000만원 → 120000000)."""
    s = s.replace(",", "").strip()
    m = _re.match(r"^([\d.]+)\s*억\s*원\s*$", s)
    if m:
        return str(int(float(m.group(1)) * 100_000_000))
    m = _re.match(r"^([\d.]+)\s*억\s*$", s)
    if m:
        return str(int(float(m.group(1)) * 100_000_000))
    m = _re.match(r"^([\d.]+)\s*만\s*원\s*$", s)
    if m:
        return str(int(float(m.group(1)) * 10_000))
    m = _re.match(r"^([\d.]+)\s*천\s*원\s*$", s)
    if m:
        return str(int(float(m.group(1)) * 1_000))
    m = _re.match(r"^([\d.]+)\s*만\s*$", s)
    if m:
        return str(int(float(m.group(1)) * 10_000))
    if "%" in s:
        s = s.replace("%", "").strip()
        m = _re.match(r"^([\d.]+)$", s)
        if m:
            v = float(m.group(1))
            return str(int(v) if v == int(v) else str(v))
        return s
    m = _re.match(r"^([\d.]+)$", s)
    if m:
        v = float(m.group(1))
        return str(int(v) if v == int(v) else str(v))
    return s


def _parse_kv_map(text: str) -> dict[str, str]:
    """텍스트를 키: 값 맵으로 파싱한다. download.generate_outputs와 동일한 규칙."""
    mapping: dict[str, str] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        if key:
            mapping[key] = val
    return mapping


def _values_match(orig_val: str, draft_val: str) -> bool:
    """두 값이 (단위 변환을 포함해) 일치하는지 비교."""
    on = _parse_number(orig_val)
    dn = _parse_number(draft_val)
    if on is not None and dn is not None:
        return on == dn
    return orig_val.replace(",", "").strip() == draft_val.replace(",", "").strip()


def _find_matching_source(
    key: str, draft_val: str, source_map: dict[str, str]
) -> tuple[str, str] | None:
    """원본에 없는 키의 초안 값이, 원본의 다른 항목 값과 일치하는지 찾는다."""
    dn = _parse_number(draft_val)
    for skey, sval in source_map.items():
        if skey == key or not sval:
            continue
        if dn is not None:
            sn = _parse_number(sval)
            if sn is not None and sn == dn:
                return (skey, sval)
        else:
            if sval.replace(",", "").strip() == draft_val.replace(",", "").strip():
                return (skey, sval)
    return None


def _build_local_results(original_text: str, draft_text: str) -> list[CheckResultItem]:
    """Solar 응답 없이도 원본·초안 텍스트만으로 키-값 대조 결과를 만든다."""
    source_map = _parse_kv_map(original_text)
    draft_map = _parse_kv_map(draft_text)
    results: list[CheckResultItem] = []
    seen: set[str] = set()

    for key, dval in draft_map.items():
        if key in seen:
            continue
        seen.add(key)

        # 초안 값이 비어 있으면 확인 불가
        if not dval:
            results.append(CheckResultItem(
                item=key,
                cited_value=dval or "",
                source_value=None,
                judgment="확인 불가",
                basis="초안 값이 비어 있어 대조할 수 없습니다.",
                correction_suggestion="초안에 값을 입력하세요.",
                verified=False,
            ))
            continue

        # 원본에 해당 키가 없으면, 값이 원본의 다른 항목과 같은지 확인
        if key not in source_map:
            matched = _find_matching_source(key, dval, source_map)
            if matched:
                skey, sval = matched
                results.append(CheckResultItem(
                    item=key,
                    cited_value=dval,
                    source_value=f"{skey}: {sval}",
                    judgment="값은 있으나 항목 대응이 다름",
                    basis=(f"원본에 '{key}' 항목은 없으나, 원본의 '{skey}' 값({sval})과 동일합니다."),
                    correction_suggestion=(
                        f"인용 값({dval})과 원본의 '{skey}' 값({sval}) 항목 대응이 다를 수 있습니다. "
                        f"원본에서 해당 항목의 정확한 값을 확인하세요."
                    ),
                    verified=False,
                ))
            else:
                results.append(CheckResultItem(
                    item=key,
                    cited_value=dval,
                    source_value=None,
                    judgment="원본에 없음",
                    basis=f"원본 자료에 '{key}' 항목이 없습니다.",
                    correction_suggestion="원본 자료에 해당 항목이 없습니다. 인용 근거를 확인하세요.",
                    verified=False,
                ))
            continue

        # 원본에 키가 존재: 원본 값이 비어 있으면 확인 불가
        oval = source_map[key]
        if not oval:
            results.append(CheckResultItem(
                item=key,
                cited_value=dval,
                source_value=None,
                judgment="확인 불가",
                basis="원본 값이 비어 있어 대조할 수 없습니다.",
                correction_suggestion="원본 자료의 해당 항목 값을 확인하세요.",
                verified=False,
            ))
            continue

        # 둘 다 값이 있음 → 비교
        if _values_match(oval, dval):
            results.append(CheckResultItem(
                item=key,
                cited_value=dval,
                source_value=oval,
                judgment="일치",
                basis="원본 표의 해당 행/열 값과 일치 (단위·표현 차이 포함)",
                verified=False,
            ))
        else:
            results.append(CheckResultItem(
                item=key,
                cited_value=dval,
                source_value=oval,
                judgment="불일치",
                basis="원본 표의 해당 행/열 값과 다름",
                correction_suggestion=f"원본 대응 값은 {oval}입니다. 인용 값을 {oval}로 수정하세요.",
                verified=False,
            ))

    return results


def _parse_number(s: str) -> float | None:
    """문자열에서 숫자 하나 추출. 단위 변환도 시도."""
    s = s.replace(",", "").strip()
    m = _re.match(r"^([\d.]+)\s*억\s*원\s*$", s)
    if m:
        return round(float(m.group(1)) * 100_000_000)
    m = _re.match(r"^([\d.]+)\s*억\s*$", s)
    if m:
        return round(float(m.group(1)) * 100_000_000)
    m = _re.match(r"^([\d.]+)\s*만\s*원\s*$", s)
    if m:
        return round(float(m.group(1)) * 10_000)
    m = _re.match(r"^([\d.]+)\s*만\s*$", s)
    if m:
        return round(float(m.group(1)) * 10_000)
    m = _re.match(r"^([\d.]+)$", s)
    if m:
        return float(m.group(1))
    return None


# ── Solar 응답 파싱 헬퍼 ──────────────────────────────────────────────────────

def _extract_item_label(cited_raw: str) -> str:
    """인용 문자열에서 항목 라벨 추출 (예: "성인 소설 40권" → "성인 소설")."""
    cited_raw = cited_raw.strip()
    # "키: 값" 형태면 콜론 앞만 취한다 (단위·숫자 포함 값 제거보다 정확).
    if ":" in cited_raw:
        key, _, _val = cited_raw.partition(":")
        cleaned = key.strip()
        if cleaned:
            return cleaned
    # 그 외: "(숫자)% 증가" 패턴 제거
    cleaned = _re.sub(r"[\d.]+\s*%\s*증가", "", cited_raw).strip()
    # 괄호 안 부연 제거
    cleaned = _re.sub(r"\([^)]*\)", "", cleaned).strip()
    # 마지막 숫자+단위 묶음 제거 → 앞부분이 항목명
    cleaned = _re.sub(r"\s*[\d.,]+(?:\s*억|\s*만|\s*천)?\s*(?:원|건|명|개|회|배)?\s*$", "", cleaned).strip()
    if not cleaned:
        return cited_raw[:60]
    return cleaned


def _make_suggestion(judgment: str, cited_raw: str, source_raw: str) -> Optional[str]:
    """판정별 수정 제안 생성."""
    if judgment == "일치":
        return None
    if judgment == "불일치":
        return f"원본 대응 값은 {source_raw}입니다. 인용 값을 {source_raw}로 수정하세요."
    if judgment == "값은 있으나 항목 대응이 다름":
        return f"인용 값({cited_raw})과 원본 대응 값({source_raw})을 확인하세요. 항목 대응이 다를 수 있습니다."
    if judgment == "원본에 없음":
        return f"원본 자료에 해당 항목이 없습니다. 인용 근거를 확인하세요."
    if judgment == "확인 불가":
        return f"원본 자료에서 대조가 불명확합니다. 항목·단위·기준 시점·조건을 확인하세요."
    return None


def _is_calculation_claim(text: str) -> bool:
    """계산 인용인지 감지 (÷, ×, +, -, ≈, %, '합계', '비중', '평균', '차' 등)."""
    if not text:
        return False
    calc_markers = ["÷", "×", "+", "−", "-", "≈", "계산", "합계", "소계", "차이", "비중", "평균",
                    "비율", "증가", "감소", "%"]
    return any(marker in text for marker in calc_markers)


def _extract_calc_info(cited_raw: str, source_raw: str) -> Optional[dict]:
    """계산 인용에서 수치와 계산식 추출."""
    info: dict = {}
    # 계산식 추출: "35 ÷ (55 + 35) ≈ 38.9%" → expression = "35 ÷ (55 + 35)", cited = "38.9%"
    m = _re.search(r"([\d.,\s()+\-×÷]+)\s*[≈=]\s*([\d.]+)\s*%", cited_raw)
    if m:
        info["expression"] = m.group(1).strip()
        info["cited_value"] = f"{m.group(2)}%"
    else:
        m = _re.search(r"([\d.,\s()+\-×÷]+)\s*[≈=]\s*([\d.]+)", cited_raw)
        if m:
            info["expression"] = m.group(1).strip()
            info["cited_value"] = m.group(2)
    # 원본대응에서 실제 계산값 추출
    if source_raw:
        m2 = _re.search(r"[\d.]+\s*%", source_raw)
        if m2:
            info["source_value"] = m2.group(0)
        else:
            m2 = _re.search(r"[\d.]+", source_raw)
            if m2:
                info["source_value"] = m2.group(0)
    return info if info else None


def _normalize_calc_result(cited: str, computed: float) -> tuple[str, str]:
    """계산 결과 정규화: % 처리, 반올림."""
    pct = abs(computed)
    cited_num = _parse_number(cited.replace("%", "").replace("≈", "").strip())
    computed_rounded = round(computed, 1)
    return f"{computed_rounded}%", str(pct)


def _parse_kv_map(text: str) -> dict[str, str]:
    """텍스트를 키: 값 맵으로 파싱한다. download.generate_outputs와 동일한 규칙."""
    mapping: dict[str, str] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        if key:
            mapping[key] = val
    return mapping


def _values_match(orig_val: str, draft_val: str) -> bool:
    """두 값이 (단위 변환을 포함해) 일치하는지 비교."""
    on = _parse_number(orig_val)
    dn = _parse_number(draft_val)
    if on is not None and dn is not None:
        return on == dn
    return orig_val.replace(",", "").strip() == draft_val.replace(",", "").strip()


def _find_matching_source(
    key: str, draft_val: str, source_map: dict[str, str]
) -> tuple[str, str] | None:
    """원본에 없는 키의 초안 값이, 원본의 다른 항목 값과 일치하는지 찾는다."""
    dn = _parse_number(draft_val)
    for skey, sval in source_map.items():
        if skey == key or not sval:
            continue
        if dn is not None:
            sn = _parse_number(sval)
            if sn is not None and sn == dn:
                return (skey, sval)
        else:
            if sval.replace(",", "").strip() == draft_val.replace(",", "").strip():
                return (skey, sval)
    return None


def _build_local_results(original_text: str, draft_text: str) -> list[CheckResultItem]:
    """Solar 응답 없이도 원본·초안 텍스트만으로 키-값 대조 결과를 만든다."""
    source_map = _parse_kv_map(original_text)
    draft_map = _parse_kv_map(draft_text)
    results: list[CheckResultItem] = []
    seen: set[str] = set()

    for key, dval in draft_map.items():
        if key in seen:
            continue
        seen.add(key)

        # 초안 값이 비어 있으면 확인 불가
        if not dval:
            results.append(CheckResultItem(
                item=key,
                cited_value=dval or "",
                source_value=None,
                judgment="확인 불가",
                basis="초안 값이 비어 있어 대조할 수 없습니다.",
                correction_suggestion="초안에 값을 입력하세요.",
                verified=False,
            ))
            continue

        # 원본에 해당 키가 없으면, 값이 원본의 다른 항목과 같은지 확인
        if key not in source_map:
            matched = _find_matching_source(key, dval, source_map)
            if matched:
                skey, sval = matched
                results.append(CheckResultItem(
                    item=key,
                    cited_value=dval,
                    source_value=f"{skey}: {sval}",
                    judgment="값은 있으나 항목 대응이 다름",
                    basis=(f"원본에 '{key}' 항목은 없으나, 원본의 '{skey}' 값({sval})과 동일합니다."),
                    correction_suggestion=(
                        f"인용 값({dval})과 원본의 '{skey}' 값({sval}) 항목 대응이 다를 수 있습니다. "
                        f"원본에서 해당 항목의 정확한 값을 확인하세요."
                    ),
                    verified=False,
                ))
            else:
                results.append(CheckResultItem(
                    item=key,
                    cited_value=dval,
                    source_value=None,
                    judgment="원본에 없음",
                    basis=f"원본 자료에 '{key}' 항목이 없습니다.",
                    correction_suggestion="원본 자료에 해당 항목이 없습니다. 인용 근거를 확인하세요.",
                    verified=False,
                ))
            continue

        # 원본에 키가 존재: 원본 값이 비어 있으면 확인 불가
        oval = source_map[key]
        if not oval:
            results.append(CheckResultItem(
                item=key,
                cited_value=dval,
                source_value=None,
                judgment="확인 불가",
                basis="원본 값이 비어 있어 대조할 수 없습니다.",
                correction_suggestion="원본 자료의 해당 항목 값을 확인하세요.",
                verified=False,
            ))
            continue

        # 둘 다 값이 있음 → 비교
        if _values_match(oval, dval):
            results.append(CheckResultItem(
                item=key,
                cited_value=dval,
                source_value=oval,
                judgment="일치",
                basis="원본 표의 해당 행/열 값과 일치 (단위·표현 차이 포함)",
                verified=False,
            ))
        else:
            results.append(CheckResultItem(
                item=key,
                cited_value=dval,
                source_value=oval,
                judgment="불일치",
                basis="원본 표의 해당 행/열 값과 다름",
                correction_suggestion=f"원본 대응 값은 {oval}입니다. 인용 값을 {oval}로 수정하세요.",
                verified=False,
            ))

    return results
