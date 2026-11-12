import json
import pathlib

import pytest

from demurrage.rules.loader import DATA_DIR, load_rules

ROOT = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def rules():
    return load_rules()


def load_scenario(sid: str) -> dict:
    for p in sorted((DATA_DIR / "scenarios").rglob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        if d["id"] == sid:
            return d
    raise KeyError(sid)


@pytest.fixture(scope="session")
def s5():
    return load_scenario("S05-storm-rush")


@pytest.fixture(scope="session")
def s5_run(s5):
    from demurrage.agents.orchestrator import run_pipeline
    return run_pipeline(s5)
