#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DEPLOYMENT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="${1:-$DEPLOYMENT_DIR/.env}"

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  echo "[ERRO] Execute como root. O instalador precisa integrar o certificado ao CloudPanel/NGINX." >&2
  exit 1
fi

for command in python3 curl clpctl nginx; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "[ERRO] Comando obrigatório não encontrado: $command" >&2
    exit 1
  }
done

[[ -f "$ENV_FILE" ]] || {
  echo "[ERRO] Arquivo .env não encontrado: $ENV_FILE" >&2
  exit 1
}

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

CF_TOKEN="$(env_get CLOUDFLARE_API_TOKEN)"
EMAIL="$(env_get ACME_EMAIL)"
DOMAIN="$(env_get ACME_DOMAIN)"
SITE_DOMAIN="$(env_get PUBLIC_PLATFORM_DOMAIN)"
DATA_ROOT="$(env_get SCHEDULER_PRO_DATA_ROOT)"
STAGING="$(env_get ACME_STAGING)"
DNS_SLEEP="$(env_get ACME_DNS_SLEEP)"

DOMAIN="${DOMAIN:-scheduler.argws.com.br}"
SITE_DOMAIN="${SITE_DOMAIN:-$DOMAIN}"
EMAIL="${EMAIL:-admin@$DOMAIN}"
DATA_ROOT="${DATA_ROOT:-./scheduler-pro-data}"
STAGING="${STAGING:-false}"
DNS_SLEEP="${DNS_SLEEP:-20}"

[[ -n "$CF_TOKEN" ]] || {
  echo "[ERRO] CLOUDFLARE_API_TOKEN é obrigatório para DNS-01." >&2
  exit 1
}

if [[ "$DATA_ROOT" != /* ]]; then
  DATA_ROOT="$(cd -- "$(dirname -- "$ENV_FILE")" && pwd)/${DATA_ROOT#./}"
fi
CERT_DIR="$DATA_ROOT/certs"
ACME_HOME="/root/.acme.sh"
ACME_BIN="$ACME_HOME/acme.sh"
DEPLOY_HOOK="/usr/local/sbin/scheduler-pro-cloudpanel-cert-deploy"

install -d -m 0755 "$CERT_DIR"
install -m 0755 "$SCRIPT_DIR/cloudpanel-cert-deploy.sh" "$DEPLOY_HOOK"

if [[ ! -x "$ACME_BIN" ]]; then
  echo "[INFO] Instalando acme.sh no host..."
  INSTALLER="$(mktemp)"
  trap 'rm -f "$INSTALLER"' EXIT
  curl -fsSL https://get.acme.sh -o "$INSTALLER"
  # Equivalente suportado a: curl https://get.acme.sh | sh -s email=...
  sh "$INSTALLER" "email=$EMAIL" --home "$ACME_HOME"
  rm -f "$INSTALLER"
  trap - EXIT
fi

SERVER="letsencrypt"
if [[ "$STAGING" == "true" || "$STAGING" == "1" ]]; then
  SERVER="letsencrypt_test"
fi

# O token fica somente no ambiente deste processo e no account.conf root-only do acme.sh.
# Não exportamos CF_Zone_ID: o plugin descobre a zone correta por Zone:Read.
export CF_Token="$CF_TOKEN"
unset CF_Zone_ID || true

"$ACME_BIN" --set-default-ca --server "$SERVER"
"$ACME_BIN" --register-account -m "$EMAIL" --server "$SERVER" || true

ISSUE_ARGS=(
  --issue
  --dns dns_cf
  -d "$DOMAIN"
  -d "*.$DOMAIN"
  --keylength ec-256
  --server "$SERVER"
)
if [[ "$DNS_SLEEP" =~ ^[0-9]+$ && "$DNS_SLEEP" -gt 0 ]]; then
  ISSUE_ARGS+=(--dnssleep "$DNS_SLEEP")
fi

if ! "$ACME_BIN" "${ISSUE_ARGS[@]}"; then
  echo "[INFO] Emissão já existente ou pendente; tentando renovação forçada do wildcard..."
  "$ACME_BIN" --renew -d "$DOMAIN" --ecc --force --server "$SERVER"
fi

RELOAD_CMD="$DEPLOY_HOOK '$SITE_DOMAIN' '$DOMAIN' '$CERT_DIR'"
"$ACME_BIN" --install-cert -d "$DOMAIN" --ecc \
  --fullchain-file "$CERT_DIR/fullchain.pem" \
  --key-file "$CERT_DIR/privkey.pem" \
  --ca-file "$CERT_DIR/ca.pem" \
  --cert-file "$CERT_DIR/cert.pem" \
  --reloadcmd "$RELOAD_CMD"

chmod 0600 "$CERT_DIR/privkey.pem"
chmod 0644 "$CERT_DIR/cert.pem" "$CERT_DIR/ca.pem" "$CERT_DIR/fullchain.pem"

date -Iseconds > "$CERT_DIR/last-acme-install-at.txt"
chmod 0644 "$CERT_DIR/last-acme-install-at.txt"
cat > "$CERT_DIR/README.txt" <<EOF
Scheduler Pro - TLS local ACME
Base: $DOMAIN
Wildcard: *.$DOMAIN
Site CloudPanel: $SITE_DOMAIN
Método: Let's Encrypt ACME v2 + Cloudflare DNS-01

O acme.sh renova automaticamente pelo cron do host e executa:
$RELOAD_CMD
EOF
chmod 0644 "$CERT_DIR/README.txt"

echo ""
echo "[OK] TLS local configurado."
echo "[OK] Certificado: $DOMAIN + *.$DOMAIN"
echo "[OK] CloudPanel: $SITE_DOMAIN"
echo "[OK] Renovação: cron do acme.sh + clpctl site:install:certificate"
echo ""
echo "IMPORTANTE: registros de tenant sob *.$DOMAIN precisam permanecer DNS-only (proxy Cloudflare desligado)."
