let deferredPrompt: any = null

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
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => undefined)
  })
}
