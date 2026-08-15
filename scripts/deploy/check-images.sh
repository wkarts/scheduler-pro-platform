#!/usr/bin/env bash
set -euo pipefail

REGISTRY="${IMAGE_REGISTRY:-ghcr.io}"
NAMESPACE="${IMAGE_NAMESPACE:-wkarts/scheduler-pro-platform}"
TAG="${APP_IMAGE_TAG:-latest}"

for image in python-base api worker web admin proxy; do
  full="${REGISTRY}/${NAMESPACE}/${image}:${TAG}"
  echo "==> docker pull ${full}"
  docker pull "${full}"
done
