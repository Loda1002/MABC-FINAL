# MABC-FINAL Vercel 서버리스 핸들러.
# FastAPI 앱을 Mangum으로 감싼다.
# Vercel은 이 파일을 /api/* 경로로 라우팅하여 서버리스 함수로 실행한다.

from mangum import Mangum
from src.backend.main import app

# Vercel 서버리스 함수로 서빙
handler = Mangum(app, lifespan="auto")
