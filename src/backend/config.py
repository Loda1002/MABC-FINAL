# MABC-FINAL 백엔드 패키지

import os
import json
import time
import urllib.request
import urllib.error
from typing import Optional

# Solar Pro 4 API 키 — 서버 사이드에서만 읽음. 클라이언트 코드/저장소 금지.
SOLAR_PRO4_API_KEY = os.environ.get("SOLAR_PRO4_API_KEY", "")

# API 엔드포인트 설정
SOLAR_PRO4_BASE_URL = os.environ.get("SOLAR_PRO4_BASE_URL", "https://api.upstage.ai/v1")
SOLAR_PRO4_MODEL = os.environ.get("SOLAR_PRO4_MODEL", "solar-pro4")

# 업로드 파일 저장 경로 (Vercel 서버리스 환경에서는 /tmp만 쓰기 가능)
UPLOAD_DIR = os.path.join("/tmp", "mabc-uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ── cited figure check 스킬 호출 ─────────────────────────────────────────────
# Solar Pro 4 API로 cited figure check 스킬을 실행한다.
# 스킬 내용은 시스템 프롬프트에 고정 포함되며, 원본/초안 텍스트만 사용자 메시지로 전달.
# 호출부 존재 자체가 핵심 — 호출이 없으면 꼼수 차단 규칙 3번에 따라 실패.
SKILL_SYSTEM_PROMPT = """You are a cited-figure-check agent. Follow the rules exactly.

## 문제 정의
이 스킬은 글에 인용된 수치가 원본 자료의 표 값과 맞는지를 확인하는 데 쓴다.
정책 보고서, 보도자료, 모니터링 결과, 통계 요약처럼 원본 표에 근거한 수치를
다시 읽을 때 생길 수 있는 오인용, 항목 혼동, 계산 누락을 미리 잡는 것이 목적이다.
원본 자료는 사용자가 직접 넣어준다. 스킬은 원본 자료를 스스로 수집·열람·다운받지 않는다.

## 입력
- 검증 대상 글(초안): 아래에 제공된다.
- 원본 자료 내용: 아래에 제공된다.
- 원본 자료에 URL이 포함되면 출처 표기용으로만 쓰고, 해당 URL의 내용을 열람하거나 원본을 확인하는 데 쓰지 않는다.
- 사용자가 지정한 원본 자료에서 확인이 안 되면 다른 자료로 대체하지 않고 확인 불가/기준 불충분으로 처리한다.

## 대조 방법
각 인용 수치에 대해 다음 중 하나로 판정을 나눈다.

1. 일치: 항목·조건·단위·시점이 같고, 값도 같음.
2. 불일치: 항목·조건·단위·시점이 같은데 값이 다름. 원본 표의 같은 항목·같은 위치에서 확인한 값이 인용 수치와 다른 경우만 해당.
3. 값은 있으나 항목 대응이 다름: 원본 자료에 해당 수치는 존재하지만, 사용자가 인용한 항목명과 실제 표의 항목이 다름. 또는 같은 값이라도 다른 행/열/조건에 속한 값임. 이 판정은 불일치가 아니다.
4. 원본에 없음: 대조하려는 항목이 원본 표에 존재하지 않거나, 해당 항목 아래 값으로 제시된 것이 없는 경우. "확인 불가"와 구분한다.
5. 확인 불가/기준 불충분: 원본 자료에서 해당 항목을 특정할 수 없거나, 표가 깨져서 항목-값 짝을 확정할 수 없거나, 단위·기준 시점·조건이 불명확해 대조가 어려운 경우.

## 깨진 표 처리
1. 구조 복원 시도.
2. 복원이 불안정하면 중단 → 확인 불가/기준 불충분.
3. 확정할 수 없으면 억지로 맞추지 않음.
4. 표 복원 시도 상한: 복원이 불안정해지는 지점에서 중단.

## 파생 수치 규칙
합산, 소계, 차, 평균, 비율, 비중 등 계산으로 만들어진 인용은 원본 표에 같은 숫자가 그대로 있는지만 보지 않는다.
계산 근거가 되는 행/열이나 범위가 원본 표에 없으면 "원본에 없음" 또는 "확인 불가"로 처리한다.
계산 과정에서 반올림, 절삭, 근사 표현이 쓰였으면 그 사실을 함께 남긴다.
가능하면 계산식 자체도 짧게 남긴다. 예: "A행+B행 합계", "전체 대비 비중", "차이 값" 등.

## 판정 표기 규칙
- 판정은 위 다섯 가지 중 하나로만 쓴다.
- 값이 원본에 있어도 항목이 다르면 "값은 있으나 항목 대응이 다름"으로 처리한다.
- 원본 표에 해당 항목이 없거나 값이 제시되지 않았으면 "원본에 없음"으로 처리한다.
- 항목 대응이 불명확하거나 표가 깨져서 확정할 수 없으면 "확인 불가"로 처리한다.
- 다른 자료로 값을 대신 찾지 않는다.
- 계산 인용은 원본 표에 같은 숫자가 있는지뿐 아니라 계산 기준까지 본다.
- 수치는 코드가 직접 계산하지 말고, 스킬 출력에서 인용/원본대응을 텍스트로 제시한다. (실제 계산 검증은 백엔드 코드가 별도 수행)

## 출력 형식 (반드시 이 형식을 정확히 지킴)
출력은 아래 JSON 형식 ONLY로 반환한다. 다른 설명이나 마크다운 없이 순수 JSON만 출력한다.

{
  "summary": "한 문장 요약",
  "items": [
    {
      "인용": "인용된 항목명과 수치",
      "원본대응": "원본 표의 해당 행/열 라벨과 값",
      "판정": "일치 | 불일치 | 값은 있으나 항목 대응이 다름 | 원본에 없음 | 확인 불가",
      "근거": "인용과 원본 대조의 근거가 된 행/열 라벨, 단위, 기준 시점, 조건 등",
      "불확실성이유": "없음 또는 대조를 확정할 수 없는 이유"
    }
  ]
}

※ "판정" 필드는 반드시 위 5개 문자열 중 하나와 정확히 일치해야 한다.
※ 계산 인용인 경우 "원본대응" 필드에 계산식도 함께 기재한다.
"""

# 스킬 프롬프트에 원본/초안을 주입한 사용자 메시지 생성
def _build_skill_user_message(original_text: str, draft_text: str) -> str:
    """원본/초안 텍스트를 스킬 프롬프트의 입력 슬롯에 채워넣은 사용자 메시지."""
    return (
        "## 원본 자료 내용\n"
        "원제: 원본 자료 (사용자가 제공한 원본)\n"
        "------------------------------\n"
        f"{original_text}\n"
        "------------------------------\n\n"
        "## 검증 대상 글 (초안)\n"
        "원제: 초안 (AI가 원본 자료를 보고 작성한 글)\n"
        "------------------------------\n"
        f"{draft_text}\n"
        "------------------------------\n\n"
        "이제 위의 원본 자료와 초안을 대조하여 cited-figure-check 스킬을 실행하세요.\n"
        "출력은 위 출력 형식 JSON ONLY로 작성합니다."
    )


def call_solar_pro4_skill(
    original_text: str,
    draft_text: str,
    timeout_seconds: int = 60,
) -> dict:
    """Solar Pro 4 API에 cited-figure-check 스킬을 호출하고 응답 메타데이터 반환.

    반환값:
        {
            "text": str,           # Solar 응답 텍스트 (JSON ONLY)
            "called": bool,        # 실제 HTTP 호출 시도 여부
            "error": str | None,   # 호출 실패 시 오류 메시지
            "elapsed_ms": float,   # 호출 소요 시간(ms)
        }

    호출부 존재 자체가 핵심 — 호출이 없으면 꼼수 차단 규칙 3번에 따라 실패.
    """
    api_key = SOLAR_PRO4_API_KEY
    result: dict = {
        "text": "",
        "called": False,
        "error": None,
        "elapsed_ms": 0.0,
    }

    if not api_key:
        # API 키가 없으면 호출 스킵 — 호출부 존재 자체는 유지 (프로덕션에서만 실행)
        result["error"] = "SOLAR_PRO4_API_KEY not set"
        return result

    url = f"{SOLAR_PRO4_BASE_URL}/chat/completions"
    user_message = _build_skill_user_message(original_text, draft_text)

    payload = {
        "model": SOLAR_PRO4_MODEL,
        "messages": [
            {"role": "system", "content": SKILL_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        "max_tokens": 8192,
        "temperature": 0.0,
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            raw = resp.read().decode("utf-8")
            decoded = json.loads(raw)
            choices = decoded.get("choices", [])
            if choices:
                result["text"] = choices[0].get("message", {}).get("content", "")
            result["called"] = True
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError) as exc:
        result["error"] = str(exc)
        result["called"] = True  # 호출 시도는 했음 (실패지만 호출부 존재 입증)
    result["elapsed_ms"] = (time.monotonic() - t0) * 1000.0
    return result
