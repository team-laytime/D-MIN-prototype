"""NFR-02 재현성, NFR-04 규칙 분리·버전, NFR-01 계산 경로에 LLM 없음."""
import ast
import copy
import json
import pathlib

from demurrage.agents.orchestrator import run_pipeline
from demurrage.engine.intake import scenario_hash
from demurrage.rules.loader import load_rules

SRC = pathlib.Path(__file__).resolve().parents[1] / "src" / "demurrage"


def test_same_input_same_result_10_times(s5):
    fps = {run_pipeline(s5, with_sensitivity=False)["fingerprint"] for _ in range(10)}
    assert len(fps) == 1


def test_scenario_hash_survives_json_roundtrip_through_browser(s5):
    js_like = json.loads(json.dumps(s5).replace(".0,", ",").replace(".0}", "}"))
    assert scenario_hash(js_like) == scenario_hash(s5)


def test_rule_table_change_changes_result_without_code_change(s5):
    base = run_pipeline(s5, with_sensitivity=False)
    patched = run_pipeline(s5, rules_patch={"terminal.shifting_hours.#6.switching": 4}, with_sensitivity=False)
    assert base["versions"]["rules"]["version"] != patched["versions"]["rules"]["version"]
    assert patched["versions"]["rules"]["patch"] == {"terminal.shifting_hours.#6.switching": 4}
    assert base["baseline"]["total_cents"] != patched["baseline"]["total_cents"]
    again = run_pipeline(s5, with_sensitivity=False)                      # 이전 규칙으로 다시 → 같은 결과
    assert again["fingerprint"] == base["fingerprint"]


def test_calculation_modules_never_import_llm():
    """금액·시각·판정 경로(engine, domain, rules)에 LLM import가 0건(코드 점검)."""
    for sub in ("engine", "domain", "rules"):
        for f in (SRC / sub).glob("*.py"):
            tree = ast.parse(f.read_text(encoding="utf-8"))
            names = [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)] + \
                    [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
            assert not any("llm" in x or "anthropic" in x for x in names), f"{f.name}: {names}"


def test_rule_ids_in_code_are_registered():
    rules = load_rules()
    import re
    used = set()
    for f in (SRC / "engine").glob("*.py"):
        used |= set(re.findall(r'"((?:ETB|LAY|DEM|WRK|ELG|OPT|WX)-\d{2})"', f.read_text(encoding="utf-8")))
    missing = used - set(rules.rule_index)
    assert not missing, f"코드가 쓰는데 규칙 표에 없는 ID: {missing}"


def test_cfr_plus_halves_crude_laytime_and_is_flagged_unconfirmed():
    """FR-27(Could): CFR Plus 원유선 Laytime 1/2 — 규칙 확정 전이라 '미확정 규칙 포함'이 붙는다."""
    from tests.conftest import load_scenario
    doc = copy.deepcopy(load_scenario("S14-contract-terms"))       # K3 = 계약서 CT-2611-53(CFR Plus 특례)
    run = run_pipeline(doc, with_sensitivity=False)
    k3 = next(v for v in run["baseline"]["vessels"] if v["vessel_id"] == "K3")
    assert k3["laytime_minutes"] == 36 * 60 // 2
    assert "미확정 규칙 포함" in k3["statuses"] and "× 1/2" in k3["laytime_note"]
    step = next(s for s in k3["sheet"]["steps"] if s["title"].startswith("허용 정박시간"))
    assert any("CT-2611-53" in b["text"] and "Rider 27" in b["text"] for b in step["basis"])
