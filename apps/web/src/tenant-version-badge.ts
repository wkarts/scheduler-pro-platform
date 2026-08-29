type VersionPayload = {
  data?: {
    version?: string
    release_tag?: string | null
    build_sha?: string | null
  }
}

let versionLabel = 'versão…'
let buildSha = ''
let disposed = false
let applying = false

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function connectionLabel(raw: string): string {
  const value = raw.trim().replace(/^Scheduler Pro\s*·\s*/i, '')
  return value || 'Operação conectada'
}

function applyTenantVersion(): void {
  if (disposed || applying) return
  const shell = document.querySelector<HTMLElement>('.tenant-console')
  if (!shell) return

  applying = true
  try {
    document.title = 'Scheduler Pro'

    // Nome/versão do produto não compete com a marca do tenant no cabeçalho.
    const topVersion = shell.querySelector<HTMLElement>('.sidebar > .brand > div > small')
    if (topVersion) {
      topVersion.hidden = true
      topVersion.style.display = 'none'
      topVersion.setAttribute('aria-hidden', 'true')
    }

    const footer = shell.querySelector<HTMLElement>('.sidebar-footer .version-info')
    if (!footer) return

    const status = connectionLabel(footer.querySelector('small')?.textContent || '')
    const version = `${versionLabel}${buildSha ? ` · ${buildSha.slice(0, 8)}` : ''}`
    const strongText = footer.querySelector('strong')?.textContent?.trim() || ''
    const smallText = footer.querySelector('small')?.textContent?.trim() || ''
    const desiredSmall = `Scheduler Pro · ${status}`

    if (strongText === version && smallText === desiredSmall) return
    footer.innerHTML = `<strong>${escapeHtml(version)}</strong><small>${escapeHtml(desiredSmall)}</small>`
    footer.dataset.schedulerRuntimeVersion = version
  } finally {
    applying = false
  }
}

export function installTenantVersionBadge(): void {
  const observer = new MutationObserver(() => applyTenantVersion())
  observer.observe(document.documentElement, { childList: true, subtree: true, characterData: true })
  applyTenantVersion()

  void fetch('/api/v1/version', { cache: 'no-store', headers: { Accept: 'application/json' } })
    .then((response) => response.ok ? response.json() : Promise.reject(new Error('version unavailable')))
    .then((payload: VersionPayload) => {
      const value = payload.data
      versionLabel = value?.release_tag || (value?.version ? `v${value.version}` : 'versão indisponível')
      buildSha = value?.build_sha || ''
      applyTenantVersion()
    })
    .catch(() => {
      versionLabel = 'versão indisponível'
      buildSha = ''
      applyTenantVersion()
    })

  window.addEventListener('beforeunload', () => {
    disposed = true
    observer.disconnect()
  }, { once: true })
}
