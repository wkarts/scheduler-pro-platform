import { spawnSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'

const outDir = process.argv[2]
if (!outDir) {
  console.error('Usage: node scripts/build/ensure-tauri-icons.mjs <icons-dir> [--ico]')
  process.exit(2)
}

const source = path.resolve('packages/branding/scheduler-pro/brand-symbol.svg')
const target = path.resolve(outDir)
const tauriBin = path.resolve('node_modules', '.bin', process.platform === 'win32' ? 'tauri.cmd' : 'tauri')

if (!fs.existsSync(source)) {
  console.error(`Canonical Scheduler PRO icon not found: ${source}`)
  process.exit(2)
}
if (!fs.existsSync(tauriBin)) {
  console.error(`Local Tauri CLI not found: ${tauriBin}. Run npm install first.`)
  process.exit(2)
}

fs.mkdirSync(target, { recursive: true })

let result
if (process.platform === 'win32') {
  // Node 24 does not spawn .cmd files directly with spawnSync; invoke the local
  // Tauri CLI through cmd.exe instead. This avoids the npx.cmd EINVAL failure.
  const command = `"${tauriBin}" icon "${source}" --output "${target}"`
  result = spawnSync(process.env.ComSpec || 'cmd.exe', ['/d', '/s', '/c', command], {
    cwd: process.cwd(),
    stdio: 'inherit',
    windowsHide: true,
  })
} else {
  result = spawnSync(tauriBin, ['icon', source, '--output', target], {
    cwd: process.cwd(),
    stdio: 'inherit',
  })
}

if (result.error) {
  console.error(result.error)
  process.exit(1)
}
if ((result.status ?? 1) !== 0) process.exit(result.status ?? 1)

console.log(`Scheduler PRO official v1.0.0 icons ready at ${target}`)
