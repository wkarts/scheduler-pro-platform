import fs from 'node:fs'
import path from 'node:path'

const [appPath, apiUrl, productName, identifier] = process.argv.slice(2)
if (!appPath || !apiUrl) {
  console.error('Uso: node configure-desktop-webview.mjs <app-path> <api-url> [product-name] [identifier]')
  process.exit(2)
}

const parsed = new URL(apiUrl)
const local = ['localhost', '127.0.0.1'].includes(parsed.hostname)
if (parsed.protocol !== 'https:' && !(local && parsed.protocol === 'http:')) {
  throw new Error('A API da distribuição exige HTTPS; HTTP é aceito apenas em localhost.')
}
let normalizedApi = parsed.toString().replace(/\/$/, '')
if (!/\/api\/v1(?:\/|$)/.test(new URL(normalizedApi).pathname)) normalizedApi += '/api/v1'

const root = path.resolve(appPath)
const srcTauri = path.join(root, 'src-tauri')
const basePath = path.join(srcTauri, 'tauri.conf.json')
const generatedPath = path.join(srcTauri, 'tauri.generated.conf.json')
const config = JSON.parse(fs.readFileSync(basePath, 'utf8'))

if (config?.build?.frontendDist !== '../dist' || !config?.build?.beforeBuildCommand) {
  throw new Error('A configuração base precisa empacotar o frontend local antes da distribuição.')
}
config.productName = productName || config.productName
if (identifier) config.identifier = identifier
config.app = config.app || {}
config.app.windows = config.app.windows || [{ label: 'main' }]
config.app.windows[0] = { ...config.app.windows[0], title: config.productName }
delete config.app.windows[0].url
config.bundle = config.bundle || {}
config.bundle.shortDescription = config.productName

const envKey = path.basename(root) === 'admin-desktop' ? 'VITE_ADMIN_API_BASE_URL' : 'VITE_API_BASE_URL'
fs.writeFileSync(path.join(root, '.env.production.local'), `${envKey}=${normalizedApi}\n`)
fs.writeFileSync(generatedPath, `${JSON.stringify(config, null, 2)}\n`)
console.log(JSON.stringify({ generatedPath, envKey, apiUrl: normalizedApi }))
