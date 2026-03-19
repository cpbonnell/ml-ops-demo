# -----------------------------------------------------------------------------
# Random suffix for globally unique names
# -----------------------------------------------------------------------------
resource "random_id" "suffix" {
  byte_length = 4
}

# -----------------------------------------------------------------------------
# Default VPC and subnets
# -----------------------------------------------------------------------------
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }

  filter {
    name   = "default-for-az"
    values = ["true"]
  }
}

# -----------------------------------------------------------------------------
# Metaflow infrastructure
# -----------------------------------------------------------------------------
module "metaflow" {
  source  = "outerbounds/metaflow/aws"
  version = "~> 0.13"

  resource_prefix = var.project_name
  resource_suffix = random_id.suffix.hex

  vpc_id          = data.aws_vpc.default.id
  subnet1_id      = data.aws_subnets.default.ids[0]
  subnet2_id      = data.aws_subnets.default.ids[1]
  vpc_cidr_blocks = [data.aws_vpc.default.cidr_block]
  with_public_ip  = true

  enable_step_functions = true
  batch_type            = "ec2"

  compute_environment_instance_types = ["c5.xlarge", "g4dn.xlarge"]
  compute_environment_max_vcpus      = var.compute_environment_max_vcpus
  compute_environment_min_vcpus      = 0
  compute_environment_desired_vcpus  = 0

  force_destroy_s3_bucket = true

  # The module's default image (v2.3.0) predates SSL support in the goose
  # migration runner. v2.5.0 properly passes MF_METADATA_DB_SSL_MODE to the
  # database connection string, which is required for PostgreSQL 16+.
  metadata_service_container_image = "netflixoss/metaflow_metadata_service:v2.5.0"

  tags = {}  # Note: we set default tags as part of the provider configuration
}

# Grant Batch:TagResource to the batch S3 task role so Metaflow can tag jobs.
# The module output is an ARN; extract the role name for aws_iam_role_policy.
resource "aws_iam_role_policy" "batch_tag_resource" {
  name = "${var.project_name}-batch-tag-resource"
  role = regex("role/(.+)$", module.metaflow.METAFLOW_ECS_S3_ACCESS_IAM_ROLE)[0]

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = "batch:TagResource"
        Resource = "*"
      }
    ]
  })
}

# The Metaflow module's custom inline policies for the Batch service role are
# missing permissions required by newer AWS Batch (e.g. ecs:TagResource).
# Attach the AWS managed policy to fill the gaps.
resource "aws_iam_role_policy_attachment" "batch_service_role_managed_policy" {
  role       = "${var.project_name}-batch-execution-role-${random_id.suffix.hex}"
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBatchServiceRole"
}

# Grant the Batch task role access to the data bucket so flow steps running
# on Batch can read/write Fashion-MNIST data.
resource "aws_iam_role_policy" "batch_task_data_bucket" {
  name = "${var.project_name}-batch-data-bucket"
  role = regex("role/(.+)$", module.metaflow.METAFLOW_ECS_S3_ACCESS_IAM_ROLE)[0]

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.data.arn,
          "${aws_s3_bucket.data.arn}/*"
        ]
      }
    ]
  })
}

# -----------------------------------------------------------------------------
# ECR repository
# -----------------------------------------------------------------------------
resource "aws_ecr_repository" "app" {
  name                 = "${var.project_name}-${random_id.suffix.hex}"
  force_delete         = true
  image_tag_mutability = "MUTABLE"
}

# -----------------------------------------------------------------------------
# S3 data bucket (Fashion-MNIST training data)
# -----------------------------------------------------------------------------
resource "aws_s3_bucket" "data" {
  bucket        = "${var.project_name}-data-${random_id.suffix.hex}"
  force_destroy = true

  tags = {
    DataSensitivity = "Public"
  }
}
