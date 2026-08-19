#!/usr/bin/env sh
set -eu

DOMAIN="${ACME_DOMAIN:-scheduler.argws.com.br}"
EMAIL="${ACME_EMAIL:?ACME_EMAIL obrigatória}"
STAGING="${ACME_STAGING:-false}"
DNS_SLEEP="${ACME_DNS_SLEEP:-20}"
SERVER="letsencrypt"

if [ "$STAGING" = "true" ] || [ "$STAGING" = "1" ]; then
  SERVER="letsencrypt_test"
fi

mkdir -p /certs /acme.sh

# O plugin dns_cf cria/remove automaticamente o TXT _acme-challenge usando
# CLOUDFLARE_API_TOKEN exposto ao container como CF_Token. O desafio/token ACME
# é obtido do Let's Encrypt a cada order; não existe TXT estático para manter.
# CF_Zone_ID é opcional: a zone pode ser descoberta pelo token com Zone:Read.
find /acme.sh -type f -name '*.conf' -exec sed -i '/^CF_Zone_ID=/d' {} \; 2>/dev/null || true
unset CF_Zone_ID || true

acme.sh --set-default-ca --server "$SERVER"
acme.sh --register-account -m "$EMAIL" --server "$SERVER" || true

issue_certificate() {
  if [ "$DNS_SLEEP" -gt 0 ] 2>/dev/null; then
    acme.sh --issue \
      --dns dns_cf \
      -d "$DOMAIN" \
      -d "*.$DOMAIN" \
      --keylength ec-256 \
      --server "$SERVER" \
      --dnssleep "$DNS_SLEEP"
  else
    acme.sh --issue \
      --dns dns_cf \
      -d "$DOMAIN" \
      -d "*.$DOMAIN" \
      --keylength ec-256 \
      --server "$SERVER"
  fi
}

# Primeira emissão ou atualização do order. Se o certificado já existir e não
# precisar ser reemitido, acme.sh pode retornar um estado de no-op; nesse caso
# executamos renew sem --force para respeitar rate limits do Let's Encrypt.
if ! issue_certificate; then
  acme.sh --renew -d "$DOMAIN" --ecc --server "$SERVER"
fi

acme.sh --install-cert -d "$DOMAIN" --ecc \
  --fullchain-file /certs/fullchain.pem \
  --key-file /certs/privkey.pem \
  --ca-file /certs/ca.pem \
  --cert-file /certs/cert.pem \
  --reloadcmd "date -Iseconds > /certs/last-installed-at.txt"

chmod 0600 /certs/privkey.pem
chmod 0644 /certs/fullchain.pem /certs/cert.pem /certs/ca.pem

date -Iseconds > /certs/last-acme-run-at.txt
chmod 0644 /certs/last-acme-run-at.txt /certs/last-installed-at.txt 2>/dev/null || true

cat > /certs/README.txt <<EOF
Scheduler Pro ACME certificate bundle
Domain: $DOMAIN
Wildcard: *.$DOMAIN
Issuer: Let's Encrypt
Challenge: DNS-01 via Cloudflare API

Fluxo automático:
1. acme.sh abre/renova o order no Let's Encrypt;
2. dns_cf cria o TXT _acme-challenge.$DOMAIN;
3. Let's Encrypt valida o DNS-01;
4. dns_cf remove o TXT temporário;
5. o bundle abaixo é atualizado;
6. o sincronizador CloudPanel importa o bundle somente quando o hash muda.

Files:
- fullchain.pem
- privkey.pem
- cert.pem
- ca.pem
EOF
chmod 0644 /certs/README.txt

# O cron interno do acme.sh verifica as renovações periodicamente. O TXT de
# challenge só existe durante a validação e não deve ser pré-criado manualmente.
crond -f
