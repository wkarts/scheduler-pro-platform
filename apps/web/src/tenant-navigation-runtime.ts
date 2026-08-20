const EXTENSION_ROUTES: Record<string, string> = {
  'Calendário': 'calendar',
  'Personalização': 'personalizacao',
  'E-mail SMTP': 'smtp',
}

let observer: MutationObserver | undefined
let syncing = false
let lastBaseRoute = 'dashboard'

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
    } else if (!mobileOpen && runtime) {
      runtime.remove()
    }
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
    const shouldBeActive = item === target
    if (shouldBeActive && !item.classList.contains('active')) item.classList.add('active')
    if (!shouldBeActive && item.classList.contains('active')) item.classList.remove('active')
  }
}

function openExtensionFromHash(): void {
  const route = currentRoute()
  if (!isExtensionRoute(route)) return
  const button = extensionButtonFor(route)
  if (!button || syncing) return

  const expectedLabel = Object.entries(EXTENSION_ROUTES).find(([, value]) => value === route)?.[0] || ''
  const currentTitle = document.querySelector<HTMLElement>('.sp-extension-header h1')?.textContent || ''
  const alreadyOpen = document.body.classList.contains('sp-extension-open')
  const correctOpenView = alreadyOpen && (
    (expectedLabel === 'Calendário' && currentTitle.includes('Calendário')) ||
    (expectedLabel === 'Personalização' && currentTitle.includes('Personalização')) ||
    (expectedLabel === 'E-mail SMTP' && currentTitle.includes('E-mail'))
  )
  if (correctOpenView) return

  syncing = true
  button.click()
  window.setTimeout(() => {
    syncing = false
    syncSelectedNavigation()
  }, 0)
}

function closeExtensionForBaseRoute(): void {
  const route = currentRoute()
  if (isExtensionRoute(route)) return
  if (!document.body.classList.contains('sp-extension-open')) return
  document.querySelector<HTMLButtonElement>('.sp-extension-root .sp-icon-button')?.click()
}

function synchronize(): void {
  if (syncing) return
  cacheAndRestoreLabels()
  closeExtensionForBaseRoute()
  openExtensionFromHash()
  syncSelectedNavigation()
}

function closeMobileDrawerIfNeeded(): void {
  const root = tenantRoot()
  if (!root?.classList.contains('mobileOpen')) return
  root.querySelector<HTMLButtonElement>('.topbar > .icon-button:first-child')?.click()
}

function handleClick(event: MouseEvent): void {
  const target = event.target instanceof Element ? event.target : null
  const extensionClose = target?.closest<HTMLButtonElement>('.sp-extension-root .sp-icon-button')
  if (extensionClose && isExtensionRoute(currentRoute())) {
    syncing = true
    window.location.hash = lastBaseRoute || 'dashboard'
    window.setTimeout(() => {
      syncing = false
      synchronize()
    }, 0)
    return
  }

  const button = target?.closest<HTMLButtonElement>('.tenant-console .nav-list .nav-item')
  if (!button) return

  if (button.classList.contains('sp-extension-nav')) {
    const label = button.textContent?.trim() || button.dataset.spLabel || ''
    const route = Object.entries(EXTENSION_ROUTES).find(([key]) => label.includes(key))?.[1]
    if (route && currentRoute() !== route) {
      syncing = true
      window.location.hash = route
      window.setTimeout(() => { syncing = false; synchronize() }, 0)
    }
  }

  window.setTimeout(() => {
    closeMobileDrawerIfNeeded()
    synchronize()
  }, 0)
}

export function installTenantNavigationRuntime(): void {
  const initialRoute = currentRoute()
  if (!isExtensionRoute(initialRoute)) lastBaseRoute = initialRoute || 'dashboard'
  document.addEventListener('pointerdown', primeVisibleLabels, true)
  document.addEventListener('click', handleClick)
  window.addEventListener('hashchange', synchronize)
  observer = new MutationObserver(() => synchronize())
  observer.observe(document.body, { subtree: true, childList: true, attributes: true, attributeFilter: ['class'] })
  window.requestAnimationFrame(() => {
    primeVisibleLabels()
    synchronize()
  })
}
