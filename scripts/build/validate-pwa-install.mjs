import { readFile } from 'node:fs/promises'

const files = {
  manifest: 'apps/web/public/manifest.webmanifest',
  serviceWorker: 'apps/web/public/sw.js',
  pwa: 'apps/web/src/pwa.ts',
  app: 'apps/web/src/App.vue',
  surface: 'apps/web/src/TenantPwaInstallSurface.vue',
  downloads: 'apps/web/src/TenantUniversalDownloads.vue',
}

const loaded = Object.fromEntries(
  await Promise.all(Object.entries(files).map(async ([key, path]) => [key, await readFile(path, 'utf8')]))
)

function requireText(name, text, needle) {
  if (!text.includes(needle)) {
    throw new Error(`PWA contract failed: ${name} must contain ${JSON.stringify(needle)}`)
  }
}

const manifest = JSON.parse(loaded.manifest)
if (manifest.display !== 'standalone') throw new Error('PWA contract failed: manifest display must be standalone')
if (manifest.start_url !== '/?source=pwa') throw new Error('PWA contract failed: manifest start_url must be /?source=pwa')
if (!Array.isArray(manifest.icons) || manifest.icons.length === 0) throw new Error('PWA contract failed: manifest must contain icons')

requireText('pwa.ts', loaded.pwa, 'beforeinstallprompt')
requireText('pwa.ts', loaded.pwa, 'appinstalled')
requireText('pwa.ts', loaded.pwa, "navigator.serviceWorker.register('/sw.js'")
requireText('pwa.ts', loaded.pwa, "updateViaCache: 'none'")
requireText('App.vue', loaded.app, 'TenantPwaInstallSurface')
requireText('App.vue', loaded.app, "new URLSearchParams(window.location.search).get('source')==='pwa'")
requireText('TenantPwaInstallSurface.vue', loaded.surface, '.tenant-login-card')
requireText('TenantPwaInstallSurface.vue', loaded.surface, '.tenant-console .topbar')
requireText('TenantUniversalDownloads.vue', loaded.downloads, 'Web App / PWA')
requireText('TenantUniversalDownloads.vue', loaded.downloads, 'Adicionar à Tela de Início')

console.log('pwa-install-contract-ok')
