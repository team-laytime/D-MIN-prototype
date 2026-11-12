"""울산 입항 신고: 실제 API는 부르지 않고 응답 XML 모양으로만 확인한다."""
from datetime import datetime, timedelta

import pytest

from demurrage.data import entry

NOW = datetime(2026, 11, 12, 18, 0, tzinfo=entry.KST)


def item(clsgn, count, details):
    ds = "".join(f"<detail><reqstSeNm>{f}</reqstSeNm><etryndNm>{e}</etryndNm><etryptDt>{dt}</etryptDt><laidupFcltyNm>{fac}</laidupFcltyNm><grtg>23386</grtg><tkoffDt/></detail>"
                 for f, e, dt, fac in details)
    return (f"<item><prtAgCd>820</prtAgCd><etryptYear>2026</etryptYear><etryptCo>{count}</etryptCo><clsgn>{clsgn}</clsgn><vsslNm>ISLAND BAY</vsslNm>"
            f"<prvsDpmprtPrtNm>CALLAO</prvsDpmprtPrtNm><dstnPrtNm></dstnPrtNm><details>{ds}</details></item>")


def xml(*items, total=None):
    return (f"<response><header><resultCode>00</resultCode><resultMsg>NORMAL_SERVICE</resultMsg></header><body><items>{''.join(items)}</items>"
            f"<totalCount>{total if total is not None else len(items)}</totalCount></body></response>").encode()


def rows_of(*items):
    return [entry.normalize(r) for r in entry.parse(xml(*items))[1]]


def test_parse_flattens_details_and_blanks_become_none():
    total, raw = entry.parse(xml(item("VRNJ4", "092", [("최초", "입항", "2026-11-12T20:00:00+09:00", "정박지-E2"), ("변경", "입항", "2026-11-12T22:00:00+09:00", "정박지-E2")])))
    assert total == 1 and len(raw) == 2
    r = entry.normalize(raw[0])
    assert (r["callSign"], r["eta"], r["facility"], r["grt"], r["prevPort"], r["destPort"], r["etd"]) == ("VRNJ4", "2026-11-12T20:00:00+09:00", "정박지-E2", 23386.0, "CALLAO", None, None)


def test_pick_latest_prefers_later_filing_and_ignores_departures():
    rows = rows_of(item("VRNJ4", "092", [("최초", "입항", "2026-11-12T20:00:00+09:00", "E2"), ("변경", "입항", "2026-11-12T22:00:00+09:00", "E2"), ("최초", "출항", "2026-11-14T08:00:00+09:00", "E2")]),
                   item("VRNJ4", "093", [("최초", "입항", "2026-11-20T08:00:00+09:00", "E3")]))
    got = {(r["count"]): r for r in entry.pick_latest(rows)}
    assert got["092"]["filing"] == "변경" and got["092"]["eta"].startswith("2026-11-12T22") and got["093"]["filing"] == "최초"


def test_arrivals_window_planned_flag_and_callsign(monkeypatch):
    rows = rows_of(item("A", "001", [("최초", "입항", "2026-11-12T20:00:00+09:00", "E1")]),
                   item("B", "001", [("최초", "입항", "2026-11-12T10:00:00+09:00", "E1")]),
                   item("C", "001", [("최초", "입항", "2026-11-18T10:00:00+09:00", "E1")]))
    monkeypatch.setattr(entry, "_fetch", lambda a, b: rows)
    entry._cache.update(rows=None, at=0.0)
    d = entry.arrivals(hours_ahead=48, ttl_s=0, now=NOW)
    assert [r["callSign"] for r in d["arrivals"]] == ["A"] and d["arrivals"][0]["planned"] is True
    d = entry.arrivals(callsgn="B", ttl_s=0, now=NOW)
    assert d["arrivals"][0]["planned"] is False  # 이미 지난 입항 신고


def test_service_error_and_missing_key(monkeypatch):
    with pytest.raises(entry.EntryError):
        entry.parse(b"<OpenAPI_ServiceResponse><cmmMsgHeader><returnReasonCode>30</returnReasonCode></cmmMsgHeader></OpenAPI_ServiceResponse>")
    monkeypatch.delenv("PUBLIC_DATA_SERVICE_KEY", raising=False)
    with pytest.raises(entry.EntryError):
        entry._fetch("20261101", "20261102")


def test_failure_serves_stale(monkeypatch):
    rows = rows_of(item("A", "001", [("최초", "입항", "2026-11-12T20:00:00+09:00", "E1")]))
    monkeypatch.setattr(entry, "_fetch", lambda a, b: rows)
    entry._cache.update(rows=None, at=0.0)
    entry.arrivals(ttl_s=0, now=NOW)
    monkeypatch.setattr(entry, "_fetch", lambda a, b: (_ for _ in ()).throw(entry.EntryError("공공데이터포털 응답 500")))
    d = entry.arrivals(ttl_s=0, now=NOW)
    assert d["stale"] is True and d["count"] == 1 and "500" in d["error"]


def test_too_many_rows_is_an_error_not_a_silent_cut(monkeypatch):
    monkeypatch.setenv("PUBLIC_DATA_SERVICE_KEY", "x")

    class R:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return xml(item("A", "001", [("최초", "입항", "2026-11-12T20:00:00+09:00", "E1")]), total=5000)
    monkeypatch.setattr(entry.urllib.request, "urlopen", lambda *a, **k: R())
    with pytest.raises(entry.EntryError, match="너무 많아"):
        entry._fetch("20261001", "20261130")
