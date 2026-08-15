#!/usr/bin/env bash
set -euo pipefail

TAG="${1:-local}"
REPO="${IMAGE_NAMESPACE:-wkarts/scheduler-pro-platform}"

docker build -f infrastructure/docker/base/python/Dockerfile -t "${REPO}/python-base:${TAG}" .
docker build -f infrastructure/docker/api/Dockerfile --build-arg PYTHON_BASE_IMAGE="${REPO}/python-base:${TAG}" -t "${REPO}/api:${TAG}" .
docker build -f infrastructure/docker/worker/Dockerfile --build-arg PYTHON_BASE_IMAGE="${REPO}/python-base:${TAG}" -t "${REPO}/worker:${TAG}" .
docker build -f infrastructure/docker/web/Dockerfile --build-arg APP_DIR=apps/web -t "${REPO}/web:${TAG}" .
docker build -f infrastructure/docker/web/Dockerfile --build-arg APP_DIR=apps/admin -t "${REPO}/admin:${TAG}" .
docker build -f infrastructure/docker/proxy/Dockerfile -t "${REPO}/proxy:${TAG}" .
