# syntax=docker/dockerfile:1
# D-MIN-agent와 같은 모양(python:3.13-slim + uv). 테스트 단계를 통과해야 실행 이미지가 만들어진다.
FROM python:3.13-slim AS base
COPY --from=ghcr.io/astral-sh/uv:0.12.20 /uv /uvx /bin/
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=0
# PYTHONHASHSEED=0: 기존 엔진은 체선료가 같은 대안(2·3안)끼리 어느 것을 먼저 내는지가 문자열 해시 순서에 따라 바뀐다 → 고정해 같은 입력이면 같은 답

# 의존성 레이어를 먼저 만든다. 코드만 바뀌면 numpy·scipy를 다시 받지 않는다.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev --no-install-project
COPY src src

# 테스트: 예시 3척의 정답(기준안 $25,641.62 → 1안 $7,192.30)이 맞아야 다음 단계로 간다
FROM base AS test
COPY tests tests
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked && .venv/bin/python -m pytest -q && touch /app/.tested

FROM base AS runtime
COPY --from=test /app/.tested /app/.tested
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev
RUN useradd --system --uid 10001 app
USER 10001
EXPOSE 8000
CMD ["/app/.venv/bin/uvicorn", "dmin_agent.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
