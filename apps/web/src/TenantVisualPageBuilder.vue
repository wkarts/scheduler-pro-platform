<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref } from 'vue'
import { SchedulerProProjectAdapter, type ArgwsVisualBuilderApp } from '@argws/visual-builder'
import '@argws/visual-builder'

const active = ref(false)
const mountPoint = ref<HTMLDivElement | null>(null)
let app: ArgwsVisualBuilderApp | null = null

async function open(): Promise<void> {
  if (active.value) return
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
  if (window.location.hash === '#visual-builder') window.location.hash = 'dashboard'
}


function syncRoute(): void {
  const next = window.location.hash === '#visual-builder'
  if (next && !active.value) void open()
  else if (!next && active.value) { app?.remove(); app = null; active.value = false }
}
onMounted(async () => { await nextTick(); window.addEventListener('hashchange', syncRoute); syncRoute() })
onUnmounted(() => { window.removeEventListener('hashchange', syncRoute); app?.remove(); app = null; active.value = false })
</script>

<template>
  <Teleport v-if="active" to="body">
    <div ref="mountPoint" class="sp-visual-builder-mount" />
  </Teleport>
</template>
