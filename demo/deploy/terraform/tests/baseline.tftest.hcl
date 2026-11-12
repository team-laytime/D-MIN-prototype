mock_provider "aws" {
  mock_data "aws_eks_cluster" {
    defaults = {
      name     = "provided-eks"
      arn      = "arn:aws:eks:ap-northeast-2:111122223333:cluster/provided-eks"
      endpoint = "https://provided-eks.example.invalid"
    }
  }
  mock_data "aws_s3_bucket" {
    defaults = {
      bucket = "provided-reports"
      arn    = "arn:aws:s3:::provided-reports"
    }
  }
  mock_data "aws_ecr_repository" {
    defaults = {
      repository_url = "111122223333.dkr.ecr.ap-northeast-2.amazonaws.com/demurrage"
    }
  }
}

variables {
  aws_account_id      = "111122223333"
  eks_cluster_name    = "provided-eks"
  reports_bucket_name = "provided-reports"
}

run "provided_resources_are_read_only_by_default" {
  command = plan
  assert {
    condition = (
      length(aws_s3_bucket.reports) == 0 &&
      length(aws_ecr_repository.app) == 0 &&
      length(aws_iam_role.batch) == 0 &&
      length(aws_eks_pod_identity_association.batch) == 0
    )
    error_message = "기본 설정은 제공받은 자원을 생성·변경하지 않아야 합니다."
  }
  assert {
    condition = (
      length(local.batch_policy.Statement[0].Action) == 1 &&
      local.batch_policy.Statement[0].Action[0] == "s3:PutObject" &&
      length(local.batch_policy.Statement[0].Resource) == 1 &&
      local.batch_policy.Statement[0].Resource[0] == "arn:aws:s3:::provided-reports/reports/*"
    )
    error_message = "배치의 권한은 보고서 prefix에 쓰기로 제한해야 합니다."
  }
}

run "reuse_provided_role_for_pod_identity" {
  command = plan
  variables {
    manage_batch_identity   = true
    existing_batch_role_arn = "arn:aws:iam::111122223333:role/provided-batch"
  }
  assert {
    condition = (
      length(aws_iam_role.batch) == 0 &&
      aws_eks_pod_identity_association.batch[0].role_arn == "arn:aws:iam::111122223333:role/provided-batch"
    )
    error_message = "제공받은 역할을 사용하면 IAM 역할을 중복 생성하지 않아야 합니다."
  }
}

run "create_only_explicitly_owned_resources" {
  command = plan
  variables {
    create_reports_bucket = true
    create_ecr_repository = true
    manage_batch_identity = true
  }
  assert {
    condition = (
      length(aws_s3_bucket.reports) == 1 &&
      length(aws_ecr_repository.app) == 1 &&
      length(aws_iam_role.batch) == 1 &&
      length(aws_eks_pod_identity_association.batch) == 1
    )
    error_message = "소유권을 선택한 자원과 배치 역할만 생성해야 합니다."
  }
  assert {
    condition = (
      aws_s3_bucket_public_access_block.reports[0].block_public_policy &&
      aws_ecr_repository.app[0].image_tag_mutability == "IMMUTABLE" &&
      !aws_s3_bucket.reports[0].force_destroy
    )
    error_message = "보고서는 비공개·삭제 보호, 이미지 태그는 고정이어야 합니다."
  }
}

run "reject_placeholder_account" {
  command = plan
  variables {
    aws_account_id = "000000000000"
  }
  expect_failures = [var.aws_account_id]
}

run "reject_cross_account_pod_role" {
  command = plan
  variables {
    manage_batch_identity   = true
    existing_batch_role_arn = "arn:aws:iam::999988887777:role/wrong-account"
  }
  expect_failures = [aws_eks_pod_identity_association.batch[0]]
}
