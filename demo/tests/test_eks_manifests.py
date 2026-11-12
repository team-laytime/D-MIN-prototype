"""실제 Kustomize 렌더링으로 이미지·설정 참조·CronJob 활성화 경계를 확인한다."""
import shutil

import pytest
import yaml

from scripts.render_eks import overlay, render

IMAGE = "111122223333.dkr.ecr.ap-northeast-2.amazonaws.com/demurrage:release-v1"


@pytest.fixture
def rendered():
    if not shutil.which("kubectl"):
        pytest.skip("Kustomize 렌더링 검사에는 kubectl이 필요합니다")

    def run(**overrides):
        configuration = {"image": IMAGE, "bucket": "team-reports", "region": "ap-northeast-2", "namespace": "team-demo"}
        configuration.update(overrides)
        return list(yaml.safe_load_all(render(overlay(**configuration))))
    return run


def workloads(documents):
    api = next(doc for doc in documents if doc["kind"] == "Deployment")
    cron = next(doc for doc in documents if doc["kind"] == "CronJob")
    return api["spec"]["template"], cron["spec"]["jobTemplate"]["spec"]["template"]


def test_workloads_use_same_release_and_generated_configuration(rendered):
    documents = rendered()
    assert {doc["metadata"]["namespace"] for doc in documents} == {"team-demo"}
    configuration = next(doc for doc in documents if doc["kind"] == "ConfigMap")
    assert configuration["data"]["REPORTS_BUCKET"] == "team-reports"
    assert configuration["data"]["AWS_ACCOUNT_ID"] == "111122223333"
    assert configuration["data"]["RELEASE_ID"] == "release-v1"
    for template in workloads(documents):
        container = template["spec"]["containers"][0]
        assert container["image"] == IMAGE
        assert container["envFrom"][0]["configMapRef"]["name"] == configuration["metadata"]["name"]
    api = workloads(documents)[0]["spec"]["containers"][0]
    assert api["env"][0]["valueFrom"]["secretKeyRef"]["key"] == "DATABASE_URL"
    assert "DATABASE_URL" not in configuration["data"]


def test_config_change_changes_pod_template_reference(rendered):
    before = workloads(rendered())[0]["spec"]["containers"][0]["envFrom"]
    after = workloads(rendered(bucket="different-reports"))[0]["spec"]["containers"][0]["envFrom"]
    assert before != after  # 새 설정을 apply하면 Deployment가 새 Pod를 시작할 수 있어야 한다.


def test_cron_activation_is_explicit_and_does_not_change_service_account(rendered):
    for enabled in (False, True):
        documents = rendered(enable_cron=enabled)
        cron = next(doc for doc in documents if doc["kind"] == "CronJob")
        assert cron["spec"]["suspend"] is (not enabled)
        assert cron["spec"]["concurrencyPolicy"] == "Forbid"
        batch = workloads(documents)[1]
        assert batch["spec"]["serviceAccountName"] == "demurrage-batch"
        assert batch["spec"]["containers"][0]["command"] == ["python", "-m", "demurrage.jobs.daily_report"]


def test_digest_is_used_without_a_second_tag(rendered):
    image = IMAGE.rsplit(":", 1)[0] + "@sha256:" + "a" * 64
    for template in workloads(rendered(image=image)):
        assert template["spec"]["containers"][0]["image"] == image


@pytest.mark.parametrize("changes", [
    {"image": IMAGE.replace("release-v1", "latest")},
    {"image": IMAGE.replace("111122223333", "000000000000")},
    {"image": IMAGE.replace("release-v1", "REPLACE_ME")},
    {"region": "us-east-1"},
    {"namespace": "wrong_namespace"},
    {"bucket": "REPLACE_ME"},
    {"prefix": "../outside"},
])
def test_bad_connection_values_are_rejected(changes):
    values = {"image": IMAGE, "bucket": "team-reports", "region": "ap-northeast-2", "namespace": "demurrage"}
    values.update(changes)
    with pytest.raises(ValueError):
        overlay(**values)
