# MABC-FINAL 백엔드 FastAPI 애플리케이션.
# 하나의 HTML로 전체가 시연되도록 정적 프론트엔드를 함께 서빙한다.

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .routes import upload, check, download, rerun, example, status
from .config import SOLAR_PRO4_API_KEY

app = FastAPI(
    title="MABC-FINAL",
    description="AI 요약 초안 vs 원본 대조 검수 웹 서비스 — MABC2026 결선 MVP",
    version="0.1.0",
)

# CORS: 프론트엔드가 별도 도메인에서 서빙될 경우 필요. 지금은 동일 서버에서 서빙.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 정적 프론트엔드 서빙 (프론트엔드 빌드 결과물이 있을 경우)
# 프론트엔드 디렉토리가 없으면 무시.
import os as _os
_FRONTEND_DIR = _os.path.abspath(
    _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))), "frontend")
)
_assets_dir = _os.path.join(_FRONTEND_DIR, "assets")
if _os.path.isdir(_FRONTEND_DIR) and _os.path.isdir(_assets_dir):
    app.mount("/assets", StaticFiles(directory=_assets_dir), name="assets")


@app.get("/")
async def root():
    """프론트엔드 메인 페이지. 단일 HTML로 전체를 서빙한다."""
    index_path = _os.path.join(_FRONTEND_DIR, "index.html")
    if _os.path.isfile(index_path):
        return FileResponse(index_path)
    # 프론트엔드가 없으면 API 웰컴 메시지
    return {"message": "MABC-FINAL API. 프론트엔드가 준비되지 않았습니다. See /docs for OpenAPI spec."}


@app.get("/api/health")
async def health():
    return {"status": "ok", "has_api_key": bool(SOLAR_PRO4_API_KEY)}


@app.get("/docs")
async def docs_redirect():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/docs")


@app.get("/openapi.json")
async def openapi():
    return app.openapi()


# 라우트 등록
app.include_router(upload.router, prefix="/api", tags=["upload"])
app.include_router(check.router, prefix="/api", tags=["check"])
app.include_router(download.router, prefix="/api", tags=["download"])
app.include_router(rerun.router, prefix="/api", tags=["rerun"])
app.include_router(example.router, prefix="/api", tags=["example"])
app.include_router(status.router, prefix="/api", tags=["status"])
