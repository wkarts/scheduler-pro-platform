<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref } from 'vue'
import { SchedulerProProjectAdapter, type ArgwsVisualBuilderApp } from '@argws/visual-builder'
import '@argws/visual-builder'

const active = ref(false)
const mountPoint = ref<HTMLDivElement | null>(null)
const mountError = ref('')
const mounting = ref(false)
let app: ArgwsVisualBuilderApp | null = null

async function open(): Promise<void> {
  if (active.value && app) return
  active.value = true
  mountError.value = ''
  await nextTick()
  window.requestAnimationFrame(() => mountBuilder())
}

function mountBuilder(): void {
  if (!mountPoint.value || app || mounting.value) return
  mounting.value = true
  mountError.value = ''
  try {
    const element = document.createElement('argws-visual-builder-app') as ArgwsVisualBuilderApp
    element.adapter = new SchedulerProProjectAdapter({ baseUrl: '/api/v1', landingSlug: 'home' })
    element.addEventListener('avb-close', close)
    mountPoint.value.appendChild(element)
    app = element
  } catch (error) {
    mountError.value = error instanceof Error ? error.message : 'Não foi possível iniciar o ARGWS Visual Builder.'
  } finally {
    mounting.value = false
  }
}

function retryMount(): void {
  app?.remove()
  app = null
  mountError.value = ''
  void nextTick().then(() => window.requestAnimationFrame(() => mountBuilder()))
}

function close(): void {
  app?.removeEventListener('avb-close', close)
  app?.remove()
  app = null
  mountError.value = ''
  mounting.value = false
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
    <div ref="mountPoint" class="sp-visual-builder-mount">
      <section v-if="mountError" class="sp-visual-builder-error" role="alert">
        <strong>ARGWS Visual Builder não pôde ser iniciado</strong>
        <p>{{ mountError }}</p>
        <div><button type="button" @click="retryMount">Tentar novamente</button><button type="button" class="secondary" @click="close">Voltar ao Scheduler Pro</button></div>
      </section>
    </div>
  </Teleport>
</template>
<style scoped>
.sp-visual-builder-error{position:fixed;inset:0;z-index:2147483000;display:grid;place-content:center;justify-items:center;gap:12px;padding:28px;background:#f8fafc;color:#0f172a;text-align:center}.sp-visual-builder-error strong{font-size:20px}.sp-visual-builder-error p{max-width:680px;margin:0;color:#64748b}.sp-visual-builder-error div{display:flex;flex-wrap:wrap;justify-content:center;gap:8px}.sp-visual-builder-error button{min-height:42px;padding:0 16px;border:0;border-radius:12px;background:#2563eb;color:#fff;font-weight:700;cursor:pointer}.sp-visual-builder-error button.secondary{background:#e2e8f0;color:#0f172a}
</style>
