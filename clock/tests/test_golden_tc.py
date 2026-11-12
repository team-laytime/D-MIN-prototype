"""Golden Set — docs/domain/04 TC-01~05 정답 재현.

cases/*.json의 expected에는 문서에 적힌 값만 넣었다(doc_ref에 출처). 엔진이 추가로 계산한 대안 금액·
추가 쟁점은 test_engine.py에서 따로 검증한다. 금액은 문서가 달러 단위로 반올림해 적었으므로
엔진의 센트 값을 달러로 반올림(ROUND_HALF_UP)해 비교한다(예: 7,291.67 → 7,292).
"""
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction
from pathlib import Path

import pytest

from laytime import LEVEL_REVIEW, compute_statement, load_case
from laytime.model import parse_local_ts

CASES = sorted((Path(__file__).resolve().parent.parent / "cases").glob("*.json"), key=lambda p: p.stem)
DOC_TCS = {"TC-01", "TC-01b", "TC-02", "TC-03", "TC-04", "TC-05", "TC-05b"}
TIME_KEYS = ("notice_expiry_at", "laytime_start_at", "demurrage_start_at", "laytime_end_at")
HOUR_KEYS = ("elapsed_hours", "used_hours", "demurrage_hours", "full_rate_hours", "half_rate_hours",
             "pumping_excess_hours", "margin_hours")


def whole_usd(amount: Decimal) -> Decimal:
    return amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


@pytest.fixture(scope="module", params=CASES, ids=lambda p: p.stem)
def run(request):
    case = load_case(request.param)
    return case, compute_statement(case), case.raw["expected"]


def test_all_doc_test_cases_present():
    assert DOC_TCS <= {p.stem for p in CASES}


def test_times(run):
    case, st, exp = run
    for key in TIME_KEYS:
        if key in exp:
            assert getattr(st, key) == parse_local_ts(exp[key], case.base_date), f"{case.case_id} {key}"
    if Fraction(exp["demurrage_hours"]) == 0:
        assert st.demurrage_start_at is None


def test_hours(run):
    case, st, exp = run
    for key in HOUR_KEYS:
        if key in exp:
            assert getattr(st, key) == Fraction(exp[key]), f"{case.case_id} {key}"
    for category, hours in exp.get("deduction_hours", {}).items():
        got = sum((d.hours for d in st.deductions if d.category == category), Fraction(0))
        assert got == Fraction(hours), f"{case.case_id} 공제 {category}"


def test_amount(run):
    case, st, exp = run
    assert whole_usd(st.amount_usd) == Decimal(exp["amount_usd"]), case.case_id


def test_flags(run):
    case, st, exp = run
    codes = [i.code for i in st.issues]
    for code in exp.get("issues", []):
        assert code in codes, f"{case.case_id}: {code} 플래그 없음 (있는 것: {codes})"
    if exp.get("no_review_issues"):
        assert [i.code for i in st.issues if i.level == LEVEL_REVIEW] == [], case.case_id


def test_alternatives(run):
    case, st, exp = run
    for code, want in exp.get("alternatives", {}).items():
        issue = st.issue(code)
        assert issue is not None and issue.alternative is not None, f"{case.case_id}: {code} 대안 계산 없음"
        alt = issue.alternative
        assert whole_usd(alt.amount_usd) == Decimal(want["amount_usd"]), f"{case.case_id} {code} 금액"
        for key in ("demurrage_hours", "used_hours"):
            if key in want:
                assert getattr(alt, key) == Fraction(want[key]), f"{case.case_id} {code} {key}"
        if "laytime_start_at" in want:
            assert alt.laytime_start_at == parse_local_ts(want["laytime_start_at"], case.base_date)


def test_every_line_has_rule_and_evidence(run):
    """계산서 줄마다 룰 ID, 그리고 SOF 행(없으면 계약 필드 등 source)이 붙는다."""
    case, st, _ = run
    for ln in st.lines:
        assert ln.rule_ids, f"{case.case_id} '{ln.label}' 룰 ID 없음"
        assert ln.sof_rows or ln.source, f"{case.case_id} '{ln.label}' 근거 없음"
    for e in st.ledger:
        assert e.rule_ids and e.sof_rows, f"{case.case_id} 원장 {e.label} 근거 없음"
    for i in st.issues:
        assert i.rule_ids, f"{case.case_id} {i.code} 룰 ID 없음"


def test_disputes_are_not_auto_decided(run):
    """05 §7 쟁점은 '담당자 확인 필요'로 올리고 반대 입장의 대안 계산을 붙인다."""
    case, st, _ = run
    for i in st.issues:
        if i.dispute_ref and i.dispute_ref.startswith("05 §7"):
            assert i.level == LEVEL_REVIEW, f"{case.case_id} {i.code}"
            assert i.alternative is not None, f"{case.case_id} {i.code} 대안 계산 없음"


def test_doc_rows_moved_out_of_events_are_not_inputs(run):
    """문서 SOF 표의 계산 결과 행(통지시간 만료·체선 개시 등)은 입력 이벤트에 섞지 않는다."""
    case, _, _ = run
    event_rows = {e.row for e in case.sof_events}
    for moved in case.raw.get("doc_rows_not_events", []):
        assert moved["row"] not in event_rows, f"{case.case_id} 행 {moved['row']}"
