#!/usr/bin/env bash
set -euo pipefail
docker compose -f deployments/development/docker-compose.yml up --build
