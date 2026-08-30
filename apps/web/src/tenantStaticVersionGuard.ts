const STATIC_VERSION_SELECTORS = [
  '.tenant-console .brand > div > small',
  '.tenant-console .sidebar-footer > .version-info',
]

function removeStaticTenantVersions(root: ParentNode = document): void {
  for (const selector of STATIC_VERSION_SELECTORS) {
    root.querySelectorAll(selector).forEach((element) => element.remove())
  }
}

export function installTenantStaticVersionGuard(): () => void {
  removeStaticTenantVersions()

  const observer = new MutationObserver(() => removeStaticTenantVersions())
  observer.observe(document.documentElement, {
    childList: true,
    subtree: true,
  })

  return () => observer.disconnect()
}
