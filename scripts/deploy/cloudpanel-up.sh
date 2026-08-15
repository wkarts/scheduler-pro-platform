#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DEPLOY_DIR="${ROOT_DIR}/deployments/cloudpanel"
ENV_FILE="${DEPLOY_DIR}/.env"

if [[ ! -f "${ENV_FILE}" ]]; then
  cp "${DEPLOY_DIR}/.env.example" "${ENV_FILE}"
  echo "Arquivo ${ENV_FILE} criado. Edite as variáveis obrigatórias antes de subir a stack."
  exit 1
fi

docker compose --env-file "${ENV_FILE}" -f "${DEPLOY_DIR}/compose.yaml" pull
docker compose --env-file "${ENV_FILE}" -f "${DEPLOY_DIR}/compose.yaml" up -d --remove-orphans
