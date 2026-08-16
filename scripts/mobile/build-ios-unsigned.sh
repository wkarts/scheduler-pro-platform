#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "O build iOS exige macOS com Xcode." >&2
  exit 2
fi

if [[ $# -lt 2 || $# -gt 3 ]]; then
  echo "Uso: $0 <apps/mobile|apps/admin-mobile> <output-dir> [label]" >&2
  exit 2
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
APP_DIR="${1%/}"
OUTPUT_DIR="$2"
LABEL="${3:-ios}"
APP_ROOT="${ROOT_DIR}/${APP_DIR}"
GEN_DIR="${APP_ROOT}/src-tauri/gen/apple"
TARGET_DIR="${APP_ROOT}/src-tauri/target/aarch64-apple-ios"

if [[ ! -f "${APP_ROOT}/package.json" || ! -d "${APP_ROOT}/src-tauri" ]]; then
  echo "Aplicação Tauri inválida: ${APP_DIR}" >&2
  exit 1
fi

mkdir -p "${OUTPUT_DIR}"
OUTPUT_DIR="$(cd "${OUTPUT_DIR}" && pwd)"
if [[ "${OUTPUT_DIR}" == "/" || "${OUTPUT_DIR}" == "${ROOT_DIR}" ]]; then
  echo "Diretório de saída inseguro: ${OUTPUT_DIR}" >&2
  exit 1
fi

find "${OUTPUT_DIR}" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
rm -rf "${GEN_DIR}/build"
LOG_FILE="${OUTPUT_DIR}/${LABEL}-tauri-ios-build.log"
BUILD_MARKER="${OUTPUT_DIR}/.build-started-at"
touch "${BUILD_MARKER}"

cd "${ROOT_DIR}"
npm --workspace "${APP_DIR}" run tauri:ios:init
npm --workspace "${APP_DIR}" run build

find_device_app() {
  find "${GEN_DIR}" "${TARGET_DIR}" \
    -type f -path '*.app/Info.plist' -newer "${BUILD_MARKER}" \
    ! -path '*iphonesimulator*' \
    ! -path '*-iphonesimulator/*' \
    2>/dev/null \
    | while IFS= read -r info_plist; do
        candidate="${info_plist%/Info.plist}"
        if [[ -d "${candidate}" ]]; then printf '%s\n' "${candidate}"; fi
      done \
    | LC_ALL=C sort \
    | head -n 1
}

set +e
CODE_SIGNING_ALLOWED=NO \
CODE_SIGNING_REQUIRED=NO \
CODE_SIGN_IDENTITY="" \
DEVELOPMENT_TEAM="" \
PROVISIONING_PROFILE_SPECIFIER="" \
npm --workspace "${APP_DIR}" run tauri -- ios build \
  --features mobile \
  --target aarch64 \
  --ci \
  --no-sign \
  --archive-only \
  2>&1 | tee "${LOG_FILE}"
TAURI_STATUS=${PIPESTATUS[0]}
set -e

if [[ ${TAURI_STATUS} -ne 0 ]]; then
  echo "Build Tauri iOS não assinado falhou. Consulte ${LOG_FILE}." >&2
  exit "${TAURI_STATUS}"
fi

APP_PATH="$(find_device_app || true)"
if [[ -z "${APP_PATH}" || ! -d "${APP_PATH}" ]]; then
  echo "O archive terminou sem erro, mas nenhum .app iphoneos foi localizado." >&2
  find "${GEN_DIR}" "${TARGET_DIR}" -maxdepth 8 -type d -name '*.app' -print 2>/dev/null || true
  exit 1
fi

FINAL_APP="${OUTPUT_DIR}/$(basename "${APP_PATH}")"
rm -rf "${FINAL_APP}"
ditto "${APP_PATH}" "${FINAL_APP}"
rm -f "${BUILD_MARKER}"
printf '%s\n' "${FINAL_APP}" > "${OUTPUT_DIR}/app-path.txt"
echo "Bundle iOS ARM64 não assinado preparado em ${FINAL_APP}"
