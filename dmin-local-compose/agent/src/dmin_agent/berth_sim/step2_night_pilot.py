"""ETB 산정 ② 야간 도선 제한 시간 충족 (멘토링 장표 08p).

장표 원문
  *야간 도선 제한
   (GRT 7.5만톤 이상) OR (3만톤 이하 AND 수입선 AND Draft >= 10.5)
   선박의 ETA >= Last POB 시간인 경우
   GRT 3만톤 이상인 경우 ETA+Direction or 이전 선박의 ETU+Switching 시간 >= 새벽 2시 AND < 오전 8시
  *LAST POB 시간(마지막 도선사 승선 가능 시간)
   GRT 3만 이상 5만 이하 일몰 – 1.5시간 / GRT 5만 이상 일몰 – 2시간 / GRT 3만 이하는 야간 도선 제한X
  → ETB = 다가오는 오전 08시

구현 해석 (현업 확인 필요, 요구사항 문서 12장 Q1)
1) 대상 선박: GRT >= 7.5만 OR (GRT >= 3만 AND 수입선 AND Draft >= 10.5)
   장표의 "3만톤 이하"를 그대로 쓰면 같은 장표의 "GRT 3만 이하는 야간 도선 제한X"와 충돌하고
   Last POB 값도 없어 판정이 불가능하므로 "3만톤 이상"으로 해석했다.
2) Last POB: 3만 <= GRT <= 5만 → 일몰 - 1.5h, GRT > 5만 → 일몰 - 2h (5만은 앞 구간).
3) 대상 선박이 아래 둘 중 하나에 해당하면 ETB를 다가오는 08:00으로 미룬다.
   (a) ETA >= ETA 당일 Last POB → ETA 다음 날 08:00 (후보 ETB가 이미 그 이후면 그대로)
   (b) 후보 ETB(① 결과 = ETA+Direction 또는 이전 선박 ETU+Switching)가 02:00 이상 08:00 미만
       → 같은 날 08:00
"""

from collections.abc import Callable, Sequence
from datetime import date, datetime, time, timedelta

from .models import Vessel
from .step1_prev_fix import EtbAdjuster, Step1Result
from .sun import ulsan_sunset

GRT_ALWAYS = 75_000  # 이 이상은 무조건 대상
GRT_MIN = 30_000  # 이 미만은 야간 도선 제한 없음
GRT_POB_2H = 50_000  # 이 초과는 Last POB = 일몰 - 2h
DRAFT_MIN = 10.5  # 수입선 Draft 기준
POB_BEFORE_SUNSET_SMALL = timedelta(hours=1.5)
POB_BEFORE_SUNSET_LARGE = timedelta(hours=2)
NIGHT_START = time(2, 0)
RELEASE = time(8, 0)

SunsetFn = Callable[[date], datetime]


def is_restricted(v: Vessel) -> bool | None:
    """야간 도선 제한 대상이면 True. 판정에 필요한 제원이 없으면 None."""
    if v.grt is None:
        return None
    if v.grt >= GRT_ALWAYS:
        return True
    if v.grt < GRT_MIN or not v.is_import:
        return False
    if v.draft is None:
        return None
    return v.draft >= DRAFT_MIN


def last_pob(v: Vessel, day: date, sunset: SunsetFn = ulsan_sunset) -> datetime:
    """대상 선박의 해당 날짜 Last POB."""
    before = POB_BEFORE_SUNSET_SMALL if v.grt <= GRT_POB_2H else POB_BEFORE_SUNSET_LARGE
    return sunset(day) - before


def make_night_pilot_adjuster(sunset: SunsetFn = ulsan_sunset) -> EtbAdjuster:
    def adjust(v: Vessel, etb: datetime, committed: Sequence[Step1Result] = ()) -> tuple[datetime, str | None]:
        restricted = is_restricted(v)
        if restricted is None:
            return etb, "야간 도선 미판정: GRT/Draft 제원 없음"
        if not restricted:
            return etb, None

        pob = last_pob(v, v.eta.date(), sunset)
        if v.eta >= pob:
            release = datetime.combine(v.eta.date() + timedelta(days=1), RELEASE)
            if etb < release:
                return release, (
                    f"야간 도선 제한: ETA {v.eta:%m/%d %H:%M} >= Last POB {pob:%m/%d %H:%M}"
                    f" → ETB {release:%m/%d %H:%M}"
                )
            # 다음 날 08시 이후라도 그날 02~08시에 걸리면 아래에서 다시 막는다

        if NIGHT_START <= etb.time() < RELEASE:
            release = datetime.combine(etb.date(), RELEASE)
            return release, f"야간 도선 제한: 후보 ETB {etb:%m/%d %H:%M}이 02~08시 → ETB {release:%m/%d %H:%M}"
        return etb, None

    return adjust
