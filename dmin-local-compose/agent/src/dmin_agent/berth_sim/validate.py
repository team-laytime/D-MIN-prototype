"""검증: 가상 데이터가 실제 기준정보와 맞는지, 규칙이 실제 접안계획을 얼마나 재현하는지.

A. 가상 데이터 검증 (모두 통과해야 함)
  A1 실제 배정 부두 적합성 (berth_fit: DWT · LOA · PBL · Draft · 제품)
  A2 QTY <= DWT (적재량이 선박 크기를 넘지 않음)
  A3 실제 ETB를 넣으면 ETB 이후 계산식이 실제 ETU를 재현 (±1분)
  A4 정박개시 분기가 여러 경우를 지나감 (가상 데이터가 한쪽으로 쏠리지 않음)
B. 실제 접안계획 대비 규칙 재현 (정보 제공)
  B1 ① 규칙만으로 계산한 ETB가 실제 ETB와 같은 선박 수
  B2 실제 계획에서 같은 부두에 두 척이 동시에 접안한 경우 (규칙은 한 부두 한 척으로 가정)
  B3 실제 계획이 ① 규칙보다 늦게 접안시킨 선박 (규칙 밖의 대기: 미반영 제약 또는 운영 판단)
  B4 선박별 접안 가능 부두 수 (최적화에서 옮길 수 있는 후보 부두)
"""

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta

from .berth_fit import allowed_berths, fits
from .master_data import MasterData
from .models import Vessel
from .scenario import ScenarioResult
from .step1_prev_fix import schedule
from .synth import SynthData

MINUTE = timedelta(minutes=1)


@dataclass(frozen=True)
class Check:
    code: str
    title: str
    passed: bool | None  # None = 정보 제공용
    detail: str
    items: tuple[str, ...] = ()


def _check(code: str, title: str, bad: list[str], total: int) -> Check:
    return Check(code, title, not bad, f"{total - len(bad)}/{total} 통과", tuple(bad))


def validate_synthetic(
    sequences: dict[str, list[Vessel]], master: MasterData, data: SynthData, baseline: ScenarioResult,
    original_etu: dict[str, datetime],
) -> list[Check]:
    vessels = [v for seq in sequences.values() for v in seq]
    n = len(vessels)
    a1, a2, a3 = [], [], []
    for v in vessels:
        p = data.profiles[v.vessel_id]
        reasons = fits(dims_of(p), v.berth, master)
        if reasons:
            a1.append(f"{v.vessel_id} #{v.berth}: " + ", ".join(reasons))
        if p.qty > p.dwt:
            a2.append(f"{v.vessel_id}: QTY {p.qty:,.0f} > DWT {p.dwt:,.0f}")
    # A3은 가상 데이터(QTY 역산) 검사라 기상 중단 없이 본다 — 기상은 실제 계획에 이미 녹아 있다고 본다
    if data.weather is not None:
        from dataclasses import replace as _replace

        from .scenario import evaluate_fixed_etb

        baseline = evaluate_fixed_etb(sequences, {o.vessel.vessel_id: o.etb for o in baseline.outcomes},
                                      _replace(data, weather=None))
    for o in baseline.outcomes:
        vid = o.vessel.vessel_id
        if o.after is None or abs(o.after.etu - original_etu[vid]) > MINUTE:
            got = f"{o.after.etu:%m/%d %H:%M}" if o.after else o.alert
            a3.append(f"{vid}: 계산 ETU {got} ≠ 실제 {original_etu[vid]:%m/%d %H:%M}")

    kinds = Counter(_branch_kind(o.after.laytime_start.reason) for o in baseline.outcomes if o.after)
    a4 = Check(
        "A4", "정박개시 분기 분포", len(kinds) >= 4,
        ", ".join(f"{k} {c}" for k, c in kinds.most_common()),
    )
    return [
        _check("A1", "배정 부두 적합성 (DWT·LOA·PBL·Draft·제품)", a1, n),
        _check("A2", "QTY ≤ DWT", a2, n),
        _check("A3", "실제 ETB → 실제 ETU 재현", a3, n),
        a4,
    ]


def dims_of(p) -> "ShipDims":
    from .berth_fit import ShipDims

    return ShipDims(p.dwt, p.loa, p.pbl, p.draft, p.cargo_group)


def berth_options(sequences: dict[str, list[Vessel]], master: MasterData, data: SynthData) -> dict[str, list[str]]:
    """선박별 접안 가능 부두 (실제 배정 부두 포함)."""
    return {
        v.vessel_id: allowed_berths(dims_of(data.profiles[v.vessel_id]), master)
        for seq in sequences.values() for v in seq
    }


def check_berth_options(options: dict[str, list[str]]) -> Check:
    counts = Counter(len(b) for b in options.values())
    movable = sum(1 for b in options.values() if len(b) > 1)
    return Check(
        "B4", "선박별 접안 가능 부두 수", None, f"다른 부두로 옮길 수 있는 선박 {movable}/{len(options)}척",
        tuple(f"가능 부두 {k}곳: {c}척" for k, c in sorted(counts.items())),
    )


def _branch_kind(reason: str) -> str:
    for key, name in (("Early", "Early Loading"), ("Miss", "LayCan Miss"), ("LayCan From", "LayCan From 시각"),
                      ("LayCan 내", "LayCan 내 +6h"), ("<= 일출", "일출 전 07시"), (">= 일몰", "일몰 후 다음날 07시"),
                      ("< 일몰", "일출~일몰 +6h")):
        if key in reason:
            return name + (" → ETB" if "더 이르므로" in reason else "")
    return reason


def validate_against_real(sequences: dict[str, list[Vessel]], original_etb: dict[str, datetime]) -> list[Check]:
    res = schedule(sequences)
    rows = [r for rs in res.values() for r in rs]
    same = [r for r in rows if r.etb == original_etb[r.vessel_id]]
    later = [r for r in rows if original_etb[r.vessel_id] > r.etb]
    overlaps = []
    for seq in sequences.values():
        for a, b in zip(seq, seq[1:]):
            if original_etb[b.vessel_id] < original_etb[a.vessel_id] + a.stay:
                overlaps.append(
                    f"#{a.berth}: {a.vessel_id} 점유 {original_etb[a.vessel_id]:%m/%d %H:%M}~"
                    f"{original_etb[a.vessel_id] + a.stay:%m/%d %H:%M} 중 {b.vessel_id} 접안 {original_etb[b.vessel_id]:%m/%d %H:%M}"
                )
    waits = sorted(((original_etb[r.vessel_id] - r.etb), r.vessel_id) for r in later)[::-1]
    return [
        Check("B1", "① 규칙 ETB = 실제 ETB", None, f"{len(same)}/{len(rows)}척 일치"),
        Check("B2", "실제 계획의 같은 부두 동시 접안", None, f"{len(overlaps)}건", tuple(overlaps)),
        Check(
            "B3", "실제 계획이 ① 규칙보다 늦게 접안", None, f"{len(later)}/{len(rows)}척",
            tuple(f"{vid}: +{w.total_seconds() / 3600:g}h" for w, vid in waits[:10]),
        ),
    ]
