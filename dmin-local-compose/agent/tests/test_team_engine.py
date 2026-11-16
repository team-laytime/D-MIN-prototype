"""팀 엔진(팀원 코드 berth_sim, CP-SAT) 검사.

핵심: 팀원 식이 낸 시각·체선료가 기존 엔진(= Spring Java판과 정답 대조로 묶인 식)과 같은 규칙에서 1분·1센트까지 같다.
그래야 Spring 재검증을 통과한다. 예시 3척의 팀 해석 정답 $9,252.07은 두 엔진이 따로 풀어 같게 나온 값이다.
"""
import copy
import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dmin_agent import team_engine as T
from dmin_agent.engine.pptcalc import Rules, load_case, make_plan, parse, profile_patch
from dmin_agent.main import app

client = TestClient(app)
EXAMPLE = json.loads((Path(__file__).parent / "example-request.json").read_text(encoding="utf-8"))
TEAM = {**EXAMPLE, "rule_patch": profile_patch("team", EXAMPLE.get("rule_patch"))}


def test_old_interpretation_is_refused_with_reasons():
    with pytest.raises(ValueError) as e:
        T.optimize(copy.deepcopy(EXAMPLE), top=3, time_limit=10)
    msg = str(e.value)
    for part in ("기상체선 세는 구간", "Draft 비교 업무 구분", "야간 도선 대상", "새벽 금지"):
        assert part in msg


def test_team_numbers_equal_old_engine_to_the_minute_and_cent():
    r = T.optimize(copy.deepcopy(TEAM), top=3, time_limit=10)
    assert r["status"] == "OK" and r["engine"]["version"].startswith("berth_sim-cpsat/")
    assert r["baseline"]["total_usd"] == 9252.07
    assert [c["total_usd"] for c in r["candidates"]] == [9252.07]          # 대안은 '3척 이상 다른 부두 · $500 안'이라 없음
    c = r["candidates"][0]
    assert c["status"] == "OPTIMAL" and not c["violations"]
    rules = Rules(patch=TEAM["rule_patch"])
    case = load_case(copy.deepcopy(TEAM), rules)
    for p in c["plans"]:
        a = case.arrivals[p["arrival_id"]]
        q = make_plan(rules, case, a, p["berth"], parse(p["etb"]), fixed=not a.movable)
        assert (parse(p["work_start"]), parse(p["work_end"]), parse(p["hose_off"]), parse(p["etu"]), parse(p["laytime_start"])) \
            == (q.a, q.c, q.h, q.u, q.lay_start), p["arrival_id"]
        assert round(p["demurrage_usd"] * 100) == q.cents, p["arrival_id"]
        assert p["trace"][0]["rule"] == "ETB" and all("src" in t for t in p["trace"])
    assert {p["arrival_id"]: (p["berth"], p["etb"]) for p in c["plans"]} == {
        "A": ("#6", "2026-11-10T07:30"), "B": ("#7", "2026-11-10T17:30"), "C": ("#8", "2026-11-10T08:30"), "F": ("#8", "2026-11-12T08:00")}


def test_api_engine_switch():
    r = client.post("/v1/optimize", json={"request": TEAM, "time_limit_s": 10, "engine": "team-cpsat"})
    assert r.status_code == 200 and r.json()["engine"]["version"].startswith("berth_sim-cpsat/")
    r = client.post("/v1/optimize", json={"request": EXAMPLE, "time_limit_s": 10, "engine": "team-cpsat"})
    assert r.status_code == 422 and "규칙 해석" in r.json()["detail"]
    r = client.post("/v1/optimize", json={"request": EXAMPLE, "engine": "bogus"})
    assert r.status_code == 422
    h = client.get("/health").json()
    assert h["engines"]["team-cpsat"] == T.ENGINE_VERSION and h["team_source_sha256"] == T.SOURCE_SHA


def test_working_ship_with_given_times_keeps_them():
    req = copy.deepcopy(TEAM)
    a = next(v for v in req["arrivals"] if v["id"] == "A")
    a["status"], a["fix"] = "WORKING", {"berth": "#6", "etb": "2026-11-10T07:30", "etu": "2026-11-11T14:00"}
    r = T.optimize(req, top=1, time_limit=10)
    p = next(p for p in r["candidates"][0]["plans"] if p["arrival_id"] == "A")
    assert (p["berth"], p["etb"], p["etu"]) == ("#6", "2026-11-10T07:30", "2026-11-11T14:00")
    assert not r["candidates"][0]["violations"]


def test_fix_off_grid_is_refused():
    req = copy.deepcopy(TEAM)
    next(v for v in req["arrivals"] if v["id"] == "F")["fix"]["etb"] = "2026-11-12T08:07"
    with pytest.raises(ValueError, match="5분"):
        T.optimize(req, top=1, time_limit=10)


def test_ship_without_any_berth_is_infeasible_with_name():
    req = copy.deepcopy(TEAM)
    next(v for v in req["arrivals"] if v["id"] == "B")["cargo_group"] = "XYZ"
    r = T.optimize(req, top=1, time_limit=10)
    assert r["status"] == "INFEASIBLE" and r["candidates"] == [] and any("B" in n for n in r["notes"])


def test_vendored_team_code_is_unchanged():
    # scripts/sync-team-engine.sh가 남긴 목록과 파일이 같아야 한다 (팀원 코드를 여기서 고치지 않는다)
    root = Path(T.__file__).resolve().parent / "berth_sim"
    rows = [l.split("|")[1:3] for l in (root / "VENDORED.md").read_text(encoding="utf-8").splitlines() if l.startswith("| ") and ".py" in l]
    assert len(rows) >= 40
    for name, sha in ((n.strip(), s.strip()) for n, s in rows):
        assert hashlib.sha256((root / name).read_bytes()).hexdigest()[:16] == sha, name
