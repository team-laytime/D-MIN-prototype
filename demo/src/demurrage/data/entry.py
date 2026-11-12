"""해양수산부 선박입출항신고 (공공데이터포털 15006353, 1192000/VsslEtrynd5/Info5) — 울산(항만청 코드 820).

대리점이 낸 입항·출항 신고다. 선장이 AIS에 손으로 넣는 ETA와 달리 '신고'라서
입항 예정 일시(미래), 예정 계선시설(정박지·부두), 전출항지, 차항지, 총톤수, 도선·예선 여부가 함께 온다.
- 같은 입항(호출부호 + 입항연도 + 입항횟수)에 최초·변경·최종 신고가 따로 쌓인다. 가장 나중 단계 하나만 쓴다.
- 입항일시가 지금보다 늦으면 '예정', 이르면 '신고된 입항'이다. 예정 시각은 대리점이 바꾸면 '변경'으로 다시 올라온다.
- 키는 PUBLIC_DATA_SERVICE_KEY(위치정보와 같은 키). 응답·오류 문구에 넣지 않는다.
"""
from __future__ import annotations

import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import Optional

BASE = "https://apis.data.go.kr/1192000/VsslEtrynd5/Info5"
ULSAN = "820"
KST = timezone(timedelta(hours=9))
_RANK = {"최초": 1, "변경": 2, "최종": 3}
_lock = threading.Lock()
_cache: dict = {"at": 0.0, "rows": None, "fetched_at": None, "window": None}


class EntryError(RuntimeError):
    pass


def _key() -> str:
    k = os.environ.get("PUBLIC_DATA_SERVICE_KEY", "").strip()
    if not k:
        raise EntryError("PUBLIC_DATA_SERVICE_KEY가 없습니다")
    return k


def _txt(v):
    return v if v not in (None, "", "None") else None


def _num(v):
    try:
        return float(v) if _txt(v) is not None else None
    except ValueError:
        return None


def parse(xml_bytes: bytes) -> tuple[int, list]:
    """응답 XML → (총 건수, 입출항 행 목록). 신고 한 건(item)에 상세(detail)가 여러 줄 있어 한 줄씩 펼친다."""
    root = ET.fromstring(xml_bytes)
    code = root.findtext(".//resultCode")
    if code not in (None, "00"):
        raise EntryError(f"공공데이터포털 오류 {code}: {root.findtext('.//resultMsg')}")
    if root.tag == "OpenAPI_ServiceResponse":  # 키·서비스 오류는 이 모양으로 온다
        raise EntryError(f"공공데이터포털 오류 {root.findtext('.//returnReasonCode')}")
    rows = []
    for it in root.iter("item"):
        base = {c.tag: (c.text or "") for c in it if c.tag != "details"}
        for d in it.iter("detail"):
            rows.append({**base, **{c.tag: (c.text or "") for c in d}})
    return int(root.findtext(".//totalCount") or 0), rows


def normalize(r: dict) -> dict:
    return {
        "callSign": _txt(r.get("clsgn")), "year": _txt(r.get("etryptYear")), "count": _txt(r.get("etryptCo")),
        "name": _txt(r.get("vsslNm")), "flag": _txt(r.get("vsslNltyNm")), "type": _txt(r.get("vsslKndNm")),
        "purpose": _txt(r.get("etryptPurpsNm")), "event": _txt(r.get("etryndNm")), "filing": _txt(r.get("reqstSeNm")),
        "eta": _txt(r.get("etryptDt")),  # 입항일시(신고). 미래면 입항 예정
        "etd": _txt(r.get("tkoffDt")) or _txt(r.get("tkoffPrrrnDt")),
        "prevPort": _txt(r.get("prvsDpmprtPrtNm")), "firstPort": _txt(r.get("frstDpmprtPrtNm")),
        "nextPort": _txt(r.get("nxlnptPrtNm")), "destPort": _txt(r.get("dstnPrtNm")),
        "facility": _txt(r.get("laidupFcltyNm")), "facilityCode": _txt(r.get("laidupFcltyCd")),
        "domestic": _txt(r.get("ibobprtNm")), "pilot": _txt(r.get("piltgYn")), "tug": _txt(r.get("tugYn")),
        "grt": _num(r.get("grtg")), "intlGrt": _num(r.get("intrlGrtg")), "crew": _num(r.get("crewCo")),
        "cargo": _txt(r.get("ldadngFrghtClCd")), "loadTon": _num(r.get("ldFrghtTon")), "unloadTon": _num(r.get("landngFrghtTon")),
        "agent": _txt(r.get("satmntEntrpsNm")),
    }


def pick_latest(rows: list) -> list:
    """같은 입항(호출부호·연도·입항횟수)의 입항 신고 중 가장 나중 단계(최종 > 변경 > 최초) 하나."""
    best: dict = {}
    for r in rows:
        if r["event"] != "입항" or not r["eta"]:
            continue
        k = (r["callSign"], r["year"], r["count"])
        if k not in best or _RANK.get(r["filing"], 0) >= _RANK.get(best[k]["filing"], 0):
            best[k] = r
    return list(best.values())


def _fetch(sde: str, ede: str) -> list:
    rows, page = [], 1
    while True:
        q = urllib.parse.urlencode({"serviceKey": _key(), "pageNo": page, "numOfRows": 50, "prtAgCd": ULSAN, "sde": sde, "ede": ede})
        try:
            with urllib.request.urlopen(f"{BASE}?{q}", timeout=20) as r:
                total, part = parse(r.read())
        except urllib.error.HTTPError as e:
            raise EntryError(f"공공데이터포털 응답 {e.code}") from None
        except EntryError:
            raise
        except Exception as e:
            raise EntryError(f"공공데이터포털 호출 실패: {type(e).__name__}") from None
        rows += [normalize(x) for x in part]
        if page * 50 >= total:
            return rows
        if page >= 40:  # 2,000건을 넘으면 조회 창이 너무 넓다. 일부만 받은 채로 통과시키지 않는다.
            raise EntryError(f"조회 건수 {total}건이 너무 많아 일부만 받을 수 있습니다. 조회 기간을 줄이세요")
        page += 1


def arrivals(callsgn: Optional[str] = None, hours_back: float = 0, hours_ahead: float = 48, ttl_s: Optional[float] = None, now: Optional[datetime] = None) -> dict:
    """입항 신고 목록(최신 단계만). 기본은 지금부터 48시간 안의 예정. 호출 창은 -3일 ~ +10일을 5분 캐시로 모은다."""
    ttl = float(os.environ.get("ENTRY_CACHE_S", "300")) if ttl_s is None else ttl_s
    now = now or datetime.now(KST)
    stale, error = False, None
    with _lock:
        if _cache["rows"] is None or time.time() - _cache["at"] > ttl:
            try:
                sde, ede = (now - timedelta(days=3)).strftime("%Y%m%d"), (now + timedelta(days=10)).strftime("%Y%m%d")
                _cache.update(rows=_fetch(sde, ede), at=time.time(), fetched_at=now.isoformat(), window=[sde, ede])
            except EntryError as e:
                if _cache["rows"] is None:
                    raise
                stale, error = True, str(e)
        rows, fetched_at, window = _cache["rows"], _cache["fetched_at"], _cache["window"]
    latest = pick_latest(rows)
    if callsgn:
        out = [r for r in latest if r["callSign"] == callsgn]
    else:
        lo, hi = now - timedelta(hours=hours_back), now + timedelta(hours=hours_ahead)
        out = [r for r in latest if lo <= datetime.fromisoformat(r["eta"]) <= hi]
    for r in out:
        r["planned"] = datetime.fromisoformat(r["eta"]) > now
    doc = {"source": "해양수산부 선박입출항신고 (공공데이터포털 15006353) · 울산 820", "fetchedAt": fetched_at, "window": window,
           "stale": stale, "count": len(out), "arrivals": sorted(out, key=lambda r: r["eta"])}
    if error:
        doc["error"] = error
    return doc
