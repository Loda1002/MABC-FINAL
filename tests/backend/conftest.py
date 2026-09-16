# MABC-FINAL 백엔드 테스트 픽스처 — 업로드 디렉토리 격리/청소.
import sys
import shutil
from pathlib import Path

import pytest

# 프로젝트의 src/ 디렉터리를 import 경로에 추가한다.
# pyproject.toml이 없을 때도 tests가 src.backend를 직접 import할 수 있게 한다.
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

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
