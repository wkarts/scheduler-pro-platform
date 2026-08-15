#!/usr/bin/env bash
set -euo pipefail
SUFFIX="${1:-local}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
mkdir -p artifacts/apps artifacts/deploy
npm install
npm --workspace apps/web run build
npm --workspace apps/admin run build
npm --workspace apps/desktop run build
npm --workspace apps/mobile run build
tar -C apps/web/dist -czf "artifacts/apps/scheduler-pro-web-${SUFFIX}.tar.gz" .
tar -C apps/admin/dist -czf "artifacts/apps/scheduler-pro-admin-${SUFFIX}.tar.gz" .
tar -C apps/desktop/dist -czf "artifacts/apps/scheduler-pro-desktop-shell-${SUFFIX}.tar.gz" .
tar -C apps/mobile/dist -czf "artifacts/apps/scheduler-pro-mobile-shell-${SUFFIX}.tar.gz" .
tar -C deployments/cloudpanel -czf "artifacts/deploy/scheduler-pro-cloudpanel-${SUFFIX}.tar.gz" .
tar -C deployments/dockge -czf "artifacts/deploy/scheduler-pro-dockge-${SUFFIX}.tar.gz" .
sha256sum artifacts/apps/*.tar.gz artifacts/deploy/*.tar.gz > artifacts/SHA256SUMS.txt
printf 'Distribution artifacts created under artifacts/\n'
