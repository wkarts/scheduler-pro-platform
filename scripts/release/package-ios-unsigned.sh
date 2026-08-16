#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Uso: $0 /caminho/Aplicacao.app /caminho/saida-unsigned.ipa" >&2
  exit 2
fi
if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "A validação do bundle iOS exige macOS/Xcode." >&2
  exit 2
fi

APP_PATH="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
OUTPUT_DIR="$(dirname "$2")"
mkdir -p "${OUTPUT_DIR}"
OUTPUT_DIR="$(cd "${OUTPUT_DIR}" && pwd)"
OUTPUT_PATH="${OUTPUT_DIR}/$(basename "$2")"

if [[ ! -d "${APP_PATH}" || "${APP_PATH}" != *.app ]]; then
  echo "Bundle .app inválido: ${APP_PATH}" >&2
  exit 1
fi
if [[ "${OUTPUT_PATH}" != *.ipa ]]; then
  echo "Saída deve terminar em .ipa: ${OUTPUT_PATH}" >&2
  exit 1
fi

INFO_PLIST="${APP_PATH}/Info.plist"
if [[ ! -f "${INFO_PLIST}" ]]; then
  echo "Info.plist ausente em ${APP_PATH}." >&2
  exit 1
fi
EXECUTABLE_NAME="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleExecutable' "${INFO_PLIST}" 2>/dev/null || true)"
if [[ -z "${EXECUTABLE_NAME}" ]]; then
  echo "CFBundleExecutable ausente." >&2
  exit 1
fi
EXECUTABLE_PATH="${APP_PATH}/${EXECUTABLE_NAME}"
if [[ ! -f "${EXECUTABLE_PATH}" || ! -x "${EXECUTABLE_PATH}" ]]; then
  echo "Executável principal inválido: ${EXECUTABLE_PATH}" >&2
  exit 1
fi

FILE_INFO="$(file "${EXECUTABLE_PATH}")"
if [[ "${FILE_INFO}" != *Mach-O* || "${FILE_INFO}" != *arm64* ]]; then
  echo "Executável não é Mach-O ARM64: ${FILE_INFO}" >&2
  exit 1
fi
if ! xcrun lipo -info "${EXECUTABLE_PATH}" 2>&1 | grep -qw arm64; then
  echo "Arquitetura ARM64 não confirmada." >&2
  exit 1
fi
BUILD_INFO="$(xcrun vtool -show-build "${EXECUTABLE_PATH}" 2>&1 || true)"
if grep -q 'platform IOSSIMULATOR' <<<"${BUILD_INFO}"; then
  echo "Bundle é de simulador, não iphoneos." >&2
  exit 1
fi
if ! grep -q 'platform IOS' <<<"${BUILD_INFO}"; then
  echo "Plataforma IOS física não confirmada." >&2
  exit 1
fi
if [[ -e "${APP_PATH}/embedded.mobileprovision" ]]; then
  echo "Bundle contém provisioning profile; esperado unsigned." >&2
  exit 1
fi
if [[ -d "${APP_PATH}/_CodeSignature" ]] || codesign -d "${APP_PATH}" >/dev/null 2>&1; then
  echo "Bundle contém assinatura; esperado unsigned." >&2
  exit 1
fi

TEMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/scheduler-ios-unsigned.XXXXXX")"
trap 'rm -rf "${TEMP_DIR}"' EXIT INT TERM
APP_BASENAME="$(basename "${APP_PATH}")"
mkdir -p "${TEMP_DIR}/Payload"
ditto "${APP_PATH}" "${TEMP_DIR}/Payload/${APP_BASENAME}"
rm -f "${OUTPUT_PATH}" "${OUTPUT_PATH}.sha256"
(
  cd "${TEMP_DIR}"
  /usr/bin/zip -qry --symlinks "${OUTPUT_PATH}" Payload
)

unzip -tq "${OUTPUT_PATH}" >/dev/null
ENTRIES="$(unzip -Z1 "${OUTPUT_PATH}")"
if grep -Eq '(^/|(^|/)\.\.(/|$))' <<<"${ENTRIES}"; then
  echo "IPA contém caminho inseguro." >&2
  exit 1
fi
if ! grep -Fxq "Payload/${APP_BASENAME}/Info.plist" <<<"${ENTRIES}"; then
  echo "IPA sem Info.plist esperado." >&2
  exit 1
fi
if ! grep -Fxq "Payload/${APP_BASENAME}/${EXECUTABLE_NAME}" <<<"${ENTRIES}"; then
  echo "IPA sem executável principal." >&2
  exit 1
fi

DIGEST="$(shasum -a 256 "${OUTPUT_PATH}" | awk '{print $1}')"
printf '%s  %s\n' "${DIGEST}" "$(basename "${OUTPUT_PATH}")" > "${OUTPUT_PATH}.sha256"
echo "IPA não assinado válido: ${OUTPUT_PATH}"
echo "SHA-256: ${DIGEST}"
