let deferredPrompt: any = null

window.addEventListener('beforeinstallprompt', event => {
  event.preventDefault()
  deferredPrompt = event
  ;(window as any).schedulerProAdminPwa = {
    install: async () => {
      if (!deferredPrompt) return
      deferredPrompt.prompt()
      await deferredPrompt.userChoice.catch(() => undefined)
      deferredPrompt = null
    },
  }
  window.dispatchEvent(new CustomEvent('scheduler-pro-admin-install-ready'))
})

window.addEventListener('appinstalled', () => {
  deferredPrompt = null
})

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => undefined)
  })
}
