"""표시용 서식. 계산에는 쓰지 않는다."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from fractions import Fraction


def fmt_hours(hours: Fraction | None) -> str:
    """Fraction 시간 → '40h 30m'. 분 단위로 나누어떨어지지 않으면 반올림하고 '≈'를 붙인다."""
    if hours is None:
        return "—"
    minutes = hours * 60
    sign = "−" if minutes < 0 else ""
    minutes = abs(minutes)
    whole = int(minutes + Fraction(1, 2)) if minutes.denominator != 1 else int(minutes)
    approx = "≈" if minutes.denominator != 1 else ""
    return f"{approx}{sign}{whole // 60}h {whole % 60:02d}m"


def fmt_num(hours: Fraction) -> str:
    """계산식에 넣을 시간 숫자. 34.5처럼 짧게."""
    if hours.denominator == 1:
        return str(hours.numerator)
    return f"{float(hours):.6g}"


def fmt_dt(dt: datetime | None, base_date: date | None = None) -> str:
    """base_date가 있으면 문서와 같은 'D1 08:00' 표기, 없으면 'YYYY-MM-DD HH:MM'."""
    if dt is None:
        return "—"
    clock = dt.strftime("%H:%M:%S" if dt.second or dt.microsecond else "%H:%M")
    if base_date is None:
        return f"{dt:%Y-%m-%d} {clock}"
    return f"D{(dt.date() - base_date).days + 1} {clock}"


def fmt_usd(amount: Decimal | None) -> str:
    return "—" if amount is None else f"USD {amount:,.2f}"


def fmt_rows(rows: tuple[int, ...]) -> str:
    """(3, 5, 6, 7, 8) → '3, 5–8'."""
    if not rows:
        return "—"
    vals = sorted(set(rows))
    runs, start, prev = [], vals[0], vals[0]
    for v in vals[1:] + [None]:
        if v is not None and v == prev + 1:
            prev = v
            continue
        runs.append(str(start) if start == prev else f"{start}–{prev}" if prev - start > 1 else f"{start}, {prev}")
        if v is not None:
            start = prev = v
    return ", ".join(runs)
