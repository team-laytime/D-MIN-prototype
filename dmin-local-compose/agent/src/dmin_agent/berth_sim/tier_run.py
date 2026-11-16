"""체선료 구간 최적화 한 번 실행 (run_cpsat.py · serve_cpsat.py 공통).

  데이터 준비(load_context) → CP-SAT 체선료 구간(cpsat_model.solve_tiers) → 화면용 결과(tier_payload)
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from .berth_availability import availability_from_plan
from .cli import apply_typhoons
from .cost_table import CostRow, build_costs
from .cpsat_model import BAND, MIN_DIFF, PER_TIER, TIERS, TIME_LIMIT_S, SolveResult, hint_from, home_from, solve_tiers, stays_for
from .dummy_data import get_data
from .feasibility import FeasibilityTable, build_table
from .master_data import MasterData, load_master
from .models import Vessel
from .report_cpsat import tier_payload
from .sample_loader import load_berth_plan
from .scenario import ScenarioResult, evaluate_rules
from .step3_berth_block import BerthBlock
from .synth import SynthData
from .tanks import TankSet, build_tanks


@dataclass
class Context:
    sequences: dict[str, list[Vessel]]
    original_etb: dict[str, datetime]
    master: MasterData
    data: SynthData
    data_src: str
    blocks: list[BerthBlock]
    available: dict[str, datetime]
    table: FeasibilityTable
    costs: dict[tuple[str, str], CostRow]
    base: ScenarioResult
    stays: dict
    tanks: TankSet


def load_context(data_path: str, year: int, dummy_dir: Path, seed: int, blocks: list[BerthBlock],
                 typhoons: list | None = None, track=None) -> Context:
    sequences, original_etb = load_berth_plan(data_path, year)
    master = load_master(data_path)
    data, src = get_data(sequences, master, dummy_dir, seed)
    data = apply_typhoons(data, typhoons or [], track)
    available = availability_from_plan(sequences, original_etb, list(master.berths))
    table = build_table(sequences, data, master, available, blocks, step=timedelta(minutes=5))
    costs = build_costs(table, data, blocks)
    base = evaluate_rules(sequences, data, blocks, "최적화 전", available)
    tanks = build_tanks(sequences, data, table.start, int(table.n_slots * table.step.total_seconds() // 3600))
    return Context(sequences, original_etb, master, data, src, blocks, available, table, costs, base,
                   stays_for(table, costs), tanks)


@dataclass(frozen=True)
class TierRun:
    results: list[SolveResult]
    payloads: list[dict]


def run_tiers(
    ctx: Context, tiers: int = TIERS, per_tier: int = PER_TIER, band: float = BAND, min_diff: int = MIN_DIFF,
    time_limit_s: float = TIME_LIMIT_S, on_result: Callable[[SolveResult, dict], None] | None = None,
) -> TierRun:
    payloads: list[dict] = []

    def each(res: SolveResult) -> None:
        if on_result:
            on_result(res, tier_payload(ctx.table, ctx.costs, res, ctx.tanks, ctx.data))

    results = solve_tiers(ctx.table, ctx.costs, ctx.data, ctx.stays, home_from(ctx.sequences), hint_from(ctx.base.outcomes),
                          tiers, per_tier, band, time_limit_s, min_diff, each, tanks=ctx.tanks)
    payloads = [tier_payload(ctx.table, ctx.costs, r, ctx.tanks, ctx.data) for r in results]
    return TierRun(results, payloads)
