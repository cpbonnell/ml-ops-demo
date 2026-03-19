variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-2"
}

variable "aws_profile" {
  description = "AWS CLI profile name"
  type        = string
  default     = "analytics-dev"
}

variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "rapid-ml-ops-demo"
}

variable "compute_environment_max_vcpus" {
  description = "Maximum vCPUs for the Batch compute environment"
  type        = number
  default     = 16
}
