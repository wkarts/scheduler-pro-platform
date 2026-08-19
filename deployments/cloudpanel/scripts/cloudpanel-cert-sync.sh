#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${1:?uso: cloudpanel-cert-sync.sh /caminho/.env}"
[[ -f "$ENV_FILE" ]] || { echo "[ERRO] .env não encontrado: $ENV_FILE" >&2; exit 1; }

for command in python3 sha256sum clpctl nginx; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "[ERRO] comando obrigatório ausente: $command" >&2
    exit 1
  }
done

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  echo "[ERRO] Execute como root: a instalação do certificado usa clpctl/nginx." >&2
  exit 1
fi

env_get() {
  python3 - "$ENV_FILE" "$1" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
key = sys.argv[2]
for raw in path.read_text(encoding="utf-8").splitlines():
    line = raw.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    name, value = line.split("=", 1)
    if name.strip() != key:
        continue
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    print(value)
    break
PY
}

SITE_DOMAIN="$(env_get PUBLIC_PLATFORM_DOMAIN)"
DATA_ROOT="$(env_get SCHEDULER_PRO_DATA_ROOT)"
SITE_DOMAIN="${SITE_DOMAIN:-scheduler.argws.com.br}"
DATA_ROOT="${DATA_ROOT:-./scheduler-pro-data}"

if [[ "$DATA_ROOT" != /* ]]; then
  DATA_ROOT="$(cd -- "$(dirname -- "$ENV_FILE")" && pwd)/${DATA_ROOT#./}"
fi

CERT_DIR="$DATA_ROOT/certs"
STATE_DIR="$DATA_ROOT/cloudpanel-sync"
STATE_FILE="$STATE_DIR/installed.sha256"
DEPLOY_SCRIPT="/usr/local/sbin/scheduler-pro-cloudpanel-cert-deploy"

for file in privkey.pem cert.pem ca.pem fullchain.pem; do
  if [[ ! -s "$CERT_DIR/$file" ]]; then
    echo "[INFO] certificado ACME ainda não disponível: $CERT_DIR/$file"
    exit 0
  fi
done

[[ -x "$DEPLOY_SCRIPT" ]] || {
  echo "[ERRO] deploy helper ausente: $DEPLOY_SCRIPT" >&2
  exit 1
}

mkdir -p "$STATE_DIR"
chmod 0700 "$STATE_DIR"
CURRENT_HASH="$(sha256sum "$CERT_DIR/fullchain.pem" "$CERT_DIR/privkey.pem" | sha256sum | awk '{print $1}')"
PREVIOUS_HASH="$(cat "$STATE_FILE" 2>/dev/null || true)"

if [[ "$CURRENT_HASH" == "$PREVIOUS_HASH" ]]; then
  echo "[OK] certificado já sincronizado com CloudPanel: $SITE_DOMAIN"
  exit 0
fi

"$DEPLOY_SCRIPT" "$SITE_DOMAIN" "$SITE_DOMAIN" "$CERT_DIR"
printf '%s\n' "$CURRENT_HASH" > "$STATE_FILE"
chmod 0600 "$STATE_FILE"
echo "[OK] wildcard renovado sincronizado com CloudPanel: $SITE_DOMAIN"
