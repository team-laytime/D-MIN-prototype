"""울산항 선박위치 중계: 실제 API는 부르지 않고 응답 한 줄 모양으로만 확인한다."""
from datetime import datetime, timedelta

import pytest

from demurrage.data import ais

RAW = {"callsgn": "D7IN", "ptentYr": "2026", "vyg": "022", "mmsiNo": "440321000", "imoNo": "9879363", "vslNm": "싸왓디 퍼시픽",
       "lot": "129.35579667", "lat": "35.44168167", "sog": "0", "cog": "279", "rot": "0", "hdgAng": "245", "drft": "9.5",
       "nvgtStts": "정박(계류)", "updtTm": "20261112170635"}


def test_normalize_maps_fields_and_age():
    now = datetime(2026, 11, 12, 17, 16, 35, tzinfo=ais.KST)
    v = ais.normalize(RAW, now)
    assert (v["mmsi"], v["imo"], v["lat"], v["lng"], v["cog"], v["draft"]) == ("440321000", "9879363", 35.44168167, 129.35579667, 279, 9.5)
    assert v["ageMin"] == 10.0 and v["updatedAt"].endswith("+09:00")


def test_normalize_skips_rows_without_position_and_blanks_become_none():
    assert ais.normalize({**RAW, "lat": ""}) is None
    v = ais.normalize({**RAW, "imoNo": "", "drft": "0"})
    assert v["imo"] is None and v["draft"] is None


def test_filters_by_age_and_bbox(monkeypatch):
    fresh = (datetime.now(ais.KST) - timedelta(minutes=5)).strftime("%Y%m%d%H%M%S")
    old = (datetime.now(ais.KST) - timedelta(days=3)).strftime("%Y%m%d%H%M%S")
    rows = [{**RAW, "updtTm": fresh}, {**RAW, "mmsiNo": "1", "updtTm": old}, {**RAW, "mmsiNo": "2", "lat": "36.5", "updtTm": fresh}]
    monkeypatch.setattr(ais, "_fetch", lambda: rows)
    ais._cache.update(items=None, at=0.0)
    d = ais.vessels(max_age_min=60, bbox=(35.4, 129.3, 35.5, 129.5), ttl_s=0)
    assert d["total"] == 3 and [v["mmsi"] for v in d["vessels"]] == ["440321000"]


def test_failure_serves_stale_then_errors_without_key(monkeypatch):
    rows = [{**RAW, "updtTm": datetime.now(ais.KST).strftime("%Y%m%d%H%M%S")}]
    monkeypatch.setattr(ais, "_fetch", lambda: rows)
    ais._cache.update(items=None, at=0.0)
    ais.vessels(ttl_s=0)

    def boom():
        raise ais.AisError("공공데이터포털 응답 500")
    monkeypatch.setattr(ais, "_fetch", boom)
    d = ais.vessels(ttl_s=0)
    assert d["stale"] is True and d["count"] == 1 and "500" in d["error"]


def test_missing_key_raises(monkeypatch):
    monkeypatch.delenv("PUBLIC_DATA_SERVICE_KEY", raising=False)
    with pytest.raises(ais.AisError):
        ais._fetch()


def test_voyage_events_filter_sort_and_none_strings(monkeypatch):
    rows = [
        {"callsgn": "A8QZ7", "vyg": "001", "ioprtVtsNm": "접안", "fcltKornNm": "SK2부두 01", "fcltSpecCd": "SK2", "ptentDt": "20261111132400", "dfptDt": "None", "jobDt": "20261111150000"},
        {"callsgn": "A8QZ7", "vyg": "001", "ioprtVtsNm": "입항", "fcltKornNm": "None", "ptentDt": "20261111132400", "dfptDt": "None", "jobDt": "20261111132400"},
        {"callsgn": "A8QZ7", "vyg": "002", "ioprtVtsNm": "입항", "fcltKornNm": "정박지-E3", "ptentDt": "20261201000000", "dfptDt": "None", "jobDt": "20261201000000"},
    ]
    monkeypatch.setattr(ais, "_fetch_voyages", lambda c, y: rows)
    ais._nv_cache.clear()
    d = ais.voyage_events("A8QZ7", "2026", "001", ttl_s=0)
    assert d["voyages"] == ["001", "002"]
    assert [e["event"] for e in d["events"]] == ["입항", "접안"]  # 시각순
    assert d["events"][0]["facility"] is None and d["events"][0]["departedAt"] is None  # 문자열 'None'은 값 없음
    assert d["events"][1]["eventAt"].startswith("2026-11-11T15:00:00+09:00")
