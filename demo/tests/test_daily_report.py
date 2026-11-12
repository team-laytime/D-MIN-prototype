"""클라우드 배치의 실패·중복 저장 경계. AWS 호출은 Stubber로 차단한다."""
import copy
import json
from datetime import date

import pytest

from demurrage.jobs import daily_report as batch


def test_local_batch_publishes_checked_report_once(tmp_path, capsys):
    args = ["--output-dir", str(tmp_path), "--date", "2026-11-11", "--release", "test-v1"]
    assert batch.main(args) == 0
    first = json.loads(capsys.readouterr().out)
    stored = list(tmp_path.rglob("*.json"))
    assert len(stored) == 1 and first["status"] == "created"
    original = stored[0].read_bytes()
    document = json.loads(original)
    assert document["input_source"] == "bundled-scenario"
    assert document["run"]["status"] == "OK"
    assert all(check["ok"] for check in document["run"]["checks"])
    assert document["run"]["llm"]["calls"] == 0
    assert batch.main(args) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "already_exists"
    assert list(tmp_path.rglob("*.json")) == stored and stored[0].read_bytes() == original


def test_identity_ignores_execution_metadata_but_distinguishes_date_and_release(monkeypatch, s5, s5_run):
    run = copy.deepcopy(s5_run)
    monkeypatch.setattr(batch, "run_pipeline", lambda *a, **kw: copy.deepcopy(run))
    key, _ = batch.report_artifact(s5, date(2026, 11, 11), release="v1")
    run["run_id"] = "another-attempt"
    run["created_at"] = "2026-11-11 09:01"
    repeated, _ = batch.report_artifact(s5, date(2026, 11, 11), release="v1")
    tomorrow, _ = batch.report_artifact(s5, date(2026, 11, 12), release="v1")
    new_release, _ = batch.report_artifact(s5, date(2026, 11, 11), release="v2")
    assert key == repeated and len({key, tomorrow, new_release}) == 3


@pytest.mark.parametrize("bad_run", [
    {"status": "INPUT_ERROR"},
    {"status": "NO_CANDIDATE"},
    {"status": "OK", "checks": [{"ok": False}]},
])
def test_invalid_results_are_not_published(monkeypatch, tmp_path, bad_run, capsys):
    monkeypatch.setattr(batch, "run_pipeline", lambda *a, **kw: bad_run)
    assert batch.main(["--output-dir", str(tmp_path)]) == 1
    assert not list(tmp_path.rglob("*.json"))
    assert json.loads(capsys.readouterr().err)["status"] == "failed"


def test_cloud_requires_bucket_owner_before_computing(monkeypatch, capsys):
    monkeypatch.delenv("AWS_ACCOUNT_ID", raising=False)
    monkeypatch.setattr(batch, "run_pipeline", lambda *a, **kw: pytest.fail("잘못된 설정으로 계산을 시작함"))
    assert batch.main(["--bucket", "test-reports"]) == 1
    assert json.loads(capsys.readouterr().err)["error_type"] == "ValueError"


@pytest.fixture
def s3():
    boto3 = pytest.importorskip("boto3")
    return boto3.client("s3", region_name="ap-northeast-2", aws_access_key_id="testing",
                        aws_secret_access_key="testing")


def test_s3_uses_atomic_conditional_put_and_expected_owner(s3):
    from botocore.stub import Stubber

    with Stubber(s3) as stub:
        stub.add_response("put_object", {}, {"Bucket": "test-reports", "Key": "reports/test.json", "Body": b"{}",
                          "ContentType": "application/json; charset=utf-8", "IfNoneMatch": "*",
                          "ExpectedBucketOwner": "111122223333"})
        assert batch.save_s3(s3, "test-reports", "reports/test.json", b"{}", account_id="111122223333")
        stub.assert_no_pending_responses()


@pytest.mark.parametrize("status, code", [(412, "PreconditionFailed"), (403, "AccessDenied"),
                                         (409, "ConditionalRequestConflict")])
def test_s3_only_treats_existing_object_as_success(s3, status, code):
    from botocore.exceptions import ClientError
    from botocore.stub import Stubber

    with Stubber(s3) as stub:
        stub.add_client_error("put_object", service_error_code=code, http_status_code=status)
        if status == 412:
            assert not batch.save_s3(s3, "test-reports", "reports/test.json", b"{}", account_id="111122223333")
        else:
            with pytest.raises(ClientError):
                batch.save_s3(s3, "test-reports", "reports/test.json", b"{}", account_id="111122223333")
