"""기상(풍속 예보) 제약: 하역작업 중단 · 접안 불가(선박 부두 이안 기준).

현업 기준표 (SK 부두 기상 기준)
                      하역작업 중단                         선박 부두 이안 (→ 접안 불가)
  #1~2, GAS1·2        풍속 ≥ 18 m/s, 대기 정체, 심한 뇌우    풍속 ≥ 20 m/s, 태풍 경로
  #3~7                풍속 ≥ 14 m/s, 대기 정체, 심한 뇌우    풍속 ≥ 21 m/s, 태풍 경로
  (로딩암/호스 분리 기준은 쓰지 않음)

적용
  - 하역 중단 구간: 접안은 가능, 하역·선적만 멈춘다. 탱크 ↔ 선박 흐름도 없다. 멈춘 시간만큼 작업완료가 늦어진다
    (after_etb.s2_work_finish.work_finish 의 stops).
  - 접안 불가 구간: 선박이 부두에 있을 수 없다 (이안 기준). 접안 기간 [ETB, ETU)가 겹치면 안 되고,
    끝난 뒤 Direction 시간 후 접안할 수 있다 (부두 제약과 같은 방식, BlockKind.WIND, whole_stay).
  - 태풍: ① 태풍 오는 시간 직접 입력(with_typhoon) → 그 시간 전 부두 접안 불가
          ② 태풍 경로 파일(with_track, typhoon.py) → 강풍반경 안에 드는 부두 · 시간만 접안 불가

가정 (현업 확인 필요)
  - #8, BUOY2·3은 기준표에 없어 #3~7 기준을 쓴다.
  - 예보는 시간 단위(각 시각부터 1시간). 예보 범위 밖은 평온으로 본다.
  - 실제 예보가 없어 가상 예보를 만든다 (synthesize_forecast, data/dummy/weather.csv).
"""

import csv
import math
import random
from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from pathlib import Path

from .step3_berth_block import BerthBlock, BlockKind

HOUR = timedelta(hours=1)

# 부두 그룹별 (하역작업 중단 풍속, 선박 부두 이안 풍속) [m/s]
THRESHOLDS: dict[str, tuple[float, float]] = {
    "#1~2·GAS": (18.0, 20.0),
    "#3~7": (14.0, 21.0),
}


def berth_group(berth: str) -> str:
    """#1-x · #2-x · GAS → '#1~2·GAS', 나머지(#3 ~ #8, BUOY) → '#3~7' (#8 · BUOY는 가정)."""
    if berth.startswith(("1-", "2-", "GAS")):
        return "#1~2·GAS"
    return "#3~7"


@dataclass(frozen=True)
class WeatherHour:
    time: datetime  # 이 시각부터 1시간
    wind: float  # 풍속 m/s
    thunder: bool = False  # 심한 뇌우
    stagnation: bool = False  # 대기 정체
    typhoon: bool = False  # 태풍 경로


@dataclass(frozen=True)
class Forecast:
    hours: tuple[WeatherHour, ...]
    source: str = ""
    typhoons: tuple[tuple[datetime, datetime], ...] = ()  # 입력받은 태풍 구간 (with_typhoon)
    track: object = None  # 태풍 경로 (typhoon.Track, with_track) → 부두별 접안 불가
    _cache: dict = field(default_factory=dict, compare=False, repr=False, hash=False)  # 부두별 구간 (객체마다 따로)

    def stop_hour(self, h: WeatherHour, group: str) -> bool:
        return h.wind >= THRESHOLDS[group][0] or h.thunder or h.stagnation or self.unberth_hour(h, group)

    def unberth_hour(self, h: WeatherHour, group: str) -> bool:
        return h.wind >= THRESHOLDS[group][1] or h.typhoon

    def stops(self, berth: str) -> tuple[tuple[datetime, datetime], ...]:
        """하역작업 중단 구간 (접안 불가 구간 포함 — 그때도 하역은 없다)."""
        return self._periods("stop", berth)

    def unberths(self, berth: str) -> tuple[tuple[datetime, datetime], ...]:
        """접안 불가 구간 (선박 부두 이안 기준)."""
        return self._periods("unberth", berth)

    def track_unberths(self, berth: str) -> tuple[tuple[datetime, datetime], ...]:
        """태풍 경로 강풍반경 안에 드는 구간 (이 부두 좌표 기준)."""
        if self.track is None:
            return ()
        key = ("track", berth)
        if key not in self._cache:
            from .typhoon import berth_periods

            self._cache[key] = berth_periods(self.track, berth)
        return self._cache[key]

    def _periods(self, kind: str, berth: str):
        key = (kind, berth)
        if key not in self._cache:
            g = berth_group(berth)
            gkey = (kind, "group", g)  # 풍속 · 뇌우 · 직접 입력 태풍은 부두 그룹 단위
            if gkey not in self._cache:
                test = self.stop_hour if kind == "stop" else self.unberth_hour
                self._cache[gkey] = merge((h.time, h.time + HOUR) for h in self.hours if test(h, g))
            self._cache[key] = merge([*self._cache[gkey], *self.track_unberths(berth)])
        return self._cache[key]


def merge(periods: Iterable[tuple[datetime, datetime]]) -> tuple[tuple[datetime, datetime], ...]:
    out: list[list[datetime]] = []
    for s, e in sorted(periods):
        if out and s <= out[-1][1]:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return tuple((s, e) for s, e in out)


def wind_blocks(fc: Forecast | None, berths: Iterable[str]) -> list[BerthBlock]:
    """접안 불가 구간 → 부두 제약 (접안 기간 전체가 겹치면 안 됨, 끝나면 + Direction)."""
    if fc is None:
        return []
    by_periods: dict[tuple, set[str]] = {}  # 같은 접안 불가 구간을 갖는 부두끼리 묶음
    for b in berths:
        by_periods.setdefault(fc.unberths(b), set()).add(b)
    out = []
    for periods, bs in by_periods.items():
        for s, e in periods:
            out.append(BerthBlock(s, e, BlockKind.WIND, frozenset(bs), whole_stay=True))
    return out


# ── 가상 예보 ─────────────────────────────────────────────────────────
# (이름, 중심 시각, 반폭 시간, 최대 풍속 m/s) — 11월이라 태풍 경로는 넣지 않는다
WIND_EVENTS = (
    ("북서 계절풍 강화", datetime(2026, 11, 10, 21), 9, 16.5),  # #3~7 하역 중단만 (14 이상, 18 미만)
    ("저기압 통과 강풍", datetime(2026, 11, 13, 13), 8, 23.0),  # 모든 부두 접안 불가 구간 포함
)
THUNDER = ((datetime(2026, 11, 12, 2), 3),)  # (시작, 시간) 심한 뇌우
STAGNATION = ((datetime(2026, 11, 16, 8), 4),)  # (시작, 시간) 대기 정체
BASE_WIND = 5.0  # 평균 풍속
DIURNAL = 2.0  # 하루 변동 폭 (오후 2시 최대)
NOISE = 1.0


def synthesize_forecast(start: datetime, end: datetime, seed: int) -> Forecast:
    rng = random.Random(f"{seed}:weather")
    t = start.replace(minute=0, second=0, microsecond=0)
    hours = []
    while t < end:
        base = BASE_WIND + DIURNAL * math.sin(2 * math.pi * (t.hour - 8) / 24) + rng.gauss(0, NOISE)
        wind = min(max(base, 0.5), 11.0)
        for _, center, half, peak in WIND_EVENTS:
            x = (t - center).total_seconds() / 3600 / half
            if abs(x) < 1:
                wind = max(wind, peak * math.cos(x * math.pi / 2) ** 2 + rng.gauss(0, 0.3))
        thunder = any(s <= t < s + timedelta(hours=n) for s, n in THUNDER)
        stagnation = any(s <= t < s + timedelta(hours=n) for s, n in STAGNATION)
        hours.append(WeatherHour(t, round(wind, 1), thunder, stagnation, False))
        t += HOUR
    return Forecast(tuple(hours), f"가상 예보 (seed {seed})")


# ── 태풍 입력 ─────────────────────────────────────────────────────────
def parse_periods(text: str, year: int) -> list[tuple[datetime, datetime]]:
    """'11/14 18:00~11/15 06:00, 11/17 00:00~11/17 12:00' → [(시작, 끝), …]"""
    out = []
    for part in text.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        s, e = (datetime.strptime(f"{year}/{x.strip()}", "%Y/%m/%d %H:%M") for x in part.split("~"))
        if e <= s:
            raise ValueError(f"태풍 구간 끝이 시작보다 늦어야 합니다: {part}")
        out.append((s, e))
    return out


def with_typhoon(fc: Forecast, periods: list[tuple[datetime, datetime]]) -> Forecast:
    """태풍이 오는 구간과 겹치는 예보 시간을 '태풍 경로'로 표시 → 그 시간은 모든 부두 접안 불가 · 하역 중단.
    예보가 시간 단위라 정각이 아닌 시작·끝은 그 시간 전체를 막는다 (보수적)."""
    if not periods:
        return fc
    hours = tuple(replace(h, typhoon=h.typhoon or any(h.time < e and h.time + HOUR > s for s, e in periods))
                  for h in fc.hours)
    covered = [(s, e) for s, e in periods if any(h.time < e and h.time + HOUR > s for h in fc.hours)]
    if len(covered) < len(periods):
        raise ValueError(f"태풍 구간이 예보 범위({fc.hours[0].time:%m/%d %H:%M} ~ {fc.hours[-1].time + HOUR:%m/%d %H:%M}) 밖입니다")
    return Forecast(hours, f"{fc.source} + 태풍 {typhoon_text(periods)}", fc.typhoons + tuple(periods), fc.track)


def with_track(fc: Forecast, track) -> Forecast:
    """태풍 경로를 붙인 예보 → 부두마다 강풍반경 안에 드는 시간이 접안 불가 (typhoon.berth_periods)."""
    if track is None:
        return fc
    return Forecast(fc.hours, f"{fc.source} + {track.source}", fc.typhoons, track)


def typhoon_text(periods) -> str:
    return ", ".join(f"{s:%m/%d %H:%M}~{e:%m/%d %H:%M}" for s, e in periods)


FIELDS = ["time", "wind_ms", "thunder", "stagnation", "typhoon"]


def write_csv(fc: Forecast, path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(FIELDS)
        for h in fc.hours:
            w.writerow([f"{h.time:%Y-%m-%d %H:%M}", h.wind, int(h.thunder), int(h.stagnation), int(h.typhoon)])


def read_csv(path: Path) -> Forecast:
    hours = []
    with path.open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            hours.append(WeatherHour(datetime.strptime(r["time"], "%Y-%m-%d %H:%M"), float(r["wind_ms"]),
                                     r["thunder"] == "1", r["stagnation"] == "1", r["typhoon"] == "1"))
    return Forecast(tuple(hours), f"파일 {path}")
