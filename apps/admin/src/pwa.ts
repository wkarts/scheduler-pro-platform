let deferredPrompt: any = null
let reloadingForWorker = false
let revalidatePromise: Promise<void> | null = null
let lastRevalidatedAt = 0
const WORKER_RELOAD_KEY = 'scheduler_pro_admin_worker_reload_at'

function isStandalone(): boolean {
  const navigatorWithStandalone = navigator as Navigator & { standalone?: boolean }
  return window.matchMedia('(display-mode: standalone)').matches || Boolean(navigatorWithStandalone.standalone)
}

function publishState(eventName = 'scheduler-pro-admin-install-state'): void {
  ;(window as any).schedulerProAdminPwa = {
    canInstall: Boolean(deferredPrompt) && !isStandalone(),
    isInstalled: isStandalone(),
    install: async () => {
      if (isStandalone() || !deferredPrompt) return { outcome: 'unavailable' }
      await deferredPrompt.prompt()
      const choice = await deferredPrompt.userChoice.catch(() => ({ outcome: 'dismissed' }))
      deferredPrompt = null
      publishState()
      return choice
    },
  }
  window.dispatchEvent(new CustomEvent(eventName))
}

function platformToken(): string {
  const raw = localStorage.getItem('scheduler-pro-admin-session')
  if (!raw) return ''
  try { return String(JSON.parse(raw)?.accessToken || '') } catch { return '' }
}

function reloadForNewWorker(): void {
  if (reloadingForWorker) return
  const now = Date.now()
  const previous = Number(sessionStorage.getItem(WORKER_RELOAD_KEY) || 0)
  if (now - previous < 10_000) return
  reloadingForWorker = true
  sessionStorage.setItem(WORKER_RELOAD_KEY, String(now))
  window.location.reload()
}

async function revalidateAdmin(reason: string): Promise<void> {
  if (document.visibilityState === 'hidden') return
  if (revalidatePromise) return revalidatePromise
  const now = Date.now()
  if (now - lastRevalidatedAt < 750 && reason !== 'online') return
  lastRevalidatedAt = now
  revalidatePromise = (async () => {
    if ('serviceWorker' in navigator) {
      const registration = await navigator.serviceWorker.getRegistration().catch(() => undefined)
      if (registration) await registration.update().catch(() => undefined)
    }
    const token = platformToken()
    if (token) {
      await fetch('/api/v1/auth/platform/2fa/state', {
        headers: { Accept: 'application/json', Authorization: `Bearer ${token}` },
        cache: 'no-store',
      }).catch(() => undefined)
    }
    window.dispatchEvent(new CustomEvent('scheduler-pro-admin-revalidate-current-view', {
      detail: { reason, at: Date.now(), online: navigator.onLine },
    }))
  })().finally(() => { revalidatePromise = null })
  return revalidatePromise
}

window.addEventListener('beforeinstallprompt', event => {
  event.preventDefault()
  if (isStandalone()) {
    deferredPrompt = null
    publishState('scheduler-pro-admin-installed')
    return
  }
  deferredPrompt = event
  publishState('scheduler-pro-admin-install-ready')
})

window.addEventListener('appinstalled', () => {
  deferredPrompt = null
  publishState('scheduler-pro-admin-installed')
})

window.addEventListener('DOMContentLoaded', () => publishState())

if ('serviceWorker' in navigator) {
  navigator.serviceWorker.addEventListener('controllerchange', reloadForNewWorker)
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js', { updateViaCache: 'none' }).then(registration => {
      void registration.update()
      window.setInterval(() => {
        if (document.visibilityState === 'visible' && navigator.onLine) void registration.update()
      }, 60_000)
    }).catch(() => undefined)
  })
}

document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible') void revalidateAdmin('visibilitychange')
})
window.addEventListener('focus', () => { void revalidateAdmin('focus') })
window.addEventListener('online', () => { void revalidateAdmin('online') })
window.addEventListener('pageshow', event => {
  void revalidateAdmin((event as PageTransitionEvent).persisted ? 'pageshow-bfcache' : 'pageshow')
})
