terraform {
  required_version = ">= 1.4"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }
}

provider "aws" {
  region  = var.aws_region
  profile = var.aws_profile

  default_tags {
    tags = {
      Terraform   = "True"
      Application = "rapid-ml-ops-demo"
      Environment = "dev"
      CostCenter  = "MLTraining"
      DELETE_ME   = "True"
    }
  }
}
