"""팀 해석 정답 파일을 만든다 → server/src/test/resources/golden/ (Spring GoldenCrossCheckTest가 Java로 다시 계산해 1분·1센트 대조).

    cd agent && uv run --frozen python tests/make_team_golden.py          # 약 4분 (54척 두 번)

  TEAM-CPSAT-EXAMPLE-3   예시 3척 · 팀 엔진(팀원 코드)          · 정답 $9,252.07
  TEAM-CPSAT-TEAM-W46    팀원 가상 데이터 54척 · 팀 엔진          · 1안 $33,328.62
  PPT-MILP-TEAM-W46      같은 54척 · 기존 엔진(HiGHS) · 팀 해석    · 1안 $33,328.62 (두 엔진이 따로 풀어 같은 값)
요청 파일에는 팀 해석 patch를 넣어 둔다(Spring 실행이 보내는 요청과 같은 모양).
"""
import json
import sys
from pathlib import Path

from dmin_agent import team_engine
from dmin_agent.engine import run as milp
from dmin_agent.engine.pptcalc import profile_patch

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "server" / "src" / "test" / "resources" / "golden"
CASES = {
    "EXAMPLE-3": ROOT / "data" / "samples" / "example-3.json",
    "TEAM-W46": ROOT / "data" / "samples" / "team-week-54.json",
}
JOBS = [("TEAM-CPSAT", "EXAMPLE-3", team_engine.optimize), ("TEAM-CPSAT", "TEAM-W46", team_engine.optimize),
        ("PPT-MILP", "TEAM-W46", milp.optimize)]


def main(only=None):
    for engine, case, solve in JOBS:
        name = f"{engine}-{case}"
        if only and name not in only:
            continue
        req = json.loads(CASES[case].read_text(encoding="utf-8"))
        req["rule_patch"] = profile_patch("team", req.get("rule_patch"))
        resp = solve(json.loads(json.dumps(req)), top=3, time_limit=120)
        resp.pop("elapsed_seconds", None)
        for c in resp.get("components", []):
            c.pop("seconds", None)
        (OUT / f"{name}.request.json").write_text(json.dumps(req, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        (OUT / f"{name}.response.json").write_text(json.dumps(resp, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(name, resp["status"], resp["baseline"] and resp["baseline"]["total_usd"], [c["total_usd"] for c in resp["candidates"]])


if __name__ == "__main__":
    main(set(sys.argv[1:]) or None)
