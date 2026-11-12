"""가상 시나리오를 계산해 검증된 보고서 JSON 하나를 저장하는 CronJob 입구.

python -m demurrage.jobs.daily_report --output-dir runtime/reports --date 2026-11-11
REPORTS_BUCKET=... python -m demurrage.jobs.daily_report

기본 입력은 이미지에 포함된 가상 시나리오다. 실시간 수집이나 현업 확정은 하지 않는다.
S3 조건부 쓰기로 같은 논리 키의 기존 결과를 보존한다. 계산 자체의 중복 실행은 가능하다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from ..agents.orchestrator import run_pipeline
from ..llm.adapter import DisabledLLM
from ..rules.loader import DATA_DIR

KST = timezone(timedelta(hours=9))


def load_scenario(identifier: str) -> dict:
    """임의 파일 대신 배포 이미지에 포함된 시나리오 ID만 허용한다."""
    for path in sorted((DATA_DIR / "scenarios").rglob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        if document.get("id") == identifier:
            return document
    raise ValueError(f"알 수 없는 시나리오 ID: {identifier}")


def report_artifact(document: dict, business_date: date, *, release: str,
                    time_limit_s: float = 20.0) -> tuple[str, bytes]:
    if not math.isfinite(time_limit_s) or not 0 < time_limit_s <= 120:
        raise ValueError("time_limit_s는 0 초과 120 이하의 유한한 값이어야 합니다")
    run = run_pipeline(document, llm=DisabledLLM(), time_limit_s=time_limit_s)
    if run["status"] != "OK" or not run.get("checks") or not all(item["ok"] for item in run["checks"]):
        raise ValueError("계산 입력·후보·실행 검증을 통과하지 못해 보고서를 저장하지 않습니다")
    identity = {"schema_version": 1, "date": business_date.isoformat(), "release": release,
                "input": document, "versions": run["versions"], "fingerprint": run["fingerprint"]}
    digest = hashlib.sha256(json.dumps(identity, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:24]
    scenario = re.sub(r"[^A-Za-z0-9_-]", "_", run["scenario"]["id"])[:80] or "scenario"
    relative_key = f"{business_date.isoformat()}/{scenario}/{digest}.json"
    artifact = {"schema_version": 1, "business_date": business_date.isoformat(), "release": release,
                "input_source": "bundled-scenario", "notice": "가상 데이터 · 의사결정 보조용 · 확정·발송하지 않음",
                "run": run}
    return relative_key, json.dumps(artifact, ensure_ascii=False, sort_keys=True).encode("utf-8")


def save_local(directory: Path, key: str, body: bytes) -> bool:
    """완성된 파일만 노출하고, 이미 있는 결과를 덮어쓰지 않는다."""
    destination = directory / key
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=destination.parent) as temporary:
        temporary.write(body)
        temporary.flush()
        try:
            os.link(temporary.name, destination)
        except FileExistsError:
            return False
    return True


def save_s3(client, bucket: str, key: str, body: bytes, *, account_id: str) -> bool:
    from botocore.exceptions import ClientError

    try:
        client.put_object(Bucket=bucket, Key=key, Body=body, ContentType="application/json; charset=utf-8",
                          IfNoneMatch="*", ExpectedBucketOwner=account_id)
    except ClientError as error:
        # 403(권한), 409(경합), 네트워크 오류는 성공으로 숨기지 않는다. Job이 실패·재시도한다.
        if error.response.get("ResponseMetadata", {}).get("HTTPStatusCode") == 412:
            return False
        raise
    return True


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", default=os.environ.get("BATCH_SCENARIO", "S05-storm-rush"))
    parser.add_argument("--date", type=date.fromisoformat,
                        default=os.environ.get("BATCH_DATE") or datetime.now(KST).date().isoformat())
    parser.add_argument("--release", default=os.environ.get("RELEASE_ID", "local"))
    parser.add_argument("--prefix", default=os.environ.get("REPORTS_PREFIX", "reports"))
    parser.add_argument("--time-limit", type=float, default=20.0)
    target = parser.add_mutually_exclusive_group()
    target.add_argument("--output-dir", type=Path)
    target.add_argument("--bucket", default=os.environ.get("REPORTS_BUCKET"))
    args = parser.parse_args(argv)
    stage = "configuration"
    try:
        prefix = args.prefix.strip("/")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9/_-]*", prefix) or ".." in prefix:
            raise ValueError("REPORTS_PREFIX는 영문·숫자·/·_·- 로 된 비어 있지 않은 경로여야 합니다")
        if not args.output_dir and (not args.bucket or args.bucket.startswith("REPLACE")):
            raise ValueError("REPORTS_BUCKET 또는 --output-dir이 필요합니다")
        account_id = os.environ.get("AWS_ACCOUNT_ID", "")
        if not args.output_dir and not re.fullmatch(r"[0-9]{12}", account_id):
            raise ValueError("S3 저장에는 버킷 소유자의 AWS_ACCOUNT_ID(12자리)가 필요합니다")
        stage = "calculation"
        relative_key, body = report_artifact(load_scenario(args.scenario), args.date,
                                             release=args.release, time_limit_s=args.time_limit)
        key = f"{prefix}/{relative_key}"
        stage = "storage"
        if args.output_dir:
            written = save_local(args.output_dir, key, body)
            location = str(args.output_dir / key)
        else:
            import boto3
            from botocore.config import Config

            client = boto3.client("s3", config=Config(connect_timeout=5, read_timeout=30,
                                                      retries={"mode": "standard", "max_attempts": 3}))
            written = save_s3(client, args.bucket, key, body, account_id=account_id)
            location = f"s3://{args.bucket}/{key}"
        print(json.dumps({"event": "daily_report", "status": "created" if written else "already_exists",
                          "business_date": args.date.isoformat(), "location": location}, ensure_ascii=False))
        return 0
    except Exception as error:
        # AWS·DB 접속 정보나 입력 원문이 들어갈 수 있는 예외 본문은 로그에 남기지 않는다.
        print(json.dumps({"event": "daily_report", "status": "failed", "stage": stage,
                          "error_type": type(error).__name__},
                         ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
