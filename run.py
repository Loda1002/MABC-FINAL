# MABC-FINAL 애플리케이션 런처.
# 개발 시: uvicorn src.backend.main:app --reload
# 프로덕션 시: uvicorn src.backend.main:app --host 0.0.0.0 --port 8000

import uvicorn

if __name__ == "__main__":
    uvicorn.run("src.backend.main:app", host="127.0.0.1", port=8000, reload=True)
