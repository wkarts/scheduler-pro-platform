<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref } from 'vue'
import { PanelsTopLeft } from 'lucide-vue-next'
import { SchedulerProProjectAdapter, type ArgwsVisualBuilderApp } from '@argws/visual-builder'
import '@argws/visual-builder'

const active = ref(false)
const portalReady = ref(false)
const mountPoint = ref<HTMLDivElement | null>(null)
let app: ArgwsVisualBuilderApp | null = null

async function open(): Promise<void> {
  window.dispatchEvent(new CustomEvent('scheduler-pro-workspace-open', { detail: 'visual-builder' }))
  active.value = true
  await nextTick()
  mountBuilder()
}

function mountBuilder(): void {
  if (!mountPoint.value || app) return
  const element = document.createElement('argws-visual-builder-app') as ArgwsVisualBuilderApp
  element.adapter = new SchedulerProProjectAdapter({ baseUrl: '/api/v1', landingSlug: 'home' })
  element.addEventListener('avb-close', close)
  mountPoint.value.appendChild(element)
  app = element
}

function close(): void {
  app?.removeEventListener('avb-close', close)
  app?.remove()
  app = null
  active.value = false
}

function workspaceOpened(event: Event): void {
  const detail = (event as CustomEvent<string>).detail
  if (active.value && detail && detail !== 'visual-builder') close()
}

onMounted(async () => {
  await nextTick()
  portalReady.value = Boolean(document.querySelector('.tenant-console .nav-list'))
  window.addEventListener('scheduler-pro-workspace-open', workspaceOpened)
})

onUnmounted(() => {
  window.removeEventListener('scheduler-pro-workspace-open', workspaceOpened)
  close()
})
</script>

<template>
  <Teleport v-if="portalReady" to=".tenant-console .nav-list">
    <button class="nav-item sp-page-editor-nav" @click="open">
      <PanelsTopLeft :size="19" />
      <span>Visual Builder</span>
    </button>
  </Teleport>
  <Teleport v-if="active" to="body">
    <div ref="mountPoint" class="sp-visual-builder-mount" />
  </Teleport>
</template>
