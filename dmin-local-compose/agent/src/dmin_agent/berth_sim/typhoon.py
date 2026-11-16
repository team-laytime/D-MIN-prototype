"""태풍 경로 → 부두별 접안 불가 시간 (기상청_태풍정보 조회서비스 형식, API 연결 없이 파일로 받음).

참고: 공공데이터포털 15043565 '기상청_태풍정보 조회서비스'
  태풍정보조회      typTm(태풍시각) typLat typLon typ15(강풍반경) typ25(폭풍반경) typ15ed(예외방향) typ15er(예외반경)
                    typSeq typName tmFc(발표시각) typWs typPs …
  태풍예상정보조회  tm lat lon rad15 ed15 er15 radPr(70% 확률반경) seq tmFc ws ps …
  날씨누리 태풍 정보 CSV (FCT_태풍정보_*.csv, CP949)
                    일시(통보 시각) · (예상 시간 0 · 12 · 24 · 36 · 48 · 72 · 96 · 120) · 위도(N) · 경도(E) · 중심기압
                    · 초속(m/s) · 시속(km/h) · 강풍반경(km)[예외반경] · 강도(1~5, L) · 크기 · 진행방향 · 이동속도 · 70% 확률 반경
세 형식을 모두 받는다 (CSV · API 응답 JSON · XML). 반경은 km. 날씨누리 CSV는 태풍 번호가 없어 파일 하나 = 태풍 하나.

입력 지점
  - 예상정보는 통보문마다 0 · 3 · 6 · 9 · 12 · 24 · 36 · 48 · 72 · 96 · 120시간 뒤 위치가 온다.
  - 통보문이 여러 개면 가장 최신 통보문(tmFc)의 경로 전체를 쓰고, 그보다 이른 시각은 이전 통보문들의
    분석 위치(각 통보문의 첫 지점 = 0시간)만 쓴다 → 과거 실제 위치 + 최신 예상 경로.
    (옛 통보문의 예상 지점이 새 경로 사이에 끼면 경로가 지그재그가 되므로 버린다)

판단 (1시간 단위)
  - 정시마다 앞뒤 지점 사이를 직선 보간한다: 위도 · 경도, 그리고 앞뒤 지점의 '부두 쪽 방향 반경'
    (예외방향이면 예외반경)을 각각 구해 보간 → 예외반경이 생겨도 반경이 갑자기 뛰지 않음.
  - 정시 t에 '태풍 중심 ~ 부두 거리 ≤ 강풍반경(15 m/s)'이면 반경 안. 그 시간 [t, t+1h)은 앞뒤 정시 중
    하나라도 반경 안이면 접안 불가 (on) — 시간 중간에 들어오거나 나가도 놓치지 않게 (보수적).
  - 첫 지점 전 · 마지막 지점 후는 태풍 없음으로 본다. 시간별 결과는 hourly_table · write_hourly (out/typhoon/hourly.csv).
  - 접안 불가 구간은 강풍과 같은 방식: 그 시간에 부두에 있을 수 없고, 하역도 없다 (weather.Forecast).

가정 (현업 확인 필요)
  - 부두 좌표는 대략값이다 (BERTH_COORDS). 부두끼리 몇 km 안이라 반경 수백 km의 태풍이면 거의 같이 켜지고 꺼진다.
    BUOY(해상 부이)만 바다 쪽으로 떨어져 있어 경계 시간에 한 시간 먼저 켜질 수 있다.
  - 기준 반경은 강풍반경(15 m/s). 예상정보에는 폭풍반경이 없어서 둘 다 쓸 수 있는 값으로 정했다.
  - 70% 확률반경은 기본으로 더하지 않는다 (ADD_PROB_RADIUS).
"""

import csv
import io
import json
import math
import re
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from .weather import merge

STEP = timedelta(hours=1)  # 판단 간격: 1시간 단위로 태풍 위치를 보간해 on/off
EARTH_KM = 6371.0
RADIUS_FIELD = "rad15"  # 접안 불가 기준 반경: rad15 = 강풍반경(15 m/s), rad25 = 폭풍반경(25 m/s, 태풍정보조회에만 있음)
ADD_PROB_RADIUS = False  # True면 70% 확률반경(radPr)만큼 더 넓게 본다 (중심이 그 안 어디로든 올 수 있다고 보는 보수적 판단)

# 부두 좌표 (위도, 경도) — 대략값 (가정). 실제 좌표를 받으면 바꾼다.
SK_PORT = (35.475, 129.385)  # SK 울산 부두 대표 지점
BERTH_COORDS: dict[str, tuple[float, float]] = {
    "BUOY2": (35.425, 129.420),  # 해상 원유 부이 (가정)
    "BUOY3": (35.405, 129.430),
}

# 기상청 방향 표기 → 방위각(도). 8방위면 ±22.5°, 16방위면 ±11.25° 안을 예외방향으로 본다.
_DIRS16 = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
_KO = {"북": "N", "동": "E", "남": "S", "서": "W"}

ALIASES = {  # 표준 이름 ← 받을 수 있는 열 이름
    "time": ("typTm", "tm", "time"),
    "lat": ("typLat", "lat"),
    "lon": ("typLon", "lon"),
    "rad15": ("typ15", "rad15"),
    "rad25": ("typ25", "rad25"),
    "ex_dir": ("typ15ed", "ed15"),
    "ex_rad": ("typ15er", "er15"),
    "prob": ("radPr",),
    "seq": ("typSeq", "seq"),
    "name": ("typName", "typEn", "name"),
    "announced": ("tmFc",),
    "ws": ("typWs", "ws"),
    "ps": ("typPs", "ps"),
}


def berth_coord(berth: str) -> tuple[float, float]:
    return BERTH_COORDS.get(berth, SK_PORT)


@dataclass(frozen=True)
class TrackPoint:
    seq: str
    name: str
    time: datetime
    lat: float
    lon: float
    rad15: float  # km
    rad25: float = 0.0
    ex_dir: str = ""  # 예외방향 (16방위 영문 · 한글)
    ex_rad: float = 0.0  # 예외방향 쪽 강풍반경 km
    prob: float = 0.0  # 70% 확률반경 km
    announced: datetime | None = None
    ws: float | None = None  # 최대풍속 m/s
    ps: float | None = None  # 중심기압 hPa


@dataclass(frozen=True)
class Track:
    points: tuple[TrackPoint, ...]
    source: str = ""

    def storms(self) -> dict[str, list[TrackPoint]]:
        """태풍 번호별 시각 순 경로: 최신 통보문 경로 전체 + 그 전 시각은 이전 통보문들의 분석 위치(0시간)."""
        out = {}
        for seq in dict.fromkeys(p.seq for p in self.points):
            bulletins: dict[datetime | None, list[TrackPoint]] = {}
            for p in self.points:
                if p.seq == seq:
                    bulletins.setdefault(p.announced, []).append(p)
            latest = max(bulletins, key=lambda a: a or datetime.min)
            start = min(p.time for p in bulletins[latest])
            chosen: dict[datetime, TrackPoint] = {}
            for a, pts in bulletins.items():
                t0 = min(p.time for p in pts)
                use = pts if a == latest else [p for p in pts if p.time == t0 and p.time < start]
                for p in use:
                    cur = chosen.get(p.time)
                    if cur is None or (p.announced or datetime.min) >= (cur.announced or datetime.min):
                        chosen[p.time] = p
            out[seq] = [chosen[t] for t in sorted(chosen)]
        return out

    def span(self) -> tuple[datetime, datetime] | None:
        if not self.points:
            return None
        return min(p.time for p in self.points), max(p.time for p in self.points)


# ── 거리 · 반경 ─────────────────────────────────────────────────────────
def distance_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * EARTH_KM * math.asin(math.sqrt(h))


def bearing_deg(a: tuple[float, float], b: tuple[float, float]) -> float:
    """a에서 본 b의 방위각 (북 0°, 동 90°)."""
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    y = math.sin(lo2 - lo1) * math.cos(la2)
    x = math.cos(la1) * math.sin(la2) - math.sin(la1) * math.cos(la2) * math.cos(lo2 - lo1)
    return math.degrees(math.atan2(y, x)) % 360


def direction_deg(text: str) -> tuple[float, float] | None:
    """'NE' · '북동' · '북동쪽' · 'NNE' → (방위각, 반폭). 모르면 None."""
    t = (text or "").strip().upper().replace("쪽", "").replace("방향", "")
    t = "".join(_KO.get(c, c) for c in t)
    if t not in _DIRS16:
        return None
    return _DIRS16.index(t) * 22.5, (22.5 if len(t) <= 2 else 11.25)


def radius_toward(p: TrackPoint, bearing: float) -> float:
    """태풍 중심에서 bearing 방향의 접안 불가 반경 km."""
    r = p.rad25 if RADIUS_FIELD == "rad25" else p.rad15
    d = direction_deg(p.ex_dir) if RADIUS_FIELD == "rad15" and p.ex_rad > 0 else None
    if d is not None and abs((bearing - d[0] + 180) % 360 - 180) <= d[1]:
        r = p.ex_rad
    return r + (p.prob if ADD_PROB_RADIUS else 0.0)


def reach(points: list[TrackPoint], t: datetime, at: tuple[float, float]) -> tuple[float, float, tuple[float, float]] | None:
    """t 시각 (태풍 중심 ~ at 거리 km, at 쪽 반경 km, 중심 위치). 경로 밖이면 None."""
    if not points or t < points[0].time or t > points[-1].time:
        return None
    a, b = points[0], points[0]
    for a, b in zip(points, points[1:]):
        if a.time <= t <= b.time:
            break
    f = (t - a.time) / (b.time - a.time) if b.time > a.time else 0.0
    c = (a.lat + (b.lat - a.lat) * f, a.lon + (b.lon - a.lon) * f)
    brg = bearing_deg(c, at)
    r = radius_toward(a, brg) + (radius_toward(b, brg) - radius_toward(a, brg)) * f
    return distance_km(c, at), r, c


def inside(points: list[TrackPoint], t: datetime, at: tuple[float, float]) -> bool:
    x = reach(points, t, at)
    return x is not None and x[0] <= x[1]


def berth_periods(track: Track, berth: str, step: timedelta = STEP) -> tuple[tuple[datetime, datetime], ...]:
    """이 부두가 태풍 강풍반경 안에 드는 구간 (접안 불가)."""
    at = berth_coord(berth)
    out: list[list[datetime]] = []
    for pts in track.storms().values():
        t = _floor(pts[0].time, step)
        prev = inside(pts, t, at)
        while t < pts[-1].time:
            nxt = inside(pts, t + step, at)
            if prev or nxt:
                if out and out[-1][1] >= t:
                    out[-1][1] = max(out[-1][1], t + step)
                else:
                    out.append([t, t + step])
            t, prev = t + step, nxt
    return merge((s, e) for s, e in out)


def status_at(track: Track, t: datetime, at: tuple[float, float] = SK_PORT) -> dict | None:
    """화면용: t 시각 가장 가까운 태풍까지 거리와 그쪽 반경."""
    best = None
    for pts in track.storms().values():
        x = reach(pts, t, at)
        if x is None:
            continue
        d, r, c = x
        if best is None or d < best["dist"]:
            best = {"name": pts[0].name or pts[0].seq, "dist": round(d), "rad": round(r), "lat": round(c[0], 2), "lon": round(c[1], 2)}
    return best


def hourly_table(track: Track, berths: Iterable[str] = ()) -> list[dict]:
    """1시간 단위 보간 결과: 정시마다 태풍 위치 · SK 부두 쪽 반경 · 거리, 그 시간 [t, t+1h) 접안 불가 여부.
    on 열은 좌표가 같은 부두끼리 묶는다 (지금은 육상 부두 한 점 + BUOY 각각)."""
    groups: dict[tuple[float, float], list[str]] = {}
    for b in berths:
        groups.setdefault(berth_coord(b), []).append(b)
    periods = {xy: berth_periods(track, bs[0]) for xy, bs in groups.items()}
    rows = []
    for seq, pts in track.storms().items():
        t = _floor(pts[0].time, STEP)
        while t <= pts[-1].time:
            x = reach(pts, t, SK_PORT)
            row = {"time": f"{t:%Y-%m-%d %H:%M}", "seq": seq, "name": pts[0].name}
            if x is not None:
                d, r, c = x
                row.update(lat=round(c[0], 3), lon=round(c[1], 3), radius_to_sk_km=round(r, 1), dist_sk_km=round(d, 1),
                           inside_sk=int(d <= r))
            for xy, bs in groups.items():
                label = "on_" + ("SK부두" if xy == SK_PORT else "·".join(bs))
                row[label] = int(any(s < t + STEP and t < e for s, e in periods[xy]))
            rows.append(row)
            t += STEP
    return rows


def write_hourly(track: Track, berths: Iterable[str], path: Path) -> Path:
    rows = hourly_table(track, berths)
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = list(dict.fromkeys(k for r in rows for k in r))
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    return path


def _floor(t: datetime, step: timedelta) -> datetime:
    base = t.replace(hour=0, minute=0, second=0, microsecond=0)
    return base + ((t - base) // step) * step


# ── 읽기 ───────────────────────────────────────────────────────────────
def _time(text: str) -> datetime | None:
    t = (text or "").strip()
    for f in ("%Y%m%d%H%M", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M", "%Y%m%d%H", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"):
        try:
            return datetime.strptime(t, f)
        except ValueError:
            pass
    return None


def _num(text, default=None):
    try:
        return float(str(text).strip())
    except (TypeError, ValueError):
        return default


def _pick(row: dict, key: str):
    for k in ALIASES[key]:
        if k in row and str(row[k]).strip() not in ("", "None", "null"):
            return row[k]
    return None


def points_from_rows(rows: Iterable[dict]) -> list[TrackPoint]:
    out = []
    for r in rows:
        t, la, lo = _time(str(_pick(r, "time") or "")), _num(_pick(r, "lat")), _num(_pick(r, "lon"))
        if t is None or la is None or lo is None:
            continue  # 시각 · 위치가 없는 줄은 건너뜀
        out.append(TrackPoint(
            seq=str(_pick(r, "seq") or "1").strip(), name=str(_pick(r, "name") or "").strip(), time=t, lat=la, lon=lo,
            rad15=_num(_pick(r, "rad15"), 0.0), rad25=_num(_pick(r, "rad25"), 0.0), ex_dir=str(_pick(r, "ex_dir") or "").strip(),
            ex_rad=_num(_pick(r, "ex_rad"), 0.0), prob=_num(_pick(r, "prob"), 0.0), announced=_time(str(_pick(r, "announced") or "")),
            ws=_num(_pick(r, "ws")), ps=_num(_pick(r, "ps")),
        ))
    return out


def _kma_time(text: str) -> datetime | None:
    """'2026년 10월 15일 15시' → datetime."""
    m = re.match(r"\s*(\d{4})\D+(\d{1,2})\D+(\d{1,2})\D+(\d{1,2})", text or "")
    return datetime(*map(int, m.groups())) if m else None


def _radius_field(text: str) -> tuple[float, str, float]:
    """'300' · '300[북동 350]' · '300[350(북동쪽)]' → (강풍반경, 예외방향, 예외반경)."""
    m = re.match(r"\s*([\d.]+)", text or "")
    rad = float(m.group(1)) if m else 0.0
    b = re.search(r"\[(.*?)\]", text or "")
    if not b:
        return rad, "", 0.0
    n = re.search(r"([\d.]+)", b.group(1))
    d = re.search(r"([북남동서]+|[NSEW]{1,3})", b.group(1))
    return rad, (d.group(1) if d else ""), (float(n.group(1)) if n and d else 0.0)


def _col(row: dict, prefix: str):
    return next((v for k, v in row.items() if k and k.strip().startswith(prefix)), None)


def _kma_fct_rows(rows: list[dict], stem: str) -> list[dict]:
    """날씨누리 태풍 CSV 한 줄 = (통보 시각, 예상 시간) 한 지점 → 표준 열 이름으로."""
    out = []
    for r in rows:
        base = _kma_time(r.get("일시", ""))
        if base is None:
            continue
        lead = _num(r.get("", _col(r, "예상")), 0.0)  # 예상 시간 열은 머리글이 비어 있음
        rad, ed, er = _radius_field(str(_col(r, "강풍반경") or ""))
        out.append({"tm": f"{base + timedelta(hours=lead):%Y%m%d%H%M}", "tmFc": f"{base:%Y%m%d%H%M}",
                    "lat": _col(r, "위도"), "lon": _col(r, "경도"), "rad15": rad, "ed15": ed, "er15": er,
                    "radPr": _col(r, "70%"), "ws": _col(r, "초속"), "ps": _col(r, "중심기압"),
                    "seq": stem, "name": _fct_name(stem)})
    return out


def _fct_name(stem: str) -> str:
    """'FCT_태풍정보_가상태풍_20261109100000' → '가상태풍' (끝의 내려받은 시각은 뺌, 이름이 없으면 그 시각)."""
    rest = stem.removeprefix("FCT_태풍정보_")
    return re.sub(r"_?\d{14}$", "", rest) or rest


def _read_text(path: Path) -> str:
    raw = path.read_bytes()
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp949")  # 날씨누리 내려받기 파일


def _rows(path: Path) -> list[dict]:
    if path.suffix.lower() == ".json":
        d = json.loads(path.read_text(encoding="utf-8-sig"))
        items = d.get("response", {}).get("body", {}).get("items", {}).get("item", d) if isinstance(d, dict) else d
        return [items] if isinstance(items, dict) else list(items)
    if path.suffix.lower() == ".xml":
        return [{c.tag: (c.text or "") for c in it} for it in ET.parse(path).getroot().iter("item")]
    rows = list(csv.DictReader(io.StringIO(_read_text(path))))
    if rows and "일시" in rows[0]:
        return _kma_fct_rows(rows, path.stem)
    return rows


def read_track(paths: Iterable[Path]) -> Track | None:
    """파일 여러 개(CSV · JSON · XML)를 한 경로 묶음으로. 지점이 없으면 None."""
    pts, names = [], []
    for p in paths:
        got = points_from_rows(_rows(Path(p)))
        if got:
            pts += got
            names.append(Path(p).name)
    if not pts:
        return None
    used = sum(len(v) for v in Track(tuple(pts)).storms().values())
    return Track(tuple(pts), f"태풍 경로 {', '.join(names)} (읽은 지점 {len(pts)}개 → 경로 {used}개)")


TRACK_DIR = Path("data/typhoon")  # 이 폴더에 넣은 파일은 자동으로 읽는다 (README.md 제외)


def track_files(arg: str | None = None) -> list[Path]:
    """--typhoon-track 경로(파일 · 폴더) 또는 기본 폴더의 CSV · JSON · XML."""
    base = Path(arg) if arg else TRACK_DIR
    if base.is_file():
        return [base]
    if base.is_dir():
        return sorted(p for p in base.iterdir() if p.suffix.lower() in (".csv", ".json", ".xml"))
    if arg:
        raise FileNotFoundError(f"태풍 경로 파일이 없습니다: {arg}")
    return []
