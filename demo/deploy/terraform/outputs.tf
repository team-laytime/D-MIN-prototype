output "connection" {
  description = "YAML 렌더링·AWS CLI 접속에 사용할 비밀이 아닌 값."
  value = {
    aws_account_id   = var.aws_account_id
    aws_region       = var.aws_region
    eks_cluster_name = data.aws_eks_cluster.provided.name
    eks_endpoint     = data.aws_eks_cluster.provided.endpoint
    namespace        = var.namespace
    repository_url   = local.repository_url
    reports_bucket   = var.reports_bucket_name
    reports_prefix   = var.reports_prefix
    batch_role_arn   = local.batch_role_arn
  }
}

output "batch_policy_json" {
  description = "IAM 생성 권한이 없을 때 제공자에게 전달할 배치 권한 정책."
  value       = jsonencode(local.batch_policy)
}

output "batch_trust_policy_json" {
  description = "Pod Identity 역할을 제공자가 생성할 때 사용할 trust policy."
  value       = jsonencode(local.batch_trust_policy)
}
