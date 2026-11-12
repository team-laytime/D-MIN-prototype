"""AWS 접속 없이 배포값을 검증하고 Kustomize로 EKS YAML을 렌더링한다.

python scripts/render_eks.py --image ACCOUNT.dkr.ecr.REGION.amazonaws.com/REPO:TAG \
    --reports-bucket BUCKET --region ap-northeast-2 --output deploy/rendered/eks.yaml
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "deploy" / "k8s" / "base"
ECR_IMAGE = re.compile(r"(?P<account>[0-9]{12})\.dkr\.ecr\.(?P<region>[a-z0-9-]+)\.amazonaws\.com/"
                       r"(?P<repository>[a-z0-9][a-z0-9/_.-]*)(?::(?P<tag>[A-Za-z0-9_][A-Za-z0-9_.-]{0,127})"
                       r"|@(?P<digest>sha256:[a-f0-9]{64}))")


def overlay(image: str, bucket: str, region: str, namespace: str, *, prefix: str = "reports",
            enable_cron: bool = False) -> dict:
    match = ECR_IMAGE.fullmatch(image)
    if not match or match["account"] == "000000000000" or match["region"] != region:
        raise ValueError("--image에는 --region과 같은 리전의 실제 ECR 주소와 고정 태그/digest가 필요합니다")
    release = match["tag"] or match["digest"]
    if release.lower() == "latest" or "replace" in release.lower():
        raise ValueError("latest·자리표시자 대신 배포 버전이나 Git SHA 태그를 사용하세요")
    if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", bucket) or ".." in bucket:
        raise ValueError("--reports-bucket에는 실제 S3 버킷 이름이 필요합니다")
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", namespace):
        raise ValueError("--namespace는 63자 이하의 Kubernetes DNS label이어야 합니다")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9/_-]*", prefix):
        raise ValueError("--reports-prefix에는 영문·숫자·/·_·- 로 된 경로가 필요합니다")
    replacement = {"name": "demurrage-app", "newName": image.split(":", 1)[0].split("@", 1)[0]}
    if match["tag"]:
        replacement["newTag"] = match["tag"]
    else:
        replacement["digest"] = match["digest"]
    return {"apiVersion": "kustomize.config.k8s.io/v1beta1", "kind": "Kustomization",
            "namespace": namespace, "resources": [str(BASE)], "images": [replacement],
            "configMapGenerator": [{"name": "demurrage-config", "behavior": "merge", "literals": [
                f"AWS_DEFAULT_REGION={region}", f"AWS_ACCOUNT_ID={match['account']}", f"REPORTS_BUCKET={bucket}",
                f"REPORTS_PREFIX={prefix}", f"RELEASE_ID={release}"]}],
            "patches": [{"target": {"kind": "CronJob", "name": "demurrage-daily-report"},
                         "patch": json.dumps([{"op": "replace", "path": "/spec/suspend", "value": not enable_cron}])}]}


def render(configuration: dict) -> str:
    with tempfile.TemporaryDirectory(prefix="demurrage-kustomize-") as temporary:
        shutil.copytree(BASE, Path(temporary) / "base")
        configuration = {**configuration, "resources": ["base"]}
        (Path(temporary) / "kustomization.yaml").write_text(json.dumps(configuration), encoding="utf-8")
        try:
            return subprocess.run(["kubectl", "kustomize", temporary], check=True, capture_output=True, text=True).stdout
        except subprocess.CalledProcessError as error:
            raise ValueError(f"Kustomize 렌더링 실패: {error.stderr.strip()}") from error


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--reports-bucket", required=True)
    parser.add_argument("--region", default="ap-northeast-2")
    parser.add_argument("--namespace", default="demurrage")
    parser.add_argument("--reports-prefix", default="reports")
    parser.add_argument("--enable-cron", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        configuration = overlay(args.image, args.reports_bucket, args.region, args.namespace,
                                prefix=args.reports_prefix, enable_cron=args.enable_cron)
        manifest = render(configuration)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.error(str(error))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(manifest, encoding="utf-8")
    print(f"렌더링 완료: {args.output} (CronJob {'활성' if args.enable_cron else '중지'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
