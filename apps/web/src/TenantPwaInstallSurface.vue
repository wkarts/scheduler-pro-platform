<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref } from 'vue'
import { CheckCircle2, Download, Share2, X } from 'lucide-vue-next'
import {
  getPwaInstallState,
  pwaInstallInstructions,
  PWA_INSTALL_STATE_EVENT,
  requestPwaInstall,
  type PwaInstallState,
} from './pwa'

const state = ref<PwaInstallState>(getPwaInstallState())
const loginTarget = ref(false)
const consoleTarget = ref(false)
const showHelp = ref(false)
const busy = ref(false)
const message = ref('')
let observer: MutationObserver | undefined

function refreshTargets(): void {
  loginTarget.value = Boolean(document.querySelector('.tenant-login-card'))
  const topbar = document.querySelector('.tenant-console .topbar')
  consoleTarget.value = Boolean(topbar && !topbar.querySelector('.install-top'))
}

function refreshState(): void {
  state.value = getPwaInstallState()
  refreshTargets()
}

function buttonLabel(): string {
  if (state.value.installed) return 'PWA instalado'
  if (state.value.platform === 'ios') return 'Instalar no iPhone/iPad'
  if (state.value.platform === 'android') return 'Instalar PWA no Android'
  if (state.value.platform === 'desktop') return 'Instalar aplicativo'
  return 'Instalar PWA'
}

async function install(): Promise<void> {
  if (state.value.installed || busy.value) return
  busy.value = true
  message.value = ''
  try {
    const result = await requestPwaInstall()
    refreshState()
    if (result === 'accepted' || result === 'installed') {
      message.value = 'Scheduler PRO instalado neste dispositivo.'
      showHelp.value = false
      return
    }
    if (result === 'dismissed') {
      message.value = 'Instalação cancelada. Você pode instalar quando quiser.'
      return
    }
    showHelp.value = true
  } finally {
    busy.value = false
  }
}

function onState(): void { refreshState() }

onMounted(async () => {
  await nextTick()
  window.requestAnimationFrame(refreshTargets)
  window.addEventListener(PWA_INSTALL_STATE_EVENT, onState)
  observer = new MutationObserver(refreshTargets)
  observer.observe(document.body, { subtree: true, childList: true })
})

onUnmounted(() => {
  window.removeEventListener(PWA_INSTALL_STATE_EVENT, onState)
  observer?.disconnect()
})
</script>

<template>
  <Teleport v-if="loginTarget" to=".tenant-login-card">
    <section class="sp-pwa-login-install">
      <div class="sp-pwa-copy">
        <CheckCircle2 v-if="state.installed" :size="19" />
        <Download v-else :size="19" />
        <div><strong>{{ state.installed ? 'Aplicativo instalado' : 'Instale o Scheduler PRO' }}</strong><span>{{ state.installed ? 'Você já está usando a experiência instalada neste dispositivo.' : 'Use a WebApp como aplicativo no celular, tablet ou computador.' }}</span></div>
      </div>
      <button v-if="!state.installed" type="button" :disabled="busy" @click="install"><Share2 v-if="state.platform==='ios'" :size="17"/><Download v-else :size="17"/>{{ busy ? 'Preparando...' : buttonLabel() }}</button>
      <p v-if="message" class="sp-pwa-message">{{ message }}</p>
      <div v-if="showHelp && !state.installed" class="sp-pwa-help"><span>{{ pwaInstallInstructions(state.platform) }}</span><button type="button" aria-label="Fechar instruções" @click="showHelp=false"><X :size="15"/></button></div>
    </section>
  </Teleport>

  <Teleport v-if="consoleTarget && !state.installed" to=".tenant-console .topbar">
    <button class="btn sp-pwa-top-install" type="button" :disabled="busy" @click="install"><Download :size="16"/>{{ state.platform==='ios' ? 'Instalar PWA' : 'Instalar' }}</button>
  </Teleport>
</template>

<style>
.sp-pwa-login-install{margin-top:18px;padding-top:18px;border-top:1px solid #e2e8f0;display:grid;gap:10px}.sp-pwa-copy{display:flex;align-items:flex-start;gap:10px;color:#2563eb}.sp-pwa-copy strong,.sp-pwa-copy span{display:block}.sp-pwa-copy strong{font-size:13px;color:#1e293b}.sp-pwa-copy span{margin-top:3px;color:#64748b;font-size:11px;line-height:1.45}.sp-pwa-login-install>button,.sp-pwa-top-install{display:flex;align-items:center;justify-content:center;gap:8px;border:1px solid #bfdbfe;border-radius:12px;background:#eff6ff;color:#1d4ed8;font:inherit;font-size:12px;font-weight:850;cursor:pointer}.sp-pwa-login-install>button{min-height:44px;width:100%}.sp-pwa-login-install>button:hover,.sp-pwa-top-install:hover{background:#dbeafe}.sp-pwa-login-install>button:disabled,.sp-pwa-top-install:disabled{opacity:.65}.sp-pwa-top-install{height:38px;padding:0 12px;white-space:nowrap}.sp-pwa-help{display:flex;align-items:flex-start;justify-content:space-between;gap:10px;padding:10px 11px;border-radius:11px;background:#f8fafc;color:#475569;font-size:11px;line-height:1.5}.sp-pwa-help button{border:0;background:transparent;color:#64748b;padding:0;cursor:pointer}.sp-pwa-message{margin:0;color:#475569;font-size:11px}@media(max-width:720px){.sp-pwa-top-install{padding:0 10px;font-size:0}.sp-pwa-top-install svg{margin:0}.sp-pwa-login-install{margin-top:16px}}
</style>
