export function installTenantExtensionNavigationBridge(): void {
  document.addEventListener('click', (event) => {
    if (!document.body.classList.contains('sp-extension-open')) return
    const target = event.target instanceof Element ? event.target : null
    if (!target?.closest('.tenant-console .nav-item:not(.sp-extension-nav)')) return
    const closeButton = document.querySelector<HTMLButtonElement>(
      '.sp-extension-root .sp-extension-header .sp-icon-button',
    )
    closeButton?.click()
  })
}
