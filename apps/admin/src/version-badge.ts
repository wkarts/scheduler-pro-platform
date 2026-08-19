type VersionPayload = { data?: { version?: string; release_tag?: string | null; build_sha?: string | null } }

export function installVersionBadge(): void {
  let disposed = false
  const badge = document.createElement('div')
  badge.className = 'scheduler-pro-version-badge'
  badge.textContent = 'Scheduler Pro · versão…'
  const style = document.createElement('style')
  style.textContent = `.scheduler-pro-version-badge{margin:8px 10px 4px;padding:8px 10px;border-top:1px solid rgba(148,163,184,.16);color:#94a3b8;font-size:10px;line-height:1.35}.scheduler-pro-version-badge strong{color:#cbd5e1}`
  document.head.appendChild(style)

  const attach = () => {
    if (disposed || badge.isConnected) return
    const footer = document.querySelector('.sidebar-footer')
    if (footer) footer.appendChild(badge)
  }
  const observer = new MutationObserver(attach)
  observer.observe(document.documentElement, { childList: true, subtree: true })
  attach()

  void fetch('/api/v1/version', { headers: { Accept: 'application/json' } })
    .then((response) => response.ok ? response.json() : Promise.reject(new Error('version unavailable')))
    .then((payload: VersionPayload) => {
      const value = payload.data
      const label = value?.release_tag || (value?.version ? `v${value.version}` : 'versão indisponível')
      const sha = value?.build_sha ? ` · ${value.build_sha.slice(0, 8)}` : ''
      badge.innerHTML = `<strong>${label}</strong>${sha}<br>Control Plane`
      attach()
    })
    .catch(() => { badge.textContent = 'Scheduler Pro · versão indisponível' })

  window.addEventListener('beforeunload', () => {
    disposed = true
    observer.disconnect()
  }, { once: true })
}
