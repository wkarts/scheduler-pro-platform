<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { announceTenantNavigation, TENANT_NAVIGATION_EVENT } from './tenantNavigation'

const LEGACY_LABELS = new Set(['Landing page', 'WhatsApp API', 'Marca e aplicativo'])
const EXTENSION_LABELS_REPLACED_BY_AGENDA = new Set(['Calendário'])
let raf = 0
let navigationRaf = 0
let warmupTimers: number[] = []

function buttonLabel(button: Element): string {
  return (button.textContent || '').replace(/\s+/g, ' ').trim()
}

function isExtensionButton(button: Element): boolean {
  return ['sp-extension-nav', 'sp-config-nav', 'sp-page-editor-nav', 'sp-visual-builder-nav']
    .some((name) => button.classList.contains(name))
}

function reconcileNavigation(): void {
  const nav = document.querySelector('.tenant-console .nav-list')
  if (!nav) return
  const buttons = Array.from(nav.querySelectorAll(':scope > .nav-item'))
  for (const button of buttons) {
    const label = buttonLabel(button)
    const legacy = !isExtensionButton(button)
    const duplicateSettings = label === 'Configurações' && legacy && buttons.some(
      (candidate) => candidate !== button && isExtensionButton(candidate) && buttonLabel(candidate) === 'Configurações',
    )
    const duplicateLanding = legacy && LEGACY_LABELS.has(label)
    const replacedAgendaExtension = EXTENSION_LABELS_REPLACED_BY_AGENDA.has(label)
    ;(button as HTMLElement).hidden = duplicateSettings || duplicateLanding || replacedAgendaExtension
  }
}

function visibleWorkspaceRoots(): HTMLElement[] {
  const selectors = [
    '.tenant-console .main-content > .sp-extension-root',
    '.tenant-console .main-content > .sp-config-root',
    '.tenant-console .main-content > .sp-agenda-operations-root',
    '.tenant-console .main-content > .sp-agenda-smart-root',
    '.tenant-console .main-content > .sp-agenda-center',
    'body > .page-editor',
    'body > .page-editor-v2',
    'body > .sp-visual-builder-shell',
  ]
  return Array.from(document.querySelectorAll<HTMLElement>(selectors.join(',')))
    .filter((node) => getComputedStyle(node).display !== 'none')
}

function closeWorkspace(root: HTMLElement): void {
  if (root.classList.contains('sp-agenda-center')) return
  root.querySelector<HTMLButtonElement>(
    'button[aria-label="Fechar"], .sp-icon-button, .editor-topbar .icon, .editor-topbar button[title="Fechar"], .sp-visual-builder-close',
  )?.click()
}

function syncWorkspaceState(): void {
  const open = visibleWorkspaceRoots().some((root) => !root.classList.contains('sp-agenda-center'))
  document.body.classList.toggle('sp-workspace-active', open)
  reconcileNavigation()
}

function scheduleSync(): void {
  cancelAnimationFrame(raf)
  raf = requestAnimationFrame(syncWorkspaceState)
}

function onNavigationClick(event: Event): void {
  const target = event.target as Element | null
  const button = target?.closest('.tenant-console .nav-list > .nav-item')
  if (!button) return
  for (const root of visibleWorkspaceRoots()) closeWorkspace(root)
  cancelAnimationFrame(navigationRaf)
  navigationRaf = requestAnimationFrame(() => {
    announceTenantNavigation(window.location.hash)
    scheduleSync()
  })
}

function onWorkspaceEvent(): void {
  scheduleSync()
  warmupTimers.push(window.setTimeout(scheduleSync, 80))
}

onMounted(() => {
  document.addEventListener('click', onNavigationClick, true)
  window.addEventListener(TENANT_NAVIGATION_EVENT, onWorkspaceEvent)
  window.addEventListener('scheduler-pro-workspace-open', onWorkspaceEvent)
  window.addEventListener('scheduler-pro-workspace-close', onWorkspaceEvent)
  scheduleSync()
  for (const delay of [50, 250, 900]) warmupTimers.push(window.setTimeout(scheduleSync, delay))
})

onUnmounted(() => {
  document.removeEventListener('click', onNavigationClick, true)
  window.removeEventListener(TENANT_NAVIGATION_EVENT, onWorkspaceEvent)
  window.removeEventListener('scheduler-pro-workspace-open', onWorkspaceEvent)
  window.removeEventListener('scheduler-pro-workspace-close', onWorkspaceEvent)
  cancelAnimationFrame(raf)
  cancelAnimationFrame(navigationRaf)
  warmupTimers.forEach((timer) => window.clearTimeout(timer))
  warmupTimers = []
  document.body.classList.remove('sp-workspace-active')
})
</script>

<template></template>

<style>
body.sp-workspace-active .tenant-console .main-content > .page-header,
body.sp-workspace-active .tenant-console .main-content > .success-banner,
body.sp-workspace-active .tenant-console .main-content > .error-banner,
body.sp-workspace-active .tenant-console .main-content > .view-stack { display:none!important }
.tenant-console .nav-list > .nav-item[hidden] { display:none!important }
</style>
