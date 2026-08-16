import fs from 'node:fs'
import path from 'node:path'

const [appPath, remoteUrl, productName, identifier] = process.argv.slice(2)
if (!appPath || !remoteUrl) {
  console.error('Uso: node configure-desktop-webview.mjs <app-path> <https-url> [product-name] [identifier]')
  process.exit(2)
}

const parsed = new URL(remoteUrl)
if (parsed.protocol !== 'https:') {
  throw new Error('A versão desktop exige URL HTTPS.')
}

const srcTauri = path.resolve(appPath, 'src-tauri')
const basePath = path.join(srcTauri, 'tauri.conf.json')
const generatedPath = path.join(srcTauri, 'tauri.generated.conf.json')
const config = JSON.parse(fs.readFileSync(basePath, 'utf8'))

config.build = config.build || {}
config.build.devUrl = parsed.toString().replace(/\/$/, '')
config.build.frontendDist = parsed.toString().replace(/\/$/, '')
config.build.beforeBuildCommand = null
config.build.beforeDevCommand = null
config.build.removeUnusedCommands = true

config.app = config.app || {}
config.app.windows = config.app.windows || [{ label: 'main' }]
config.app.windows[0] = {
  ...config.app.windows[0],
  label: config.app.windows[0].label || 'main',
  url: parsed.toString().replace(/\/$/, ''),
}

if (productName) {
  config.productName = productName
  config.app.windows[0].title = productName
  config.bundle = config.bundle || {}
  config.bundle.shortDescription = productName
}
if (identifier) config.identifier = identifier

fs.writeFileSync(generatedPath, `${JSON.stringify(config, null, 2)}\n`)
console.log(generatedPath)
