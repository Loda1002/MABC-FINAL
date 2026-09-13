# MABC-FINAL 백엔드 라우트 테스트.

import pytest
from fastapi.testclient import TestClient

from src.backend.main import app


client = TestClient(app)


class TestHealth:
    def test_health_ok(self):
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "has_api_key" in data


class TestUpload:
    def test_upload_allowed_files(self):
        """Allowed file extensions can be uploaded successfully."""
        files = {
            "original": ("source.txt", b"source content", "text/plain"),
            "draft": ("draft.md", b"# draft\n\ncontent", "text/markdown"),
        }
        response = client.post("/api/upload", files=files)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "uploaded"
        assert len(data["original_id"]) == 12
        assert len(data["draft_id"]) == 12

    def test_upload_disallowed_extension(self):
        """Disallowed extension on original file is rejected."""
        files = {
            "original": ("source.pdf", b"PDF content", "application/pdf"),
            "draft": ("draft.txt", b"draft content", "text/plain"),
        }
        response = client.post("/api/upload", files=files)
        assert response.status_code == 400
        detail = response.json().get("detail", "")
        assert "원본 파일 확장자가 허용되지 않습니다" in detail

    def test_upload_disallowed_draft_extension(self):
        files = {
            "original": ("source.txt", b"source content", "text/plain"),
            "draft": ("draft.jpg", b"image", "image/jpeg"),
        }
        response = client.post("/api/upload", files=files)
        assert response.status_code == 400
        detail = response.json().get("detail", "")
        assert "초안 파일 확장자가 허용되지 않습니다" in detail


class TestDownload:
    def test_download_unknown_type(self):
        """Unknown download type returns 400."""
        response = client.get("/api/download/unknown")
        assert response.status_code == 400
        detail = response.json().get("detail", "")
        assert "알 수 없는 다운로드 유형" in detail

    def test_download_missing_fixed(self):
        """Missing fixed file returns 404."""
        response = client.get("/api/download/fixed")
        assert response.status_code == 404

    def test_download_missing_memory(self):
        """Missing memory file returns 404."""
        response = client.get("/api/download/memory")
        assert response.status_code == 404


class TestCheck:
    def test_check_returns_results(self):
        """check returns verification results based on uploaded files."""
        # Upload first
        files = {
            "original": ("original.txt", "품목: 가상품목 A\n2025년 12월 생산량: 12000만원\n2026년 1월 생산량: 15000만원\n총 판매액: 27000만원\n".encode(), "text/plain"),
            "draft": ("draft.txt", "품목: 가상품목 A\n2025년 12월 생산량: 1.2억\n2026년 1월 생산량: 1.5억\n증감률: 35% 증가\n총 판매액: 27000만원\n".encode(), "text/plain"),
        }
        upload_resp = client.post("/api/upload", files=files)
        assert upload_resp.status_code == 200
        upload_data = upload_resp.json()

        # Call check
        response = client.post(
            "/api/check",
            json={"original_id": upload_data["original_id"], "draft_id": upload_data["draft_id"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "done"
        assert len(data["results"]) > 0
        # Judgments must be within 5 labels
        allowed = {"일치", "불일치", "값은 있으나 항목 대응이 다름", "원본에 없음", "확인 불가"}
        for r in data["results"]:
            assert r["judgment"] in allowed, f"Disallowed judgment: {r['judgment']}"
        # Must include calculated claim verification
        calc_items = [r for r in data["results"] if r.get("calculation")]
        assert len(calc_items) >= 1, "Calculated claim verification must be included"


class TestExample:
    def test_example_returns_data(self):
        """example returns example dataset."""
        response = client.post("/api/example")
        assert response.status_code == 200
        data = response.json()
        assert data["original_text"]
        assert data["draft_text"]
        assert data["memory_json"]
        assert len(data["expected_results"]) >= 5


    def test_download_after_check(self):
        """check 실행 후 다운로드가 가능한지 확인."""
        files = {
            "original": ("original.txt", "품목: 가상품목\n2025년 12월 생산량: 12000만원\n".encode(), "text/plain"),
            "draft": ("draft.txt", "품목: 가상품목\n2025년 12월 생산량: 1.2억\n".encode(), "text/plain"),
        }
        up = client.post("/api/upload", files=files)
        assert up.status_code == 200
        uid = up.json()
        ch = client.post("/api/check", json={"original_id": uid["original_id"], "draft_id": uid["draft_id"]})
        assert ch.status_code == 200
        assert ch.json()["status"] == "done"
        # 이제 다운로드 가능
        f = client.get("/api/download/fixed")
        assert f.status_code == 200
        m = client.get("/api/download/memory")
        assert m.status_code == 200

    def test_rerun_after_check(self):
        """check 후 기억 파일을 올리면 재검증 건수가 축소되는지 확인."""
        files = {
            "original": ("original.txt", "key: value\n".encode(), "text/plain"),
            "draft": ("draft.txt", "key: value2\n".encode(), "text/plain"),
        }
        up = client.post("/api/upload", files=files)
        assert up.status_code == 200
        uid = up.json()
        ch = client.post("/api/check", json={"original_id": uid["original_id"], "draft_id": uid["draft_id"]})
        assert ch.status_code == 200
        assert ch.json()["status"] == "done"
        # 기억 파일 다운로드 후 재업로드
        mem_resp = client.get("/api/download/memory")
        mem_data = mem_resp.json()
        rer = client.post("/api/rerun", json={"memory_data": mem_data})
        assert rer.status_code == 200
        assert rer.json()["status"] == "ok"
    def test_rerun_with_memory(self):
        """rerun shrinks re-verification targets from memory file."""
        response = client.post(
            "/api/rerun",
            json={"memory_data": {"results": [{"item": "x", "judgment": "일치"}]}},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"


class TestStatus:
    def test_status_not_found(self):
        response = client.get("/api/status/missing")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"


class TestRoot:
    def test_root_serves_frontend(self):
        """Root serves frontend HTML."""
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        assert "MABC-FINAL" in response.text
