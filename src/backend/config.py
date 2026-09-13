# MABC-FINAL 백엔드 패키지

import os

# Solar Pro 4 API 키 — 서버 사이드에서만 읽음. 클라이언트 코드/저장소 금지.
SOLAR_PRO4_API_KEY = os.environ.get("SOLAR_PRO4_API_KEY", "")

# API 엔드포인트 설정
SOLAR_PRO4_BASE_URL = os.environ.get("SOLAR_PRO4_BASE_URL", "https://api.upstage.ai/v1")
SOLAR_PRO4_MODEL = os.environ.get("SOLAR_PRO4_MODEL", "solar-pro4")

# 업로드 파일 저장 경로 (Vercel 서버리스 환경에서는 /tmp만 쓰기 가능)
UPLOAD_DIR = os.path.join("/tmp", "mabc-uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
