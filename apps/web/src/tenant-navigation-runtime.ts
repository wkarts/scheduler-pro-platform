import { announceTenantNavigation } from './tenantNavigation'

const EXTENSION_ROUTES: Record<string, string> = {
  'Calendário': 'calendar',
  'Personalização': 'personalizacao',
  'E-mail SMTP': 'smtp',
  'Agenda pública': 'agenda-publica',
  'Mensagens': 'mensagens',
}

let installed = false
let syncing = false
let lastBaseRoute = 'dashboard'
let openingRoute = ''
let openRaf = 0
let retryTimer: number | undefined

function tenantRoot(): HTMLElement | null {
  return document.querySelector<HTMLElement>('.tenant-console')
}

function currentRoute(): string {
  return (window.location.hash || '#dashboard').replace(/^#/, '')
}

function isExtensionRoute(route: string): boolean {
  return Object.values(EXTENSION_ROUTES).includes(route)
}

function extensionButtonFor(route: string): HTMLButtonElement | null {
  const entry = Object.entries(EXTENSION_ROUTES).find(([, value]) => value === route)
  if (!entry) return null
  const [label] = entry
  return Array.from(document.querySelectorAll<HTMLButtonElement>('.tenant-console .sp-extension-nav'))
    .find((button) => button.textContent?.trim().includes(label)) || null
}

function primeVisibleLabels(): void {
  const root = tenantRoot()
  if (!root) return
  for (const button of Array.from(root.querySelectorAll<HTMLButtonElement>('.sidebar .nav-item'))) {
    const regular = Array.from(button.querySelectorAll('span'))
      .find((span) => !span.classList.contains('sp-runtime-mobile-label'))
    const text = regular?.textContent?.trim() || ''
    if (text) button.dataset.spLabel = text
  }
}

function cacheAndRestoreLabels(): void {
  const root = tenantRoot()
  if (!root) return
  const mobileOpen = root.classList.contains('mobileOpen')
  const buttons = Array.from(root.querySelectorAll<HTMLButtonElement>('.sidebar .nav-item'))
  for (const button of buttons) {
    const regular = Array.from(button.querySelectorAll('span'))
      .find((span) => !span.classList.contains('sp-runtime-mobile-label'))
    const text = regular?.textContent?.trim() || button.dataset.spLabel || ''
    if (text && button.dataset.spLabel !== text) button.dataset.spLabel = text
    const runtime = button.querySelector<HTMLSpanElement>('.sp-runtime-mobile-label')
    if (mobileOpen && !regular && button.dataset.spLabel && !runtime) {
      const span = document.createElement('span')
      span.className = 'sp-runtime-mobile-label'
      span.textContent = button.dataset.spLabel
      button.appendChild(span)
    } else if (!mobileOpen && runtime) runtime.remove()
  }
}

function syncSelectedNavigation(): void {
  const root = tenantRoot()
  if (!root) return
  const route = currentRoute()
  const extensionRoute = isExtensionRoute(route)
  document.body.classList.toggle('sp-smart-agenda-open', route === 'agenda')
  if (!extensionRoute) {
    if (route) lastBaseRoute = route
    root.querySelectorAll('.sp-extension-nav.active').forEach((item) => item.classList.remove('active'))
    return
  }
  const target = extensionButtonFor(route)
  for (const item of Array.from(root.querySelectorAll<HTMLElement>('.sidebar .nav-item'))) {
    item.classList.toggle('active', item === target)
  }
}

function titleMatches(expectedLabel: string, currentTitle: string): boolean {
  if (expectedLabel === 'Calendário') return currentTitle.includes('Calendário')
  if (expectedLabel === 'Personalização') return currentTitle.includes('Personalização')
  if (expectedLabel === 'E-mail SMTP') return currentTitle.includes('E-mail')
  if (expectedLabel === 'Agenda pública') return currentTitle.includes('Agenda pública')
  if (expectedLabel === 'Mensagens') return currentTitle.includes('Mensagens')
  return false
}

function clearRetry(): void {
  if (retryTimer !== undefined) window.clearTimeout(retryTimer)
  retryTimer = undefined
}

function openExtensionFromHash(attempt = 0): void {
  const route = currentRoute()
  if (!isExtensionRoute(route) || syncing || openingRoute === route) return
  const button = extensionButtonFor(route)
  if (!button) {
    if (attempt < 12) {
      clearRetry()
      retryTimer = window.setTimeout(() => openExtensionFromHash(attempt + 1), Math.min(250, 20 + attempt * 20))
    }
    return
  }
  clearRetry()
  const expectedLabel = Object.entries(EXTENSION_ROUTES).find(([, value]) => value === route)?.[0] || ''
  const currentTitle = document.querySelector<HTMLElement>('.sp-extension-header h1')?.textContent || ''
  const alreadyOpen = document.body.classList.contains('sp-extension-open') || Boolean(document.querySelector('.sp-booking-message-root'))
  if (alreadyOpen && titleMatches(expectedLabel, currentTitle)) return
  openingRoute = route
  syncing = true
  button.click()
  cancelAnimationFrame(openRaf)
  openRaf = requestAnimationFrame(() => {
    syncing = false
    openingRoute = ''
    cacheAndRestoreLabels()
    syncSelectedNavigation()
  })
}

function closeExtensionForBaseRoute(): void {
  const route = currentRoute()
  if (isExtensionRoute(route)) return
  const extensionOpen = document.body.classList.contains('sp-extension-open') || Boolean(document.querySelector('.sp-booking-message-root'))
  if (!extensionOpen) return
  document.querySelector<HTMLButtonElement>('.sp-extension-root .sp-icon-button')?.click()
}

function synchronizeRoute(openFromHash = true): void {
  if (syncing) return
  primeVisibleLabels()
  cacheAndRestoreLabels()
  closeExtensionForBaseRoute()
  if (openFromHash) openExtensionFromHash()
  syncSelectedNavigation()
}

function closeMobileDrawerIfNeeded(): void {
  const root = tenantRoot()
  if (!root?.classList.contains('mobileOpen')) return
  root.querySelector<HTMLButtonElement>('.topbar > .icon-button:first-child')?.click()
}

function routeForExtensionButton(button: HTMLButtonElement): string {
  const label = button.textContent?.trim() || button.dataset.spLabel || ''
  return Object.entries(EXTENSION_ROUTES).find(([key]) => label.includes(key))?.[1] || ''
}

function setRoute(route: string, replace = false): void {
  if (!route || currentRoute() === route) return
  const target = `${window.location.pathname}${window.location.search}#${route}`
  if (replace) history.replaceState(history.state, '', target)
  else history.pushState(history.state, '', target)
  announceTenantNavigation(`#${route}`)
}

function handleClick(event: MouseEvent): void {
  const target = event.target instanceof Element ? event.target : null
  const extensionClose = target?.closest<HTMLButtonElement>('.sp-extension-root .sp-icon-button')
  if (extensionClose && isExtensionRoute(currentRoute())) {
    setRoute(lastBaseRoute || 'dashboard')
    requestAnimationFrame(() => synchronizeRoute(false))
    return
  }
  const button = target?.closest<HTMLButtonElement>('.tenant-console .nav-list .nav-item')
  if (!button) return
  closeMobileDrawerIfNeeded()
  if (button.classList.contains('sp-extension-nav')) {
    const route = routeForExtensionButton(button)
    if (route) setRoute(route)
    requestAnimationFrame(() => synchronizeRoute(false))
    return
  }
  requestAnimationFrame(() => {
    const route = currentRoute()
    if (route && !isExtensionRoute(route)) lastBaseRoute = route
    announceTenantNavigation(window.location.hash)
    synchronizeRoute(false)
  })
}

function handleHistoryNavigation(): void {
  const route = currentRoute()
  if (route && !isExtensionRoute(route)) lastBaseRoute = route
  announceTenantNavigation(window.location.hash)
  synchronizeRoute(true)
}

export function installTenantNavigationRuntime(): void {
  if (installed) return
  installed = true
  const initialRoute = currentRoute()
  if (!isExtensionRoute(initialRoute)) lastBaseRoute = initialRoute || 'dashboard'
  document.addEventListener('pointerdown', primeVisibleLabels, true)
  document.addEventListener('click', handleClick)
  window.addEventListener('hashchange', handleHistoryNavigation)
  window.addEventListener('popstate', handleHistoryNavigation)
  requestAnimationFrame(() => synchronizeRoute(true))
}
