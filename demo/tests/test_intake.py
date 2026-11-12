"""FR-02 — 계산 전 입력 검증: 오류 시험 11건이 모두 계산 전에 걸리고 선박·항목·사유가 표시된다."""
import copy

import pytest

from demurrage.agents.orchestrator import run_pipeline
from demurrage.engine.build import build_context
from demurrage.rules.contracts import load_contracts
from demurrage.rules.loader import DATA_DIR
from tests.conftest import load_scenario


def _base():
    return copy.deepcopy(load_scenario("S01-normal"))


def _v(doc, vid):
    return next(v for v in doc["vessels"] if v["id"] == vid)


def _inline(doc, vid):
    """계약서 번호 대신 계약 조건을 직접 적은 형태로 바꾼다(화면에서 고친 시나리오와 같은 모양)."""
    v = _v(doc, vid)
    c = load_contracts(DATA_DIR)[v.pop("contract_id")]
    v["contract"] = {"type": c["type"], "laytime_h": c["terms"]["laytime"]["hours"],
                     "demurrage_rate_usd_day": c["terms"]["demurrage_rate_usd_day"],
                     "laycan_from": c["laycan"]["from"], "laycan_to": c["laycan"]["to"]}
    return v["contract"]


CASES = [
    ("필수값 누락(ETA)", lambda d: _v(d, "V03").pop("eta"), "MISSING"),
    ("형식 오류(ETA)", lambda d: _v(d, "V03").update(eta="11월 10일 7시"), "FORMAT"),
    ("값 범위(GRT 0)", lambda d: _v(d, "V03").update(grt=0), "RANGE"),
    ("시각 순서(Laycan To < From)", lambda d: _inline(d, "V03").update(laycan_from="2026-11-12", laycan_to="2026-11-10"), "ORDER"),
    ("ID 중복", lambda d: _v(d, "V04").update(id="V03"), "DUPLICATE"),
    ("미등록 부두 참조(FIX)", lambda d: _v(d, "F1")["fixed"].update(berth="#99"), "UNKNOWN_REF"),
    ("미등록 자재코드", lambda d: _v(d, "V03").update(material_code="XX-999"), "UNKNOWN_REF"),
    ("미등록 계약 유형", lambda d: _inline(d, "V03").update(type="DES"), "UNKNOWN_REF"),
    ("없는 계약서 번호", lambda d: _v(d, "V03").update(contract_id="CT-0000-00"), "UNKNOWN_REF"),
    ("배정 가능한 부두 없음(DWT 초과)", lambda d: _v(d, "V07").update(dwt=999999), "NO_BERTH"),
    ("작업시간 추정 불가(실적 없음)", lambda d: (_v(d, "V07").update(material_code="BO-G3")), "NO_WORKTIME"),
]


@pytest.mark.parametrize("name,mutate,code", CASES, ids=[c[0] for c in CASES])
def test_input_errors_stop_before_calculation(rules, name, mutate, code):
    doc = _base()
    mutate(doc)
    ctx, issues = build_context(doc, rules)
    assert ctx is None, f"{name}: 오류인데 계산 문맥이 만들어짐"
    errs = [i for i in issues if i.level == "ERROR"]
    assert any(i.code == code for i in errs), [i.as_dict() for i in errs]
    assert all(i.vessel and i.field and i.message for i in errs)


def test_pipeline_keeps_input_on_error():
    doc = _base()
    _v(doc, "V03").pop("eta")
    run = run_pipeline(doc)
    assert run["status"] == "INPUT_ERROR"
    assert run["input"] is doc                       # NFR-11 입력 보존
    assert run["agent_log"][0]["agent"] == "입력검증 Agent" and len(run["agent_log"]) == 1
