service=version_flow
test_data_path=tests/data
codartifact_domain=clairity
delivery_region=us-east-2
delivery_account=629478721045

export PROJECT_NAME=${service}
export DELIVERY_REGION=$(delivery_region)
export PRERELEASE_SUFFIX=rc
export CONTAINER_NAME=clairity/version-flow
export RELEASE_BRANCH=release
export TRUNK_BRANCH=main
export VERSION=$(shell ./scripts/get-version.sh)
export REGISTRY_ENDPOINT=$(delivery_account).dkr.ecr.$(delivery_region).amazonaws.com
export CODEARTIFACT_AUTH_TOKEN ?= $(shell aws codeartifact get-authorization-token --domain $(codartifact_domain) --domain-owner $(delivery_account) --query authorizationToken --output text  --region $(delivery_region))


.PHONY: list init

#login to ECR
login:
	./scripts/docker-login.sh

# runs before build, it unmounts volumes as well
down:
	docker-compose down -v

# build is a helper to make it easy to build the docker container, it runs before
# any downstream step
build: down login
	docker-compose build

# a wrapper for docker-compose up, runs an immutable instance of the app
up: build
	docker-compose up -d

# dev runs the container with a mounted volume to the code repo. In dev mode, it runs the
# container just like `up` but you can "live code" in the directory. Optionally, you drop into
# a shell in a dev container with `make exec`
dev: build
	./scripts/container-run.sh

# exec is used in combination with a running container. This allows you to drop into a shell for
# an active shell.
exec:
	./scripts/container-exec.sh

# shell is meant to give you a /bin/bash into the container with a mounted volume
# this allows for administrator of things such as poetry update and other administrative tasks
# in which you might want to mutate the state of files in your repo
shell: build
	ENTRYPOINT=/bin/bash ./scripts/container-run.sh

# test is an immutable pytest that is safe to run locally and in CI
test: build
	rm -f .test_durations
	@ENTRYPOINT='pytest' ./scripts/container-run.sh

test-pdb: build
	rm -f .test_durations
	@ENTRYPOINT='pytest' ./scripts/container-run.sh "--pdb"

# smoke-test is an immutable smoke-testing method that is safe to run locally and in CI
smoke-test: build
	ENTRYPOINT=python3 ./scripts/container-run.sh "import version_flow; print(version_flow.__version__)"

# register is a helper to register the container with ecr based on the current working branch hash tag
register: build
	./scripts/register-build.sh
