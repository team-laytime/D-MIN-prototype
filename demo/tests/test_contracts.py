"""계약서 예시와 시나리오 라이브러리 — 계산 조건이 계약서에서 오고, 근거가 조항 번호로 붙는다(FR-26, FR-39, NFR-04)."""
import json

import pytest
from fastapi.testclient import TestClient

from demurrage.agents.orchestrator import run_pipeline
from demurrage.api.app import create_app
from demurrage.store.db import Store
from demurrage.rules.contracts import contract_from_doc, load_contracts
from demurrage.rules.loader import DATA_DIR
from tests.conftest import load_scenario

CONTRACTS = load_contracts(DATA_DIR)
LIBRARY = sorted((DATA_DIR / "scenarios").glob("*.json"))


def _vessel(run, label, vid):
    s = run["baseline"] if label == "기준안" else next(c for c in run["candidates"] if c["label"] == label)
    return next(v for v in s["vessels"] if v["vessel_id"] == vid)


def test_contract_files_are_labelled_fictional_and_map_to_known_rules(rules):
    assert len(CONTRACTS) >= 20
    for cid, doc in CONTRACTS.items():
        assert doc["id"] == cid and "가상" in doc["label"]
        assert doc["type"] in rules.contract_types
        assert sum(1 for p in doc["parties"] if p.get("counterparty")) == 1
        for c in doc["clauses"]:
            unknown = set(c["rules"]) - set(rules.rule_index)
            assert not unknown, f"{cid} {c['ref']}: 규칙 표에 없는 ID {unknown}"


def test_pro_rata_laytime_comes_from_contract():
    c = contract_from_doc(CONTRACTS["CT-2611-05"], qty=30000, nor_tender=None)
    assert c.laytime_h == 12                                  # 36시간 × 30,000 ÷ 90,000
    assert "부분 화물 비례" in c.laytime_basis
    assert c.ref("LAY-07") == ("Part I (H)",)


@pytest.mark.parametrize("path", LIBRARY, ids=lambda p: p.stem)
def test_library_scenarios_have_cards_and_resolvable_contracts(path):
    doc = json.loads(path.read_text(encoding="utf-8"))
    card = doc["card"]
    assert card["category"] and card["situation"] and card["question"] and card["watch"]
    for v in doc["vessels"]:
        assert v.get("contract_id") in CONTRACTS, f"{doc['id']} {v['id']}: 계약서 번호 없음"


def test_library_order_is_unique():
    orders = [json.loads(p.read_text(encoding="utf-8"))["card"]["order"] for p in LIBRARY]
    assert len(orders) == len(set(orders))


def test_calc_sheet_cites_contract_clause_numbers():
    run = run_pipeline(load_scenario("S05-storm-rush"), with_sensitivity=False)
    v05 = _vessel(run, "1안", "V05")
    step = next(s for s in v05["sheet"]["steps"] if s["title"].startswith("허용 정박시간"))
    chip = next(b for b in step["basis"] if b["kind"] == "계약")
    assert chip["contract_id"] == "CT-2611-05" and chip["clauses"] == ["Part I (H)"]
    assert "30,000 ÷ 계약 90,000" in step["formula"]
    assert len(v05["sheet"]["steps"]) == 9 and v05["sheet"]["summary"]


def test_weather_clause_differs_by_contract():
    """S14: 같은 배 두 척 — 용선계약(기상 절반 감면)과 매매계약(감면 없음)이 다른 금액을 낸다."""
    run = run_pipeline(load_scenario("S14-contract-terms"), with_sensitivity=False)
    k2_base = _vessel(run, "기준안", "K2")                  # 매매계약 — 기다려도 감면 없음
    assert k2_base["weather_minutes"] > 0 and k2_base["weather_deduction_minutes"] == 0
    k1_best = _vessel(run, "1안", "K1")                     # 용선계약 — 기상 대기의 절반 공제
    assert k1_best["weather_deduction_minutes"] == k1_best["weather_minutes"] / 2 > 0
    assert _vessel(run, "1안", "K2")["amount_usd"] == 0     # 감면이 없는 배를 강풍 전에 붙인다
    assert run["candidates"][0]["savings_usd"] > 0


def test_baseline_that_breaks_a_deadline_is_reported_not_compared():
    """S15: 도착 순서로는 V09 선적 기한을 못 지킨다 → 기준안 '성립 안 함', 절감액 비교 없음."""
    run = run_pipeline(load_scenario("S15-deadline"), with_sensitivity=False)
    b = run["baseline"]
    assert not b["complete"] and [x["vessel"] for x in b["infeasible"]] == ["V09"]
    best = run["candidates"][0]
    assert "savings_usd" not in best
    assert _vessel(run, "1안", "V09")["etb"] <= "2026-11-11 08:00"
    assert "성립하지 않습니다" in run["report"]["narrative"]["summary"]
    assert "기준안 성립 안 함" in run["mail"]["subject"]


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    db = tmp_path_factory.mktemp("db") / "c.db"
    with TestClient(create_app(store=Store(f"sqlite:///{db}"))) as c:
        yield c


def test_contracts_api(client):
    lst = client.get("/api/contracts").json()
    assert len(lst) == len(CONTRACTS)
    ct = next(c for c in lst if c["id"] == "CT-2611-05")
    assert {u["scenario"] for u in ct["used_in"]} >= {"S05-storm-rush"}
    doc = client.get("/api/contracts/CT-2611-05").json()
    assert doc["summary"]["pro_rata"] and doc["clauses"]
    assert client.get("/api/contracts/CT-0000-00").status_code == 404
    sc = client.get("/api/scenarios").json()
    assert sc[0]["id"] == "S05-storm-rush" and all(x["card"] for x in sc)
