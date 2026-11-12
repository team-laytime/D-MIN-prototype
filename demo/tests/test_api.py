"""API·저장소 — 실행 → 근거 → 보고서 → 사람의 확정(덧붙이기만) → 감사, 운영 엔드포인트."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from demurrage.api.app import create_app
from demurrage.store.db import Store


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    db = tmp_path_factory.mktemp("db") / "t.db"
    store = Store(f"sqlite:///{db}")
    app = create_app(store=store)
    with TestClient(app) as c:
        c.store = store
        yield c


@pytest.fixture(scope="module")
def run_id(client):
    r = client.post("/api/runs", json={"scenario_id": "S05-storm-rush"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "OK" and body["candidates"]
    return body["run_id"]


def test_ops_endpoints(client, run_id):
    assert client.get("/healthz").json()["status"] == "ok"
    assert client.get("/readyz").json()["status"] == "ready"
    m = client.get("/metrics").text
    assert "demurrage_runs_total" in m and "demurrage_db_runs 1" in m
    meta = client.get("/api/meta").json()
    assert meta["llm"]["enabled"] is False and len(meta["agents"]) == 7


def test_scenarios_and_validation(client):
    ids = [s["id"] for s in client.get("/api/scenarios").json()]
    assert {"S01-normal", "S02-wind", "S03-rush", "S04-maintenance", "S05-storm-rush"} <= set(ids)
    doc = client.get("/api/scenarios/S01-normal").json()
    doc["vessels"][0]["eta"] = "잘못된 시각"
    v = client.post("/api/validate", json=doc).json()
    assert v["ok"] is False and v["issues"][0]["code"] == "FORMAT"


def test_input_error_returns_422_with_input_kept(client):
    doc = client.get("/api/scenarios/S01-normal").json()
    doc["vessels"][0].pop("eta")
    r = client.post("/api/runs", json={"scenario": doc})
    assert r.status_code == 422 and r.json()["input"]["vessels"][0]["id"] == doc["vessels"][0]["id"]


def test_run_detail_evidence_and_exports(client, run_id):
    run = client.get(f"/api/runs/{run_id}").json()
    assert run["candidate_states"] == {"1안": "추천", "2안": "추천", "3안": "추천"}
    svg = client.get(f"/api/runs/{run_id}/timeline/1안.svg")
    assert svg.status_code == 200 and svg.text.startswith("<svg") and 'data-vessel="V05"' in svg.text
    ev = client.get(f"/api/runs/{run_id}/vessels/1안/V05").json()
    assert {e["item"] for e in ev["evidence"]} >= {"ETANR", "정박개시", "정박종료", "ETB", "작업시작", "작업완료", "호스분리", "기상 공제", "하루 체선료", "예상 체선료"}
    assert client.get(f"/api/runs/{run_id}/report.md").text.startswith("# 접안 순서 후보 제안 보고서")
    assert "<table>" in client.get(f"/api/runs/{run_id}/report.html").text
    docx = client.get(f"/api/runs/{run_id}/report.docx")
    assert docx.status_code == 200 and docx.content[:2] == b"PK"
    csv_ = client.get(f"/api/runs/{run_id}/schedule.csv?label=1안")
    assert csv_.status_code == 200 and "선박" in csv_.content.decode("utf-8-sig")
    assert "담당자가 내용을 확인하고 직접 보냅니다" in client.get(f"/api/runs/{run_id}/mail.txt").text


def test_human_decisions_are_append_only(client, run_id):
    r = client.post(f"/api/runs/{run_id}/decisions", json={"candidate": "1안", "action": "SELECT", "actor": "스케줄러 김데모", "reason": "절감 최대"})
    assert r.status_code == 200 and r.json()["states"]["1안"] == "선택됨"
    assert r.json()["warning"]                                    # 남은 리스크가 있으면 경고(막지는 않음)
    r = client.post(f"/api/runs/{run_id}/decisions", json={"candidate": "2안", "action": "APPLIED", "actor": "x", "reason": ""})
    assert r.status_code == 409                                    # 선택되지 않은 후보는 반영 완료 불가
    client.post(f"/api/runs/{run_id}/decisions", json={"candidate": "1안", "action": "CANCEL", "actor": "스케줄러 김데모", "reason": "재검토"})
    client.post(f"/api/runs/{run_id}/decisions", json={"candidate": "2안", "action": "SELECT", "actor": "스케줄러 김데모", "reason": "리스크 적음"})
    d = client.get(f"/api/runs/{run_id}/decisions").json()
    assert [h["action"] for h in d["history"]] == ["SELECT", "CANCEL", "SELECT"]
    assert d["states"] == {"1안": "추천", "2안": "선택됨", "3안": "추천"}
    assert client.post(f"/api/runs/{run_id}/decisions", json={"candidate": "1안", "action": "SELECT", "actor": "", "reason": ""}).status_code == 422
    with client.store.engine.begin() as c:                         # DB 트리거가 수정·삭제를 막는다
        with pytest.raises(Exception, match="append-only"):
            c.execute(text("UPDATE decisions SET candidate='3안'"))
    with client.store.engine.begin() as c:
        with pytest.raises(Exception, match="append-only"):
            c.execute(text("DELETE FROM decisions"))


def test_audit(client, run_id):
    assert client.post(f"/api/runs/{run_id}/ask", json={"question": "왜?"}).status_code in (404, 405)
    au = client.get(f"/api/runs/{run_id}/audit").json()
    kinds = [e["kind"] for e in au["events"]]
    assert kinds[0] == "RUN_CREATED" and "DECISION_SELECT" in kinds
    assert [x["agent"] for x in au["agent_log"]][:3] == ["입력검증 Agent", "제약판단 Agent", "최적화 Agent"]


def test_verify_quick(client):
    v = client.post("/api/verify?quick=true").json()
    assert v["golden"]["mismatches"] == [] and v["golden"]["match_rate"] == 1.0
