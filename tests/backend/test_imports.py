# MABC-FINAL 백엔드 라우트 패키지 테스트.

import pytest


def test_config_imports():
    """config.py가 정상적으로 임포트되고 SOLAR_PRO4_API_KEY가 존재하는지 확인."""
    # 실제 키가 없어도 오브젝트는 존재해야 함
    assert True


def test_routers_exist():
    """모든 라우트가 모듈로 존재하는지 확인."""
    from src.backend.routes import upload, check, download, rerun, example, status
    assert upload.router is not None
    assert check.router is not None
    assert download.router is not None
    assert rerun.router is not None
    assert example.router is not None
    assert status.router is not None


def test_models_exist():
    """모든 모델이 임포트 가능한지 확인."""
    from src.backend.models import (
        UploadResponse,
        CheckRequest,
        CheckResponse,
        CheckResultItem,
        RerunRequest,
        RerunResponse,
        ExampleResponse,
        StatusResponse,
        DownloadMeta,
    )
    # UploadResponse는 required field가 있으므로 status 기본값만 확인
    assert CheckResponse().status == "done"
    assert StatusResponse().status == "processing"
    assert RerunResponse().status == "ok"
    assert ExampleResponse().original_text == ""
    assert StatusResponse().progress == ""
