import { spawnSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { boundedWindowsBuildNumber, prepareWindowsConfig } from './prepare-windows-tauri-version.mjs'

const cliArgs = process.argv.slice(2)
const cwd = process.cwd()
const isWindows = process.platform === 'win32'
const scriptDir = path.dirname(fileURLToPath(import.meta.url))
const repoRoot = path.resolve(scriptDir, '..', '..')

function configArgument(args) {
  const index = args.findIndex((item) => item === '--config')
  if (index >= 0 && args[index + 1]) return { index, value: args[index + 1] }
  const inlineIndex = args.findIndex((item) => item.startsWith('--config='))
  if (inlineIndex >= 0) return { index: inlineIndex, value: args[inlineIndex].slice('--config='.length), inline: true }
  return null
}

function bundlesContainWindowsInstaller(args) {
  const index = args.findIndex((item) => item === '--bundles')
  const raw = index >= 0 ? args[index + 1] || '' : args.find((item) => item.startsWith('--bundles='))?.slice('--bundles='.length) || ''
  return raw.split(',').some((item) => ['msi', 'nsis'].includes(item.trim().toLowerCase()))
}

function resolveRequestedVersion() {
  return String(process.env.SCHEDULER_PRO_RELEASE_TAG || '').trim()
}

function resolveBuildNumber() {
  const explicit = boundedWindowsBuildNumber(process.env.WINDOWS_MSI_BUILD_NUMBER || '')
  if (explicit) return explicit
  return boundedWindowsBuildNumber(process.env.GITHUB_RUN_NUMBER || '')
}

let args = [...cliArgs]
if (isWindows && bundlesContainWindowsInstaller(args)) {
  const currentConfig = configArgument(args)
  const sourceConfigPath = currentConfig?.value || path.join('src-tauri', 'tauri.conf.json')
  if (!fs.existsSync(path.resolve(cwd, sourceConfigPath))) {
    throw new Error(`Configuração Tauri informada não existe: ${sourceConfigPath}`)
  }

  const prepared = prepareWindowsConfig({
    appPath: cwd,
    sourceConfigPath,
    requestedVersion: resolveRequestedVersion(),
    buildNumber: resolveBuildNumber(),
  })
  const generatedRelative = path.relative(cwd, prepared.generatedPath).replaceAll('\\', '/')

  if (currentConfig) {
    if (currentConfig.inline) args[currentConfig.index] = `--config=${generatedRelative}`
    else args[currentConfig.index + 1] = generatedRelative
  } else {
    args.push('--config', generatedRelative)
  }
  console.log(`[windows-bundle] Tauri/WiX version ${prepared.sourceVersion} -> ${prepared.windowsVersion}`)
}

const tauriCli = path.join(repoRoot, 'node_modules', '@tauri-apps', 'cli', 'tauri.js')
if (!fs.existsSync(tauriCli)) {
  throw new Error(`Tauri CLI local não encontrado: ${tauriCli}. Execute npm install antes do build.`)
}

const result = spawnSync(process.execPath, [tauriCli, 'build', ...args], {
  cwd,
  env: process.env,
  stdio: 'inherit',
})

if (result.error) throw result.error
process.exit(result.status ?? 1)
