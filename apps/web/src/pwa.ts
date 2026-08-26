type BeforeInstallPromptEvent = Event & {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed'; platform: string }>
}

export type PwaPlatform = 'ios' | 'android' | 'desktop' | 'other'
export type PwaInstallState = {
  installed: boolean
  promptAvailable: boolean
  platform: PwaPlatform
  supported: boolean
  manualInstall: boolean
}
export type PwaInstallResult = 'accepted' | 'dismissed' | 'installed' | 'manual' | 'unavailable'

export const PWA_INSTALL_STATE_EVENT = 'scheduler:pwa-install-state'
export const APP_REVALIDATE_EVENT = 'scheduler-pro-revalidate-current-view'

let deferredPrompt: BeforeInstallPromptEvent | null = null
let reloadingForWorker = false
let revalidatePromise: Promise<void> | null = null
let lastRevalidatedAt = 0
const WORKER_RELOAD_KEY = 'scheduler_pro_worker_reload_at'

function iosDevice(): boolean {
  const ua = navigator.userAgent
  return /iPad|iPhone|iPod/i.test(ua) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)
}

function androidDevice(): boolean {
  return /Android/i.test(navigator.userAgent)
}

export function pwaPlatform(): PwaPlatform {
  if (iosDevice()) return 'ios'
  if (androidDevice()) return 'android'
  if (/Windows|Macintosh|Linux|CrOS/i.test(navigator.userAgent)) return 'desktop'
  return 'other'
}

export function isPwaInstalled(): boolean {
  return window.matchMedia('(display-mode: standalone)').matches ||
    Boolean((window.navigator as Navigator & { standalone?: boolean }).standalone)
}

export function getPwaInstallState(): PwaInstallState {
  const platform = pwaPlatform()
  const installed = isPwaInstalled()
  return {
    installed,
    promptAvailable: Boolean(deferredPrompt),
    platform,
    supported: window.isSecureContext && 'serviceWorker' in navigator,
    manualInstall: !installed && platform === 'ios',
  }
}

function notifyInstallState(): void {
  window.dispatchEvent(new CustomEvent<PwaInstallState>(PWA_INSTALL_STATE_EVENT, {
    detail: getPwaInstallState(),
  }))
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

async function validateSession(): Promise<void> {
  if (!localStorage.getItem('scheduler_pro_access_token')) return
  await fetch('/api/v1/auth/2fa/state', {
    method: 'GET',
    headers: { Accept: 'application/json' },
    cache: 'no-store',
  }).catch(() => undefined)
}

export async function revalidateApplication(reason: string): Promise<void> {
  if (document.visibilityState === 'hidden') return
  const now = Date.now()
  if (revalidatePromise) return revalidatePromise
  if (now - lastRevalidatedAt < 750 && reason !== 'online') return
  lastRevalidatedAt = now
  revalidatePromise = (async () => {
    if ('serviceWorker' in navigator) {
      const registration = await navigator.serviceWorker.getRegistration().catch(() => undefined)
      if (registration) await registration.update().catch(() => undefined)
    }
    await validateSession()
    window.dispatchEvent(new CustomEvent(APP_REVALIDATE_EVENT, {
      detail: { reason, at: Date.now(), online: navigator.onLine },
    }))
  })().finally(() => { revalidatePromise = null })
  return revalidatePromise
}

export function pwaInstallInstructions(platform: PwaPlatform = pwaPlatform()): string {
  if (platform === 'ios') {
    return 'No iPhone ou iPad, abra esta página no Safari, toque em Compartilhar e escolha “Adicionar à Tela de Início”.'
  }
  if (platform === 'android') {
    return 'No Android, use Chrome ou Edge e escolha “Instalar app” ou “Adicionar à tela inicial” no menu do navegador.'
  }
  if (platform === 'desktop') {
    return 'No Chrome ou Edge, use o ícone de instalação na barra de endereço ou o menu do navegador e escolha “Instalar Scheduler PRO”.'
  }
  return 'Use o menu do navegador para instalar ou adicionar o Scheduler PRO à tela inicial.'
}

export async function requestPwaInstall(): Promise<PwaInstallResult> {
  if (isPwaInstalled()) return 'installed'
  if (pwaPlatform() === 'ios') return 'manual'
  if (!deferredPrompt) return 'unavailable'

  const prompt = deferredPrompt
  deferredPrompt = null
  await prompt.prompt()
  const choice = await prompt.userChoice
  notifyInstallState()
  return choice.outcome
}

window.addEventListener('beforeinstallprompt', (event) => {
  event.preventDefault()
  deferredPrompt = event as BeforeInstallPromptEvent
  notifyInstallState()
})

window.addEventListener('appinstalled', () => {
  deferredPrompt = null
  notifyInstallState()
})

const displayMode = window.matchMedia('(display-mode: standalone)')
if (typeof displayMode.addEventListener === 'function') {
  displayMode.addEventListener('change', notifyInstallState)
}

if ('serviceWorker' in navigator) {
  navigator.serviceWorker.addEventListener('controllerchange', reloadForNewWorker)

  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').then((registration) => {
      notifyInstallState()
      void registration.update()
      window.setInterval(() => {
        if (document.visibilityState === 'visible' && navigator.onLine) {
          void registration.update()
        }
      }, 60_000)
    }).catch(() => undefined)
  })
}

document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible') void revalidateApplication('visibilitychange')
})
window.addEventListener('focus', () => { void revalidateApplication('focus') })
window.addEventListener('online', () => { void revalidateApplication('online') })
window.addEventListener('pageshow', (event) => {
  void revalidateApplication((event as PageTransitionEvent).persisted ? 'pageshow-bfcache' : 'pageshow')
})

window.queueMicrotask(notifyInstallState)
