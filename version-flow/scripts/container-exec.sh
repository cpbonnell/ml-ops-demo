#!/bin/bash
set -e

CONTAINER_NAME="clairity/version-flow"

container_id="$(docker ps | grep ${CONTAINER_NAME} | awk '{print $1;}')"
docker exec -it "${container_id}" /bin/bash
