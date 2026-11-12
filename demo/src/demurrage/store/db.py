"""저장소 — 실행 기록·결정 기록·감사 기록 (FR-47 확정 이력, NFR-02 재현, NFR-17 실행 로그).

- 같은 코드가 SQLite(로컬·테스트)와 PostgreSQL(컨테이너·운영)에서 돈다: SQLAlchemy Core + DATABASE_URL.
- 결정(decisions)과 감사(audit_events)는 '덧붙이기만' 한다. 고치거나 지우는 SQL은 DB 트리거가 막는다.
  확정 취소도 지우는 게 아니라 CANCEL 행을 하나 더 쓴다 → 누가 언제 무엇을 왜 골랐는지 끝까지 남는다.
- 실행 결과(runs.result_json)에는 입력·규칙 버전·엔진 버전·탐색 설정이 같이 들어가 같은 조건으로 다시 돌릴 수 있다.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import (Boolean, Column, Float, Integer, MetaData, String, Table, Text, create_engine, event, func,
                        insert, select, text)

KST = timezone(timedelta(hours=9))
md = MetaData()

runs = Table("runs", md,
             Column("id", String(32), primary_key=True),
             Column("created_at", String(32), nullable=False),
             Column("scenario_id", String(64)),
             Column("scenario_hash", String(32)),
             Column("rules_version", String(32)),
             Column("engine_version", String(16)),
             Column("status", String(16)),
             Column("fingerprint", String(32)),
             Column("baseline_usd", Float),
             Column("best_usd", Float),
             Column("savings_usd", Float),
             Column("elapsed_ms", Float),
             Column("llm_calls", Integer),
             Column("llm_cost_usd", Float),
             Column("result_json", Text, nullable=False))

decisions = Table("decisions", md,
                  Column("id", Integer, primary_key=True, autoincrement=True),
                  Column("run_id", String(32), nullable=False, index=True),
                  Column("scenario_hash", String(32)),
                  Column("candidate", String(16), nullable=False),
                  Column("action", String(16), nullable=False),     # SELECT / CANCEL / APPLIED
                  Column("actor", String(64), nullable=False),
                  Column("reason", Text),
                  Column("created_at", String(32), nullable=False))

audit_events = Table("audit_events", md,
                     Column("id", Integer, primary_key=True, autoincrement=True),
                     Column("run_id", String(32), index=True),
                     Column("ts", String(32), nullable=False),
                     Column("kind", String(32), nullable=False),
                     Column("actor", String(64)),
                     Column("detail_json", Text))

llm_calls = Table("llm_calls", md,
                  Column("id", Integer, primary_key=True, autoincrement=True),
                  Column("run_id", String(32), index=True),
                  Column("ts", String(32)),
                  Column("purpose", String(32)),
                  Column("model", String(64)),
                  Column("input_tokens", Integer),
                  Column("output_tokens", Integer),
                  Column("cost_usd", Float),
                  Column("ok", Boolean),
                  Column("error", Text))

APPEND_ONLY = ("decisions", "audit_events", "llm_calls")


def now() -> str:
    return datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")


class Store:
    def __init__(self, url: str = None):
        self.url = url or os.environ.get("DATABASE_URL") or "sqlite:///./runtime/demurrage.db"
        if self.url.startswith("sqlite:///"):
            path = self.url[len("sqlite:///"):]
            if path and path != ":memory:":
                os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self.engine = create_engine(self.url, future=True, pool_pre_ping=True)
        if self.engine.dialect.name == "sqlite":
            @event.listens_for(self.engine, "connect")
            def _fk(dbapi_conn, _):  # pragma: no cover - 연결 설정
                dbapi_conn.execute("PRAGMA journal_mode=WAL")
        md.create_all(self.engine)
        self._append_only_triggers()

    @property
    def dialect(self) -> str:
        return self.engine.dialect.name

    def _append_only_triggers(self):
        with self.engine.begin() as c:
            if self.dialect == "sqlite":
                for t in APPEND_ONLY:
                    for op in ("UPDATE", "DELETE"):
                        c.execute(text(f"CREATE TRIGGER IF NOT EXISTS {t}_no_{op.lower()} BEFORE {op} ON {t} "
                                       f"BEGIN SELECT RAISE(ABORT, 'append-only table: {t}'); END;"))
            elif self.dialect == "postgresql":
                c.execute(text("CREATE OR REPLACE FUNCTION forbid_change() RETURNS trigger AS $$ "
                               "BEGIN RAISE EXCEPTION 'append-only table: %', TG_TABLE_NAME; END; $$ LANGUAGE plpgsql;"))
                for t in APPEND_ONLY:
                    c.execute(text(f"DROP TRIGGER IF EXISTS {t}_append_only ON {t}"))
                    c.execute(text(f"CREATE TRIGGER {t}_append_only BEFORE UPDATE OR DELETE ON {t} "
                                   f"FOR EACH ROW EXECUTE FUNCTION forbid_change()"))

    def ping(self) -> bool:
        with self.engine.connect() as c:
            return c.execute(text("SELECT 1")).scalar() == 1

    # ---------- 실행 ----------
    def save_run(self, run: dict, elapsed_ms: float = 0.0):
        best = run["candidates"][0]["total_usd"] if run.get("candidates") else None
        base = run.get("baseline", {}).get("total_usd")
        with self.engine.begin() as c:
            c.execute(insert(runs).values(
                id=run["run_id"], created_at=run["created_at"], scenario_id=run["scenario"].get("id"),
                scenario_hash=run["scenario"].get("hash"), rules_version=run["versions"]["rules"]["version"],
                engine_version=run["versions"]["engine"], status=run["status"], fingerprint=run.get("fingerprint"),
                baseline_usd=base, best_usd=best, savings_usd=(base - best) if (base is not None and best is not None) else None,
                elapsed_ms=elapsed_ms, llm_calls=run.get("llm", {}).get("calls", 0), llm_cost_usd=run.get("llm", {}).get("cost_usd", 0.0),
                result_json=json.dumps(run, ensure_ascii=False)))
            for e in run.get("llm", {}).get("log", []):
                c.execute(insert(llm_calls).values(run_id=run["run_id"], ts=now(), purpose=e["purpose"], model=e["model"],
                                                   input_tokens=e["input_tokens"], output_tokens=e["output_tokens"],
                                                   cost_usd=e["cost_usd"], ok=e["ok"], error=e["error"]))
        self.audit(run["run_id"], "RUN_CREATED", "system", {"scenario": run["scenario"].get("id"), "status": run["status"],
                                                             "fingerprint": run.get("fingerprint")})

    def get_run(self, run_id: str):
        with self.engine.connect() as c:
            row = c.execute(select(runs.c.result_json).where(runs.c.id == run_id)).first()
        return json.loads(row[0]) if row else None

    def list_runs(self, limit: int = 20) -> list:
        cols = [runs.c.id, runs.c.created_at, runs.c.scenario_id, runs.c.status, runs.c.baseline_usd, runs.c.best_usd,
                runs.c.savings_usd, runs.c.fingerprint, runs.c.rules_version, runs.c.elapsed_ms]
        with self.engine.connect() as c:
            rows = c.execute(select(*cols).order_by(runs.c.created_at.desc(), runs.c.id).limit(limit)).all()
        return [dict(r._mapping) for r in rows]

    # ---------- 결정(사람만) ----------
    def add_decision(self, run_id: str, scenario_hash: str, candidate: str, action: str, actor: str, reason: str) -> dict:
        row = {"run_id": run_id, "scenario_hash": scenario_hash, "candidate": candidate, "action": action,
               "actor": actor, "reason": reason, "created_at": now()}
        with self.engine.begin() as c:
            rid = c.execute(insert(decisions).values(**row)).inserted_primary_key[0]
        self.audit(run_id, f"DECISION_{action}", actor, {"candidate": candidate, "reason": reason})
        return {"id": rid, **row}

    def list_decisions(self, run_id: str) -> list:
        with self.engine.connect() as c:
            rows = c.execute(select(decisions).where(decisions.c.run_id == run_id).order_by(decisions.c.id)).all()
        return [dict(r._mapping) for r in rows]

    def candidate_states(self, run_id: str, labels: list) -> dict:
        """FR-48: 추천(Agent) → 선택됨(담당자) → 현업 반영 완료(담당자). 기록을 처음부터 다시 읽어 현재 상태를 만든다."""
        state = {l: "추천" for l in labels}
        for d in self.list_decisions(run_id):
            if d["action"] == "SELECT":
                for l in state:
                    if state[l] == "선택됨":
                        state[l] = "추천"
                state[d["candidate"]] = "선택됨"
            elif d["action"] == "CANCEL" and state.get(d["candidate"]) in ("선택됨", "현업 반영 완료"):
                state[d["candidate"]] = "추천"
            elif d["action"] == "APPLIED" and state.get(d["candidate"]) == "선택됨":
                state[d["candidate"]] = "현업 반영 완료"
        return state

    # ---------- 감사 ----------
    def audit(self, run_id, kind, actor, detail: dict):
        with self.engine.begin() as c:
            c.execute(insert(audit_events).values(run_id=run_id, ts=now(), kind=kind, actor=actor,
                                                  detail_json=json.dumps(detail, ensure_ascii=False)))

    def list_audit(self, run_id: str) -> list:
        with self.engine.connect() as c:
            rows = c.execute(select(audit_events).where(audit_events.c.run_id == run_id).order_by(audit_events.c.id)).all()
        return [{**dict(r._mapping), "detail": json.loads(r.detail_json or "{}")} for r in rows]

    def list_llm_calls(self, run_id: str) -> list:
        with self.engine.connect() as c:
            rows = c.execute(select(llm_calls).where(llm_calls.c.run_id == run_id).order_by(llm_calls.c.id)).all()
        return [dict(r._mapping) for r in rows]

    def counts(self) -> dict:
        with self.engine.connect() as c:
            return {"runs": c.execute(select(func.count()).select_from(runs)).scalar(),
                    "decisions": c.execute(select(func.count()).select_from(decisions)).scalar(),
                    "llm_calls": c.execute(select(func.count()).select_from(llm_calls)).scalar(),
                    "llm_cost_usd": float(c.execute(select(func.coalesce(func.sum(llm_calls.c.cost_usd), 0.0))).scalar())}
