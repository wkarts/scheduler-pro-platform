import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

const MAX_MSI_PRERELEASE = 65535

export function normalizeWindowsBundleVersion(rawVersion, buildNumberRaw = '') {
  const version = String(rawVersion || '').trim().replace(/^v/i, '')
  const match = version.match(/^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$/)
  if (!match) throw new Error(`Versão SemVer inválida para o bundle Windows: ${rawVersion}`)

  const [, major, minor, patch, prerelease = ''] = match
  if (!prerelease) return `${major}.${minor}.${patch}`

  const explicitBuild = String(buildNumberRaw || '').trim()
  const prereleaseParts = prerelease.split('.')
  const numericCandidate = explicitBuild || [...prereleaseParts].reverse().find((part) => /^\d+$/.test(part)) || ''
  if (!/^\d+$/.test(numericCandidate)) {
    throw new Error(
      `O MSI exige prerelease numérico. Informe um build number entre 0 e ${MAX_MSI_PRERELEASE} para ${rawVersion}.`,
    )
  }

  const numeric = Number(numericCandidate)
  if (!Number.isSafeInteger(numeric) || numeric < 0 || numeric > MAX_MSI_PRERELEASE) {
    throw new Error(`Build number MSI fora do intervalo 0..${MAX_MSI_PRERELEASE}: ${numericCandidate}`)
  }
  return `${major}.${minor}.${patch}-${numeric}`
}

function selfTest() {
  assert.equal(normalizeWindowsBundleVersion('0.1.0-alpha.1'), '0.1.0-1')
  assert.equal(normalizeWindowsBundleVersion('v0.1.0-alpha.847'), '0.1.0-847')
  assert.equal(normalizeWindowsBundleVersion('0.1.0-beta.7', '991'), '0.1.0-991')
  assert.equal(normalizeWindowsBundleVersion('0.1.0'), '0.1.0')
  assert.throws(() => normalizeWindowsBundleVersion('0.1.0-alpha'), /prerelease numérico/)
  assert.throws(() => normalizeWindowsBundleVersion('0.1.0-alpha.70000'), /fora do intervalo/)
  console.log('windows-tauri-version-self-test-ok')
}

if (process.argv.includes('--self-test')) {
  selfTest()
  process.exit(0)
}

const [appPath, requestedVersion = '', buildNumber = ''] = process.argv.slice(2)
if (!appPath) {
  console.error('Uso: node prepare-windows-tauri-version.mjs <app-path> [semantic-version] [build-number]')
  process.exit(2)
}

const root = path.resolve(appPath)
const srcTauri = path.join(root, 'src-tauri')
const basePath = path.join(srcTauri, 'tauri.conf.json')
const generatedPath = path.join(srcTauri, 'tauri.windows.conf.json')
const config = JSON.parse(fs.readFileSync(basePath, 'utf8'))
const sourceVersion = requestedVersion || config.version
const windowsVersion = normalizeWindowsBundleVersion(sourceVersion, buildNumber)

config.version = windowsVersion
fs.writeFileSync(generatedPath, `${JSON.stringify(config, null, 2)}\n`)
console.log(JSON.stringify({ appPath: root, sourceVersion, windowsVersion, generatedPath }))
