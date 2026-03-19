-include .env
export WANDB_API_KEY
export AWS_PROFILE

VENV_DIR := .venv
FLOW_FILE := src/flow.py
ECR_IMAGE = $(shell terraform -chdir=terraform output -raw ecr_repository_url):latest
DATA_BUCKET = $(shell terraform -chdir=terraform output -raw data_bucket_name)

.PHONY: help setup infra-init infra infra-destroy infra-output docker-build docker-push configure run-local run-cloud deploy

## Default target
help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

## Setup
setup: ## Create venv and install dependencies
	uv venv $(VENV_DIR)
	uv sync

## Infrastructure
infra-init: ## Initialize Terraform
	terraform -chdir=terraform init

infra: ## Provision all AWS infrastructure
	terraform -chdir=terraform apply

infra-destroy: ## Tear down all AWS infrastructure
	terraform -chdir=terraform destroy

infra-output: ## Show Terraform outputs as JSON
	@terraform -chdir=terraform output -json

## Docker & Configuration
ECR_URL = $(shell terraform -chdir=terraform output -raw ecr_repository_url)
ECR_REGISTRY = $(shell echo $(ECR_URL) | cut -d/ -f1)
REGION = $(shell terraform -chdir=terraform output -raw aws_region 2>/dev/null || echo "us-east-2")

docker-build: ## Build Docker image and tag for ECR
	docker build -t $(ECR_URL):latest -f docker/Dockerfile .

docker-push: ## Authenticate to ECR and push image
	aws ecr get-login-password --region $(REGION) | docker login --username AWS --password-stdin $(ECR_REGISTRY)
	docker push $(ECR_URL):latest

configure: ## Generate Metaflow config from Terraform outputs
	@mkdir -p ~/.metaflowconfig
	@DATASTORE_SYSROOT=$$(terraform -chdir=terraform output -raw metaflow_datastore_sysroot_s3) && \
	SERVICE_URL=$$(terraform -chdir=terraform output -raw metaflow_service_url) && \
	JOB_QUEUE=$$(terraform -chdir=terraform output -raw batch_job_queue_arn) && \
	TASK_ROLE=$$(terraform -chdir=terraform output -raw batch_s3_task_role_arn) && \
	API_KEY_ID=$$(terraform -chdir=terraform output -raw api_gateway_api_key_id) && \
	API_KEY=$$(aws apigateway get-api-key --api-key $$API_KEY_ID --include-value --region $(REGION) --profile $(AWS_PROFILE) --query 'value' --output text) && \
	CONFIG='{\n  "METAFLOW_DEFAULT_DATASTORE": "s3",\n  "METAFLOW_DATASTORE_SYSROOT_S3": "'"$$DATASTORE_SYSROOT"'",\n  "METAFLOW_DEFAULT_METADATA": "service",\n  "METAFLOW_SERVICE_URL": "'"$$SERVICE_URL"'",\n  "METAFLOW_SERVICE_AUTH_KEY": "'"$$API_KEY"'",\n  "METAFLOW_ECS_S3_ACCESS_IAM_ROLE": "'"$$TASK_ROLE"'",\n  "METAFLOW_BATCH_JOB_QUEUE": "'"$$JOB_QUEUE"'",\n  "METAFLOW_BATCH_EMIT_TAGS": true,\n  "METAFLOW_BATCH_DEFAULT_TAGS": {\n    "Terraform": "False",\n    "Application": "rapid-ml-ops-demo",\n    "Environment": "dev",\n    "CostCenter": "MLTraining"\n  }\n}' && \
	printf "$$CONFIG\n" > ~/.metaflowconfig/config.json && \
	echo "Wrote Metaflow config to ~/.metaflowconfig/config.json:" && \
	cat ~/.metaflowconfig/config.json

## Run & Deploy
run-local: ## Run the training flow locally
	python $(FLOW_FILE) run --data-bucket $(DATA_BUCKET)

run-cloud: ## Run the training flow on AWS Batch
	python $(FLOW_FILE) run --data-bucket $(DATA_BUCKET) --with batch:image=$(ECR_IMAGE)

deploy: ## Deploy the flow as an AWS Step Function
	python $(FLOW_FILE) step-functions create --data-bucket $(DATA_BUCKET) --with batch:image=$(ECR_IMAGE)
