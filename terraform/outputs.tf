output "metaflow_s3_bucket_name" {
  description = "Metaflow datastore S3 bucket name"
  value       = module.metaflow.metaflow_s3_bucket_name
}

output "metaflow_datastore_sysroot_s3" {
  description = "Metaflow S3 datastore root URL"
  value       = module.metaflow.METAFLOW_DATASTORE_SYSROOT_S3
}

output "metaflow_service_url" {
  description = "Metaflow metadata service URL"
  value       = module.metaflow.METAFLOW_SERVICE_URL
}

output "metaflow_service_internal_url" {
  description = "Metaflow metadata service internal URL"
  value       = module.metaflow.METAFLOW_SERVICE_INTERNAL_URL
}

output "data_bucket_name" {
  description = "S3 bucket for Fashion-MNIST training data"
  value       = aws_s3_bucket.data.id
}

output "ecr_repository_url" {
  description = "ECR repository URL for Docker push"
  value       = aws_ecr_repository.app.repository_url
}

output "batch_job_queue_arn" {
  description = "AWS Batch job queue ARN for Metaflow"
  value       = module.metaflow.METAFLOW_BATCH_JOB_QUEUE
}

output "batch_s3_task_role_arn" {
  description = "IAM role ARN for Batch tasks to access S3"
  value       = module.metaflow.METAFLOW_ECS_S3_ACCESS_IAM_ROLE
}

output "api_gateway_api_key_id" {
  description = "API Gateway Key ID for the metadata service"
  value       = module.metaflow.api_gateway_rest_api_id_key_id
}
