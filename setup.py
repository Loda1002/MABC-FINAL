# MABC-FINAL 패키지 설정 (루트에서 `pip install -e .` 지원).

from setuptools import setup, find_packages

setup(
    name="mabc-final",
    version="0.1.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "fastapi>=0.140",
        "uvicorn[standard]>=0.20",
        "python-multipart>=0.0.6",
        "pydantic>=2.0",
    ],
    python_requires=">=3.10",
)
