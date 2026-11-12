"""시나리오 문서 → 계산 문맥. 입력 검증(FR-02)을 통과해야만 문맥이 만들어진다."""
from __future__ import annotations

from pathlib import Path

from ..data.providers import SunTable
from ..rules.loader import DATA_DIR
from .context import Ctx
from .intake import check_assignability, parse_scenario
from .worktime import WorkModel, load_history
from ..rules.contracts import load_contracts

HISTORY_FILE = "history/shipments.v1.csv"


def build_context(doc: dict, rules, data_dir: Path = None):
    """(Ctx 또는 None, 입력 검증 이슈 목록)."""
    base = Path(data_dir) if data_dir else DATA_DIR
    sc, issues = parse_scenario(doc, rules, load_contracts(base))
    if sc is None:
        return None, issues
    hist_path = base / (doc.get("history_file") or HISTORY_FILE)
    wm = WorkModel(load_history(hist_path), rules.etu_after_work_min, rules.work_start_delay_min)
    issues = issues + check_assignability(sc, rules, wm)
    if any(i.level == "ERROR" for i in issues):
        return None, issues
    sun = SunTable(rules.location, sc.sun_override, base / "public" / "sun_ulsan.json")
    return Ctx(sc, rules, wm, sun), issues
