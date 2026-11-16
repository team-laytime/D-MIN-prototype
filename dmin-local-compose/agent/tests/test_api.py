"""에이전트 경로 검사. 정답은 docs/milp/ppt/out/EXAMPLE-3.response.json(손계산·전수 탐색으로 검산된 값)."""
import copy
import json
from pathlib import Path

from fastapi.testclient import TestClient

from dmin_agent.main import RULES_SHA256, app

client = TestClient(app)
EXAMPLE = json.loads((Path(__file__).parent / "example-request.json").read_text(encoding="utf-8"))
# EXAMPLE-3.response.json 1안의 입항 건별 (부두, ETB, 체선료). F는 요청에서부터 FIX다.
FIRST = {"A": ("#8", "2026-11-10T07:30", 0.0), "B": ("#6", "2026-11-10T17:30", 0.0),
         "C": ("#7", "2026-11-10T08:30", 0.0), "F": ("#8", "2026-11-12T08:00", 7192.3)}


def test_health_reports_engine_and_rules():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok" and body["engine"] == "ppt-milp/1.0"
    assert body["rules_version"] == "ulsan-clx/ppt-v1" and body["rules_sha256"] == RULES_SHA256


def test_optimize_example_matches_golden():
    r = client.post("/v1/optimize", json={"request": EXAMPLE, "top": 3, "time_limit_s": 30})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "OK"
    assert body["baseline"]["total_usd"] == 25641.62
    assert [c["total_usd"] for c in body["candidates"]] == [7192.3, 7192.3, 7192.3]
    assert all(not c["violations"] for c in body["candidates"])
    assert body["engine"]["rules_sha256"] == RULES_SHA256


def test_bad_input_is_422_not_500():
    bad = {**EXAMPLE, "arrivals": [{"id": "X"}]}
    r = client.post("/v1/optimize", json={"request": bad})
    assert r.status_code == 422


def test_all_fixed_request_keeps_fixed_plans():
    # 다시 짤 입항 건이 없으면(묶음 0개) 후보는 FIX 계획 그대로다. 전에는 계획 0개·$0·'작업계획 없음'이 나왔다.
    req = copy.deepcopy(EXAMPLE)
    for v in req["arrivals"]:
        if v["id"] != "F":
            berth, etb, _ = FIRST[v["id"]]
            v["status"], v["fix"] = "FIX", {"berth": berth, "etb": etb}
    r = client.post("/v1/optimize", json={"request": req, "time_limit_s": 30})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "OK" and body["components"] == [] and len(body["candidates"]) == 1
    c = body["candidates"][0]
    assert len(c["plans"]) == 4 and not c["violations"]
    assert {p["arrival_id"]: (p["berth"], p["etb"], p["demurrage_usd"]) for p in c["plans"]} == FIRST
    assert c["total_usd"] == round(sum(usd for _, _, usd in FIRST.values()), 2) == 7192.3


def test_api_docs_are_closed():
    # /health와 /v1/optimize만 연다
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404


def test_rule_patch_must_be_object():
    # []는 엔진이 '패치 없음'으로 넘기므로 API에서 막는다
    for patch in ([], ["demurrage.weather_basis"]):
        r = client.post("/v1/optimize", json={"request": {**EXAMPLE, "rule_patch": patch}})
        assert r.status_code == 422 and "rule_patch" in r.json()["detail"]


def test_engine_input_errors_are_422_not_500():
    over = copy.deepcopy(EXAMPLE)
    over["arrivals"][0]["contract"]["rate_usd_day"] = 1e308
    for req, kind in (({**EXAMPLE, "rule_patch": {"berths.99.size": 1}}, "IndexError"),
                      (over, "OverflowError")):
        r = client.post("/v1/optimize", json={"request": req})
        assert r.status_code == 422 and r.json()["detail"].startswith(f"입력 오류 {kind}: ")
    # options 모양이 틀리면 엔진에 들어가기 전에 막힌다(예전에는 엔진 안에서 AttributeError)
    r = client.post("/v1/optimize", json={"request": {**EXAMPLE, "options": []}})
    assert r.status_code == 422 and r.json()["detail"] == "입력 오류: options는 객체여야 합니다"


def test_engine_failure_is_500_and_frees_lock(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("솔버가 낸 조합이 규칙을 어김")

    monkeypatch.setattr("dmin_agent.engine.run.optimize", boom)
    r = client.post("/v1/optimize", json={"request": EXAMPLE})
    assert r.status_code == 500 and r.json()["detail"] == "계산 실패: 솔버가 낸 조합이 규칙을 어김"
    assert client.get("/health").json()["busy"] is False


def test_bad_options_are_422_before_solving():
    # grid_min ≤ 0이면 엔진의 GRID 눈금 반복이 끝나지 않는다 → 계산에 들어가기 전에 막아야 한다
    for opts in ({"generation": "GRID", "grid_min": -30}, {"grid_min": 0}, {"max_wait_h": -1}, {"generation": "FAST"}, {"grid_min": 7.5}):
        r = client.post("/v1/optimize", json={"request": {**EXAMPLE, "options": opts}})
        assert r.status_code == 422, (opts, r.text)
    assert client.get("/health").json()["busy"] is False
