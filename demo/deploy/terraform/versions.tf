terraform {
  required_version = ">= 1.10.0, < 2.0.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  # 이 버킷은 제공자/관리자가 먼저 준비한다. 앱 보고서 버킷과 수명을 분리한다.
  backend "s3" {}
}

provider "aws" {
  region              = var.aws_region
  allowed_account_ids = [var.aws_account_id]

  default_tags {
    tags = {
      Project     = "demurrage"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}
