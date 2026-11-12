variable "aws_region" {
  description = "제공받은 AWS 리전. EKS·ECR·보고서 버킷은 같은 리전을 기준으로 한다."
  type        = string
  default     = "ap-northeast-2"
}

variable "aws_account_id" {
  description = "제공받은 AWS 계정 ID. provider가 다른 계정에 적용되는 것을 막는다."
  type        = string
  validation {
    condition     = can(regex("^[0-9]{12}$", var.aws_account_id)) && var.aws_account_id != "000000000000"
    error_message = "실제 AWS 계정 ID 12자리를 입력하세요."
  }
}

variable "environment" {
  type    = string
  default = "dev"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{0,19}$", var.environment))
    error_message = "environment는 소문자로 시작하는 20자 이하 이름이어야 합니다."
  }
}

variable "eks_cluster_name" {
  description = "기존 EKS 이름. 이 구성에서는 EKS·VPC·노드를 생성하거나 변경하지 않는다."
  type        = string
}

variable "namespace" {
  description = "YAML 렌더링의 --namespace와 동일한 팀 namespace. 생성은 YAML/제공자가 담당한다."
  type        = string
  default     = "demurrage"
  validation {
    condition     = can(regex("^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$", var.namespace))
    error_message = "유효한 Kubernetes namespace 이름이 필요합니다."
  }
}

variable "reports_bucket_name" {
  description = "같은 AWS 계정·리전의 보고서 버킷 이름. 기존 버킷은 조회만 한다."
  type        = string
  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$", var.reports_bucket_name))
    error_message = "S3 버킷 이름이 필요합니다."
  }
}

variable "reports_prefix" {
  description = "배치가 쓸 경로. YAML 렌더링의 --reports-prefix와 일치시킨다."
  type        = string
  default     = "reports"
  validation {
    condition     = can(regex("^[A-Za-z0-9][A-Za-z0-9/_-]*$", var.reports_prefix)) && !endswith(var.reports_prefix, "/")
    error_message = "영문·숫자·/·_·- 경로를 입력하고 끝의 /는 제외하세요."
  }
}

variable "create_reports_bucket" {
  description = "새 버킷 생성 권한과 소유 범위를 확인한 경우에만 true. 기존 버킷 이름에는 false."
  type        = bool
  default     = false
}

variable "reports_kms_key_arn" {
  description = "기존 버킷이 SSE-KMS이면 해당 키 ARN. 배치에 GenerateDataKey 권한을 추가한다."
  type        = string
  default     = null
  nullable    = true
  validation {
    condition     = var.reports_kms_key_arn == null || can(regex("^arn:aws:kms:", var.reports_kms_key_arn))
    error_message = "KMS 키 ARN 또는 null이어야 합니다."
  }
}

variable "ecr_repository_name" {
  description = "동일 계정·리전의 앱 이미지 저장소 이름."
  type        = string
  default     = "demurrage"
}

variable "create_ecr_repository" {
  description = "새 ECR 생성이 팀의 담당 범위일 때만 true."
  type        = bool
  default     = false
}

variable "manage_batch_identity" {
  description = "Pod Identity 연결을 Terraform으로 관리할지 선택. 제공자가 관리하면 false."
  type        = bool
  default     = false
}

variable "existing_batch_role_arn" {
  description = "제공받은 배치 역할. null이면 manage_batch_identity=true일 때 역할·정책을 새로 만든다."
  type        = string
  default     = null
  nullable    = true
  validation {
    condition     = var.existing_batch_role_arn == null || can(regex("^arn:aws:iam::[0-9]{12}:role/", var.existing_batch_role_arn))
    error_message = "IAM 역할 ARN 또는 null이어야 합니다."
  }
}
