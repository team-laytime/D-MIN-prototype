"""금액 (NFR-06: USD 센트 정수로 계산하고, 표시할 때만 반올림).

체선료 = 체선 시간 × 하루 체선료 ÷ 24  (PPT 11쪽, 규칙 DEM-03)
       = 체선 분 × 하루 체선료 × 100 ÷ 1440  (센트)
선박마다 센트로 반올림(ROUND_HALF_UP)한 뒤 더하므로, 합계와 선박별 금액의 합은 늘 같다(차이 0).
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction


def round_half_up(q: Fraction) -> int:
    d = Decimal(q.numerator) / Decimal(q.denominator)
    return int(d.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def demurrage_cents(demurrage_min, rate_usd_day: int) -> int:
    """체선 분(정수·Fraction) × 하루 요율 → 센트 정수."""
    q = Fraction(demurrage_min) * rate_usd_day * 100 / 1440
    if q <= 0:
        return 0
    return round_half_up(q)


def fmt_usd(cents: int, *, exact: bool = False) -> str:
    """$52,000 / $12,750.50. exact=False면 달러로 반올림해 보여 준다."""
    if cents is None:
        return "-"
    neg = cents < 0
    c = abs(int(cents))
    if exact:
        s = f"${c // 100:,}.{c % 100:02d}"
    else:
        s = f"${round_half_up(Fraction(c, 100)):,}"
    return f"-{s}" if neg else s


def usd(cents: int) -> float:
    return cents / 100
