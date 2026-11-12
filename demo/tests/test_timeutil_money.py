"""NFR-06 — KST·분 단위 시각, 센트 정수 금액, 자정·월말 경계."""
from fractions import Fraction

from demurrage.domain.money import demurrage_cents, fmt_usd
from demurrage.domain.timeutil import DAY, day_start, fmt, fmt_iso, hours_to_min, parse_ts


def test_month_end_and_midnight_boundaries():
    t = parse_ts("2026-11-30 23:30")
    assert fmt_iso(t + 60) == "2026-12-01 00:30"
    assert day_start(parse_ts("2026-12-01 00:00")) == parse_ts("2026-12-01 00:00")
    assert fmt(parse_ts("2026-12-31 23:59") + 1) == "01/01 00:00"
    assert parse_ts("2026-11-10", end_of_day=True) == parse_ts("2026-11-10 23:59")
    assert DAY == 1440


def test_hours_to_minutes_and_cents_rounding():
    assert hours_to_min(1.5) == 90 and hours_to_min("2.5") == 150
    assert demurrage_cents(Fraction(765), 24000) == 1275000          # 12.75h × 1,000/h
    assert demurrage_cents(Fraction(1, 2), 1000) == 35                 # 0.3472… 센트 → 반올림
    assert demurrage_cents(-30, 24000) == 0
    assert fmt_usd(1275050) == "$12,751" and fmt_usd(1275050, exact=True) == "$12,750.50"


def test_total_equals_sum_of_vessels(s5_run):
    for s in [s5_run["baseline"]] + s5_run["candidates"]:
        assert s["total_cents"] == sum(v["amount_cents"] for v in s["vessels"])
        if "delta_sum_cents" in s:
            assert s["delta_sum_cents"] == -s["savings_cents"]
