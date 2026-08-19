#!/usr/bin/env sh
set -eu

DOMAIN="${ACME_DOMAIN:-scheduler.argws.com.br}"
EMAIL="${ACME_EMAIL:?ACME_EMAIL obrigatória}"
STAGING="${ACME_STAGING:-false}"
DNS_SLEEP="${ACME_DNS_SLEEP:-20}"
CHECK_INTERVAL="${ACME_CHECK_INTERVAL_SECONDS:-43200}"
SERVER="letsencrypt"

if [ "$STAGING" = "true" ] || [ "$STAGING" = "1" ]; then
  SERVER="letsencrypt_test"
fi

mkdir -p /certs /acme.sh
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

install_bundle() {
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
}

if ! issue_certificate; then
  acme.sh --renew -d "$DOMAIN" --ecc --server "$SERVER" || true
fi
install_bundle

cat > /certs/README.txt <<EOF
Scheduler Pro ACME certificate bundle
Domain: $DOMAIN
Wildcard: *.$DOMAIN
Issuer: Let's Encrypt
Challenge: DNS-01 via Cloudflare API

O TXT _acme-challenge.$DOMAIN é temporário e criado/removido automaticamente pelo dns_cf.
EOF
chmod 0644 /certs/README.txt

while :; do
  sleep "$CHECK_INTERVAL"
  acme.sh --cron --home /acme.sh || true
  install_bundle || true
done
