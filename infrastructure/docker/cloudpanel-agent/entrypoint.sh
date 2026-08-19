#!/usr/bin/env bash
set -euo pipefail

HOST_ROOT="${HOST_ROOT:-/host}"
CERT_DIR="${CERT_DIR:-/certs}"
STATE_DIR="${STATE_DIR:-/state}"
SITE_DOMAIN="${CLOUDPANEL_SITE_DOMAIN:-scheduler.argws.com.br}"
WILDCARD_DOMAIN="${CLOUDPANEL_WILDCARD_DOMAIN:-*.scheduler.argws.com.br}"
SYNC_INTERVAL="${CLOUDPANEL_SYNC_INTERVAL_SECONDS:-60}"
HOST_TMP_REL="/run/scheduler-pro-cloudpanel-agent"
HOST_TMP="$HOST_ROOT$HOST_TMP_REL"
STATE_FILE="$STATE_DIR/installed.sha256"

log() {
  printf '%s [cloudpanel-agent] %s\n' "$(date -Iseconds)" "$*"
}

host_exec() {
  chroot "$HOST_ROOT" /usr/bin/env \
    PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    "$@"
}

host_ready() {
  [[ -d "$HOST_ROOT/etc/nginx/sites-enabled" ]] || return 1
  host_exec /bin/sh -lc 'command -v clpctl >/dev/null 2>&1 && command -v nginx >/dev/null 2>&1'
}

find_vhost() {
  local exact="$HOST_ROOT/etc/nginx/sites-enabled/${SITE_DOMAIN}.conf"
  if [[ -f "$exact" ]]; then
    printf '%s\n' "$exact"
    return 0
  fi

  local candidate
  while IFS= read -r candidate; do
    if grep -Eq "^[[:space:]]*server_name[[:space:]].*${SITE_DOMAIN//./\.}" "$candidate"; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done < <(find "$HOST_ROOT/etc/nginx/sites-enabled" -maxdepth 1 -type f -name '*.conf' -print 2>/dev/null | sort)

  return 1
}

reconcile_vhost() {
  local vhost="$1"
  local pre result
  pre="${vhost}.scheduler-pro-agent.pre"
  cp -a "$vhost" "$pre"

  result="$(python3 - "$vhost" "$SITE_DOMAIN" "$WILDCARD_DOMAIN" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
site = sys.argv[2]
wildcard = sys.argv[3]
lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
changed = False
matched = False
out: list[str] = []

for line in lines:
    stripped = line.strip()
    if stripped.startswith("server_name "):
        tokens = stripped.split(";", 1)[0].split()[1:]
        if site in tokens:
            matched = True
            if wildcard not in tokens:
                semicolon = line.rfind(";")
                if semicolon >= 0:
                    line = line[:semicolon].rstrip() + f" {wildcard};" + line[semicolon + 1:]
                    changed = True
    out.append(line)

if not matched:
    print("missing")
elif changed:
    path.write_text("".join(out), encoding="utf-8")
    print("changed")
else:
    print("ready")
PY
)"

  if [[ "$result" == "missing" ]]; then
    mv -f "$pre" "$vhost"
    return 2
  fi

  if [[ "$result" == "changed" ]]; then
    if ! host_exec nginx -t >/dev/null 2>&1; then
      mv -f "$pre" "$vhost"
      host_exec nginx -t >/dev/null 2>&1 || true
      log "VHost revertido: nginx -t falhou após adicionar $WILDCARD_DOMAIN"
      return 1
    fi

    local backup="${vhost}.scheduler-pro-agent.$(date +%Y%m%d%H%M%S).bak"
    mv -f "$pre" "$backup"
    find "$(dirname "$vhost")" -maxdepth 1 -type f -name "$(basename "$vhost").scheduler-pro-agent.*.bak" -printf '%T@ %p\n' 2>/dev/null \
      | sort -nr | tail -n +6 | cut -d' ' -f2- | xargs -r rm -f
    host_exec nginx -s reload >/dev/null 2>&1 || true
    log "VHost reconciliado automaticamente: $SITE_DOMAIN $WILDCARD_DOMAIN"
  else
    rm -f "$pre"
  fi
}

certificate_ready() {
  local file
  for file in privkey.pem cert.pem ca.pem fullchain.pem; do
    [[ -s "$CERT_DIR/$file" ]] || return 1
  done
}

certificate_hash() {
  sha256sum "$CERT_DIR/fullchain.pem" "$CERT_DIR/privkey.pem" | sha256sum | awk '{print $1}'
}

install_certificate() {
  local current previous
  current="$(certificate_hash)"
  previous="$(cat "$STATE_FILE" 2>/dev/null || true)"

  if [[ "$current" == "$previous" ]]; then
    return 0
  fi

  mkdir -p "$HOST_TMP"
  chmod 0700 "$HOST_TMP"
  cp "$CERT_DIR/privkey.pem" "$HOST_TMP/privkey.pem"
  cp "$CERT_DIR/cert.pem" "$HOST_TMP/cert.pem"
  cp "$CERT_DIR/ca.pem" "$HOST_TMP/ca.pem"
  cp "$CERT_DIR/fullchain.pem" "$HOST_TMP/fullchain.pem"
  chmod 0600 "$HOST_TMP/privkey.pem"
  chmod 0644 "$HOST_TMP/cert.pem" "$HOST_TMP/ca.pem" "$HOST_TMP/fullchain.pem"

  if ! host_exec clpctl site:install:certificate \
      --domainName="$SITE_DOMAIN" \
      --privateKey="$HOST_TMP_REL/privkey.pem" \
      --certificate="$HOST_TMP_REL/cert.pem" \
      --certificateChain="$HOST_TMP_REL/ca.pem"; then
    log "clpctl recusou a instalação do certificado; nova tentativa em ${SYNC_INTERVAL}s"
    rm -f "$HOST_TMP"/*.pem
    return 1
  fi

  if ! host_exec nginx -t >/dev/null 2>&1; then
    log "nginx -t falhou após clpctl; certificado não será marcado como sincronizado"
    rm -f "$HOST_TMP"/*.pem
    return 1
  fi

  host_exec nginx -s reload >/dev/null 2>&1 || true
  printf '%s\n' "$current" > "$STATE_FILE"
  chmod 0600 "$STATE_FILE"
  date -Iseconds > "$CERT_DIR/last-cloudpanel-installed-at.txt"
  printf '%s\n' "$SITE_DOMAIN" > "$CERT_DIR/cloudpanel-site-domain.txt"
  printf '%s\n' "$WILDCARD_DOMAIN" > "$CERT_DIR/wildcard-domain.txt"
  chmod 0644 "$CERT_DIR/last-cloudpanel-installed-at.txt" "$CERT_DIR/cloudpanel-site-domain.txt" "$CERT_DIR/wildcard-domain.txt"
  rm -f "$HOST_TMP"/*.pem
  log "Certificado wildcard instalado automaticamente no CloudPanel via clpctl"
}

mkdir -p "$STATE_DIR"
chmod 0700 "$STATE_DIR"
log "Agente iniciado; aguardando o Reverse Proxy $SITE_DOMAIN criado no CloudPanel"

while :; do
  if ! host_ready; then
    log "CloudPanel/clpctl/nginx ainda não disponíveis no host"
    sleep "$SYNC_INTERVAL"
    continue
  fi

  if ! vhost="$(find_vhost)"; then
    log "Reverse Proxy/VHost $SITE_DOMAIN ainda não existe; nenhuma alteração realizada"
    sleep "$SYNC_INTERVAL"
    continue
  fi

  if ! reconcile_vhost "$vhost"; then
    log "VHost localizado, mas não foi possível reconciliar o wildcard com segurança"
    sleep "$SYNC_INTERVAL"
    continue
  fi

  if ! certificate_ready; then
    log "VHost pronto; aguardando emissão ACME do certificado wildcard"
    sleep "$SYNC_INTERVAL"
    continue
  fi

  install_certificate || true
  sleep "$SYNC_INTERVAL"
done
