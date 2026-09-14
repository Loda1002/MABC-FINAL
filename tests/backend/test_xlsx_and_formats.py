# xlsx 파싱 및 여러 파일 형식 검증 테스트

import pytest
from fastapi.testclient import TestClient
from src.backend.main import app

client = TestClient(app)


class TestXlsxUploadAndCheck:
    """xlsx 파일 업로드 및 체크 동작 검증."""

    def test_xlsx_upload_and_check(self):
        """xlsx 원본/초안 업로드 후 체크가 정상 동작하는지 확인."""
        import openpyxl
        from io import BytesIO

        wb_orig = openpyxl.Workbook()
        ws_orig = wb_orig.active
        ws_orig.title = "데이터"
        ws_orig.append(["품목", "가상품목 A"])
        ws_orig.append(["2025년 12월 생산량", "12000만원"])
        ws_orig.append(["2026년 1월 생산량", "15000만원"])
        ws_orig.append(["총 판매액", "27000만원"])
        orig_buf = BytesIO()
        wb_orig.save(orig_buf)
        orig_buf.seek(0)

        wb_draft = openpyxl.Workbook()
        ws_draft = wb_draft.active
        ws_draft.title = "초안"
        ws_draft.append(["품목", "가상품목 A"])
        ws_draft.append(["2025년 12월 생산량", "1.2억"])
        ws_draft.append(["2026년 1월 생산량", "1.5억"])
        ws_draft.append(["총 판매액", "30000만원"])
        draft_buf = BytesIO()
        wb_draft.save(draft_buf)
        draft_buf.seek(0)

        files = {
            "original": ("original.xlsx", orig_buf.read(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            "draft": ("draft.xlsx", draft_buf.read(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        }
        up = client.post("/api/upload", files=files)
        assert up.status_code == 200
        uid = up.json()

        ch = client.post("/api/check", json={"original_id": uid["original_id"], "draft_id": uid["draft_id"]})
        assert ch.status_code == 200
        results = ch.json()["results"]
        judgments = {r["item"]: r["judgment"] for r in results}

        assert judgments["2025년 12월 생산량"] == "일치"
        assert judgments["2026년 1월 생산량"] == "일치"
        assert judgments["총 판매액"] == "불일치"

    def test_xlsx_multiple_sheets(self):
        """여러 시트가 있는 xlsx도 정상 파싱되는지 확인."""
        import openpyxl
        from io import BytesIO

        wb_orig = openpyxl.Workbook()
        ws1 = wb_orig.active
        ws1.title = "시트1"
        ws1.append(["품목", "가상품목"])
        ws1.append(["매출", "1억"])

        ws2 = wb_orig.create_sheet("시트2")
        ws2.append(["비용", "5000만원"])
        ws2.append(["이익", "5000만원"])

        buf = BytesIO()
        wb_orig.save(buf)
        buf.seek(0)

        draft_text = "품목: 가상품목\n매출: 1억\n비용: 5000만원\n이익: 5000만원\n"
        files = {
            "original": ("original.xlsx", buf.read(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            "draft": ("draft.txt", draft_text.encode("utf-8"), "text/plain"),
        }
        up = client.post("/api/upload", files=files)
        assert up.status_code == 200
        uid = up.json()

        ch = client.post("/api/check", json={"original_id": uid["original_id"], "draft_id": uid["draft_id"]})
        assert ch.status_code == 200
        results = ch.json()["results"]
        judgments = {r["item"]: r["judgment"] for r in results}

        assert judgments["매출"] == "일치"
        assert judgments["비용"] == "일치"
        assert judgments["이익"] == "일치"

    def test_md_file_upload_and_check(self):
        """md 파일 업로드 및 체크 검증."""
        orig_text = "# 원본 자료\n\n품목: 가상품목 A\n2025년 12월 생산량: 12000만원\n2026년 1월 생산량: 15000만원\n"
        draft_text = "# 초안\n\n품목: 가상품목 A\n2025년 12월 생산량: 1.2억\n2026년 1월 생산량: 1.5억\n"
        files = {
            "original": ("original.md", orig_text.encode("utf-8"), "text/markdown"),
            "draft": ("draft.md", draft_text.encode("utf-8"), "text/markdown"),
        }
        up = client.post("/api/upload", files=files)
        assert up.status_code == 200
        uid = up.json()

        ch = client.post("/api/check", json={"original_id": uid["original_id"], "draft_id": uid["draft_id"]})
        assert ch.status_code == 200
        results = ch.json()["results"]
        judgments = {r["item"]: r["judgment"] for r in results}

        assert judgments["2025년 12월 생산량"] == "일치"
        assert judgments["2026년 1월 생산량"] == "일치"

    def test_json_file_upload_and_check(self):
        """json 파일 업로드 및 체크 검증."""
        orig_text = '{"품목": "가상품목 A", "2025년 12월 생산량": "12000만원", "2026년 1월 생산량": "15000만원"}'
        draft_text = '{"품목": "가상품목 A", "2025년 12월 생산량": "1.2억", "2026년 1월 생산량": "1.5억"}'
        files = {
            "original": ("original.json", orig_text.encode("utf-8"), "application/json"),
            "draft": ("draft.json", draft_text.encode("utf-8"), "application/json"),
        }
        up = client.post("/api/upload", files=files)
        assert up.status_code == 200
        uid = up.json()

        ch = client.post("/api/check", json={"original_id": uid["original_id"], "draft_id": uid["draft_id"]})
        assert ch.status_code == 200
        results = ch.json()["results"]
        judgments = {r["item"]: r["judgment"] for r in results}

        assert len(results) > 0


class TestMannwonNormalization:
    """만톤(1억) 정규화 검증."""

    def test_10000만원_is_1억(self):
        """10000만원이 1억과 단위 변환으로 일치 판정되는지 확인."""
        files = {
            "original": ("original.txt", "매출액: 1억\n".encode("utf-8"), "text/plain"),
            "draft": ("draft.txt", "매출액: 10000만원\n".encode("utf-8"), "text/plain"),
        }
        up = client.post("/api/upload", files=files)
        assert up.status_code == 200
        uid = up.json()
        ch = client.post("/api/check", json={"original_id": uid["original_id"], "draft_id": uid["draft_id"]})
        assert ch.status_code == 200
        results = ch.json()["results"]
        judgments = {r["item"]: r["judgment"] for r in results}
        assert judgments["매출액"] == "일치"

    def test_5000만원_is_0_5억(self):
        """5000만원이 0.5억과 단위 변환으로 일치 판정되는지 확인."""
        files = {
            "original": ("original.txt", "매출액: 0.5억\n".encode("utf-8"), "text/plain"),
            "draft": ("draft.txt", "매출액: 5000만원\n".encode("utf-8"), "text/plain"),
        }
        up = client.post("/api/upload", files=files)
        assert up.status_code == 200
        uid = up.json()
        ch = client.post("/api/check", json={"original_id": uid["original_id"], "draft_id": uid["draft_id"]})
        assert ch.status_code == 200
        results = ch.json()["results"]
        judgments = {r["item"]: r["judgment"] for r in results}
        assert judgments["매출액"] == "일치"
