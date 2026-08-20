const EXTENSION_ROUTES: Record<string, string> = {
  'Calendário': 'calendar',
  'Personalização': 'branding',
  'E-mail SMTP': 'smtp',
}

let observer: MutationObserver | undefined
let syncing = false

function tenantRoot(): HTMLElement | null {
  return document.querySelector<HTMLElement>('.tenant-console')
}

function currentRoute(): string {
  return (window.location.hash || '#dashboard').replace(/^#/, '')
}

function extensionButtonFor(route: string): HTMLButtonElement | null {
  const entry = Object.entries(EXTENSION_ROUTES).find(([, value]) => value === route)
  if (!entry) return null
  const [label] = entry
  return Array.from(document.querySelectorAll<HTMLButtonElement>('.tenant-console .sp-extension-nav'))
    .find((button) => button.textContent?.trim().includes(label)) || null
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
    if (text) button.dataset.spLabel = text

    const runtime = button.querySelector<HTMLSpanElement>('.sp-runtime-mobile-label')
    if (mobileOpen && !regular && button.dataset.spLabel) {
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
  const extensionRoute = Object.values(EXTENSION_ROUTES).includes(route)

  document.body.classList.toggle('sp-smart-agenda-open', route === 'agenda')

  if (!extensionRoute) {
    root.querySelectorAll('.sp-extension-nav.active').forEach((item) => item.classList.remove('active'))
    return
  }

  root.querySelectorAll('.sidebar .nav-item.active').forEach((item) => item.classList.remove('active'))
  extensionButtonFor(route)?.classList.add('active')
}

function openExtensionFromHash(): void {
  const route = currentRoute()
  if (!Object.values(EXTENSION_ROUTES).includes(route)) return
  if (document.body.classList.contains('sp-extension-open')) return
  const button = extensionButtonFor(route)
  if (!button || syncing) return
  syncing = true
  button.click()
  window.setTimeout(() => { syncing = false; syncSelectedNavigation() }, 0)
}

function closeExtensionForBaseRoute(): void {
  const route = currentRoute()
  if (Object.values(EXTENSION_ROUTES).includes(route)) return
  if (!document.body.classList.contains('sp-extension-open')) return
  document.querySelector<HTMLButtonElement>('.sp-extension-root .sp-icon-button')?.click()
}

function synchronize(): void {
  cacheAndRestoreLabels()
  closeExtensionForBaseRoute()
  openExtensionFromHash()
  syncSelectedNavigation()
}

function handleClick(event: MouseEvent): void {
  const target = event.target instanceof Element ? event.target : null
  const button = target?.closest<HTMLButtonElement>('.tenant-console .nav-list .nav-item')
  if (!button) return

  const extension = button.classList.contains('sp-extension-nav')
  if (extension) {
    const label = button.textContent?.trim() || button.dataset.spLabel || ''
    const route = Object.entries(EXTENSION_ROUTES).find(([key]) => label.includes(key))?.[1]
    if (route && currentRoute() !== route) window.location.hash = route
  }

  window.setTimeout(() => {
    const root = tenantRoot()
    if (root?.classList.contains('mobileOpen')) {
      root.querySelector<HTMLButtonElement>('.topbar > .icon-button:first-child')?.click()
    }
    synchronize()
  }, 0)
}

export function installTenantNavigationRuntime(): void {
  document.addEventListener('click', handleClick)
  window.addEventListener('hashchange', synchronize)
  observer = new MutationObserver(() => synchronize())
  observer.observe(document.body, { subtree: true, childList: true, attributes: true, attributeFilter: ['class'] })
  window.requestAnimationFrame(synchronize)
}
