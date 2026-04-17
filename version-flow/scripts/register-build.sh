#!/bin/bash
set -e
set -u
set -o pipefail
set -x

CURRENT_HASH="$(git log --pretty=format:'%h' -n 1)"
: "${VERSION="NO-VERSION"}"

function version_plus_hash () {
    echo "$VERSION-$CURRENT_HASH"
}

# get PKG_VERSION from branch unless specifically passed in.
: "${PKG_VERSION="$(version_plus_hash)"}"

# get fresh push creds
echo "STEP 1 - getting aws creds for docker build"
aws ecr get-login-password | docker login --username AWS --password-stdin "${REGISTRY_ENDPOINT}"

# build the container
echo "STEP 2 - building the container with specific version $PKG_VERSION"
TAG=$PKG_VERSION make build

# tag the version based on the PKG_VERSION
echo "STEP 3 - tagging the version"
docker tag "$CONTAINER_NAME:$PKG_VERSION" "$REGISTRY_ENDPOINT/$CONTAINER_NAME:$PKG_VERSION"

# push the version to the repo
echo "STEP 4 - pushing version-hash image to AWS docker registry"
docker push "$REGISTRY_ENDPOINT/$CONTAINER_NAME:$PKG_VERSION"

echo "STEP 5 - pushing release image to AWS docker registry"
docker tag "$CONTAINER_NAME:$PKG_VERSION" "$REGISTRY_ENDPOINT/$CONTAINER_NAME:$VERSION"
docker push "$REGISTRY_ENDPOINT/$CONTAINER_NAME:$VERSION"
