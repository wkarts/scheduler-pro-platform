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

if (!fs.existsSync(source)) {
  console.error(`Canonical Scheduler PRO icon not found: ${source}`)
  process.exit(2)
}

fs.mkdirSync(target, { recursive: true })

const result = spawnSync(
  'npx',
  ['tauri', 'icon', source, '--output', target],
  {
    cwd: process.cwd(),
    stdio: 'inherit',
    shell: process.platform === 'win32',
    windowsHide: true,
  },
)

if (result.error) {
  console.error(result.error)
  process.exit(1)
}
if ((result.status ?? 1) !== 0) process.exit(result.status ?? 1)

console.log(`Scheduler PRO official v1.0.0 icons ready at ${target}`)
