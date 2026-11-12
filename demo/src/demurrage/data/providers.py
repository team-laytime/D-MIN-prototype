"""외부 데이터 제공자 — 일출·일몰, 조석, 기상 (FR-05, FR-06, NFR-10).

원칙: 바깥 API가 실패해도 계산은 멈추지 않는다. 대신 '어떤 값을, 어디서, 언제 받았는지'를 결과에 남긴다.
우선순위: 시나리오가 준 값 → 저장해 둔 수집본(data/public/*.json) → 오프라인 계산(일출·일몰만)
공공데이터포털 API 호출은 서비스키(PUBLIC_DATA_SERVICE_KEY)가 있을 때만 `demurrage fetch-public`이 한다.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from ..domain.timeutil import DAY, date_key, day_start, parse_ts
from .solar import sunrise_sunset


class SunTable:
    """날짜별 일출·일몰(그날 0시부터 분)."""

    def __init__(self, location: dict, override: Optional[dict] = None, cache_path: Optional[Path] = None):
        self.lat = float(location.get("lat", 35.5384))
        self.lon = float(location.get("lon", 129.3114))
        self.tz = float(location.get("tz_hours", 9))
        self.override = dict(override or {})
        self.cache = {}
        self.cache_meta = None
        if cache_path and cache_path.exists():
            doc = json.loads(cache_path.read_text(encoding="utf-8"))
            self.cache = {k: tuple(v) for k, v in doc.get("days", {}).items()}
            self.cache_meta = {k: doc.get(k) for k in ("source", "fetched_at", "status")}
        self.used = {}  # date → 출처

    def _hm(self, s) -> int:
        if isinstance(s, int):
            return s
        hh, mm = str(s).split(":")
        return int(hh) * 60 + int(mm)

    def get(self, day0: int) -> tuple:
        """그날(00:00 분)의 (일출, 일몰) 절대 분."""
        key = date_key(day0)
        if key in self.override:
            r, s = self.override[key]
            self.used[key] = "시나리오 입력"
        elif key in self.cache:
            r, s = self.cache[key]
            self.used[key] = (self.cache_meta or {}).get("source", "저장된 수집본")
        else:
            d = date.fromisoformat(key)
            r, s = sunrise_sunset(d, self.lat, self.lon, self.tz)
            self.used[key] = "NOAA 태양 위치식 계산(오프라인)"
        return day0 + self._hm(r), day0 + self._hm(s)

    def sunset(self, day0: int) -> int:
        return self.get(day0)[1]

    def provenance(self) -> dict:
        kinds = sorted(set(self.used.values()))
        return {"name": "일출·일몰", "sources": kinds, "days": len(self.used),
                "fallback": any("계산" in k for k in kinds),
                "cache": self.cache_meta}


def weather_restrictions(segments: list, berths: dict, limits: dict, active: Optional[list] = None):
    """풍속 예보 구간 → 기상 부두 제한(WX-01). segments: [(start, end, wind_ms)] (분)."""
    from ..domain.model import Restriction

    out = []
    for i, (s, e, w) in enumerate(segments):
        for bid, b in berths.items():
            if active and bid not in active:
                continue
            lim = float(limits.get(b.type, limits.get("PIER", 15)))
            if w >= lim:
                out.append(Restriction(id=f"WX{i + 1}-{bid}", berths=(bid,), start=s, end=e, reason="WEATHER",
                                       note=f"예보 풍속 {w:g} m/s ≥ 접안 한계 {lim:g} m/s (WX-01)", source="예보"))
    # 같은 부두에서 이어지는 구간은 합친다
    merged = {}
    for r in sorted(out, key=lambda r: (r.berths[0], r.start)):
        key = r.berths[0]
        if key in merged and merged[key][-1].end >= r.start:
            last = merged[key][-1]
            merged[key][-1] = type(r)(id=last.id, berths=last.berths, start=last.start, end=max(last.end, r.end),
                                      reason="WEATHER", note=last.note, source=last.source)
        else:
            merged.setdefault(key, []).append(r)
    return [r for rs in merged.values() for r in rs]


def load_public_cache(data_dir: Path, name: str) -> Optional[dict]:
    p = data_dir / "public" / name
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return None
