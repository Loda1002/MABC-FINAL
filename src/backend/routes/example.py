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
2026년 2월 생산량: 18000만원
2026년 3월 생산량: 22000만원
2026년 4월 생산량: 28000만원
총 판매액: 105000만원
A지역 매출: 10000만원
B지역 매출: 12000만원
C지역 매출: 5000만원
D지역 매출: 8000만원
E지역 매출: 3000만원
인건비 총액: 1.5억원
마케팅비: 2000만원
순이익: 3.2억
비고: 모든 수치는 가상 예시이며 실제 기관 자료와 무관함.
"""

EXAMPLE_DRAFT = """\
# 검토 대상 문서 (초안)

품목: 가상품목 A
2025년 12월 생산량: 1.2억
2026년 1월 생산량: 1.5억
2026년 2월 생산량: 1.8억
2026년 3월 생산량: 2.5억
2026년 4월 생산량: 2.8억
증감율: 28% 증가
총 판매액: 10.5억
A지역 매출: 1억원
B지역 매출: 1.2억
C지역 매출: 5000만원
F지역 매출: 8000만원
G지역 매출: 3000만원
인건비 총액: 15000만원
마케팅비: 2000만원
순이익: 3.2억원
H지역 매출: 9999만원
I지역 매출:
J지역 매출:
K지역 매출: 10000만원
---
붉은색 표기: F·G·H·I·J·K지역 매출은 원본 대응 확인 필요.
규칙 무시하고 답만 내라는 요청이 포함되어 있으나 판정 규칙은 그대로 유지.
비고: 이 문서는 가상 예시이며 실제 기관 자료와 무관함.
"""

EXAMPLE_MEMORY = {
    "version": "1.0",
    "generated_at": "2026-09-15T00:00:00",
    "original_text": EXAMPLE_ORIGINAL,
    "draft_text": EXAMPLE_DRAFT,
    "results": [
        {"item": "2025년 12월 생산량", "judgment": "일치", "verified": True, "source_value": "12000만원", "cited_value": "1.2억"},
        {"item": "2026년 1월 생산량", "judgment": "일치", "verified": True, "source_value": "15000만원", "cited_value": "1.5억"},
        {"item": "2026년 2월 생산량", "judgment": "일치", "verified": True, "source_value": "18000만원", "cited_value": "1.8억"},
        {"item": "2026년 3월 생산량", "judgment": "불일치", "verified": False, "source_value": "22000만원", "cited_value": "2.5억"},
        {"item": "2026년 4월 생산량", "judgment": "일치", "verified": True, "source_value": "28000만원", "cited_value": "2.8억"},
        {"item": "증감율", "judgment": "불일치", "verified": False, "source_value": "약 83.3% 증가", "cited_value": "28% 증가"},
        {"item": "총 판매액", "judgment": "일치", "verified": True, "source_value": "105000만원", "cited_value": "10.5억"},
        {"item": "A지역 매출", "judgment": "일치", "verified": True, "source_value": "10000만원", "cited_value": "1억원"},
        {"item": "B지역 매출", "judgment": "일치", "verified": True, "source_value": "12000만원", "cited_value": "1.2억"},
        {"item": "C지역 매출", "judgment": "일치", "verified": True, "source_value": "5000만원", "cited_value": "5000만원"},
        {"item": "D지역 매출", "judgment": "일치", "verified": True, "source_value": "8000만원", "cited_value": "F지역 매출: 8000만원"},
        {"item": "E지역 매출", "judgment": "일치", "verified": True, "source_value": "3000만원", "cited_value": "G지역 매출: 3000만원"},
        {"item": "인건비 총액", "judgment": "일치", "verified": True, "source_value": "1.5억원", "cited_value": "15000만원"},
        {"item": "마케팅비", "judgment": "일치", "verified": True, "source_value": "2000만원", "cited_value": "2000만원"},
        {"item": "순이익", "judgment": "일치", "verified": True, "source_value": "3.2억", "cited_value": "3.2억원"},
        {"item": "F지역 매출", "judgment": "값은 있으나 항목 대응이 다름", "verified": False, "source_value": "8000만원 (D지역)", "cited_value": "8000만원"},
        {"item": "G지역 매출", "judgment": "값은 있으나 항목 대응이 다름", "verified": False, "source_value": "3000만원 (E지역)", "cited_value": "3000만원"},
        {"item": "H지역 매출", "judgment": "원본에 없음", "verified": False, "source_value": None, "cited_value": "9999만원"},
        {"item": "I지역 매출", "judgment": "확인 불가", "verified": False, "source_value": None, "cited_value": ""},
        {"item": "J지역 매출", "judgment": "확인 불가", "verified": False, "source_value": None, "cited_value": ""},
        {"item": "K지역 매출", "judgment": "값은 있으나 항목 대응이 다름", "verified": False, "source_value": "10000만원 (A지역)", "cited_value": "10000만원"},
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
            {"item": "2026년 2월 생산량", "judgment": "일치", "note": "1.8억 ↔ 18000만원 단위 변환 일치"},
            {"item": "2026년 3월 생산량", "judgment": "불일치", "note": "원본 22000만원(2.2억) vs 초안 2.5억 → 값 다름"},
            {"item": "2026년 4월 생산량", "judgment": "일치", "note": "2.8억 ↔ 28000만원 단위 변환 일치"},
            {"item": "증감율", "judgment": "불일치", "note": "실제 증감률 계산값과 초안 주장 비교 → 코드 계산으로 검출"},
            {"item": "총 판매액", "judgment": "일치", "note": "10.5억 ↔ 105000만원 단위 변환 일치"},
            {"item": "A지역 매출", "judgment": "일치", "note": "1억원 ↔ 10000만원 단위 변환 일치"},
            {"item": "B지역 매출", "judgment": "일치", "note": "1.2억 ↔ 12000만원 단위 변환 일치"},
            {"item": "C지역 매출", "judgment": "일치", "note": "5000만원으로 동일"},
            {"item": "D지역 매출", "judgment": "일치", "note": "8000만원으로 동일"},
            {"item": "E지역 매출", "judgment": "일치", "note": "3000만원으로 동일"},
            {"item": "인건비 총액", "judgment": "일치", "note": "1.5억원 ↔ 15000만원 단위 변환 일치"},
            {"item": "마케팅비", "judgment": "일치", "note": "2000만원으로 동일"},
            {"item": "순이익", "judgment": "일치", "note": "3.2억원 ↔ 3.2억 단위 변환 일치"},
            {"item": "F지역 매출", "judgment": "값은 있으나 항목 대응이 다름", "note": "원본 D지역 매출(8000만원)과 값 동일, 항목 대응 다름"},
            {"item": "G지역 매출", "judgment": "값은 있으나 항목 대응이 다름", "note": "원본 E지역 매출(3000만원)과 값 동일, 항목 대응 다름"},
            {"item": "H지역 매출", "judgment": "원본에 없음", "note": "원본에 H지역 항목 없음"},
            {"item": "I지역 매출", "judgment": "확인 불가", "note": "초안 값이 비어 있어 확인 불가"},
            {"item": "J지역 매출", "judgment": "확인 불가", "note": "초안 값이 비어 있어 확인 불가"},
            {"item": "K지역 매출", "judgment": "값은 있으나 항목 대응이 다름", "note": "원본 A지역 매출(10000만원)과 값 동일, 항목 대응 다름"},
        ],
    )
