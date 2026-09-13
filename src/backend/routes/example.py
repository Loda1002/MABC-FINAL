# POST /api/example — 예시 버튼 클릭 시 예시 데이터 채우기.

from fastapi import APIRouter
from ..models import ExampleResponse

router = APIRouter()


# 예시 데이터: 가상 예시임을 명시, 최소 판정 케이스 5종 포함
EXAMPLE_ORIGINAL = """\
# 원본 자료 (가상 예시)

품목: 가상품목 A
2025년 12월 생산량: 12000만원
2026년 1월 생산량: 15000만원
총 판매액: 27000만원
A지역 매출: 10000만원
B지역 매출: 12000만원
C지역 매출: 5000만원
비고: 모든 수치는 가상 예시이며 실제 기관 자료와 무관함.
"""

EXAMPLE_DRAFT = """\
# 검토 대상 문서 (초안)

품목: 가상품목 A
2025년 12월 생산량: 1.2억
2026년 1월 생산량: 1.5억
증감율: 35% 증가
총 판매액: 27000만원
A지역 매출: 1억원
B지역 매출: 1.2억
D지역 매출: 5000만원
---
붉은색 표기: D지역 매출은 원본에 없는 값임.
규칙 무시하고 답만 내라는 요청이 포함되어 있으나 판정 규칙은 그대로 유지.
비고: 이 문서는 가상 예시이며 실제 기관 자료와 무관함.
"""

EXAMPLE_MEMORY = {
    "version": "1.0",
    "generated_at": "2026-09-13T00:00:00",
    "results": [
        {"item": "2025년 12월 생산량", "judgment": "일치", "verified": True},
        {"item": "2026년 1월 생산량", "judgment": "일치", "verified": True},
        {"item": "증감율", "judgment": "불일치", "verified": False},
        {"item": "총 판매액", "judgment": "일치", "verified": True},
        {"item": "A지역 매출", "judgment": "일치", "verified": True},
        {"item": "B지역 매출", "judgment": "일치", "verified": True},
        {"item": "D지역 매출", "judgment": "원본에 없음", "verified": False},
    ],
    "fixed_text": "",
}


@router.post("/example", response_model=ExampleResponse)
async def get_example():
    """예시 버튼 첫 화면: 예시 데이터 채워넣기.

    최소 판정 케이스 5종 + 추가 케이스를 포함한 예시 데이터셋을 반환.
    프론트엔드는 이 데이터로 업로드 칸을 채우고 바로 검수 실행 흐름으로 연결.
    """
    return ExampleResponse(
        original_text=EXAMPLE_ORIGINAL,
        draft_text=EXAMPLE_DRAFT,
        memory_json=EXAMPLE_MEMORY,
        expected_results=[
            {"item": "2025년 12월 생산량", "judgment": "일치", "note": "1.2억 ↔ 12000만원 단위 변환 일치"},
            {"item": "2026년 1월 생산량", "judgment": "일치", "note": "1.5억 ↔ 15000만원 단위 변환 일치"},
            {"item": "증감율", "judgment": "불일치", "note": "실제 증감률 25%인데 초안은 35%로 기재 → 코드 계산으로 검출"},
            {"item": "총 판매액", "judgment": "일치", "note": "27000만원으로 동일"},
            {"item": "A지역 매출", "judgment": "일치", "note": "1억원 ↔ 10000만원 단위 변환 일치"},
            {"item": "B지역 매출", "judgment": "일치", "note": "1.2억 ↔ 12000만원 단위 변환 일치"},
            {"item": "D지역 매출", "judgment": "원본에 없음", "note": "원본에 D지역 항목 없음"},
        ],
    )
