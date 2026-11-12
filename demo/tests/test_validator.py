"""독립 검증기가 일부러 망가뜨린 일정을 잡아내는지 (위반 후보가 정상 후보로 보이지 않게, FR-36)."""
import copy

from demurrage.engine.build import build_context
from demurrage.engine.optimizer import optimize
from demurrage.engine.validator import validate
from tests.conftest import load_scenario


def _best(rules, sid):
    ctx, _ = build_context(load_scenario(sid), rules)
    res = optimize(ctx, k=1, time_limit_s=10)
    return ctx, dict(res.candidates[0].state.pl)


def _shift(p, minutes):
    q = copy.copy(p)
    for k in ("etb", "work_start", "work_end", "hose_off", "etu", "excl_end"):
        setattr(q, k, getattr(q, k) + minutes)
    return q


def test_clean_candidate_has_no_violation(rules):
    ctx, pl = _best(rules, "S05-storm-rush")
    assert validate(ctx, pl) == []


def test_detects_berthing_inside_weather_restriction(rules):
    ctx, pl = _best(rules, "S05-storm-rush")
    r = next(r for r in ctx.restrictions if r.reason == "WEATHER" and r.covers("#7"))
    vid = next(v for v, p in pl.items() if p.berth == "#7" and p.kind == "MOVABLE")
    pl[vid] = _shift(pl[vid], (r.start + 60) - pl[vid].etb)
    codes = {v["code"] for v in validate(ctx, pl)}
    assert "RESTRICTED" in codes


def test_detects_same_berth_overlap_and_fix_move(rules):
    ctx, pl = _best(rules, "S01-normal")
    on6 = sorted([p for p in pl.values() if p.berth == "#6"], key=lambda p: p.etb)
    a, b = on6[0], on6[1]
    pl[b.vid] = _shift(b, (a.etb + 30) - b.etb)
    pl["F1"] = _shift(pl["F1"], 60)
    codes = {v["code"] for v in validate(ctx, pl)}
    assert "OVERLAP" in codes and "FIX_MOVED" in codes


def test_detects_same_cargo_group_simultaneous(rules):
    ctx, pl = _best(rules, "VAL-01-combo")
    diesel = [p for p in pl.values() if ctx.vessels[p.vid].cargo_group == "DIESEL" and p.berth in ("#6", "#7", "#8") and p.kind == "MOVABLE"]
    a = diesel[0]
    other = next(p for p in pl.values() if p.vid != a.vid and ctx.vessels[p.vid].cargo_group == "DIESEL" and p.berth != a.berth)
    pl[a.vid] = _shift(a, other.etb + 30 - a.etb)
    codes = {v["code"] for v in validate(ctx, pl)}
    assert "SIMULTANEOUS" in codes
