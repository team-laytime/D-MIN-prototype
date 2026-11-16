"""D-MIN agent server — Spring이 보낸 요청만 처리한다 (정의서 4.3: Python은 Spring을 다시 부르지 않는다).

지금 여는 경로 (이 둘뿐이다. /docs·/redoc·/openapi.json 같은 API 문서 경로는 열지 않는다)
  GET  /health        엔진·규칙 표 버전과 지문. Spring 상태 화면과 liveness/readiness probe가 쓴다.
  POST /v1/optimize   요청 JSON → 후보 → 응답 JSON. 계약은 docs/milp/ppt README 6-2절. engine으로 엔진을 고른다:
                        team-cpsat  팀 엔진 — 팀원 코드 berth_sim(OR-Tools CP-SAT)을 그대로 부른다 (team_engine.py가 바꿔 끼움)
                        ppt-milp    기존 엔진 — docs/milp/ppt(HiGHS)
                      422 입력 오류 · 429 다른 계산 중 · 500 계산 실패(솔버 결과가 규칙 검사를 통과하지 못함 등)

금액은 여기서 낸 값을 그대로 공개하지 않는다. Spring이 같은 PPT 식(Java)으로 다시 계산하고, 1센트라도 다르면 공개하지 않는다.
LLM은 부르지 않는다(NFR-01: 금액 계산에 LLM 0건). 문장·임베딩 경로는 팀이 LangGraph로 붙일 자리다.
"""
from __future__ import annotations

import ctypes
import gc
import hashlib
import json
import logging
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from . import team_engine
from .engine import run as engine

RULES_FILE = Path(engine.__file__).resolve().parent / "rules" / "terminal.json"
RULES_SHA256 = hashlib.sha256(RULES_FILE.read_bytes()).hexdigest()
RULES_VERSION = json.loads(RULES_FILE.read_text(encoding="utf-8"))["version"]

# uvicorn이 형식을 잡아 둔 로거에 남긴다(접근 로그는 꺼 두었으므로 실패 원인은 여기서만 보인다).
log = logging.getLogger("uvicorn.error")

# 엔진이 그대로 쓰는 옵션의 범위. grid_min이 0 이하면 엔진의 눈금 반복이 끝나지 않는다(Spring 입구도 같은 범위로 막는다).
_OPTION_RANGES = {
    "grid_min": (5, 240, True),
    "max_wait_h": (0, 720, False),
    "inventory_wait_step_h": (0.25, 24, False),
    "inventory_wait_max_h": (0, 720, False),
}


def _check_options(request: dict) -> None:
    opts = request.get("options")
    if opts is None:
        return
    if not isinstance(opts, dict):
        raise HTTPException(422, "입력 오류: options는 객체여야 합니다")
    gen = opts.get("generation")
    if gen is not None and gen not in ("auto", "EXACT", "GRID"):
        raise HTTPException(422, f"입력 오류: options.generation은 auto·EXACT·GRID 중 하나: {gen!r}")
    for name, (lo, hi, integer) in _OPTION_RANGES.items():
        v = opts.get(name)
        if v is None:
            continue
        bad = isinstance(v, bool) or not isinstance(v, (int, float)) or (integer and not float(v).is_integer()) or not lo <= v <= hi
        if bad:
            raise HTTPException(422, f"입력 오류: options.{name}는 {'정수 ' if integer else ''}{lo}~{hi}: {v!r}")


# 에이전트는 한 번에 한 계산만 한다. HiGHS가 코어를 여러 개 쓰고, Spring도 동시 계산 1건으로 보낸다.
_solving = threading.Lock()

# 계산이 끝나면 쓴 메모리를 운영체제에 돌려준다. Python은 큰 계산 뒤에도 메모리를 쥐고 있어서(조각난 힙) 54척 계산을
# 연달아 세 번 하면 1.5Gi 한도에 걸려 OOMKilled가 났다(11-16 verify-full). glibc malloc_trim이 빈 힙을 돌려준다(맥은 없음).
try:
    _malloc_trim = ctypes.CDLL("libc.so.6").malloc_trim
except (OSError, AttributeError):
    _malloc_trim = None


def _release_memory() -> None:
    gc.collect()
    if _malloc_trim is not None:
        _malloc_trim(0)

app = FastAPI(title="D-MIN agent", version="0.1.0", docs_url=None, redoc_url=None, openapi_url=None)


class OptimizeIn(BaseModel):
    request: dict
    top: int = Field(3, ge=1, le=5)
    time_limit_s: float = Field(120, ge=1, le=600)
    engine: str = Field("ppt-milp", pattern="^(ppt-milp|team-cpsat)$")


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "engine": engine.ENGINE_VERSION,
        "engines": {"ppt-milp": engine.ENGINE_VERSION, "team-cpsat": team_engine.ENGINE_VERSION},
        "team_source_sha256": team_engine.SOURCE_SHA,
        "rules_version": RULES_VERSION,
        "rules_sha256": RULES_SHA256,
        "busy": _solving.locked(),
    }


@app.post("/v1/optimize")
def optimize(body: OptimizeIn) -> dict:
    # def(비동기 아님)라 FastAPI가 스레드에서 돌린다 → 계산 중에도 /health가 응답해 상태 확인(healthcheck)이 끊기지 않는다.
    patch = body.request.get("rule_patch")
    if patch is not None and not isinstance(patch, dict):      # 빈 목록 []은 엔진이 '패치 없음'으로 넘기므로 여기서 막는다
        raise HTTPException(422, f"입력 오류 TypeError: rule_patch는 객체여야 합니다 (받은 값 {type(patch).__name__})")
    _check_options(body.request)
    if not _solving.acquire(blocking=False):
        raise HTTPException(429, "다른 계산이 진행 중입니다")
    try:
        solve = team_engine.optimize if body.engine == "team-cpsat" else engine.optimize
        resp = solve(body.request, top=body.top, time_limit=body.time_limit_s)
    except (KeyError, ValueError, TypeError, AttributeError, IndexError, OverflowError) as e:
        log.warning("입력 오류 %s: %s", type(e).__name__, e)
        raise HTTPException(422, f"입력 오류 {type(e).__name__}: {e}") from None
    except RuntimeError as e:
        log.error("계산 실패: %s", e, exc_info=True)
        raise HTTPException(500, f"계산 실패: {e}") from None
    finally:
        _release_memory()
        _solving.release()
    resp["engine"]["rules_sha256"] = RULES_SHA256
    return resp
