# generate_outputs 단위 테스트 — accepted_items 유무에 따른 동작 검증.
import pytest

from src.backend.routes.download import generate_outputs


def _base_results() -> list[dict]:
    return [
        {
            "item": "2026년 3월 생산량",
            "judgment": "불일치",
            "source_value": "22000만원",
            "cited_value": "2.5억",
            "basis": "원본 표의 해당 행/열 값과 다름",
            "correction_suggestion": "원본 대응 값은 22000만원입니다. 인용 값을 22000만원으로 수정하세요.",
            "verified": False,
        },
        {
            "item": "2025년 12월 생산량",
            "judgment": "일치",
            "source_value": "12000만원",
            "cited_value": "1.2억",
            "basis": "원본 표의 해당 행/열 값과 일치 (단위·표현 차이 포함)",
            "correction_suggestion": None,
            "verified": False,
        },
    ]


ORIGINAL_TEXT = (
    "품목: 가상품목 A\n"
    "2025년 12월 생산량: 12000만원\n"
    "2026년 3월 생산량: 22000만원\n"
)

DRAFT_TEXT = (
    "품목: 가상품목 A\n"
    "2025년 12월 생산량: 1.2억\n"
    "2026년 3월 생산량: 2.5억\n"
)


class TestGenerateOutputs:
    def test_accepted_items_none_replaces_all_mismatches(self):
        """accepted_items가 없으면 기존 동작(비일치 전체 교체)을 유지한다."""
        fixed = generate_outputs(_base_results(), ORIGINAL_TEXT, DRAFT_TEXT, accepted_items=None)
        assert "2026년 3월 생산량: 2.5억" not in fixed
        assert "2026년 3월 생산량: 22000만원" in fixed
        # 일치 항목은 교체하지 않음
        assert "2025년 12월 생산량: 1.2억" in fixed

    def test_accepted_items_empty_replaces_all_mismatches(self):
        """accepted_items가 빈 집합이어도 전체 교체 동작과 같아진다."""
        fixed = generate_outputs(_base_results(), ORIGINAL_TEXT, DRAFT_TEXT, accepted_items=set())
        assert "2026년 3월 생산량: 2.5억" not in fixed
        assert "2026년 3월 생산량: 22000만원" in fixed

    def test_accepted_items_contains_mismatch_replaces_only_that(self):
        """accepted_items에 포함된 불일치 항목만 원본 값으로 교체한다."""
        fixed = generate_outputs(
            _base_results(),
            ORIGINAL_TEXT,
            DRAFT_TEXT,
            accepted_items={"2026년 3월 생산량"},
        )
        assert "2026년 3월 생산량: 22000만원" in fixed
        # 다른 불일치 항목이 없으므로 결과상 차이는 없지만, accepted가 아닌 항목은 교체 안 함을
        # 확인하기 위해 별도 케이스를 아래서 검증한다.

    def test_accepted_items_missing_mismatch_does_not_replace(self):
        """accepted_items에 없는 불일치 항목은 교체하지 않는다."""
        results = [
            {
                "item": "a",
                "judgment": "불일치",
                "source_value": "원본값",
                "cited_value": "초안값",
                "basis": "",
                "correction_suggestion": "고치세요",
                "verified": False,
            },
            {
                "item": "b",
                "judgment": "불일치",
                "source_value": "원본값2",
                "cited_value": "초안값2",
                "basis": "",
                "correction_suggestion": "고치세요",
                "verified": False,
            },
        ]
        original = "a: 원본값\nb: 원본값2\nc: 원본값3\n"
        draft = "a: 초안값\nb: 초안값2\nc: 초안값3\n"
        fixed = generate_outputs(results, original, draft, accepted_items={"a"})
        assert "a: 원본값" in fixed
        assert "b: 초안값2" in fixed  # accepted가 아니므로 교체 안 됨
        assert "c: 초안값3" in fixed

    def test_accepted_items_with_non_mismatch_no_replace(self):
        """accepted_items에 들어 있어도 '불일치'가 아닌 항목은 교체하지 않는다."""
        results = [
            {
                "item": "x",
                "judgment": "일치",
                "source_value": "원본값",
                "cited_value": "원본값",
                "basis": "",
                "correction_suggestion": None,
                "verified": False,
            },
        ]
        original = "x: 원본값\n"
        draft = "x: 다른값\n"
        fixed = generate_outputs(results, original, draft, accepted_items={"x"})
        # 일치 판정이므로 accepted에 들어 있어도 교체하지 않음
        assert "x: 다른값" in fixed

    def test_accepted_items_replaces_only_specified_mismatch(self):
        """accepted_items가 여러 불일치 항목 중 일부만 지정하면 해당 항목만 교체."""
        results = [
            {
                "item": "a",
                "judgment": "불일치",
                "source_value": "A원본",
                "cited_value": "A초안",
                "basis": "",
                "correction_suggestion": "고치세요",
                "verified": False,
            },
            {
                "item": "b",
                "judgment": "불일치",
                "source_value": "B원본",
                "cited_value": "B초안",
                "basis": "",
                "correction_suggestion": "고치세요",
                "verified": False,
            },
        ]
        original = "a: A원본\nb: B원본\n"
        draft = "a: A초안\nb: B초안\n"
        fixed = generate_outputs(results, original, draft, accepted_items={"a"})
        assert "a: A원본" in fixed
        assert "b: B초안" in fixed  # accepted가 아니므로 유지

    def test_accepted_items_set_type_preserved(self):
        """accepted_items에 set를 넘겨도 정상 동작한다."""
        results = _base_results()
        fixed = generate_outputs(results, ORIGINAL_TEXT, DRAFT_TEXT, accepted_items={"2026년 3월 생산량"})
        assert "2026년 3월 생산량: 22000만원" in fixed
