"""SC-01 — 순서를 바꾸면 체선료가 줄어드는 손계산 정답 (docs/requirements/09-first-steps.md).

부두 하나를 두 배가 나눠 쓴다. 도착 순서(A)와 Y 먼저(B)에서 선박별 체선료를 손으로 계산해 두었고,
엔진이 같은 값을 내는지 매번 확인한다. 사례 입력은 docs/requirements/answers/ 에 있다.
(cases/ 폴더에 넣지 않은 것은 test_golden_tc.py가 그 폴더의 TC 7개만 정답 세트로 보기 때문이다.)
"""
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction
from pathlib import Path

import pytest

from laytime import compute_statement, load_case
from laytime.model import parse_local_ts

ANSWERS = Path(__file__).resolve().parents[2] / "docs" / "requirements" / "answers"
CASES = sorted(ANSWERS.glob("SC-01-*.json"), key=lambda p: p.stem)
ORDER_TOTAL = {"A": Decimal("52000"), "B": Decimal("6000")}  # 순서별 총 체선료 (손계산)


def whole_usd(amount: Decimal) -> Decimal:
    return amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


@pytest.fixture(scope="module", params=CASES, ids=lambda p: p.stem)
def run(request):
    case = load_case(request.param)
    return case, compute_statement(case), case.raw["expected"]


def test_cases_present():
    assert [p.stem for p in CASES] == ["SC-01-A-X", "SC-01-A-Y", "SC-01-B-X", "SC-01-B-Y"]


def test_ship_results(run):
    case, st, exp = run
    for key in ("laytime_start_at", "laytime_end_at"):
        assert getattr(st, key) == parse_local_ts(exp[key], case.base_date), f"{case.case_id} {key}"
    for key in ("elapsed_hours", "used_hours", "demurrage_hours"):
        assert getattr(st, key) == Fraction(exp[key]), f"{case.case_id} {key}"
    assert whole_usd(st.amount_usd) == Decimal(exp["amount_usd"]), case.case_id


def test_order_totals_and_saving():
    totals = {"A": Decimal(0), "B": Decimal(0)}
    for path in CASES:
        totals[path.stem.split("-")[2]] += whole_usd(compute_statement(load_case(path)).amount_usd)
    assert totals == ORDER_TOTAL
    assert totals["A"] - totals["B"] == Decimal("46000")
