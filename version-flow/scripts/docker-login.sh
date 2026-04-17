#!/bin/bash
set -e
set -u
set -o pipefail
set -x

# get fresh push creds
aws ecr get-login-password --region $DELIVERY_REGION | docker login --username AWS --password-stdin "${REGISTRY_ENDPOINT}"
