"""실시간 예시 시나리오: 공공 API는 부르지 않고, 신고·운항정보·위치를 흉내 낸 값으로 시나리오가 계산까지 가는지 본다."""
import importlib.util
from datetime import datetime
from pathlib import Path

import pytest

from demurrage.agents.orchestrator import run_pipeline
from demurrage.data import ais, entry
from demurrage.llm.adapter import get_llm

spec = importlib.util.spec_from_file_location("live_scenario", Path(__file__).resolve().parents[1] / "scripts" / "live_scenario.py")
live = importlib.util.module_from_spec(spec)
spec.loader.exec_module(live)
NOW = datetime(2026, 11, 12, 18, 0, tzinfo=entry.KST)


def arrival(call, name, kind, eta, fac, grt, unload=None, load=None, count="001"):
    return {"callSign": call, "year": "2026", "count": count, "name": name, "type": kind, "filing": "최초", "eta": eta, "facility": fac,
            "prevPort": "SINGAPORE", "grt": grt, "unloadTon": unload, "loadTon": load, "planned": True}


@pytest.fixture
def fake(monkeypatch):
    rows = [arrival("V7XU8", "AS SUWAYQ", "원유운반선", "2026-11-12T13:00:00+09:00", "SK부이 02", 164364, unload=129247),
            arrival("9HA5873", "ATHINA", "원유운반선", "2026-11-15T10:00:00+09:00", "SK부이 02", 160241, unload=270923),
            arrival("160064", "제1은희호", "기타 유조선", "2026-11-13T23:00:00+09:00", "SK5부두", 2458),
            arrival("X1", "S-OIL SHIP", "원유운반선", "2026-11-14T10:00:00+09:00", "S-OIL부이 01", 160000, unload=250000)]  # SK 아님
    monkeypatch.setattr(entry, "arrivals", lambda **k: {"arrivals": rows})
    monkeypatch.setattr(ais, "vessels", lambda **k: {"vessels": []})
    ev = {"V7XU8": [{"event": "입항", "facility": "SK부이 02", "eventAt": "2026-11-12T13:40:00+09:00"}]}
    monkeypatch.setattr(ais, "voyage_events", lambda call, year, voyage=None: {"events": ev.get(call, [])})


def test_only_sk_facilities_and_docked_vessel_is_working(fake):
    doc = live.build(NOW)
    ids = {v["id"]: v for v in doc["vessels"]}
    assert set(ids) == {"V7XU8", "9HA5873", "160064"}  # S-OIL 부이로 신고된 배는 SK 시나리오에 넣지 않는다
    assert ids["V7XU8"]["status"] == "WORKING" and ids["V7XU8"]["working"]["berth"] == "Buoy" and ids["V7XU8"]["working"]["etb"] == "2026-11-12 13:40"
    assert ids["9HA5873"]["status"] == "PLANNED" and ids["9HA5873"]["direction"] == "IMPORT"
    assert "draft" in doc["provenance"]["9HA5873"]["가정"] and "contract" in doc["provenance"]["160064"]["가정"]


def test_scenario_runs_through_pipeline_without_input_errors(fake):
    doc = live.build(NOW)
    run = run_pipeline({k: v for k, v in doc.items() if k not in ("provenance", "skipped")}, llm=get_llm(), time_limit_s=10, k=2)
    assert run["status"] != "INPUT_ERROR", run.get("input_issues")
    assert run["baseline"]["total_cents"] >= 0


def test_vtype_and_tide_windows():
    assert live.vtype("원유운반선") == "CRUDE" and live.vtype("케미칼 운반선") == "CHEMICAL" and live.vtype("풀컨테이너선") is None
    w = live.tide_windows(NOW, NOW + (live.TIDE_PERIOD * 3))
    assert len(w) >= 3 and all(a < b for a, b in w)
