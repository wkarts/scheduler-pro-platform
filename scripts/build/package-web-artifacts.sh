#!/usr/bin/env bash
set -euo pipefail

VERSION="${1:-local}"
mkdir -p artifacts
npm install
npm --workspace apps/web run build
npm --workspace apps/admin run build
tar -C apps/web/dist -czf "artifacts/scheduler-pro-web-${VERSION}.tar.gz" .
tar -C apps/admin/dist -czf "artifacts/scheduler-pro-admin-${VERSION}.tar.gz" .
tar -C deployments/cloudpanel -czf "artifacts/scheduler-pro-cloudpanel-deploy-${VERSION}.tar.gz" .
tar -C deployments/dockge -czf "artifacts/scheduler-pro-dockge-deploy-${VERSION}.tar.gz" .
