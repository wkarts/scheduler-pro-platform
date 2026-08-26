<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'

const LEGACY_LABELS = new Set([
  'Landing page',
  'WhatsApp API',
  'Marca e aplicativo',
])

let observer: MutationObserver | undefined
let raf = 0

function buttonLabel(button: Element): string {
  return (button.textContent || '').replace(/\s+/g, ' ').trim()
}

function isExtensionButton(button: Element): boolean {
  return [
    'sp-extension-nav',
    'sp-config-nav',
    'sp-page-editor-nav',
  ].some((name) => button.classList.contains(name))
}

function reconcileNavigation(): void {
  const nav = document.querySelector('.tenant-console .nav-list')
  if (!nav) return
  const buttons = Array.from(nav.querySelectorAll(':scope > .nav-item'))

  for (const button of buttons) {
    const label = buttonLabel(button)
    const legacy = !isExtensionButton(button)
    const duplicateSettings = label === 'Configurações' && legacy && buttons.some(
      (candidate) => candidate !== button &&
        isExtensionButton(candidate) &&
        buttonLabel(candidate) === 'Configurações',
    )
    const duplicateLanding = legacy && LEGACY_LABELS.has(label)
    ;(button as HTMLElement).hidden = duplicateSettings || duplicateLanding
  }
}

function scheduleReconcile(): void {
  cancelAnimationFrame(raf)
  raf = requestAnimationFrame(reconcileNavigation)
}

function visibleWorkspaceRoots(): HTMLElement[] {
  const selectors = [
    '.tenant-console .main-content > .sp-extension-root',
    '.tenant-console .main-content > .sp-config-root',
    '.tenant-console .main-content > .sp-agenda-operations-root',
    '.tenant-console .main-content > .sp-agenda-smart-root',
    'body > .page-editor',
    'body > .page-editor-v2',
  ]
  return Array.from(document.querySelectorAll<HTMLElement>(selectors.join(',')))
    .filter((node) => getComputedStyle(node).display !== 'none')
}

function closeWorkspace(root: HTMLElement): void {
  const close = root.querySelector<HTMLButtonElement>(
    'button[aria-label="Fechar"], .sp-icon-button, .editor-topbar .icon, .editor-topbar button[title="Fechar"]',
  )
  close?.click()
}

function onNavigationClick(event: Event): void {
  const target = event.target as Element | null
  const button = target?.closest('.tenant-console .nav-list > .nav-item')
  if (!button) return
  for (const root of visibleWorkspaceRoots()) closeWorkspace(root)
}

function syncWorkspaceState(): void {
  const open = visibleWorkspaceRoots().length > 0
  document.body.classList.toggle('sp-workspace-active', open)
  scheduleReconcile()
}

onMounted(() => {
  document.addEventListener('click', onNavigationClick, true)
  observer = new MutationObserver(syncWorkspaceState)
  observer.observe(document.body, { childList: true, subtree: true })
  syncWorkspaceState()
})

onUnmounted(() => {
  document.removeEventListener('click', onNavigationClick, true)
  observer?.disconnect()
  cancelAnimationFrame(raf)
  document.body.classList.remove('sp-workspace-active')
})
</script>

<template></template>

<style>
body.sp-workspace-active .tenant-console .main-content > .page-header,
body.sp-workspace-active .tenant-console .main-content > .success-banner,
body.sp-workspace-active .tenant-console .main-content > .error-banner,
body.sp-workspace-active .tenant-console .main-content > .view-stack {
  display: none !important;
}
.tenant-console .nav-list > .nav-item[hidden] {
  display: none !important;
}
</style>
