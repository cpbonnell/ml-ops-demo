#!/bin/bash

: "${ENTRYPOINT=""}"
: "${AWS_REGION="us-east-2"}"
service="version_flow"

if [ "$ENTRYPOINT" == "" ]; then
    docker-compose run \
        -v "${PWD}":/home/app/version-flow \
        ${service}
else
    echo "${ENTRYPOINT}"
    docker-compose run \
    --entrypoint "${ENTRYPOINT}" \
    -v "${PWD}":/home/app/version-flow \
    "${service}" "$@"
fi
