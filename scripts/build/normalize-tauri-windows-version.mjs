import fs from 'node:fs'
import path from 'node:path'

const [appPath, configRelativePath = 'src-tauri/tauri.conf.json', requestedVersion = ''] = process.argv.slice(2)

if (!appPath) {
  console.error('Uso: node normalize-tauri-windows-version.mjs <app-path> [config-path] [release-version]')
  process.exit(2)
}

const configPath = path.resolve(appPath, configRelativePath)
if (!fs.existsSync(configPath)) {
  throw new Error(`Configuração Tauri não encontrada: ${configPath}`)
}

const config = JSON.parse(fs.readFileSync(configPath, 'utf8'))
const sourceVersion = String(requestedVersion || config.version || '').trim().replace(/^v/i, '')
const match = sourceVersion.match(/^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$/)

if (!match) {
  throw new Error(`Versão SemVer inválida para normalização Windows: ${sourceVersion || '<vazia>'}`)
}

const [, major, minor, patch, prerelease = ''] = match
let safeVersion = `${major}.${minor}.${patch}`

if (prerelease) {
  const runNumber = Number(process.env.GITHUB_RUN_NUMBER || '')
  const prereleaseNumbers = prerelease.match(/\d+/g)?.map(Number).filter(Number.isFinite) || []
  const requestedNumeric = Number.isSafeInteger(runNumber) && runNumber > 0
    ? runNumber
    : (prereleaseNumbers.at(-1) || 1)

  // Tauri/WiX aceita identificador pre-release no MSI apenas quando ele é
  // exclusivamente numérico e <= 65535. Mantemos o SemVer canônico do projeto
  // intacto e normalizamos somente a configuração efêmera usada no runner.
  const numericPrerelease = ((requestedNumeric - 1) % 65535) + 1
  safeVersion = `${major}.${minor}.${patch}-${numericPrerelease}`
}

config.version = safeVersion
fs.writeFileSync(configPath, `${JSON.stringify(config, null, 2)}\n`)

const result = {
  configPath,
  sourceVersion,
  windowsBundleVersion: safeVersion,
}
console.log(JSON.stringify(result))

if (process.env.GITHUB_OUTPUT) {
  fs.appendFileSync(process.env.GITHUB_OUTPUT, `windows_bundle_version=${safeVersion}\n`)
}
