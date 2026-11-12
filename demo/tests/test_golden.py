"""성공기준 ① — 손계산 정답 세트 대비 자동 계산 일치율 100% (FR-50, NFR-05)."""
from demurrage.verify import run_golden


def test_golden_set_matches_hand_calculation_100_percent():
    r = run_golden()
    assert r["errors"] == []
    assert r["total"] >= 250
    assert r["mismatches"] == [], r["mismatches"][:5]
    assert r["match_rate"] == 1.0


def test_every_golden_check_cites_rule_ids(rules):
    r = run_golden(quick=True)
    for row in r["checks"]:
        assert row["rule_ids"], row
        for rid in row["rule_ids"]:
            assert rid in rules.rule_index, f"정답 세트가 규칙 표에 없는 ID를 씀: {rid}"
