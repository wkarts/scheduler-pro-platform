export function installTenantExtensionNavigationBridge(): void {
  document.addEventListener('click', (event) => {
    const target = event.target instanceof Element ? event.target : null
    if (!target) return

    const root = target.closest('.tenant-console') || document.querySelector('.tenant-console')
    const extensionNav = target.closest('.tenant-console .sp-extension-nav')
    if (extensionNav && root?.classList.contains('mobileOpen') && window.matchMedia('(max-width: 900px)').matches) {
      const menuButton = document.querySelector<HTMLButtonElement>('.tenant-console .topbar > .icon-button:first-child')
      menuButton?.click()
    }

    if (!document.body.classList.contains('sp-extension-open')) return
    if (!target.closest('.tenant-console .nav-item:not(.sp-extension-nav)')) return
    const closeButton = document.querySelector<HTMLButtonElement>(
      '.sp-extension-root .sp-extension-header .sp-icon-button',
    )
    closeButton?.click()
  })
}
