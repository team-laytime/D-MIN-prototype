"""LLM 어댑터 — '문장만 쓰는' 가장자리 계층 (NFR-01, NFR-10, NFR-12, NFR-14, NFR-15, NFR-18).

원칙
1. 숫자를 만들지 않는다: LLM 출력에는 숫자가 하나도 없어야 한다. 금액·시각은 {{키}} 자리표시자로만 쓰고,
   렌더러가 엔진 값으로 바꿔 넣는다. 숫자가 섞여 나오면 그 출력은 버리고 템플릿 문장을 쓴다(guard_text).
2. 보내는 항목을 제한한다: 선박 ID·선종·화물·부두·리스크 상태·자리표시자 이름과 표시값만 보낸다.
   계약 요율, 선박명 원문, 비고(자유 입력 문장)는 보내지 않는다(allowlist).
3. 입력 문장은 지시가 아니라 데이터다: 시스템 프롬프트에 명시하고, 자유 입력 문장 자체를 보내지 않는다.
4. 실패해도 멈추지 않는다: 키가 없거나 API가 실패하거나 비용 상한(1회 1달러)을 넘으면 템플릿으로 끝까지 간다.
5. 공급자를 바꿔도 다른 모듈은 그대로: LLMClient 인터페이스(complete)만 맞추면 된다.
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from typing import Optional

# 1M 토큰당 USD (입력, 출력) — 비용 추정용. 2026-10 공개 가격표 기준.
PRICING = {
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
}
DEFAULT_MODEL = "claude-opus-5-5"


@dataclass
class LLMResult:
    ok: bool
    text: str = ""
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_s: float = 0.0
    error: str = ""


@dataclass
class CostMeter:
    """실행 1회 동안의 호출 수·토큰·추정 비용. 상한을 넘으면 더 부르지 않는다(NFR-12)."""
    cap_usd: float = 1.0
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    log: list = field(default_factory=list)

    def allow(self, est_usd: float) -> bool:
        return self.cost_usd + est_usd <= self.cap_usd

    def record(self, purpose: str, r: LLMResult):
        self.calls += 1
        self.input_tokens += r.input_tokens
        self.output_tokens += r.output_tokens
        self.cost_usd += r.cost_usd
        self.log.append({"purpose": purpose, "model": r.model, "ok": r.ok, "input_tokens": r.input_tokens,
                         "output_tokens": r.output_tokens, "cost_usd": round(r.cost_usd, 6),
                         "latency_s": round(r.latency_s, 3), "error": r.error})

    def summary(self) -> dict:
        return {"calls": self.calls, "input_tokens": self.input_tokens, "output_tokens": self.output_tokens,
                "cost_usd": round(self.cost_usd, 6), "cap_usd": self.cap_usd, "log": self.log}


def estimate_cost(model: str, in_tokens: int, out_tokens: int) -> float:
    pin, pout = PRICING.get(model, PRICING[DEFAULT_MODEL])
    return in_tokens / 1e6 * pin + out_tokens / 1e6 * pout


class LLMClient:
    name = "none"
    model = ""

    def available(self) -> bool:
        return False

    def complete(self, system: str, user: str, schema: Optional[dict] = None, max_tokens: int = 4000) -> LLMResult:
        return LLMResult(ok=False, error="LLM 미사용")


class DisabledLLM(LLMClient):
    """키가 없거나 LLM_PROVIDER=none — 템플릿 문장으로 끝까지 간다."""
    name = "disabled"


class AnthropicLLM(LLMClient):
    """Anthropic Messages API (Python SDK). 선택 사항 — 설치·키가 없으면 쓰지 않는다."""
    name = "anthropic"

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL, base_url: str = "https://api.anthropic.com",
                 timeout_s: float = 60.0, max_retries: int = 2, effort: str = "medium"):
        import anthropic  # 지연 import — 엔진·API는 이 패키지 없이도 돈다
        self._anthropic = anthropic
        self.client = anthropic.Anthropic(api_key=api_key, base_url=base_url, timeout=timeout_s, max_retries=max_retries)
        self.model = model
        self.effort = effort

    def available(self) -> bool:
        return True

    def _create(self, **kw):
        # 거절(refusal) 시 서버가 다른 모델로 이어 받게 하는 폴백(server-side fallback)을 기본으로 켠다.
        return self.client.beta.messages.create(
            model=self.model, betas=["server-side-fallback-2026-07-01"], fallbacks="default",
            output_config={"effort": self.effort, **kw.pop("output_config", {})}, **kw)

    def _result(self, resp, t0) -> LLMResult:
        u = resp.usage
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        ok = resp.stop_reason not in ("refusal", "max_tokens")
        return LLMResult(ok=ok, text=text, model=getattr(resp, "model", self.model), input_tokens=u.input_tokens,
                         output_tokens=u.output_tokens, cost_usd=estimate_cost(self.model, u.input_tokens, u.output_tokens),
                         latency_s=time.perf_counter() - t0, error="" if ok else f"stop_reason={resp.stop_reason}")

    def complete(self, system: str, user: str, schema: Optional[dict] = None, max_tokens: int = 4000) -> LLMResult:
        t0 = time.perf_counter()
        a = self._anthropic
        kw = {"max_tokens": max_tokens, "system": system, "messages": [{"role": "user", "content": user}]}
        if schema:
            kw["output_config"] = {"format": {"type": "json_schema", "schema": schema}}
        try:
            return self._result(self._create(**kw), t0)
        except a.RateLimitError as e:
            return LLMResult(ok=False, model=self.model, error=f"rate_limit: {e}", latency_s=time.perf_counter() - t0)
        except a.APIStatusError as e:
            return LLMResult(ok=False, model=self.model, error=f"api_status {e.status_code}", latency_s=time.perf_counter() - t0)
        except a.APIConnectionError as e:
            return LLMResult(ok=False, model=self.model, error=f"connection: {e}", latency_s=time.perf_counter() - t0)


def get_llm(env: Optional[dict] = None) -> LLMClient:
    """환경변수로 고른다: LLM_PROVIDER=anthropic + ANTHROPIC_API_KEY가 있을 때만 실제 호출."""
    env = env if env is not None else os.environ
    provider = (env.get("LLM_PROVIDER") or "none").lower()
    key = env.get("ANTHROPIC_API_KEY")
    if provider == "anthropic" and key:
        try:
            return AnthropicLLM(api_key=key, model=env.get("LLM_MODEL") or DEFAULT_MODEL,
                                base_url=env.get("LLM_BASE_URL") or "https://api.anthropic.com",
                                timeout_s=float(env.get("LLM_TIMEOUT_S") or 60))
        except ImportError:
            return DisabledLLM()
    return DisabledLLM()


# ---------- 숫자 검문 ----------
PLACEHOLDER = re.compile(r"\{\{([A-Za-z0-9_:.\-#]+)\}\}")


def guard_text(text: str, allowed_tokens: set) -> list:
    """자리표시자·허용 토큰(선박 ID, 부두 ID, 1안·2안·3안)을 지운 뒤 숫자가 남으면 문제 목록을 돌려준다."""
    problems = []
    stripped = PLACEHOLDER.sub(" ", text)
    for tok in sorted(allowed_tokens, key=len, reverse=True):
        stripped = stripped.replace(tok, " ")
    for m in re.finditer(r"\d[\d,.:]*", stripped):
        problems.append(m.group(0))
    return problems


def fill_placeholders(text: str, facts: dict) -> tuple:
    """{{키}} → 표시값. 모르는 키가 있으면 (텍스트, [모르는 키])."""
    unknown = []

    def rep(m):
        k = m.group(1)
        if k in facts:
            return str(facts[k])
        unknown.append(k)
        return m.group(0)
    return PLACEHOLDER.sub(rep, text), unknown
