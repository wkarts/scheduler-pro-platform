let refreshTimer: number | undefined

function scheduleRefresh(): void {
  if (refreshTimer !== undefined) window.clearTimeout(refreshTimer)
  refreshTimer = window.setTimeout(() => {
    const refresh = document.querySelector<HTMLButtonElement>('.mobile-app .mobile-top .round-button')
    if (refresh && !refresh.disabled) refresh.click()
  }, 30)
}

function handleNavigation(event: MouseEvent): void {
  const target = event.target instanceof Element ? event.target : null
  if (!target) return
  if (target.closest('.bottom-nav button, .quick-grid button, .hero-card .primary-button')) {
    scheduleRefresh()
  }
}

export function installMobileNavigationRefresh(): void {
  document.addEventListener('click', handleNavigation)
}
