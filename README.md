# rapid-ml-ops-demo

A proof-of-concept ML experimentation stack that demonstrates three phases of
the development lifecycle:

1. **Developing** — run a training flow on local workstation resources
2. **Scaling** — run the same flow on AWS Batch with GPU instances
3. **Deployment** — deploy the flow as an AWS Step Function for production use

The stack uses Metaflow for orchestration, PyTorch for model training, wandb for
experiment tracking, and AWS Batch + Step Functions for cloud compute and
deployment. The POC trains a small CNN on Fashion-MNIST with a hyperparameter
sweep over learning rates.

## Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv)
- Docker
- AWS CLI configured with the `analytics-dev` profile
- Terraform
- A [wandb](https://wandb.ai) account and API key

## Quick Start

1. Copy the example environment file and fill in your values:
   ```sh
   cp .env.example .env
   ```

2. Install Python dependencies:
   ```sh
   make setup
   ```

3. Provision AWS infrastructure:
   ```sh
   make infra-init && make infra
   ```

4. Configure Metaflow to use the provisioned infrastructure:
   ```sh
   make configure
   ```

5. Build and push the Docker image to ECR:
   ```sh
   make docker-build && make docker-push
   ```

6. Run the training flow locally:
   ```sh
   make run-local
   ```

7. Run the training flow on AWS Batch:
   ```sh
   make run-cloud
   ```

8. Deploy as an AWS Step Function:
   ```sh
   make deploy
   ```

## Teardown

Remove all AWS resources:

```sh
make infra-destroy
```

## Project Structure

```
rapid-ml-ops-demo/
  src/
    flow.py              # Metaflow training flow
    model.py             # PyTorch CNN model definition
    data.py              # Data loading and S3 utilities
  terraform/
    main.tf              # Metaflow module, ECR, S3 data bucket
    variables.tf         # AWS region, profile, resource naming
    outputs.tf           # Values consumed by Makefile and Metaflow config
    providers.tf         # AWS provider configuration
  docker/
    Dockerfile           # CUDA-based image with PyTorch and Metaflow
  Makefile               # Single entry point for all operations
  pyproject.toml         # Python dependencies managed by uv
  .env.example           # Template for environment variables
```

## Makefile Targets

| Target          | Description                                     |
|-----------------|-------------------------------------------------|
| `help`          | Show available targets                          |
| `setup`         | Create venv and install dependencies            |
| `infra-init`    | Initialize Terraform                            |
| `infra`         | Provision all AWS infrastructure                |
| `infra-destroy` | Tear down all AWS infrastructure                |
| `infra-output`  | Show Terraform outputs as JSON                  |
| `docker-build`  | Build Docker image and tag for ECR              |
| `docker-push`   | Authenticate to ECR and push image              |
| `configure`     | Generate Metaflow config from Terraform outputs |
| `run-local`     | Run the training flow locally                   |
| `run-cloud`     | Run the training flow on AWS Batch              |
| `deploy`        | Deploy the flow as an AWS Step Function         |

## Targeting GPU Instances on AWS Batch

When running on AWS Batch, Metaflow's `@resources` decorator controls which EC2
instance type Batch selects for each step. Getting this right is important —
request too much and your job won't schedule; request too little and you won't
get a GPU.

### How instance selection works

The Metaflow module in `terraform/main.tf` defines the allowed instance types
for your cloud runs (currently `c5.xlarge` and `g4dn.xlarge`). When a job is
submitted, AWS Batch matches the job's resource requirements against these
instance types and launches one that fits. If none of your allowed instance
types can satisfy the request, the job stays stuck in `RUNNABLE`.

### Available instance types

| Instance        | vCPUs | Memory (GiB) | GPUs | GPU Type    | Use case             |
|-----------------|-------|--------------|------|-------------|----------------------|
| `c5.xlarge`     | 4     | 8            | 0    | —           | CPU-only steps       |
| `g4dn.xlarge`   | 4     | 16           | 1    | NVIDIA T4   | Single-GPU training  |
| `g4dn.2xlarge`  | 8     | 32           | 1    | NVIDIA T4   | Larger models        |
| `g4dn.12xlarge` | 48    | 192          | 4    | NVIDIA T4   | Multi-GPU training   |
| `p3.2xlarge`    | 8     | 61           | 1    | NVIDIA V100 | HPC / large models   |
| `g5.xlarge`     | 4     | 16           | 1    | NVIDIA A10G | Inference / training |
| `g5.2xlarge`    | 8     | 32           | 1    | NVIDIA A10G | Larger models        |

To use an instance type not currently in the compute environment, add it to the
`compute_environment_instance_types` parameter of the Metaflow module in
`terraform/main.tf` and run `make infra`.

### Writing the `@resources` decorator

```python
@resources(gpu=1, cpu=4, memory=14000)
@step
def train(self):
    ...
```

The three parameters that matter for instance selection:

- **`gpu`** — set to `1` (or more) to land on a GPU instance. If `gpu=0` or
  omitted, Batch may place the step on a cheaper CPU instance.
- **`cpu`** — number of vCPUs. Must be <= the instance's vCPU count.
- **`memory`** — memory in MB. Must be **less than the instance's total memory**
  because AWS Batch reserves ~1.5–2 GiB per instance for the ECS agent and OS.
  For a 16 GiB instance, request **no more than** 14000 MB.

### Rules of thumb

1. **Always leave memory headroom.** For an instance with *N* GiB of RAM,
   request at most *(N - 2) × 1024* MB. Requesting the full amount will cause
   the job to stay in `RUNNABLE` permanently, but never get actually scheduled.
2. **Set `gpu=1` explicitly** on any step that needs a GPU. Without it, Batch
   has no reason to place the job on a GPU instance.
3. **CPU-only steps don't need `@resources`.** Metaflow's defaults work fine for
   lightweight steps like `start`, `data_validation`, and `end`.
4. **Check `compute_environment_max_vcpus`** in `terraform/variables.tf`. The
   total vCPUs across all running instances cannot exceed this limit. If you run
   many parallel steps, increase it accordingly.
5. **Stuck in `RUNNABLE`?** Check the job's `statusReason` in the AWS Batch
   console or via CLI:
   ```sh
   aws batch describe-jobs --jobs <job-id> --region us-east-2 \
     --query 'jobs[0].statusReason'
   ```
   Common causes: memory request too high, GPU requested but no GPU instance
   type in the compute environment, or `maxvCpus` limit reached.
