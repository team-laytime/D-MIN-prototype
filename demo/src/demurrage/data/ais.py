"""울산항만공사 '항내 선박위치정보' (공공데이터포털 B551938/VslPstnInfoService).

브라우저에는 서비스키를 줄 수 없으므로 서버가 대신 부르고, 화면에는 정리한 값만 내려 준다.
- 키는 환경변수 PUBLIC_DATA_SERVICE_KEY(Decoding 키)에서만 읽는다. 응답·로그·오류 문구에 넣지 않는다.
- 호출은 AIS_CACHE_S초(기본 30초) 동안 모아 쓴다. 공공 API 호출 한도를 화면 새로고침 수에 묶지 않으려는 것이다.
- 실패하면 마지막 성공값을 `stale`로 표시해 내려 준다. 처음부터 실패하면 `error`만 내려 준다.
- 이 API에는 목적지·ETA·길이·폭·DWT가 없다. 그 값은 상용 AIS(ShipStaticData)나 대리점 자료가 채운다.
"""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Optional

BASE = "https://apis.data.go.kr/B551938/VslPstnInfoService/getVslPstnInfo"
KST = timezone(timedelta(hours=9))
_lock = threading.Lock()
_cache: dict = {"at": 0.0, "items": None, "fetched_at": None}


class AisError(RuntimeError):
    pass


def _key() -> str:
    k = os.environ.get("PUBLIC_DATA_SERVICE_KEY", "").strip()
    if not k:
        raise AisError("PUBLIC_DATA_SERVICE_KEY가 없습니다")
    return k


def _num(s, cast=float):
    try:
        return cast(s) if s not in (None, "") else None
    except ValueError:
        return None


def normalize(raw: dict, now: Optional[datetime] = None) -> Optional[dict]:
    """API 한 줄 → 화면용 한 줄. 위치가 없으면 None."""
    lat, lng = _num(raw.get("lat")), _num(raw.get("lot"))
    if lat is None or lng is None:
        return None
    now = now or datetime.now(KST)
    try:
        upd = datetime.strptime(raw["updtTm"], "%Y%m%d%H%M%S").replace(tzinfo=KST)
    except (KeyError, ValueError):
        upd = None
    return {
        "mmsi": raw.get("mmsiNo") or None,
        "imo": raw.get("imoNo") or None,
        "callSign": raw.get("callsgn") or None,
        "name": (raw.get("vslNm") or "").strip(),
        "lat": lat, "lng": lng,
        "sog": _num(raw.get("sog")), "cog": _num(raw.get("cog"), int),
        "heading": _num(raw.get("hdgAng"), int), "rot": _num(raw.get("rot")),
        "draft": _num(raw.get("drft")) or None,
        "navStatus": raw.get("nvgtStts") or None,
        "callYear": raw.get("ptentYr") or None, "voyage": raw.get("vyg") or None,  # 입항연도·항차: PORT-MIS와 잇는 열쇠
        "updatedAt": upd.isoformat() if upd else None,
        "ageMin": round((now - upd).total_seconds() / 60, 1) if upd else None,
    }


def _fetch() -> list:
    q = urllib.parse.urlencode({"serviceKey": _key(), "pageNo": 1, "numOfRows": 1000, "resultType": "json"})
    try:
        with urllib.request.urlopen(f"{BASE}?{q}", timeout=15) as r:
            doc = json.load(r)
    except urllib.error.HTTPError as e:
        raise AisError(f"공공데이터포털 응답 {e.code}") from None  # URL(키 포함)을 문구에 넣지 않는다
    except Exception as e:
        raise AisError(f"공공데이터포털 호출 실패: {type(e).__name__}") from None
    body = (doc.get("response") or {}).get("body") or {}
    head = (doc.get("response") or {}).get("header") or {}
    if head.get("resultCode") != "00":
        raise AisError(f"공공데이터포털 오류 {head.get('resultCode')}: {head.get('resultMsg')}")
    items = (body.get("items") or {}).get("item") or []
    return [items] if isinstance(items, dict) else items


def vessels(max_age_min: float = 60, bbox: Optional[tuple] = None, ttl_s: Optional[float] = None) -> dict:
    """선박 목록. bbox = (남, 서, 북, 동)."""
    ttl = float(os.environ.get("AIS_CACHE_S", "30")) if ttl_s is None else ttl_s
    stale = False
    error = None
    with _lock:
        if _cache["items"] is None or time.time() - _cache["at"] > ttl:
            try:
                _cache.update(items=_fetch(), at=time.time(), fetched_at=datetime.now(KST).isoformat())
            except AisError as e:
                if _cache["items"] is None:
                    raise
                stale, error = True, str(e)
        raw, fetched_at = _cache["items"], _cache["fetched_at"]
    now = datetime.now(KST)
    out = [v for v in (normalize(r, now) for r in raw) if v]
    total = len(out)
    out = [v for v in out if v["ageMin"] is not None and v["ageMin"] <= max_age_min]
    if bbox:
        s, w, n, e = bbox
        out = [v for v in out if s <= v["lat"] <= n and w <= v["lng"] <= e]
    doc = {
        "source": "울산항만공사 항내 선박위치정보 (공공데이터포털 15156631)",
        "fetchedAt": fetched_at, "stale": stale, "total": total, "count": len(out), "maxAgeMin": max_age_min,
        "vessels": sorted(out, key=lambda v: v["ageMin"]),
    }
    if error:
        doc["error"] = error
    return doc


# ── 항만 내 선박 운항정보 (B551938/VslNvgtInfoService/getVtsBaseVslNvgtInfo) ──
# 호출부호 + 입항연도로 한 척의 입항 기록을 받는다. 입항·투묘·양묘·접안·이안·이선·출항 '이미 일어난 일'의 기록이고
# 미래 ETA는 없다(2026-11-12 63척 1,830행 모두 과거). 체선료의 정박 시작·종료 시각을 실제 기록과 맞춰 보는 데 쓴다.
NVGT = "https://apis.data.go.kr/B551938/VslNvgtInfoService/getVtsBaseVslNvgtInfo"
_nv_cache: dict = {}
_nv_lock = threading.Lock()


def _kst(s):
    try:
        return datetime.strptime(s, "%Y%m%d%H%M%S").replace(tzinfo=KST).isoformat()
    except (TypeError, ValueError):
        return None


def normalize_event(r: dict) -> dict:
    return {
        "voyage": r.get("vyg") or None, "event": r.get("ioprtVtsNm") or None,
        "facility": r.get("fcltKornNm") if r.get("fcltKornNm") not in (None, "None", "") else None,
        "facilityCode": r.get("fcltSpecCd") or None,
        "arrivedAt": _kst(r.get("ptentDt")), "departedAt": _kst(r.get("dfptDt")),  # 항차의 입항·출항 일시
        "eventAt": _kst(r.get("jobDt")),  # 이 행(입항·접안 등)이 일어난 시각
        "updatedAt": _kst(r.get("updtDt")),
    }


def _fetch_voyages(callsgn: str, year: str) -> list:
    q = urllib.parse.urlencode({"serviceKey": _key(), "pageNo": 1, "numOfRows": 200, "resultType": "json", "callsgn": callsgn, "ptentVtsYr": year})
    try:
        with urllib.request.urlopen(f"{NVGT}?{q}", timeout=15) as r:
            doc = json.load(r)
    except urllib.error.HTTPError as e:
        raise AisError(f"공공데이터포털 응답 {e.code}") from None
    except Exception as e:
        raise AisError(f"공공데이터포털 호출 실패: {type(e).__name__}") from None
    resp = doc.get("response")
    if not resp:  # 오류는 OpenAPI_ServiceResponse로 온다(키·변수 문제)
        code = ((doc.get("OpenAPI_ServiceResponse") or {}).get("cmmMsgHeader") or {}).get("returnReasonCode")
        raise AisError(f"공공데이터포털 오류 {code}")
    items = ((resp.get("body") or {}).get("items") or {}).get("item") or []
    return [items] if isinstance(items, dict) else items


def voyage_events(callsgn: str, year: str, voyage: Optional[str] = None, ttl_s: float = 300) -> dict:
    """한 척의 입항 기록. voyage를 주면 그 항차만."""
    k = (callsgn, year)
    with _nv_lock:
        hit = _nv_cache.get(k)
        if not hit or time.time() - hit[0] > ttl_s:
            _nv_cache[k] = hit = (time.time(), [normalize_event(r) for r in _fetch_voyages(callsgn, year)])
    ev = hit[1]
    voyages = sorted({e["voyage"] for e in ev if e["voyage"]})
    if voyage:
        ev = [e for e in ev if e["voyage"] == voyage]
    ev = sorted(ev, key=lambda e: e["eventAt"] or "")
    return {"source": "울산항만공사 항만 내 선박 운항정보 (공공데이터포털 15156628)", "callSign": callsgn, "year": year,
            "voyage": voyage, "voyages": voyages, "events": ev}
