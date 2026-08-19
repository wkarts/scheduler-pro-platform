#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DEPLOYMENT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="${1:-$DEPLOYMENT_DIR/.env}"

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  echo "[ERRO] Execute como root." >&2
  exit 1
fi

[[ -f "$ENV_FILE" ]] || {
  echo "[ERRO] Arquivo .env não encontrado: $ENV_FILE" >&2
  exit 1
}

install -m 0755 "$SCRIPT_DIR/cloudpanel-cert-deploy.sh" /usr/local/sbin/scheduler-pro-cloudpanel-cert-deploy
install -m 0755 "$SCRIPT_DIR/cloudpanel-cert-sync.sh" /usr/local/sbin/scheduler-pro-cloudpanel-cert-sync

ABS_ENV="$(cd -- "$(dirname -- "$ENV_FILE")" && pwd)/$(basename -- "$ENV_FILE")"
CRON_FILE="/etc/cron.d/scheduler-pro-cloudpanel-cert-sync"
cat > "$CRON_FILE" <<EOF
# Scheduler Pro: importa no CloudPanel somente quando o wildcard ACME muda.
*/5 * * * * root /usr/local/sbin/scheduler-pro-cloudpanel-cert-sync '$ABS_ENV' >> /var/log/scheduler-pro-cloudpanel-cert-sync.log 2>&1
EOF
chmod 0644 "$CRON_FILE"

# Tenta sincronizar já na instalação; se o ACME ainda não emitiu, o cron cuidará depois.
/usr/local/sbin/scheduler-pro-cloudpanel-cert-sync "$ABS_ENV" || true

echo "[OK] Sincronização automática CloudPanel instalada."
echo "[OK] Verificação a cada 5 minutos; clpctl só roda quando o certificado muda."
echo "[OK] Log: /var/log/scheduler-pro-cloudpanel-cert-sync.log"
