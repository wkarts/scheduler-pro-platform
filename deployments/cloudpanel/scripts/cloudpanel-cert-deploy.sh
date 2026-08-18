#!/usr/bin/env bash
set -euo pipefail

SITE_DOMAIN="${1:?uso: cloudpanel-cert-deploy.sh <site-domain> <certificate-domain> <cert-dir>}"
CERT_DOMAIN="${2:?certificate-domain obrigatório}"
CERT_DIR="${3:?cert-dir obrigatório}"
WILDCARD="*.${CERT_DOMAIN}"

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  echo "[ERRO] Execute como root para instalar certificado e recarregar o NGINX do CloudPanel." >&2
  exit 1
fi

for command in clpctl nginx python3; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "[ERRO] Comando obrigatório não encontrado: $command" >&2
    exit 1
  }
done

for file in privkey.pem cert.pem ca.pem fullchain.pem; do
  [[ -s "$CERT_DIR/$file" ]] || {
    echo "[ERRO] Certificado incompleto: $CERT_DIR/$file" >&2
    exit 1
  }
done

# CloudPanel mantém seu inventário de certificados consistente e recarrega o site.
clpctl site:install:certificate \
  --domainName="$SITE_DOMAIN" \
  --privateKey="$CERT_DIR/privkey.pem" \
  --certificate="$CERT_DIR/cert.pem" \
  --certificateChain="$CERT_DIR/ca.pem"

VHOST="/etc/nginx/sites-enabled/${SITE_DOMAIN}.conf"
if [[ ! -f "$VHOST" ]]; then
  VHOST="$(find /etc/nginx/sites-enabled -maxdepth 1 -type f -name "*${SITE_DOMAIN}*.conf" -print -quit 2>/dev/null || true)"
fi

if [[ -z "$VHOST" || ! -f "$VHOST" ]]; then
  echo "[ERRO] VHost do CloudPanel não localizado para $SITE_DOMAIN." >&2
  exit 1
fi

BACKUP="${VHOST}.scheduler-pro.$(date +%Y%m%d%H%M%S).bak"
cp -a "$VHOST" "$BACKUP"

# Garante que o mesmo reverse proxy aceite todos os tenants sob o domínio gerenciado.
python3 - "$VHOST" "$SITE_DOMAIN" "$WILDCARD" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
site = sys.argv[2]
wildcard = sys.argv[3]
lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
changed = False
out: list[str] = []
for line in lines:
    stripped = line.strip()
    if stripped.startswith("server_name ") and site in stripped and wildcard not in stripped:
        semicolon = line.rfind(";")
        if semicolon >= 0:
            line = line[:semicolon].rstrip() + f" {wildcard};" + line[semicolon + 1:]
            changed = True
    out.append(line)
if changed:
    path.write_text("".join(out), encoding="utf-8")
PY

if ! nginx -t; then
  cp -a "$BACKUP" "$VHOST"
  nginx -t || true
  echo "[ERRO] Alteração do VHost foi revertida porque nginx -t falhou." >&2
  exit 1
fi

if command -v systemctl >/dev/null 2>&1; then
  systemctl reload nginx
else
  nginx -s reload
fi

# A API lê somente certificado público e marcadores para diagnóstico. A chave
# privada continua root-only e nunca é lida/exposta pela aplicação.
install -d -m 0755 "$CERT_DIR"
chmod 0600 "$CERT_DIR/privkey.pem"
chmod 0644 "$CERT_DIR/cert.pem" "$CERT_DIR/ca.pem" "$CERT_DIR/fullchain.pem"
date -Iseconds > "$CERT_DIR/last-cloudpanel-installed-at.txt"
printf '%s\n' "$SITE_DOMAIN" > "$CERT_DIR/cloudpanel-site-domain.txt"
printf '%s\n' "$WILDCARD" > "$CERT_DIR/wildcard-domain.txt"
chmod 0644 "$CERT_DIR/last-cloudpanel-installed-at.txt" "$CERT_DIR/cloudpanel-site-domain.txt" "$CERT_DIR/wildcard-domain.txt"

# Mantém apenas alguns backups recentes do VHost.
ls -1t "${VHOST}.scheduler-pro."*.bak 2>/dev/null | tail -n +6 | xargs -r rm -f

echo "[OK] Certificado $CERT_DOMAIN / $WILDCARD instalado no CloudPanel ($SITE_DOMAIN)."
