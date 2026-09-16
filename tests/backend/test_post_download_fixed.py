# POST /api/download/fixed 엔드포인트 테스트.
import json

import pytest
from fastapi.testclient import TestClient

from src.backend.main import app
from src.backend.routes.example import EXAMPLE_ORIGINAL, EXAMPLE_DRAFT, EXAMPLE_MEMORY

client = TestClient(app)


def _upload_text_files(original_text: str, draft_text: str):
    resp = client.post(
        "/api/upload",
        files={
            "original": ("original.txt", original_text.encode(), "text/plain"),
            "draft": ("draft.txt", draft_text.encode(), "text/plain"),
        },
    )
    assert resp.status_code == 200
    return resp.json()


def _check(original_id: str, draft_id: str):
    resp = client.post(
        "/api/check",
        json={"original_id": original_id, "draft_id": draft_id},
    )
    assert resp.status_code == 200
    return resp.json()


def _check_with_verified(original_id: str, draft_id: str, verified_item: str):
    resp = _check(original_id, draft_id)
    # memory_data의 results 안에서 verified를 true로 만든 뒤 다시 올리지 않고,
    # 여기서는 memory_data 전체를 그대로 POST /api/download/fixed로 전달한다.
    # 실제 프론트 흐름은 체크박스 토글 후 POST로 전송하므로 이 테스트도 그 모델을 따른다.
    return resp


class TestPostDownloadFixed:
    def test_accepted_items_only_replaces_approved_mismatches(self):
        """accepted_items + original_text + draft_text만 전달해도 교체된 fixed_text가 반환된다."""
        original_text = (
            "품목: 가상품목 A\n"
            "2025년 12월 생산량: 12000만원\n"
            "2026년 3월 생산량: 22000만원\n"
        )
        draft_text = (
            "품목: 가상품목 A\n"
            "2025년 12월 생산량: 1.2억\n"
            "2026년 3월 생산량: 2.5억\n"
        )

        resp = client.post(
            "/api/download/fixed",
            json={
                "accepted_items": ["2026년 3월 생산량"],
                "original_text": original_text,
                "draft_text": draft_text,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "fixed_text" in body
        fixed = body["fixed_text"]
        assert "2026년 3월 생산량: 22000만원" in fixed
        # accepted가 아닌 불일치 항목은 교체하지 않는다 (2025년 12월은 일치라서 원래 미교체지만,
        # 여기서는 accepted에 2025년 12월이 없으므로 교체되지 않음을 확인한다)
        assert "2025년 12월 생산량: 1.2억" in fixed

    def test_accepted_items_empty_rejects(self):
        """accepted_items가 비었고 memory_data도 없으면 400."""
        resp = client.post(
            "/api/download/fixed",
            json={
                "accepted_items": [],
                "original_text": "a: 1\n",
                "draft_text": "a: 2\n",
            },
        )
        assert resp.status_code == 400
        assert "accepted_items" in resp.json().get("detail", "")

    def test_accepted_items_with_results_replaces_only_approved(self):
        """results + accepted_items 조합으로 교체 범위가 제한된다."""
        results = [
            {"item": "a", "judgment": "불일치", "source_value": "원본A", "cited_value": "초안A",
             "basis": "", "correction_suggestion": "고치세요", "verified": False},
            {"item": "b", "judgment": "불일치", "source_value": "원본B", "cited_value": "초안B",
             "basis": "", "correction_suggestion": "고치세요", "verified": False},
        ]
        resp = client.post(
            "/api/download/fixed",
            json={
                "results": results,
                "accepted_items": ["a"],
                "original_text": "a: 원본A\nb: 원본B\nc: 원본C\n",
                "draft_text": "a: 초안A\nb: 초안B\nc: 초안C\n",
            },
        )
        assert resp.status_code == 200
        fixed = resp.json()["fixed_text"]
        assert "a: 원본A" in fixed
        assert "b: 초안B" in fixed  # accepted가 아니므로 유지
        assert "c: 초안C" in fixed

    def test_memory_data_path_replaces_using_accepted_items(self):
        """memory_data를 전달하면 accepted_items + results를 함께 쓴다."""
        memory_data = {
            "results": [
                {"item": "x", "judgment": "불일치", "source_value": "원본X",
                 "cited_value": "초안X", "basis": "", "correction_suggestion": "고치세요",
                 "verified": False},
                {"item": "y", "judgment": "불일치", "source_value": "원본Y",
                 "cited_value": "초안Y", "basis": "", "correction_suggestion": "고치세요",
                 "verified": False},
            ],
            "accepted_items": ["x"],
            "original_text": "x: 원본X\ny: 원본Y\n",
            "draft_text": "x: 초안X\ny: 초안Y\n",
        }
        resp = client.post(
            "/api/download/fixed",
            json={"memory_data": memory_data},
        )
        assert resp.status_code == 200
        fixed = resp.json()["fixed_text"]
        assert "x: 원본X" in fixed
        assert "y: 초안Y" in fixed

    def test_memory_data_without_texts_rejects(self):
        """memory_data만 있고 original_text/draft_text가 없으면 400."""
        memory_data = {
            "results": [{"item": "z", "judgment": "불일치", "source_value": "원",
                         "cited_value": "초", "basis": "", "correction_suggestion": "고치세요",
                         "verified": False}],
            "accepted_items": ["z"],
            # original_text/draft_text 없음
        }
        resp = client.post("/api/download/fixed", json={"memory_data": memory_data})
        assert resp.status_code == 400
        assert "original_text" in resp.json().get("detail", "")

    def test_accepted_items_none_without_memory_data_rejects(self):
        """accepted_items도 memory_data도 없으면 400."""
        resp = client.post(
            "/api/download/fixed",
            json={
                "original_text": "a: 1\n",
                "draft_text": "a: 2\n",
            },
        )
        assert resp.status_code == 400
        assert "accepted_items" in resp.json().get("detail", "")

    def test_missing_original_text_with_accepted_items_rejects(self):
        """accepted_items는 있으나 original_text가 없으면 400."""
        resp = client.post(
            "/api/download/fixed",
            json={
                "accepted_items": ["a"],
                "draft_text": "a: 2\n",
            },
        )
        assert resp.status_code == 400
        assert "original_text" in resp.json().get("detail", "")

    def test_accepted_item_not_in_draft_ignored(self):
        """accepted_items에 있는 항목이 초안에 없으면 교체 대상이 아니다(오류 없이 무시)."""
        resp = client.post(
            "/api/download/fixed",
            json={
                "accepted_items": ["없는항목"],
                "original_text": "있는항목: 원본값\n",
                "draft_text": "있는항목: 초안값\n",
            },
        )
        assert resp.status_code == 200
        fixed = resp.json()["fixed_text"]
        assert "있는항목: 초안값" in fixed  # 교체 대상 아님
        assert "없는항목" not in fixed

    def test_all_approved_mismatches_replaced(self):
        """accepted_items에 포함된 모든 불일치 항목이 원본 값으로 교체된다."""
        original_text = "a: 100\nb: 200\nc: 300\n"
        draft_text = "a: 10\nb: 20\nc: 30\n"
        resp = client.post(
            "/api/download/fixed",
            json={
                "accepted_items": ["a", "b", "c"],
                "original_text": original_text,
                "draft_text": draft_text,
            },
        )
        assert resp.status_code == 200
        fixed = resp.json()["fixed_text"]
        # accepted_items가 모두 있으므로 전체 교체
        assert "a: 100" in fixed
        assert "b: 200" in fixed
        assert "c: 300" in fixed

    def test_approved_mismatch_not_replaced_when_judgment_not_mismatch(self):
        """accepted_items에 있어도 judgment가 '불일치'가 아니면 교체하지 않는다."""
        results = [
            {"item": "x", "judgment": "일치", "source_value": "원본X", "cited_value": "원본X",
             "basis": "", "correction_suggestion": None, "verified": False},
        ]
        resp = client.post(
            "/api/download/fixed",
            json={
                "results": results,
                "accepted_items": ["x"],
                "original_text": "x: 원본X\n",
                "draft_text": "x: 다른값\n",
            },
        )
        assert resp.status_code == 200
        assert "x: 다른값" in resp.json()["fixed_text"]


class TestPostDownloadFixedWithExampleData:
    """EXAMPLE_* 상수를 활용한 해피패스 검증."""

    def test_example_memory_data_replaces_approved_only(self):
        """EXAMPLE_MEMORY의 accepted_items가 비어 있으므로 아무것도 교체되지 않는다."""
        resp = client.post("/api/download/fixed", json={"memory_data": EXAMPLE_MEMORY})
        assert resp.status_code == 200
        fixed = resp.json()["fixed_text"]
        # EXAMPLE_MEMORY은 accepted_items가 없어서 교체 없음 — 초안과 그대로
        assert "2026년 3월 생산량: 2.5억" in fixed
        assert "2026년 2월 생산량: 1.8억" in fixed

    def test_example_with_accepted_items_replaces_those(self):
        """EXAMPLE 데이터에서 특정 항목만 approved로 교체한 고정본."""
        original_text = EXAMPLE_ORIGINAL
        draft_text = EXAMPLE_DRAFT
        approved = ["2026년 3월 생산량"]
        resp = client.post(
            "/api/download/fixed",
            json={
                "results": EXAMPLE_MEMORY["results"],
                "accepted_items": approved,
                "original_text": original_text,
                "draft_text": draft_text,
            },
        )
        assert resp.status_code == 200
        fixed = resp.json()["fixed_text"]
        assert "2026년 3월 생산량: 22000만원" in fixed
        # approved가 아닌 불일치는 교체되지 않음
        assert "2026년 2월 생산량: 1.8억" in fixed
        assert "증감율: 28% 증가" in fixed  # accepted 아님


class TestPostDownloadFixedFiles:
    """파일 업로드 후 check를 거쳐 memory_data 기반 다운로드 흐름 검증."""

    def test_upload_check_then_download_fixed_with_accepted_items(self):
        """실제 upload→check→download 흐름에서 승인된 항목만 교체된 텍스트가 반환된다."""
        files = {
            "original": ("original.txt",
                         ("품목: 가상품목 A\n"
                          "2025년 12월 생산량: 12000만원\n"
                          "2026년 3월 생산량: 22000만원\n").encode(),
                         "text/plain"),
            "draft": ("draft.txt",
                      ("품목: 가상품목 A\n"
                       "2025년 12월 생산량: 1.2억\n"
                       "2026년 3월 생산량: 2.5억\n").encode(),
                      "text/plain"),
        }
        up = client.post("/api/upload", files=files)
        assert up.status_code == 200
        ids = up.json()
        chk = _check(ids["original_id"], ids["draft_id"])
        assert chk["status"] == "done"
        # memory_data에서 approved를 골라 POST로 전달
        memory_data = chk["memory_data"]
        approved = [r["item"] for r in memory_data["results"]
                    if r["item"] == "2026년 3월 생산량"]
        resp = client.post(
            "/api/download/fixed",
            json={
                "memory_data": memory_data,
                "accepted_items": approved,
            },
        )
        assert resp.status_code == 200
        fixed = resp.json()["fixed_text"]
        assert "2026년 3월 생산량: 22000만원" in fixed
