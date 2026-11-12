"""엔진 동작 — 손계산 기대값을 둔 작은 SOF, 05 §7 쟁점 플래그, 입력 검증, 불변식.

여기의 대안 금액 중 문서에 없는 값은 '엔진 산출'이라고 주석을 달았다(문서 정답이 아님).
요율은 대부분 USD 48,000/일(= 시간당 2,000, 반액 1,000)로 두어 손계산을 쉽게 했다.
"""
import copy
import json
from datetime import date
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

import pytest

from laytime import (LEVEL_EVIDENCE, LEVEL_INFO, LEVEL_REVIEW, LEVEL_WARNING, CaseError, Policy, case_from_dict,
                     compute_statement, load_case)
from laytime import rules
from laytime.__main__ import main
from laytime.model import parse_local_ts

CASES_DIR = Path(__file__).resolve().parent.parent / "cases"
D1 = date(2026, 11, 3)
TERMS = {"form": "ASBATANKVOY", "layer": "CHARTER_PARTY", "laytime_this_port_hours": 30, "notice_hours": 6,
         "demurrage_rate_usd_day": 48000, "shifting_counts_on_demurrage": "DISPUTED"}


def build(events, terms=None, terminal=None, pumping_log=None, operation="DISCHARGE"):
    evs = []
    for row, etype, ts, *reason in events:
        e = {"row": row, "event_type": etype, "ts_local": ts}
        if reason:
            e["reason_code"] = reason[0]
        evs.append(e)
    return case_from_dict({"case_id": "T", "base_date": D1.isoformat(), "port_call": {"operation": operation},
                           "contract_terms": {**TERMS, **(terms or {})}, "terminal": terminal or {},
                           "pumping_log": pumping_log, "sof_events": evs})


def at(s):
    return parse_local_ts(s, D1)


def H(x):
    return Fraction(str(x))


def raw(name):
    return json.loads((CASES_DIR / f"{name}.json").read_text(encoding="utf-8"))


def codes(st):
    return {i.code for i in st.issues}


# 도착·NOR D1 06:00, 양묘 07:00, 접안 08:00, 하역 09:00~D2 09:00, 호스 분리 D2 10:00 → 개시 08:00, 경과 26h
STANDARD = [(1, "ANCHORED", "D1 06:00"), (1, "NOR_TENDERED", "D1 06:00"), (1, "NOR_RECEIVED", "D1 06:00"),
            (2, "ANCHOR_AWEIGH", "D1 07:00"), (3, "ALL_FAST", "D1 08:00"), (4, "HOSES_CONNECTED", "D1 08:30"),
            (5, "OPS_COMMENCED", "D1 09:00"), (6, "OPS_COMPLETED", "D2 09:00"), (7, "HOSES_DISCONNECTED", "D2 10:00")]

# 묘박지에서 체선 돌입: NOR D1 00:00 → 개시 06:00, 허용 10h → 16:00 체선 개시, 이동 20:00~22:00(체선 중)
ON_DEMURRAGE_SHIFT = [(1, "ANCHORED", "D1 00:00"), (1, "NOR_TENDERED", "D1 00:00"), (1, "NOR_RECEIVED", "D1 00:00"),
                      (2, "ANCHOR_AWEIGH", "D1 20:00"), (3, "ALL_FAST", "D1 22:00"), (4, "HOSES_CONNECTED", "D1 23:00"),
                      (5, "OPS_COMMENCED", "D2 00:00"), (8, "OPS_COMPLETED", "D2 10:00"),
                      (9, "HOSES_DISCONNECTED", "D2 11:00")]


def with_stop(events, reason, start="D2 02:00", end="D2 05:00"):
    return events + [(10, "OPS_STOPPED", start, reason), (11, "OPS_RESUMED", end)]


# ---------------------------------------------------------------- 개시 규칙 (ASB-06-NOR-START)

def test_start_is_notice_expiry_when_berthing_is_later():
    st = compute_statement(build([(1, "ANCHORED", "D1 06:00"), (1, "NOR_TENDERED", "D1 06:00"),
                                  (1, "NOR_RECEIVED", "D1 06:00"), (2, "ANCHOR_AWEIGH", "D1 12:30"),
                                  (3, "ALL_FAST", "D1 14:00"), (4, "OPS_COMMENCED", "D1 15:30"),
                                  (5, "OPS_COMPLETED", "D2 15:30"), (6, "HOSES_DISCONNECTED", "D2 16:30")]))
    assert st.laytime_start_at == at("D1 12:00") and st.start_basis == "NOTICE_EXPIRY"
    assert st.elapsed_hours == H(28.5) and st.used_hours == H(27)   # 이동 1h 30m 공제


def test_start_is_all_fast_when_berthing_is_earlier():
    st = compute_statement(build(STANDARD))
    assert st.laytime_start_at == at("D1 08:00") and st.start_basis == "ALL_FAST"
    assert st.used_hours == H(26) and st.demurrage_hours == 0 and st.margin_hours == H(4)


def test_nor_after_berthing_starts_at_nor():
    st = compute_statement(build([(1, "ALL_FAST", "D1 08:00"), (2, "NOR_TENDERED", "D1 09:00"),
                                  (2, "NOR_RECEIVED", "D1 09:00"), (3, "OPS_COMMENCED", "D1 10:00"),
                                  (4, "OPS_COMPLETED", "D1 20:00"), (5, "HOSES_DISCONNECTED", "D1 21:00")]))
    assert st.laytime_start_at == at("D1 09:00") and st.used_hours == H(12)
    assert {"NOR-AFTER-BERTH", "NOR-ARRIVAL-UNKNOWN"} <= codes(st)


def test_second_nor_after_valid_first_is_ignored_and_noted():
    st = compute_statement(build(STANDARD + [(8, "NOR_TENDERED", "D1 07:00"), (8, "NOR_RECEIVED", "D1 07:00")]))
    assert st.nor_received_at == at("D1 06:00") and st.issue("NOR-MULTIPLE").level == LEVEL_INFO


def test_missing_nor_receipt_uses_tender_time_and_flags_it():
    events = [e for e in STANDARD if e[1] != "NOR_RECEIVED"]
    st = compute_statement(build(events))
    assert st.nor_received_at == at("D1 06:00") and st.issue("NOR-NO-RECEIPT").level == LEVEL_EVIDENCE


# ---------------------------------------------------------------- 이동 (ASB-07-SHIFTING-EXCL, 05 §7-1)

def test_shift_before_start_needs_no_deduction():
    st = compute_statement(build(STANDARD, terms={"laytime_this_port_hours": 10}))
    # 개시(접안 08:00) 전 이동이라 공제할 것이 없다 → 체선 16h (개시 후 이동 공제는 위 notice_expiry 테스트)
    assert st.demurrage_hours == H(16) and not [d for d in st.deductions if d.category == "SHIFTING"]
    line = next(ln for ln in st.lines if ln.label == "(−) 이동 shifting")
    assert line.note == "개시 전 이동이라 이미 미산입" and line.sof_rows == (2, 3)


@pytest.mark.parametrize("contract, amount, dispute", [
    ("DISPUTED", "38000.00", True),   # 체선 19h — 기본은 산입(선주 입장), 대안 17h
    ("YES", "38000.00", False),
    ("NO", "34000.00", False),
])
def test_shift_on_demurrage_follows_contract_field(contract, amount, dispute):
    st = compute_statement(build(ON_DEMURRAGE_SHIFT, terms={"laytime_this_port_hours": 10,
                                                            "shifting_counts_on_demurrage": contract}))
    assert st.demurrage_start_at == at("D1 16:00")
    assert st.amount_usd == Decimal(amount)
    assert ("DISPUTE-SHIFT-ON-DEM" in codes(st)) is dispute
    if dispute:
        issue = st.issue("DISPUTE-SHIFT-ON-DEM")
        assert issue.level == LEVEL_REVIEW and issue.dispute_ref == "05 §7-1" and issue.hours == 2
        assert issue.alternative.amount_usd == Decimal("34000.00") and issue.sof_rows == (2, 3)
    if contract == "NO":
        (d,) = [d for d in st.deductions if d.category == "SHIFTING"]
        assert d.hours == 2 and not d.disputed


# ---------------------------------------------------------------- 하역 중단·반액 (ASB-08-HALF-RATE)

@pytest.mark.parametrize("reason, half_events, amount, half", [
    ("WEATHER", None, "35000.00", 3),                         # 반액 3h + 전액 16h
    ("WEATHER", ["FIRE", "EXPLOSION", "STRIKE", "PLANT_BREAKDOWN"], "38000.00", 0),   # 계약에 폭풍 반액 없음
    ("SHORE_TANK", None, "38000.00", 0),                     # 육상 탱크는 반액 사유 아님
    ("SHORE_EQUIPMENT", None, "35000.00", 3),                # 육상 설비 고장 = 용선주 측 플랜트 고장 [가정]
])
def test_half_rate_only_for_contract_half_rate_causes(reason, half_events, amount, half):
    terms = {"laytime_this_port_hours": 10}
    if half_events is not None:
        terms["half_rate_events"] = half_events
    st = compute_statement(build(with_stop(ON_DEMURRAGE_SHIFT, reason), terms=terms))
    assert st.demurrage_hours == H(19) and st.half_rate_hours == half and st.amount_usd == Decimal(amount)


def test_vessel_fault_stop_in_laytime_is_deducted():
    st = compute_statement(build(with_stop(STANDARD, "SHIP_EQUIPMENT", "D1 12:00", "D1 14:00")))
    (d,) = [d for d in st.deductions if d.category == "VESSEL_FAULT"]
    assert d.hours == 2 and d.rule_id == "ASB-07-VESSEL-FAULT" and d.sof_rows == (10, 11)
    assert st.used_hours == H(24)


def test_vessel_fault_stop_on_demurrage_is_flagged_with_alternative():
    st = compute_statement(build(with_stop(ON_DEMURRAGE_SHIFT, "SHIP_EQUIPMENT"), terms={"laytime_this_port_hours": 10}))
    assert st.demurrage_hours == H(16) and st.amount_usd == Decimal("32000.00")
    issue = st.issue("VESSEL-FAULT-ON-DEM")
    assert issue.level == LEVEL_REVIEW and issue.alternative.amount_usd == Decimal("38000.00")   # 엔진 산출


def test_stop_without_reason_code_is_counted_as_other_and_flagged():
    st = compute_statement(build(STANDARD + [(10, "OPS_STOPPED", "D1 12:00"), (11, "OPS_RESUMED", "D1 13:00")],
                                 terms={"laytime_this_port_hours": 10}))
    assert st.half_rate_hours == 0 and st.issue("STOP-NO-REASON").level == LEVEL_EVIDENCE


def test_storm_during_laytime_is_dispute_3():
    """04 변형 3b: 레이타임 중 폭풍 중단은 산입, 그 때문에 생긴 체선의 반액 여부는 쟁점(엔진 산출 대안)."""
    events = [(1, "ANCHORED", "D1 00:00"), (1, "NOR_TENDERED", "D1 00:00"), (1, "NOR_RECEIVED", "D1 00:00"),
              (2, "ANCHOR_AWEIGH", "D1 01:00"), (3, "ALL_FAST", "D1 02:00"), (4, "OPS_COMMENCED", "D1 03:00"),
              (5, "OPS_STOPPED", "D1 05:00", "WEATHER"), (6, "OPS_RESUMED", "D1 11:00"),
              (7, "OPS_COMPLETED", "D1 23:00"), (8, "HOSES_DISCONNECTED", "D2 00:00")]
    st = compute_statement(build(events, terms={"laytime_this_port_hours": 10}))
    assert st.demurrage_start_at == at("D1 12:00") and st.demurrage_hours == H(12) and st.half_rate_hours == 0
    assert st.amount_usd == Decimal("24000.00")
    issue = st.issue("DISPUTE-LAYTIME-HALF-RATE")
    assert issue.dispute_ref == "05 §7-3" and issue.hours == 6 and issue.sof_rows == (5, 6)
    assert issue.alternative.half_rate_hours == 6 and issue.alternative.amount_usd == Decimal("18000.00")


def test_storm_during_laytime_without_demurrage_is_not_flagged():
    st = compute_statement(build(with_stop(STANDARD, "WEATHER", "D1 12:00", "D1 14:00")))
    assert st.demurrage_hours == 0 and "DISPUTE-LAYTIME-HALF-RATE" not in codes(st)


# ---------------------------------------------------------------- 서류 대기 (05 §7-5)

def test_docs_wait_over_grace_is_dispute_5():
    st = compute_statement(build(STANDARD + [(8, "DOCS_ON_BOARD", "D2 15:00")], terms={"laytime_this_port_hours": 20}))
    assert st.laytime_end_at == at("D2 10:00") and st.amount_usd == Decimal("12000.00")   # 체선 6h
    issue = st.issue("DISPUTE-DOCS-WAIT")
    assert issue.level == LEVEL_REVIEW and issue.hours == 2   # 5h 대기 중 3h 유예 초과분
    assert issue.alternative.demurrage_hours == 8 and issue.alternative.amount_usd == Decimal("16000.00")


def test_short_docs_wait_is_only_shown_as_reference_line():
    st = compute_statement(load_case(CASES_DIR / "TC-01.json"))
    assert "DISPUTE-DOCS-WAIT" not in codes(st)
    line = next(ln for ln in st.lines if ln.label.startswith("(참고) 호스 분리 후 서류 대기"))
    assert line.value == "1h 00m" and line.sof_rows == (9, 10)


# ---------------------------------------------------------------- 펌핑 보증 (RIDER-PUMPING)

def tc04_variant(**changes):
    d = raw("TC-04")
    for key, value in changes.items():
        section, field = key.split("__")
        if value is None:
            d[section].pop(field, None)
        else:
            d[section][field] = value
    return compute_statement(case_from_dict(d))


def test_pumping_excess_is_carved_from_end_of_discharge():
    st = compute_statement(load_case(CASES_DIR / "TC-04.json"))
    (d,) = [d for d in st.deductions if d.category == "PUMPING_EXCESS"]
    assert (d.from_ts, d.to_ts, d.hours) == (at("D2 09:30"), at("D2 16:30"), 7)


def test_pumping_without_log_is_not_deducted():
    d = raw("TC-04")
    d["pumping_log"] = None
    st = compute_statement(case_from_dict(d))
    assert st.used_hours == H(33.5) and st.amount_usd == Decimal("7291.67")
    assert st.issue("PUMPING-NO-LOG").level == LEVEL_EVIDENCE


def test_pumping_with_shore_restriction_is_not_deducted():
    st = tc04_variant(pumping_log__shore_restriction=True)
    assert st.pumping_excess_hours == 0 and st.amount_usd == Decimal("7291.67")
    assert st.issue("PUMPING-SHORE-RESTRICTED").level == LEVEL_INFO


def test_pumping_warranty_met_by_pressure_is_not_deducted():
    st = tc04_variant(pumping_log__avg_manifold_psi=110)
    assert st.pumping_excess_hours == 0 and not {c for c in codes(st) if c.startswith("PUMPING")}


def test_pumping_warranty_ignored_for_loading():
    st = tc04_variant(port_call__operation="LOAD")
    assert st.pumping_excess_hours == 0 and st.amount_usd == Decimal("7291.67")


# ---------------------------------------------------------------- 문서 케이스의 엔진 산출값

def test_tc01_only_low_margin_warning():
    st = compute_statement(load_case(CASES_DIR / "TC-01.json"))
    assert [(i.code, i.level) for i in st.issues] == [("LOW-MARGIN", LEVEL_WARNING)]
    assert st.issue("LOW-MARGIN").hours == H(0.5)


def test_tc01b_night_wait_alternative():
    st = compute_statement(load_case(CASES_DIR / "TC-01b.json"))
    issue = st.issue("DISPUTE-NIGHT-WAIT")
    assert issue.hours == 4 and issue.sof_rows == (3,)
    assert issue.alternative.amount_usd == Decimal("0.00")          # 엔진 산출: 야간 대기 4h를 빼면 사용 35h 30m


def test_tc02_has_no_issues():
    """선석이 06:00에 비었고 그때 움직여도 07:30 접안(주간) → 야간 제한 대기가 아니다."""
    st = compute_statement(load_case(CASES_DIR / "TC-02.json"))
    assert st.issues == ()
    waits = [(e.reason, e.hours) for e in st.ledger if e.kind == "WAIT" and e.phase == "LAYTIME"]
    assert waits == [("BERTH_OCCUPIED", 10), ("OTHER", H(0.5))]


def test_tc03_issues_and_engine_alternative():
    st = compute_statement(load_case(CASES_DIR / "TC-03.json"))
    assert codes(st) == {"DISPUTE-SHIFT-ON-DEM", "DISPUTE-NIGHT-WAIT"}
    night = st.issue("DISPUTE-NIGHT-WAIT")
    assert night.hours == 9 and night.sof_rows == (3, 5)
    assert night.alternative.amount_usd == Decimal("117500.00")    # 04 TC-03 계산표 쟁점 행의 값(선석 전환 0 가정)
    assert night.alternative.demurrage_start_at == at("D3 18:00")


def test_tc04_and_tc05_alternatives_in_cents():
    tc04 = compute_statement(load_case(CASES_DIR / "TC-04.json"))
    tc05 = compute_statement(load_case(CASES_DIR / "TC-05.json"))
    assert tc04.issue("PUMPING-EVIDENCE").alternative.amount_usd == Decimal("7291.67")   # 문서 7,292
    assert tc05.issue("DISPUTE-NOR-WAIVER").alternative.amount_usd == Decimal("3791.67")  # 문서 3,792


def test_tc05b_retender_still_raises_waiver_question():
    st = compute_statement(load_case(CASES_DIR / "TC-05b.json"))
    assert st.start_basis == "RETENDER_NOTICE_EXPIRY" and st.nor_received_at == at("D1 13:00")
    waiver = st.issue("DISPUTE-NOR-WAIVER")
    assert waiver.alternative.laytime_start_at == at("D1 17:00")
    assert waiver.alternative.delta_usd == Decimal("2166.67")    # 엔진 산출: 3,791.67 − 1,625


def test_invalid_nor_without_retender_or_ops_stops():
    events = [(1, "NOR_TENDERED", "D1 05:00"), (1, "NOR_RECEIVED", "D1 05:00"), (2, "ANCHORED", "D1 06:00"),
              (3, "ANCHOR_AWEIGH", "D1 07:00"), (4, "ALL_FAST", "D1 08:00"), (5, "HOSES_DISCONNECTED", "D1 20:00")]
    with pytest.raises(CaseError, match="도착 전 NOR"):
        compute_statement(build(events))


# ---------------------------------------------------------------- 경계

def test_zero_laytime_means_demurrage_from_start():
    st = compute_statement(build(STANDARD, terms={"laytime_this_port_hours": 0}))
    assert st.demurrage_start_at == at("D1 08:00") and st.demurrage_hours == H(26)


def test_laytime_used_exactly_has_no_demurrage():
    st = compute_statement(build(STANDARD, terms={"laytime_this_port_hours": 26}))
    assert st.demurrage_hours == 0 and st.demurrage_start_at is None and st.margin_hours == 0


def test_fractional_laytime_is_exact():
    st = compute_statement(build(STANDARD, terms={"laytime_this_port_hours": "25.75"}))   # 25h 45m
    assert st.demurrage_hours == Fraction(1, 4) and st.amount_usd == Decimal("500.00")
    assert st.demurrage_start_at == at("D2 09:45")


def test_amount_rounds_half_up_to_cents():
    st = compute_statement(build(STANDARD, terms={"laytime_this_port_hours": "25.9", "demurrage_rate_usd_day": 10001}))
    # 0.1h × 10,001 / 24 = 41.670833… → 41.67
    assert st.amount_usd == Decimal("41.67")


def test_night_wait_needs_a_daytime_rule():
    d = raw("TC-01b")
    d["terminal"]["berthing_rules"] = []
    st = compute_statement(case_from_dict(d))
    assert "DISPUTE-NIGHT-WAIT" not in codes(st) and st.amount_usd == Decimal("17500.00")


def test_iso_timestamps_give_same_result():
    d = raw("TC-02")
    for e in d["sof_events"]:
        day, hhmm = e["ts_local"].split()
        e["ts_local"] = f"2026-11-{2 + int(day[1:]):02d}T{hhmm}:00+09:00"
    d["terminal"]["berth_ready_at"] = "2026-11-04T06:00+09:00"
    d.pop("base_date")
    st, ref = compute_statement(case_from_dict(d)), compute_statement(load_case(CASES_DIR / "TC-02.json"))
    assert (st.amount_usd, st.used_hours, st.laytime_start_at) == (ref.amount_usd, ref.used_hours, ref.laytime_start_at)


# ---------------------------------------------------------------- 입력 검증 — 계산하지 않고 멈춘다

@pytest.mark.parametrize("mutate, message", [
    (lambda d: d["sof_events"].append({"row": 99, "event_type": "BERTHED", "ts_local": "D2 08:00"}), "알 수 없는 event_type"),
    (lambda d: d["sof_events"].pop(), "필수 이벤트 HOSES_DISCONNECTED"),
    (lambda d: d["sof_events"].append({"row": 99, "event_type": "ALL_FAST", "ts_local": "D2 10:00"}), "ALL_FAST가 2번"),
    (lambda d: d["sof_events"].append({"row": 99, "event_type": "OPS_STOPPED", "ts_local": "D2 12:00",
                                       "reason_code": "WEATHER"}), "OPS_RESUMED가 없음"),
    (lambda d: d["sof_events"][4].update(ts_local="D2 09:00"), "ANCHOR_AWEIGH\\(행 3\\)가 ALL_FAST\\(행 4\\)보다 늦음"),
    (lambda d: d["sof_events"][0].update(ts_local="2026-11-03T05:00Z"), "KST"),
    (lambda d: d["sof_events"][0].update(reason_code="WEATHER"), "reason_code는 OPS_STOPPED에만"),
    (lambda d: d["contract_terms"].update(demurrage_rate_usd_day=0), "0보다 커야"),
    (lambda d: d["contract_terms"].update(shifting_counts_on_demurrage="MAYBE"), "shifting_counts_on_demurrage"),
    (lambda d: d["terminal"].update(berthing_rules=["ULS-NOPE"]), "등록되지 않은 rule_id: ULS-NOPE"),
])
def test_invalid_input_is_rejected(mutate, message):
    d = copy.deepcopy(raw("TC-02"))
    mutate(d)
    with pytest.raises(CaseError, match=message):
        compute_statement(case_from_dict(d))


# ---------------------------------------------------------------- 불변식·재현성

def all_statements():
    """문서 케이스 전부와 각 쟁점의 대안 계산."""
    for path in sorted(CASES_DIR.glob("*.json")):
        st = compute_statement(load_case(path))
        yield pytest.param(st, id=path.stem)
        for alt in st.alt_calculations:
            policy = Policy(**{**st.policy.__dict__, **alt.policy})
            alt_st = compute_statement(load_case(path), policy, with_alternatives=False)
            yield pytest.param(alt_st, id=f"{path.stem}/{alt.code}")


@pytest.mark.parametrize("st", list(all_statements()))
def test_invariants(st):
    deducted = sum((d.hours for d in st.deductions), Fraction(0))
    assert st.used_hours == st.elapsed_hours - deducted
    assert st.demurrage_hours == max(Fraction(0), st.used_hours - st.allowed_hours)
    assert st.demurrage_hours == st.full_rate_hours + st.half_rate_hours
    counted = [e for e in st.ledger if e.phase in ("LAYTIME", "DEMURRAGE")]
    assert sum((e.hours for e in counted), Fraction(0)) == st.elapsed_hours
    assert counted[0].from_ts == st.laytime_start_at and counted[-1].to_ts == st.laytime_end_at
    assert all(a.to_ts == b.from_ts for a, b in zip(st.ledger, st.ledger[1:]))   # 원장은 빈틈없이 이어진다
    rate = Fraction(st.rate_usd_day)
    exact = st.full_rate_hours * rate / 24 + st.half_rate_hours * rate / 48
    assert abs(Fraction(st.amount_usd) - exact) <= Fraction(1, 200)


def test_rule_ids_are_registered_and_output_is_deterministic_json():
    for path in sorted(CASES_DIR.glob("*.json")):
        a = compute_statement(load_case(path)).to_dict()
        b = compute_statement(load_case(path)).to_dict()
        assert a == b and json.loads(json.dumps(a, ensure_ascii=False)) == a
        used = {r for ln in a["lines"] for r in ln["rule_ids"]} | {r for i in a["issues"] for r in i["rule_ids"]}
        assert used <= set(rules.REGISTRY)


def test_statement_uses_06_field_names():
    d = compute_statement(load_case(CASES_DIR / "TC-02.json")).to_dict()
    for field in ("nor_received_at", "notice_expiry_at", "all_fast_at", "laytime_start_at", "start_rule",
                  "laytime_end_at", "end_rule", "deductions", "used_hours", "allowed_hours", "demurrage_hours",
                  "demurrage_start_at", "half_rate_hours", "amount_usd", "alt_calculations", "issues",
                  "version", "computed_at", "rules_version"):
        assert field in d, field
    (ded,) = d["deductions"]
    assert set(ded) >= {"from_ts", "to_ts", "hours", "category", "rule_id", "evidence_ref", "disputed"}
    assert (ded["category"], ded["hours"], ded["rule_id"], ded["evidence_ref"]) == \
        ("SHIFTING", 1.5, "ASB-07-SHIFTING-EXCL", "SOF 3, 4행")


def test_cli_summary_and_json(capsys):
    assert main([]) == 0
    out = capsys.readouterr().out
    assert "TC-03" in out and "USD 187,500.00" in out
    assert main([str(CASES_DIR / "TC-02.json"), "--json"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["amount_usd"] == 6875 and doc["computed_at"]


def test_cli_reports_input_errors(tmp_path, capsys):
    bad = raw("TC-02")
    bad["sof_events"].pop()
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
    assert main([str(path)]) == 2
    assert "HOSES_DISCONNECTED" in capsys.readouterr().err
