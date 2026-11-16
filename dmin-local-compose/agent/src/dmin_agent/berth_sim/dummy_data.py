"""가상 더미 데이터 파일: 실제 데이터가 오기 전까지 이 파일을 실제 데이터처럼 읽어서 계산한다.

data/dummy/
  past_shipments.csv     과거 Shipment 실적 — 평균 Rate 산출용 (장표: 선박코드+자재코드+부두 → 부두+자재코드)
                         shipment_id, vessel_code, material_code, berth, work_start, work_end, qty, hours, rate
  current_shipments.csv  이번 접안계획 선박의 선박 제원 · 화물 · 물량(QTY) · 계약(LayCan · LayTime · 일 체선료 · CFR)
                         vessel_id(접안계획 키), vessel_code, ship_class, dwt, grt, loa, pbl, draft, cargo_group, ...
  weather.csv            시간별 풍속 예보 (가상): time, wind_ms, thunder(심한 뇌우), stagnation(대기 정체), typhoon(태풍 경로)
  meta.json              생성 seed · 시각 · 건수
  work_time_check.csv    선박별 작업시간 산출 근거 (조회 방식, 기록 수, 평균 Rate, QTY, 작업시간, ETU)

실제 데이터가 오면 같은 열 이름으로 past_shipments.csv / current_shipments.csv를 바꿔 넣으면 된다.
hours · rate 열은 사람이 보기 위한 값이고, 읽을 때는 work_start · work_end · qty로 다시 계산한다.
"""

import csv
import json
from dataclasses import fields
from datetime import datetime, timedelta
from pathlib import Path

from .after_etb.s1_work_start import ETB_TO_START
from .after_etb.s2_work_finish import PastShipment, average_rate, work_finish
from .after_etb.s3_etu import etu
from .master_data import MasterData
from .models import Vessel
from .synth import SEED, SynthData, VesselProfile, synthesize
from .weather import read_csv as read_weather, write_csv as write_weather

DUMMY_DIR = Path("data/dummy")
PAST = "past_shipments.csv"
CURRENT = "current_shipments.csv"
META = "meta.json"
CHECK = "work_time_check.csv"
WEATHER = "weather.csv"
FMT = "%Y-%m-%d %H:%M"

_DT_FIELDS = {"laycan_from", "laycan_to", "nr_tender"}
_FLOAT_FIELDS = {"dwt", "grt", "draft", "loa", "pbl", "qty", "work_hours", "demurrage_rate"}


def _dt(text: str) -> datetime | None:
    return datetime.strptime(text, FMT) if text else None


def export(data: SynthData, out_dir: Path = DUMMY_DIR) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {k: out_dir / name for k, name in (("past", PAST), ("current", CURRENT), ("meta", META), ("weather", WEATHER))}
    if data.weather is not None:
        write_weather(data.weather, paths["weather"])

    with paths["past"].open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["shipment_id", "vessel_code", "material_code", "berth", "work_start", "work_end", "qty", "hours", "rate"])
        for i, h in enumerate(sorted(data.history, key=lambda h: (h.berth, h.material_code, h.work_start)), 1):
            w.writerow([f"PS-{i:05d}", h.vessel_code, h.material_code, h.berth, f"{h.work_start:{FMT}}",
                        f"{h.work_end:{FMT}}", h.qty, round(h.hours, 2), round(h.qty / h.hours, 1)])

    names = [f.name for f in fields(VesselProfile)]
    with paths["current"].open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow([n if n != "laytime" else "laytime_h" for n in names])
        for p in data.profiles.values():
            row = []
            for n in names:
                val = getattr(p, n)
                if n in _DT_FIELDS:
                    val = f"{val:{FMT}}" if val else ""
                elif n == "laytime":
                    val = val.total_seconds() / 3600
                elif n == "cfr":
                    val = int(val)
                row.append(val)
            w.writerow(row)

    paths["meta"].write_text(json.dumps({
        "seed": data.seed, "generated": f"{datetime.now():{FMT}}", "past_shipments": len(data.history),
        "current_shipments": len(data.profiles), "weather_hours": len(data.weather.hours) if data.weather else 0,
        "note": "가상 더미 데이터 (berth_sim/synth.py로 생성)",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return paths


def load(in_dir: Path = DUMMY_DIR) -> SynthData:
    history = []
    with (in_dir / PAST).open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            history.append(PastShipment(r["vessel_code"], r["material_code"], r["berth"],
                                        _dt(r["work_start"]), _dt(r["work_end"]), float(r["qty"])))
    profiles = {}
    with (in_dir / CURRENT).open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            kw = {}
            for fld in fields(VesselProfile):
                n = fld.name
                if n == "laytime":
                    kw[n] = timedelta(hours=float(r["laytime_h"]))
                elif n in _DT_FIELDS:
                    kw[n] = _dt(r[n])
                elif n in _FLOAT_FIELDS:
                    kw[n] = float(r[n])
                elif n == "cfr":
                    kw[n] = r[n] == "1"
                else:
                    kw[n] = r[n]
            profiles[kw["vessel_id"]] = VesselProfile(**kw)
    meta_path = in_dir / META
    seed = json.loads(meta_path.read_text(encoding="utf-8")).get("seed", SEED) if meta_path.exists() else SEED
    weather = read_weather(in_dir / WEATHER) if (in_dir / WEATHER).exists() else None
    return SynthData(profiles, tuple(history), seed, weather)


def get_data(
    sequences: dict[str, list[Vessel]], master: MasterData, in_dir: Path | None = DUMMY_DIR, seed: int = SEED,
) -> tuple[SynthData, str]:
    """더미 파일이 있으면 읽고, 없으면 메모리에서 만든다. (데이터, 출처 설명)"""
    if in_dir is not None and (in_dir / PAST).exists() and (in_dir / CURRENT).exists():
        data = load(in_dir)
        missing = {v.vessel_id for s in sequences.values() for v in s} - data.profiles.keys()
        if missing:
            raise ValueError(f"{in_dir / CURRENT}에 접안계획 선박이 없습니다: {sorted(missing)[:5]} …")
        return data, f"파일 {in_dir}"
    return synthesize(sequences, master, seed), f"메모리 생성 (seed {seed})"


def work_time_rows(sequences: dict[str, list[Vessel]], data: SynthData, original_etb: dict[str, datetime]) -> list[dict]:
    """선박별 작업시간 산출 근거: 실제 배정 부두 기준."""
    rows = []
    for seq in sequences.values():
        for v in seq:
            p = data.profiles[v.vessel_id]
            rate = average_rate(data.history, p.vessel_code, p.material_code, v.berth)
            start = original_etb[v.vessel_id] + ETB_TO_START
            finish = work_finish(start, p.qty, rate)
            calc_etu = etu(finish)
            real_etu = original_etb[v.vessel_id] + v.stay
            rows.append({
                "vessel_id": v.vessel_id, "berth": v.berth, "vessel_code": p.vessel_code, "material_code": p.material_code,
                "lookup": rate.basis, "records": rate.sample_count, "avg_rate": round(rate.rate, 1),
                "qty": round(p.qty, 1), "work_h": round(p.qty / rate.rate, 2),
                "etb": f"{original_etb[v.vessel_id]:{FMT}}", "work_start": f"{start:{FMT}}",
                "work_finish": f"{finish:{FMT}}", "etu_calc": f"{calc_etu:{FMT}}", "etu_real": f"{real_etu:{FMT}}",
                "etu_diff_min": round((calc_etu - real_etu).total_seconds() / 60, 1),
            })
    return rows


def write_work_time_check(rows: list[dict], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return path
