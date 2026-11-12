"""CSV 체선료 계산기 검증.

1. 파싱: 시각만 있는 행의 날짜 추정, 중복 기록 무시
2. 손계산: 항차 몇 건을 손으로 따라간 값과 일치
3. 골든: docs/domain/04 TC-02 (공제·체선 걷기)
4. 교차 검증: 같은 이벤트를 clock/ 엔진(독립 구현)에 넣어 개시·체선 시간·금액이 분 단위로 같은지
"""
from datetime import datetime
from pathlib import Path

import pytest

import laytime_csv as lc

DATA = Path(__file__).resolve().parents[1] / "data" / "vessel_journeys.csv"
TERMS = lc.Terms()


@pytest.fixture(scope="module")
def voyages():
    return {v.jid: v for v in lc.build_voyages(lc.load_rows(DATA))}


@pytest.fixture(scope="module")
def calls(voyages):
    return {j: lc.extract_call(v) for j, v in voyages.items()}


@pytest.fixture(scope="module")
def results():
    res, _ = lc.analyze(DATA, TERMS)
    return {r.jid: r for r in res}


def dt(s):
    return datetime.strptime(s, "%Y-%m-%d %H:%M")


# ---------------------------------------------------------------- 1. 파싱

def test_all_23_voyages_are_calculable(voyages, results):
    assert len(voyages) == 23 and len(results) == 23


def test_time_only_rows_get_dates(voyages):
    """J001: NOR 승인 '13:45'와 마지막 선적 완료 '00:45'는 일시가 비어 시각만 있다."""
    inferred = {(e.kind, e.t) for e in voyages["J001"].events if e.inferred}
    assert inferred == {("NOR_A", dt("2025-01-10 13:45")), ("OPS_E", dt("2025-01-11 00:45"))}


def test_duplicate_time_only_rows_are_ignored(voyages):
    """J022의 입항 '18:00'·접안 '22:24'·양하 시작 '01:15'는 이미 시각이 있는 이벤트의 중복 기록."""
    assert not any(e.inferred for e in voyages["J022"].events)


def test_only_j001_needs_inferred_dates(voyages):
    assert [j for j, v in voyages.items() if any(e.inferred for e in v.events)] == ["J001"]


def test_all_fast_is_last_berthing_before_first_operation(calls):
    assert calls["J006"].allfast == dt("2025-04-25 21:05")     # 일반부두 07 접안(04-23)이 아니라 하역 선석
    assert calls["J020"].allfast == dt("2025-09-15 08:09")     # 하역 개시 뒤 18:24 접안 기록은 쓰지 않음
    assert calls["J022"].allfast == dt("2025-09-29 22:24")


def test_nor_early_flags(calls):
    early = sorted(j for j, c in calls.items() if c.nor_early)
    assert early == ["J003", "J004", "J005", "J009", "J012", "J013", "J016", "J019"]


def test_quantity_follows_operation_berth(calls):
    assert calls["J022"].qty_t == pytest.approx(6673.07 + 5328.86 + 1504.17)
    assert calls["J003"].qty_t == pytest.approx(2368.486)      # 가스부두 UCO 2,947t는 제외


# ---------------------------------------------------------------- 2. 손계산

def test_j002_long_anchorage_wait_counts(results):
    r = results["J002"]       # NOR 01-20 12:40 + 6h → 01-28 08:55, 이동은 이미 체선 중이라 산입
    assert r.laytime_start == dt("2025-01-20 18:40")
    assert r.elapsed_h == pytest.approx(182.25) and r.deducted_h == 0
    assert r.demurrage_h == pytest.approx(158.25)
    assert r.amount_usd == pytest.approx(158.25 * 26000 / 24)


def test_j004_shifting_is_deducted_inside_laytime(results):
    r = results["J004"]       # 개시 13:00, 양묘 23:00은 허용 24h 안 → 이동 70분 공제
    assert r.deducted_h == pytest.approx(70 / 60)
    assert r.used_h == pytest.approx(23 + 40 / 60)
    assert r.demurrage_h == 0 and r.margin_h == pytest.approx(20 / 60)
    assert "LOW-MARGIN" in r.flags


def test_j011_berthed_before_notice_expires(results):
    r = results["J011"]       # NOR 17:45 + 6h = 23:45 이전에 접안(20:25) → 접안 완료부터
    assert (r.start_rule, r.laytime_start) == ("ALL_FAST", dt("2025-05-21 20:25"))


def test_j022_interruption_alternative(results):
    r = results["J022"]
    assert r.demurrage_h == pytest.approx(74 + 26 / 60 - 24)
    gap_h = (dt("2025-10-02 20:40") - dt("2025-10-01 12:55")).total_seconds() / 3600
    assert r.alt["no_gap"]["demurrage_h"] == pytest.approx(r.demurrage_h - gap_h)


def test_j005_strict_nor_alternative(calls):
    r = lc.compute(calls["J005"], TERMS, nor_validity="strict")
    assert r.laytime_start == dt("2025-03-25 09:00") and r.demurrage_h == 0


def test_accepted_basis_never_exceeds_tender_basis(results):
    for r in results.values():
        assert r.alt["accept_basis"]["demurrage_h"] <= r.demurrage_h + 1e-9


def test_rate_scales_amount_linearly(calls):
    a = lc.compute(calls["J012"], lc.Terms(rate_usd_day=26000))
    b = lc.compute(calls["J012"], lc.Terms(rate_usd_day=52000))
    assert b.amount_usd == pytest.approx(2 * a.amount_usd) and a.demurrage_h == b.demurrage_h


# ---------------------------------------------------------------- 3. 골든 (docs/domain/04 TC-02)

def test_golden_tc02_walk():
    """TC-02: 개시 D1 20:00, 종료 D3 06:30, 이동 D2 06:30~08:00 공제 1.5h, 허용 30h → 체선 3h, 55,000/일 → 6,875."""
    start, end = dt("2026-11-03 20:00"), dt("2026-11-05 06:30")
    shifts = [(dt("2026-11-04 06:30"), dt("2026-11-04 08:00"))]
    used, ded, dem, expiry = lc.walk(start, end, 30 * 60, shifts, [], True)
    assert (used / 60, ded / 60, dem / 60) == (33, 1.5, 3)
    assert round(dem / 60 * 55000 / 24, 2) == 6875.00
    assert expiry == dt("2026-11-05 03:30")        # 레이타임 만료 = 개시 + 30h + 공제 1.5h


def test_walk_shift_after_expiry_counts_by_default_and_deducts_on_request():
    start, end = dt("2026-01-01 00:00"), dt("2026-01-03 00:00")
    shifts = [(dt("2026-01-02 06:00"), dt("2026-01-02 07:00"))]          # 개시 30h 뒤, 허용 24h는 이미 끝남
    assert lc.walk(start, end, 24 * 60, shifts, [], True)[2] == 24 * 60
    assert lc.walk(start, end, 24 * 60, shifts, [], False)[2] == 23 * 60


# ---------------------------------------------------------------- 4. 엔진 교차 검증

def engine_case(call, terms, *, with_receipt=False):
    def ev(row, typ, t):
        return {"row": row, "event_type": typ, "ts_local": t.isoformat(timespec="minutes")}
    seq = []
    if call.anchor_first:
        seq.append(("ANCHORED", call.anchor_first))
    seq.append(("NOR_TENDERED", call.nor_t))
    if with_receipt and call.nor_a:
        seq.append(("NOR_RECEIVED", call.nor_a))
    if call.shifts:
        seq.append(("ANCHOR_AWEIGH", call.shifts[0][0]))
    seq += [("ALL_FAST", call.allfast), ("OPS_COMMENCED", call.ops_start), ("OPS_COMPLETED", call.ops_end),
            ("HOSES_DISCONNECTED", call.ops_end)]
    return {
        "case_id": call.jid,
        "port_call": {"call_id": call.jid, "operation": call.operation},
        "contract_terms": {"laytime_this_port_hours": terms.laytime_hours, "notice_hours": terms.notice_hours,
                           "demurrage_rate_usd_day": terms.rate_usd_day, "shifting_counts_on_demurrage": "DISPUTED"},
        "sof_events": [ev(i + 1, t, ts) for i, (t, ts) in enumerate(seq)],
    }


def run_engine(call, terms, policy_kwargs=None, **kw):
    from laytime import Policy, case_from_dict, compute_statement
    return compute_statement(case_from_dict(engine_case(call, terms, **kw)), Policy(**(policy_kwargs or {})),
                             with_alternatives=False)


ENGINE_IDS = [f"J{n:03d}" for n in range(1, 24) if n != 22]     # J022는 재접안이라 엔진이 지원하지 않음


@pytest.mark.parametrize("jid", ENGINE_IDS)
def test_matches_clock_engine_lenient_nor(calls, jid):
    """우리 기본 계산(제출 시각 기준, NOR 유효 가정) = 엔진의 '무효 NOR 치유(waiver)' 대안과 같다."""
    c = calls[jid]
    st = run_engine(c, TERMS, {"invalid_nor_waived": True})
    r = lc.compute(c, TERMS)
    assert st.laytime_start_at == r.laytime_start
    assert float(st.used_hours) == pytest.approx(r.used_h, abs=1e-6)
    assert float(st.demurrage_hours) == pytest.approx(r.demurrage_h, abs=1e-6)
    assert float(st.amount_usd) == pytest.approx(r.amount_usd, abs=0.01)


@pytest.mark.parametrize("jid", ENGINE_IDS)
def test_matches_clock_engine_strict_nor(calls, jid):
    """엄격한 NOR 해석(투묘 전 제출은 무효 → 하역 개시부터) = 엔진 기본 정책."""
    c = calls[jid]
    st = run_engine(c, TERMS)
    r = lc.compute(c, TERMS, nor_validity="strict")
    assert st.laytime_start_at == r.laytime_start
    assert float(st.demurrage_hours) == pytest.approx(r.demurrage_h, abs=1e-6)
    assert float(st.amount_usd) == pytest.approx(r.amount_usd, abs=0.01)


@pytest.mark.parametrize("jid", ENGINE_IDS)
def test_matches_clock_engine_accepted_basis(calls, jid):
    """NOR 승인 시각을 수령으로 본 계산 = 엔진에 NOR_RECEIVED(승인 시각)를 넣은 결과."""
    c = calls[jid]
    st = run_engine(c, TERMS, {"invalid_nor_waived": True}, with_receipt=True)
    r = lc.compute(c, TERMS, nor_basis="accepted")
    assert st.laytime_start_at == r.laytime_start
    assert float(st.demurrage_hours) == pytest.approx(r.demurrage_h, abs=1e-6)


@pytest.mark.parametrize("laytime,rate", [(12, 10_000), (36, 120_000), (48, 26_000)])
def test_matches_clock_engine_other_terms(calls, laytime, rate):
    terms = lc.Terms(laytime_hours=laytime, rate_usd_day=rate)
    for jid in ENGINE_IDS:
        st = run_engine(calls[jid], terms, {"invalid_nor_waived": True})
        r = lc.compute(calls[jid], terms)
        assert float(st.demurrage_hours) == pytest.approx(r.demurrage_h, abs=1e-6), jid
        assert float(st.amount_usd) == pytest.approx(r.amount_usd, abs=0.01), jid
