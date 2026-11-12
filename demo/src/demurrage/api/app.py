"""HTTP API (FastAPI) + 정적 화면.

경계 규칙
- 계산은 오케스트레이터가, 저장은 Store가 한다. API는 입력을 검증하고 둘을 잇기만 한다.
- '후보 확정'은 POST /api/runs/{id}/decisions 하나뿐이고, 사람이 화면에서 누른 요청만 들어온다.
  계산 단계(역할 모듈)와 LLM은 이 경로를 부를 수 없다(NFR-16).
- 결정·감사 기록을 고치거나 지우는 API는 만들지 않는다(FR-47). DB 트리거도 막는다.
"""
from __future__ import annotations

import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Literal, Optional
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .. import ENGINE_VERSION
from ..agents.orchestrator import run_pipeline
from ..agents.roles import AGENTS, HUMAN_ONLY_ACTIONS
from ..engine.build import build_context
from ..llm.adapter import CostMeter, get_llm
from ..report.builder import report_docx, schedule_csv
from ..rules.contracts import contract_summary, load_contracts
from ..rules.loader import DATA_DIR, load_rules
from ..store.db import Store

WEB_DIR = Path(__file__).resolve().parents[1] / "web"


class JsonFormatter(logging.Formatter):
    def format(self, rec):
        d = {"ts": self.formatTime(rec, "%Y-%m-%dT%H:%M:%S"), "level": rec.levelname, "msg": rec.getMessage()}
        for k in ("request_id", "path", "method", "status", "ms", "run_id", "event"):
            if hasattr(rec, k):
                d[k] = getattr(rec, k)
        return json.dumps(d, ensure_ascii=False)


log = logging.getLogger("demurrage")
if not log.handlers:
    h = logging.StreamHandler()
    h.setFormatter(JsonFormatter())
    log.addHandler(h)
    log.setLevel(os.environ.get("LOG_LEVEL", "INFO"))


class RunRequest(BaseModel):
    scenario_id: Optional[str] = Field(None, description="data/scenarios의 시나리오 ID")
    scenario: Optional[dict] = Field(None, description="화면에서 고친 시나리오(전체 JSON)")
    rules_patch: Optional[dict] = Field(None, description="규칙 표 '만약' 변경 — 예: {\"contract.weather_deduction.ratio\": 0}")
    k: int = Field(3, ge=1, le=5)
    time_limit_s: float = Field(20.0, gt=0, le=120)


class DecisionRequest(BaseModel):
    candidate: str
    action: Literal["SELECT", "CANCEL", "APPLIED"]
    actor: str = Field(..., min_length=1, max_length=64)
    reason: str = Field("", max_length=1000)


METRICS = {"runs_total": 0, "run_seconds_sum": 0.0, "decisions_total": 0, "verify_total": 0,
           "last_match_rate": None, "http_requests_total": 0}


def create_app(store: Store = None, data_dir: Path = None) -> FastAPI:
    data = Path(data_dir) if data_dir else DATA_DIR
    app = FastAPI(title="척화비 — 울산 CLX 체선료 최적화 Agent (데모)", version=ENGINE_VERSION,
                  description="가상 데이터 · 의사결정 보조용. 최종 접안 계획은 담당자가 확정합니다.")
    app.state.store = store or Store()
    app.state.data = data

    @app.middleware("http")
    async def access_log(request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:10]
        t0 = time.perf_counter()
        resp = await call_next(request)
        ms = round((time.perf_counter() - t0) * 1000, 1)
        METRICS["http_requests_total"] += 1
        resp.headers["x-request-id"] = rid
        if not request.url.path.startswith(("/static", "/healthz", "/metrics")):
            log.info("http", extra={"request_id": rid, "path": request.url.path, "method": request.method,
                                    "status": resp.status_code, "ms": ms})
        return resp

    # ---------- 운영 ----------
    @app.get("/healthz")
    def healthz():
        return {"status": "ok", "engine": ENGINE_VERSION}

    @app.get("/readyz")
    def readyz():
        try:
            ok = app.state.store.ping()
        except Exception as exc:  # pragma: no cover - DB 장애 시
            return JSONResponse({"status": "db_unavailable", "error": str(exc)}, status_code=503)
        return {"status": "ready" if ok else "db_unavailable", "db": app.state.store.dialect}

    @app.get("/metrics", response_class=PlainTextResponse)
    def metrics():
        c = app.state.store.counts()
        lines = [
            "# HELP demurrage_runs_total 파이프라인 실행 수(이 프로세스)", "# TYPE demurrage_runs_total counter",
            f"demurrage_runs_total {METRICS['runs_total']}",
            "# TYPE demurrage_run_seconds_sum counter", f"demurrage_run_seconds_sum {METRICS['run_seconds_sum']:.3f}",
            "# TYPE demurrage_decisions_total counter", f"demurrage_decisions_total {METRICS['decisions_total']}",
            "# TYPE demurrage_http_requests_total counter", f"demurrage_http_requests_total {METRICS['http_requests_total']}",
            "# HELP demurrage_db_runs DB에 저장된 실행 수", "# TYPE demurrage_db_runs gauge", f"demurrage_db_runs {c['runs']}",
            "# TYPE demurrage_db_decisions gauge", f"demurrage_db_decisions {c['decisions']}",
            "# TYPE demurrage_llm_calls gauge", f"demurrage_llm_calls {c['llm_calls']}",
            "# TYPE demurrage_llm_cost_usd gauge", f"demurrage_llm_cost_usd {c['llm_cost_usd']:.6f}",
        ]
        if METRICS["last_match_rate"] is not None:
            lines += ["# HELP demurrage_golden_match_rate 정답 세트 일치율(마지막 검증)", "# TYPE demurrage_golden_match_rate gauge",
                      f"demurrage_golden_match_rate {METRICS['last_match_rate']:.4f}"]
        return "\n".join(lines) + "\n"

    @app.get("/api/meta")
    def meta():
        llm = get_llm()
        rules = load_rules(data_dir=data)
        return {"engine": ENGINE_VERSION, "rules": rules.summary(), "db": app.state.store.dialect,
                "llm": {"provider": llm.name, "model": getattr(llm, "model", ""), "enabled": llm.available(),
                        "cost_cap_usd": float(os.environ.get("LLM_COST_CAP_USD", "1.0"))},
                "agents": [vars(a) | {"tools": list(a.tools), "requirements": list(a.requirements)} for a in AGENTS.values()],
                "human_only_actions": list(HUMAN_ONLY_ACTIONS),
                "notice": "가상 데이터 · 의사결정 보조용 · 최종 확정은 담당자"}

    @app.get("/api/ais/vessels")
    def ais_vessels(max_age_min: float = 60, bbox: Optional[str] = None):
        """울산항 항내 선박 실시간 위치(공공데이터포털). bbox=남,서,북,동. 키는 서버에만 있다."""
        from ..data import ais
        box = None
        if bbox:
            try:
                box = tuple(float(x) for x in bbox.split(","))
                assert len(box) == 4
            except (ValueError, AssertionError):
                raise HTTPException(422, "bbox는 '남,서,북,동' 숫자 4개입니다")
        try:
            return ais.vessels(max_age_min=max_age_min, bbox=box)
        except ais.AisError as e:
            return JSONResponse({"error": str(e), "vessels": []}, status_code=503)

    @app.get("/api/ais/voyage")
    def ais_voyage(callsgn: str, year: str, voyage: Optional[str] = None):
        """한 척의 입항·투묘·접안·이안·출항 기록(울산항만공사 운항정보). 미래 ETA는 없다."""
        from ..data import ais
        if not (1 <= len(callsgn) <= 12 and year.isdigit() and len(year) == 4):
            raise HTTPException(422, "callsgn은 호출부호, year는 입항연도 4자리입니다")
        try:
            return ais.voyage_events(callsgn, year, voyage)
        except ais.AisError as e:
            return JSONResponse({"error": str(e), "events": []}, status_code=503)

    @app.get("/api/entry/arrivals")
    def entry_arrivals(callsgn: Optional[str] = None, hours_back: float = 0, hours_ahead: float = 48):
        """울산 입항 신고(해양수산부 선박입출항신고). 입항일시가 지금보다 늦으면 대리점이 신고한 입항 예정(ETA에 해당)이다."""
        from ..data import entry
        if callsgn is not None and not (1 <= len(callsgn) <= 12):
            raise HTTPException(422, "callsgn은 호출부호입니다")
        try:
            return entry.arrivals(callsgn=callsgn, hours_back=hours_back, hours_ahead=hours_ahead)
        except entry.EntryError as e:
            return JSONResponse({"error": str(e), "arrivals": []}, status_code=503)

    @app.get("/api/rules")
    def rules_tables():
        r = load_rules(data_dir=data)
        return {"summary": r.summary(), "registry": r.docs["registry"]["rules"], "terminal": r.docs["terminal"],
                "contract": r.docs["contract"], "cargo": r.docs["cargo"], "phrases": r.docs["phrases"]}

    # ---------- 시나리오 ----------
    def _scenario_files():
        return sorted((data / "scenarios").glob("*.json"))

    def _scenario_brief(d: dict, group: str) -> dict:
        card = d.get("card") or {}
        vs = d.get("vessels", [])
        return {"id": d["id"], "title": d.get("title"), "description": d.get("description"), "group": group,
                "card": card, "category": card.get("category", ""), "order": card.get("order", 99),
                "vessels": len(vs), "movable": sum(1 for v in vs if v.get("status", "PLANNED") in ("ORDERED", "PLANNED")),
                "berths": d.get("berths"), "has_weather": bool(d.get("weather_forecast")),
                "restrictions": len(d.get("restrictions", [])), "has_inventory": bool(d.get("inventory")),
                "contracts": sorted({v["contract_id"] for v in vs if v.get("contract_id")})}

    @app.get("/api/scenarios")
    def scenarios(validation: bool = False):
        out = [_scenario_brief(json.loads(p.read_text(encoding="utf-8")), "library") for p in _scenario_files()]
        if validation:
            out += [_scenario_brief(json.loads(p.read_text(encoding="utf-8")), "validation")
                    for p in sorted((data / "scenarios" / "validation").glob("*.json"))]
        return sorted(out, key=lambda x: (x["group"] != "library", x["order"], x["id"]))

    def _load_scenario(sid: str) -> dict:
        for p in list(_scenario_files()) + sorted((data / "scenarios" / "validation").glob("*.json")):
            d = json.loads(p.read_text(encoding="utf-8"))
            if d["id"] == sid:
                return d
        raise HTTPException(404, f"시나리오 {sid} 없음")

    # ---------- 계약서 ----------
    def _contract_usage() -> dict:
        used = {}
        for p in _scenario_files():
            d = json.loads(p.read_text(encoding="utf-8"))
            for v in d.get("vessels", []):
                if v.get("contract_id"):
                    used.setdefault(v["contract_id"], []).append({"scenario": d["id"], "scenario_title": d.get("title"),
                                                                 "vessel": v["id"], "vessel_name": v.get("name")})
        return used

    @app.get("/api/contracts")
    def contracts():
        used = _contract_usage()
        return [contract_summary(doc) | {"used_in": used.get(cid, [])} for cid, doc in sorted(load_contracts(data).items())]

    @app.get("/api/contracts/{cid}")
    def contract(cid: str):
        docs = load_contracts(data)
        if cid not in docs:
            raise HTTPException(404, f"계약서 {cid} 없음")
        return docs[cid] | {"summary": contract_summary(docs[cid]), "used_in": _contract_usage().get(cid, [])}

    @app.get("/api/scenarios/{sid}")
    def scenario(sid: str):
        return _load_scenario(sid)

    @app.post("/api/validate")
    def validate(doc: dict):
        ctx, issues = build_context(doc, load_rules(data_dir=data), data_dir=data)
        return {"ok": ctx is not None, "issues": [i.as_dict() for i in issues]}

    # ---------- 실행 ----------
    @app.post("/api/runs")
    def create_run(req: RunRequest):
        if not req.scenario and not req.scenario_id:
            raise HTTPException(422, "scenario_id 또는 scenario 중 하나가 필요")
        doc = req.scenario or _load_scenario(req.scenario_id)
        t0 = time.perf_counter()
        try:
            rules = load_rules(patch=req.rules_patch, data_dir=data)
        except KeyError as exc:
            raise HTTPException(422, str(exc))
        run = run_pipeline(doc, rules=rules, llm=get_llm(), k=req.k, time_limit_s=req.time_limit_s,
                           cost_cap_usd=float(os.environ.get("LLM_COST_CAP_USD", "1.0")), data_dir=data)
        elapsed = time.perf_counter() - t0
        METRICS["runs_total"] += 1
        METRICS["run_seconds_sum"] += elapsed
        if run["status"] == "INPUT_ERROR":
            # 오류여도 입력은 그대로 돌려준다(NFR-11) — 저장하지 않고 화면이 고칠 수 있게
            return JSONResponse({"status": "INPUT_ERROR", "issues": run["input_issues"], "input": doc,
                                 "agent_log": run["agent_log"]}, status_code=422)
        app.state.store.save_run(run, elapsed_ms=elapsed * 1000)
        log.info("run", extra={"run_id": run["run_id"], "event": "run_created", "ms": round(elapsed * 1000, 1)})
        return _summary(run)

    def _summary(run):
        return {"run_id": run["run_id"], "status": run["status"], "scenario": run["scenario"], "search": run["search"],
                "baseline": {k: run["baseline"][k] for k in ("label", "total_usd", "total_display")},
                "candidates": [{k: c.get(k) for k in ("label", "total_usd", "total_display", "savings_usd", "savings_display", "savings_pct")}
                               for c in run["candidates"]],
                "fingerprint": run["fingerprint"], "checks": run["checks"]}

    def _get(rid):
        run = app.state.store.get_run(rid)
        if not run:
            raise HTTPException(404, f"실행 {rid} 없음")
        return run

    @app.get("/api/runs")
    def list_runs(limit: int = 20):
        return app.state.store.list_runs(limit)

    @app.get("/api/runs/{rid}")
    def get_run(rid: str):
        run = _get(rid)
        labels = [c["label"] for c in run["candidates"]]
        run["candidate_states"] = app.state.store.candidate_states(rid, labels)
        run.pop("timeline_svgs", None)
        run.get("report", {}).pop("html", None)
        return run

    @app.get("/api/runs/{rid}/timeline/{label}.svg")
    def timeline(rid: str, label: str):
        run = _get(rid)
        svg = run["timeline_svgs"].get(label)
        if svg is None:
            raise HTTPException(404, "후보 없음")
        return Response(svg, media_type="image/svg+xml")

    @app.get("/api/runs/{rid}/vessels/{label}/{vid}")
    def vessel_evidence(rid: str, label: str, vid: str):
        run = _get(rid)
        for s in [run["baseline"]] + run["candidates"]:
            if s["label"] == label:
                for v in s["vessels"]:
                    if v["vessel_id"] == vid:
                        return v
        raise HTTPException(404, "선박 없음")

    @app.get("/api/runs/{rid}/report.md", response_class=PlainTextResponse)
    def report_md(rid: str):
        return _get(rid)["report"]["markdown"]

    @app.get("/api/runs/{rid}/report.html", response_class=HTMLResponse)
    def report_html(rid: str):
        return _get(rid)["report"]["html"]

    @app.get("/api/runs/{rid}/report.docx")
    def report_word(rid: str):
        run = _get(rid)
        data_b = report_docx(run, run["report"]["narrative"])
        app.state.store.audit(rid, "EXPORT_DOCX", "user", {})
        return Response(data_b, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        headers={"Content-Disposition": f"attachment; filename=report-{rid}.docx"})

    @app.get("/api/runs/{rid}/mail.txt", response_class=PlainTextResponse)
    def mail(rid: str):
        m = _get(rid)["mail"]
        return f"받는 사람: {m['to']}\n제목: {m['subject']}\n\n{m['body']}"

    @app.get("/api/runs/{rid}/schedule.csv")
    def schedule(rid: str, label: str = "1안"):
        run = _get(rid)
        for s in [run["baseline"]] + run["candidates"]:
            if s["label"] == label:
                fname = quote(f"schedule-{rid}-{label}.csv")
                return Response(schedule_csv(s), media_type="text/csv; charset=utf-8",
                                headers={"Content-Disposition": f"attachment; filename=schedule-{rid}.csv; filename*=UTF-8''{fname}"})
        raise HTTPException(404, "후보 없음")

    # ---------- 사람의 결정 ----------
    @app.post("/api/runs/{rid}/decisions")
    def decide(rid: str, req: DecisionRequest):
        run = _get(rid)
        labels = [c["label"] for c in run["candidates"]]
        if req.candidate not in labels:
            raise HTTPException(422, f"후보 {req.candidate} 없음 (가능: {labels})")
        states = app.state.store.candidate_states(rid, labels)
        if req.action == "APPLIED" and states.get(req.candidate) != "선택됨":
            raise HTTPException(409, "'선택됨' 상태의 후보만 '현업 반영 완료'로 바꿀 수 있음")
        unchecked = [r["name"] for r in run["risks"].get(req.candidate, []) if r["status"] == "APPLIES"]
        d = app.state.store.add_decision(rid, run["scenario"]["hash"], req.candidate, req.action, req.actor, req.reason)
        METRICS["decisions_total"] += 1
        return {"decision": d, "states": app.state.store.candidate_states(rid, labels),
                "warning": (f"남은 리스크 {len(unchecked)}건({', '.join(unchecked)})이 있는 후보입니다. 확인 후 진행해 주세요."
                            if req.action == "SELECT" and unchecked else None)}

    @app.get("/api/runs/{rid}/decisions")
    def decisions(rid: str):
        run = _get(rid)
        labels = [c["label"] for c in run["candidates"]]
        return {"history": app.state.store.list_decisions(rid), "states": app.state.store.candidate_states(rid, labels)}

    @app.get("/api/runs/{rid}/audit")
    def audit(rid: str):
        run = _get(rid)
        return {"agent_log": run["agent_log"], "events": app.state.store.list_audit(rid),
                "llm": run.get("llm"), "llm_calls": app.state.store.list_llm_calls(rid),
                "versions": run["versions"], "fingerprint": run["fingerprint"], "checks": run["checks"]}

    # ---------- 검증 ----------
    @app.post("/api/verify")
    def verify_all(quick: bool = False):
        from ..verify import run_golden, run_scenarios
        g = run_golden(data_dir=data, quick=quick)
        s = run_scenarios(scenario_dir=data / "scenarios" / "validation", data_dir=data, time_limit_s=10) if not quick else {"scenarios": []}
        METRICS["verify_total"] += 1
        METRICS["last_match_rate"] = g["match_rate"]
        titles = {}
        for p in sorted((data / "golden").glob("GC-*.json")):
            gd = json.loads(p.read_text(encoding="utf-8"))
            titles[gd.get("id", p.stem[:5])] = gd.get("title", "")
        return {"golden": {k: g[k] for k in ("total", "passed", "match_rate", "mismatches", "errors")},
                "golden_by_case": _by_case(g["checks"]), "golden_titles": titles, "scenarios": s}

    def _by_case(rows):
        out = {}
        for r in rows:
            k = (r["gc"], r["case"])
            o = out.setdefault(k, {"gc": r["gc"], "case": r["case"], "total": 0, "passed": 0, "rule_ids": r["rule_ids"]})
            o["total"] += 1
            o["passed"] += int(r["ok"])
        return list(out.values())

    # ---------- 화면 ----------
    if WEB_DIR.exists():
        app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

        @app.get("/", response_class=HTMLResponse)
        def index():
            return (WEB_DIR / "index.html").read_text(encoding="utf-8")

    return app

