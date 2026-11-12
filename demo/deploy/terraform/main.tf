data "aws_eks_cluster" "provided" {
  name = var.eks_cluster_name
}

data "aws_s3_bucket" "provided" {
  count  = var.create_reports_bucket ? 0 : 1
  bucket = var.reports_bucket_name
}

data "aws_ecr_repository" "provided" {
  count = var.create_ecr_repository ? 0 : 1
  name  = var.ecr_repository_name
}

locals {
  reports_bucket_arn = var.create_reports_bucket ? aws_s3_bucket.reports[0].arn : data.aws_s3_bucket.provided[0].arn
  repository_url     = var.create_ecr_repository ? aws_ecr_repository.app[0].repository_url : data.aws_ecr_repository.provided[0].repository_url
  create_batch_role  = var.manage_batch_identity && var.existing_batch_role_arn == null
  batch_role_arn     = local.create_batch_role ? aws_iam_role.batch[0].arn : var.existing_batch_role_arn

  # 배치는 완성된 JSON 하나를 조건부 PUT한다. List/Get/Delete 권한은 필요하지 않다.
  batch_policy = {
    Version = "2012-10-17"
    Statement = concat([
      {
        Sid      = "WriteReportsOnly"
        Effect   = "Allow"
        Action   = ["s3:PutObject"]
        Resource = ["${local.reports_bucket_arn}/${var.reports_prefix}/*"]
      }
      ], var.reports_kms_key_arn == null ? [] : [
      {
        Sid      = "EncryptReportsWithProvidedKey"
        Effect   = "Allow"
        Action   = ["kms:GenerateDataKey"]
        Resource = [var.reports_kms_key_arn]
      }
    ])
  }

  batch_trust_policy = {
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "pods.eks.amazonaws.com" }
      Action    = ["sts:AssumeRole", "sts:TagSession"]
      Condition = {
        StringEquals = {
          "aws:RequestTag/eks-cluster-arn"            = data.aws_eks_cluster.provided.arn
          "aws:RequestTag/kubernetes-namespace"       = var.namespace
          "aws:RequestTag/kubernetes-service-account" = "demurrage-batch"
        }
      }
    }]
  }
}

resource "aws_s3_bucket" "reports" {
  count         = var.create_reports_bucket ? 1 : 0
  bucket        = var.reports_bucket_name
  force_destroy = false

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_public_access_block" "reports" {
  count                   = var.create_reports_bucket ? 1 : 0
  bucket                  = aws_s3_bucket.reports[0].id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "reports" {
  count  = var.create_reports_bucket ? 1 : 0
  bucket = aws_s3_bucket.reports[0].id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_versioning" "reports" {
  count  = var.create_reports_bucket ? 1 : 0
  bucket = aws_s3_bucket.reports[0].id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "reports" {
  count  = var.create_reports_bucket ? 1 : 0
  bucket = aws_s3_bucket.reports[0].id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = var.reports_kms_key_arn == null ? "AES256" : "aws:kms"
      kms_master_key_id = var.reports_kms_key_arn
    }
  }
}

resource "aws_s3_bucket_policy" "reports_tls" {
  count  = var.create_reports_bucket ? 1 : 0
  bucket = aws_s3_bucket.reports[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "RequireTLS"
      Effect    = "Deny"
      Principal = "*"
      Action    = "s3:*"
      Resource  = [aws_s3_bucket.reports[0].arn, "${aws_s3_bucket.reports[0].arn}/*"]
      Condition = { Bool = { "aws:SecureTransport" = "false" } }
    }]
  })
}

resource "aws_ecr_repository" "app" {
  count                = var.create_ecr_repository ? 1 : 0
  name                 = var.ecr_repository_name
  image_tag_mutability = "IMMUTABLE"
  force_delete         = false

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_iam_role" "batch" {
  count              = local.create_batch_role ? 1 : 0
  name               = "demurrage-${var.environment}-batch"
  assume_role_policy = jsonencode(local.batch_trust_policy)
}

resource "aws_iam_role_policy" "batch" {
  count  = local.create_batch_role ? 1 : 0
  name   = "reports-write-only"
  role   = aws_iam_role.batch[0].id
  policy = jsonencode(local.batch_policy)
}

resource "aws_eks_pod_identity_association" "batch" {
  count           = var.manage_batch_identity ? 1 : 0
  cluster_name    = data.aws_eks_cluster.provided.name
  namespace       = var.namespace
  service_account = "demurrage-batch"
  role_arn        = local.batch_role_arn

  lifecycle {
    precondition {
      condition     = var.existing_batch_role_arn == null || can(regex("^arn:aws:iam::${var.aws_account_id}:role/", var.existing_batch_role_arn))
      error_message = "Pod Identity의 역할은 제공받은 AWS 계정의 역할이어야 합니다."
    }
  }
}
