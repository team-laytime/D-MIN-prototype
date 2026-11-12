"""시각·기간 처리 (NFR-06: 모든 시각은 KST, 분 단위로 계산하고 'MM/DD HH:mm'으로 표시).

내부 표현은 '기준 시각(2026-01-01 00:00 KST)부터 지난 분' 정수다.
- 정수라서 같은 입력이면 같은 결과가 나오고(부동소수점 오차 없음),
- 자정 = 1440의 배수라서 '그날 00:00', '다가오는 08:00' 같은 계산이 나눗셈 한 번으로 끝난다.
체선 시간처럼 반(1/2)이 생기는 값만 Fraction으로 다룬다.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction

EPOCH = datetime(2026, 1, 1, 0, 0)  # KST, 시각 0
HOUR = 60
DAY = 24 * HOUR


class TimeFormatError(ValueError):
    pass


def parse_ts(value, *, end_of_day: bool = False) -> int:
    """'2026-11-10 08:00' / '2026-11-10T08:00' / '2026-11-10' (KST) → 분 정수.

    날짜만 오면 00:00, end_of_day=True면 23:59로 읽는다(Laycan To 같은 '그날 끝까지').
    +09:00이 아닌 시간대 표기는 받지 않는다(변환은 입력 단계의 몫).
    """
    if isinstance(value, int):
        return value
    if value is None:
        raise TimeFormatError("시각이 비어 있음")
    s = str(value).strip().replace("T", " ")
    if s.endswith("+09:00"):
        s = s[:-6]
    elif "+" in s[10:] or s.endswith("Z"):
        raise TimeFormatError(f"KST(+09:00)만 받는다: {value}")
    try:
        if len(s) == 10:
            dt = datetime.strptime(s, "%Y-%m-%d")
            if end_of_day:
                dt = dt + timedelta(hours=23, minutes=59)
        else:
            dt = datetime.strptime(s[:16], "%Y-%m-%d %H:%M")
    except ValueError as exc:  # pragma: no cover - 메시지만 바꿈
        raise TimeFormatError(f"시각 형식 오류: {value!r} (예: 2026-11-10 08:00)") from exc
    delta = dt - EPOCH
    return delta.days * DAY + delta.seconds // 60


def to_datetime(m) -> datetime:
    return EPOCH + timedelta(minutes=float(m))


def fmt(m) -> str:
    """화면 표시용 'MM/DD HH:mm'. 분 아래(Fraction)는 표시하지 않는다."""
    if m is None:
        return "-"
    return to_datetime(int(m)).strftime("%m/%d %H:%M")


def fmt_iso(m) -> str:
    if m is None:
        return None
    return to_datetime(int(m)).strftime("%Y-%m-%d %H:%M")


def day_start(m: int) -> int:
    """그날 00:00 (EPOCH가 자정이라 1440으로 내림하면 된다)."""
    return m - (m % DAY)


def at_hour(day0: int, hour) -> int:
    """day0(그날 00:00)에서 hour시(소수 가능) 뒤."""
    return day0 + hours_to_min(hour)


def minute_of_day(m: int) -> int:
    return m % DAY


def date_of(m: int) -> date:
    return to_datetime(day_start(m)).date()


def date_key(m: int) -> str:
    return date_of(m).isoformat()


def from_date(d: date) -> int:
    return parse_ts(d.isoformat())


def hours_to_min(h) -> int:
    """시간(1.5, '2.5', Fraction)을 분 정수로. 분 아래는 반올림(ROUND_HALF_UP)."""
    if h is None:
        return 0
    q = h * 60 if isinstance(h, Fraction) else Fraction(str(h)) * 60
    if q.denominator == 1:
        return int(q)
    return int((Decimal(q.numerator) / Decimal(q.denominator)).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def min_to_hours(m) -> Fraction:
    return Fraction(m) / 60


def fmt_hours(m) -> str:
    """분(정수 또는 Fraction) → '13.5시간', '0시간', '12.75시간'."""
    h = Fraction(m) / 60
    if h.denominator == 1:
        return f"{h.numerator}시간"
    d = (Decimal(h.numerator) / Decimal(h.denominator)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    s = format(d.normalize(), "f")
    return f"{s}시간"


def hours_str(m) -> str:
    """분 → 'H:MM' (예: 810 → '13:30', 765/1 → '12:45', 반분은 ':30초' 없이 내림 표시)."""
    total = Fraction(m)
    neg = total < 0
    total = abs(total)
    hh = int(total // 60)
    mm = total - hh * 60
    mm_i = int(mm)
    sec = "" if mm == mm_i else "+30초"
    return f"{'-' if neg else ''}{hh}:{mm_i:02d}{sec}"


def overlap(a0, a1, b0, b1):
    """두 구간 [a0, a1), [b0, b1)의 겹친 길이."""
    lo = max(a0, b0)
    hi = min(a1, b1)
    return hi - lo if hi > lo else 0
