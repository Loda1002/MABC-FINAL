# MABC-FINAL 백엔드 테스트 픽스처 — 업로드 디렉토리 격리/청소.
import shutil
from pathlib import Path

import pytest

UPLOAD_DIR = Path("/tmp/mabc-uploads")


@pytest.fixture(autouse=True)
def _reset_upload_dir():
    """각 테스트 실행 전 업로드 디렉토리를 비우고, 끝날 때 정리한다."""
    previous = UPLOAD_DIR.exists()
    if UPLOAD_DIR.exists():
        shutil.rmtree(UPLOAD_DIR)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    yield
    if UPLOAD_DIR.exists():
        shutil.rmtree(UPLOAD_DIR)
    if not previous and UPLOAD_DIR.exists():
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
