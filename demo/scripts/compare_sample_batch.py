"""Compare a demo API run with a one-off Job from the local CronJob."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path, PurePosixPath
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
from uuid import uuid4


DEMO = Path(__file__).resolve().parents[1]
KUBECTL = [
    "kubectl", "--kubeconfig", str(DEMO / "runtime/k8s-rehearsal/kubeconfig"),
    "--context", "kind-demurrage-rehearsal", "-n", "demurrage",
]


def api_json(base: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    request = Request(base + path, data=data, headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=60) as response:
        return json.load(response)


def batch_report(scenario: str, job_name: str) -> tuple[dict, dict]:
    job = json.loads(subprocess.check_output([
        *KUBECTL, "create", "job", job_name, "--from=cronjob/demurrage-daily-report",
        "--dry-run=client", "-o", "json",
    ]))
    containers = job["spec"]["template"]["spec"]["containers"]
    container = next(container for container in containers if container["name"] == "daily-report")
    if container.get("args") != ["--output-dir", "/reports"]:
        raise ValueError("kind 실습 가이드의 로컬 오버레이를 적용한 뒤 실행하세요.")
    # Override only this Job. The suspended CronJob remains available for other samples.
    env = container.setdefault("env", [])
    env[:] = [item for item in env if item["name"] != "BATCH_SCENARIO"]
    env.append({"name": "BATCH_SCENARIO", "value": scenario})
    subprocess.run([*KUBECTL, "create", "-f", "-"], input=json.dumps(job), text=True, check=True)
    subprocess.run([*KUBECTL, "wait", "--for=condition=complete", f"job/{job_name}", "--timeout=120s"], check=True)
    event = json.loads(subprocess.check_output([*KUBECTL, "logs", f"job/{job_name}"]))
    path = PurePosixPath(event["location"])
    if (event["status"] not in {"created", "already_exists"} or not path.is_relative_to("/reports")
            or ".." in path.parts or path.suffix != ".json"):
        raise ValueError("Job 로그에서 로컬 보고서 경로를 확인할 수 없습니다.")
    report = json.loads(subprocess.check_output([*KUBECTL, "exec", "deployment/demurrage-api", "--", "cat", str(path)]))
    return report, event


def compare(api: dict, batch: dict) -> None:
    for run in (api, batch):
        if run["status"] != "OK" or not run["checks"] or not all(check["ok"] for check in run["checks"]):
            raise ValueError("API와 배치의 상태 및 실행 검사가 모두 통과해야 합니다.")
        if not run["candidates"] or any(candidate["violations"] for candidate in run["candidates"]):
            raise ValueError("하드 제약을 충족한 후보를 확인할 수 없습니다.")

    for key, name in (("input", "샘플 입력"), ("versions", "엔진·규칙 버전과 탐색 설정"),
                      ("fingerprint", "결과 지문"), ("checks", "실행 검사")):
        if api[key] != batch[key]:
            raise ValueError(f"API와 배치의 {name}이 일치하지 않습니다.")

    if api["baseline"]["total_cents"] != batch["baseline"]["total_cents"]:
        raise ValueError("API와 배치의 기준안 금액이 일치하지 않습니다.")
    if len(api["candidates"]) != len(batch["candidates"]) or any(
        (a["label"], a["total_cents"], a["signature"]) != (b["label"], b["total_cents"], b["signature"])
        for a, b in zip(api["candidates"], batch["candidates"])
    ):
        raise ValueError("API와 배치의 후보 금액 또는 접안 순서가 일치하지 않습니다.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sample = parser.add_mutually_exclusive_group()
    sample.add_argument("--scenario", help="이미지에 포함된 샘플 ID (기본 S05-storm-rush)")
    sample.add_argument("--run-id", help="기존 화면의 ‘보고서 · 메일’에서 확인한 실행 ID")
    parser.add_argument("--port", type=int, default=18080, help="실습 API의 localhost 포트")
    args = parser.parse_args()
    base = f"http://127.0.0.1:{args.port}"

    try:
        run_id = args.run_id
        if run_id is None:
            started = api_json(base, "/api/runs", {"scenario_id": args.scenario or "S05-storm-rush"})
            run_id = started["run_id"]
        run_path = f"/api/runs/{quote(run_id, safe='')}"
        api = api_json(base, run_path)
        scenario = api["scenario"]["id"]
        if api["input"] != api_json(base, f"/api/scenarios/{quote(scenario, safe='')}"):
            raise ValueError("화면 입력이 원본 샘플과 다릅니다. 라이브러리에서 샘플을 다시 계산하세요.")

        job_name = f"demurrage-demo-{uuid4().hex[:10]}"
        report, event = batch_report(scenario, job_name)
        batch = report["run"]
        compare(api, batch)
    except (URLError, OSError, KeyError, ValueError, StopIteration, subprocess.CalledProcessError) as error:
        parser.exit(1, f"대조 실패. {error}\n")

    out = DEMO / "out/k8s-sample" / job_name
    out.mkdir(parents=True)
    (out / "batch-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "batch-report.html").write_text(batch["report"]["html"], encoding="utf-8")
    baseline = api["baseline"]["total_cents"]
    first = api["candidates"][0]["total_cents"]
    rows = "\n".join(
        f"| {candidate['label']} | ${candidate['total_cents'] / 100:,.2f} | 0건 |"
        for candidate in api["candidates"]
    )
    summary = f"""# 데모 API와 배치 결과 대조

가상 샘플 `{scenario}`의 원본 입력, 엔진·규칙 버전, 탐색 설정, 후보 금액·접안 순서, 결과 지문이 일치했습니다.

| 비교 항목 | API와 배치에서 확인한 값 | 하드 제약 위반 |
|---|---:|---:|
| 도착 순서 기준안 | ${baseline / 100:,.2f} | |
{rows}

기준안 대비 1안의 예상 차이는 **${(baseline - first) / 100:,.2f}**입니다. 양쪽의 실행 검사는 각각 **{len(api['checks'])}/{len(api['checks'])}** 통과했습니다. 결과 지문은 `{api['fingerprint']}`입니다.

- API 실행 `{run_id}`. [API 보고서]({base}{run_path}/report.html)
- 수동 Job `{job_name}`, 보고서 저장 상태 `{event['status']}`, 파일 `{event['location']}`. [배치 보고서](batch-report.html) · [배치 JSON](batch-report.json)

이 금액은 가상 시나리오의 예상 체선료입니다. 담당자는 보고서의 계산 근거와 남은 리스크를 확인한 뒤 접안안을 판단합니다.
"""
    (out / "comparison.md").write_text(summary, encoding="utf-8")
    print(f"대조 통과 · {scenario} · {api['fingerprint']} · 보고서 {event['status']}")
    print(out / "comparison.md")


if __name__ == "__main__":
    main()
