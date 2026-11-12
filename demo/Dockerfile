# 척화비 데모 — API·화면·계산 엔진을 담은 컨테이너 1개 (ADR-006)
# 1) 빌드 단계: 의존성만 가상환경에 설치 → 2) 실행 단계: 작은 이미지에 복사, root가 아닌 사용자로 실행
FROM python:3.12-slim AS build
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
RUN pip install "fastapi>=0.115" "uvicorn[standard]>=0.30" "pydantic>=2.7" "sqlalchemy>=2.0" \
                "psycopg[binary]>=3.2" "python-docx>=1.1" "anthropic>=1.0" "boto3>=1.35.99,<2"

FROM python:3.12-slim
LABEL org.opencontainers.image.title="chukhwabi-demurrage-demo" \
      org.opencontainers.image.description="울산 CLX 체선료 최적화 Agent 데모 (가상 데이터)"
ENV PATH=/opt/venv/bin:$PATH PYTHONPATH=/app/src PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    DEMURRAGE_DATA_DIR=/app/data HOST=0.0.0.0 PORT=8000 LLM_PROVIDER=none
RUN useradd --create-home --uid 10001 app
COPY --from=build /opt/venv /opt/venv
WORKDIR /app
COPY src ./src
COPY data ./data
RUN mkdir -p /app/runtime && chown -R app:app /app/runtime
USER app
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2).status == 200 else 1)"
CMD ["sh", "-c", "uvicorn demurrage.api.app:create_app --factory --host ${HOST} --port ${PORT} --no-access-log"]
