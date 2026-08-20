<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { CheckCircle2, Download, Globe2, MonitorSmartphone, RefreshCw, Share2, Smartphone } from 'lucide-vue-next'
import {
  getPwaInstallState,
  pwaInstallInstructions,
  PWA_INSTALL_STATE_EVENT,
  requestPwaInstall,
  type PwaInstallState,
} from './pwa'

type Artifact = {
  id: string
  target: string
  artifact_type: string
  name: string
  download_url?: string | null
  size_bytes?: number
  metadata?: { release?: string; universal?: boolean }
}
type Catalog = {
  universal: boolean
  release?: string | null
  published_at?: string | null
  artifacts: Artifact[]
  tenant: { id: string; slug: string; hostname: string }
  setup: { desktop: string; mobile: string }
}
type Envelope<T> = { data: T; error?: { message?: string } }

const visible = ref(window.location.hash === '#builds')
const catalog = ref<Catalog | null>(null)
const loading = ref(false)
const installingPwa = ref(false)
const showPwaHelp = ref(false)
const error = ref('')
const pwaState = ref<PwaInstallState>(getPwaInstallState())
const currentHostname = window.location.hostname
const token = () => localStorage.getItem('scheduler_pro_access_token') || ''
const desktopArtifacts = computed(() => catalog.value?.artifacts.filter((item) => item.target.startsWith('desktop-')) || [])
const mobileArtifacts = computed(() => catalog.value?.artifacts.filter((item) => ['android', 'ios'].includes(item.target)) || [])

function formatBytes(value = 0): string {
  if (!value) return '—'
  const units = ['B', 'KB', 'MB', 'GB']
  let size = value
  let unit = 0
  while (size >= 1024 && unit < units.length - 1) { size /= 1024; unit += 1 }
  return `${size.toFixed(unit ? 1 : 0)} ${units[unit]}`
}

async function load(): Promise<void> {
  if (!visible.value || loading.value) return
  loading.value = true
  error.value = ''
  try {
    const response = await fetch('/api/v1/downloads/apps', {
      headers: { Accept: 'application/json', Authorization: `Bearer ${token()}` },
    })
    const payload = await response.json().catch(() => ({})) as Partial<Envelope<Catalog>>
    if (!response.ok) throw new Error(payload.error?.message || `Falha HTTP ${response.status}`)
    catalog.value = payload.data || null
  } catch (exc) {
    error.value = exc instanceof Error ? exc.message : 'Não foi possível consultar os aplicativos disponíveis.'
  } finally { loading.value = false }
}

function pwaLabel(): string {
  if (pwaState.value.installed) return 'PWA instalado'
  if (pwaState.value.platform === 'ios') return 'Adicionar à Tela de Início'
  if (pwaState.value.platform === 'android') return 'Instalar PWA no Android'
  return 'Instalar PWA neste dispositivo'
}

async function installPwa(): Promise<void> {
  if (pwaState.value.installed || installingPwa.value) return
  installingPwa.value = true
  try {
    const result = await requestPwaInstall()
    pwaState.value = getPwaInstallState()
    showPwaHelp.value = result === 'manual' || result === 'unavailable' || result === 'dismissed'
  } finally {
    installingPwa.value = false
  }
}

function onPwaState(): void { pwaState.value = getPwaInstallState() }

function syncHash(): void {
  visible.value = window.location.hash === '#builds'
  if (visible.value && !catalog.value) void load()
}

watch(visible, (value) => document.body.classList.toggle('sp-universal-downloads-open', value), { immediate: true })
onMounted(() => {
  window.addEventListener('hashchange', syncHash)
  window.addEventListener(PWA_INSTALL_STATE_EVENT, onPwaState)
  if (visible.value) void load()
})
onUnmounted(() => {
  window.removeEventListener('hashchange', syncHash)
  window.removeEventListener(PWA_INSTALL_STATE_EVENT, onPwaState)
  document.body.classList.remove('sp-universal-downloads-open')
})
</script>

<template>
  <Teleport v-if="visible" to=".tenant-console .main-content">
    <section class="sp-universal-downloads">
      <header>
        <div><span>Distribuição universal</span><h2>Aplicativos Scheduler Pro</h2><p>Os mesmos binários atendem todos os tenants. No primeiro uso, informe a URL desta instância: <strong>{{ catalog?.tenant.hostname || currentHostname }}</strong>.</p></div>
        <button type="button" :disabled="loading" @click="load"><RefreshCw :size="16" :class="{spin:loading}"/> Atualizar</button>
      </header>
      <p v-if="error" class="sp-download-error">{{ error }}</p>
      <div v-if="catalog" class="sp-download-release"><strong>{{ catalog.release || 'Release atual' }}</strong><span>Não é necessário gerar build específica para este tenant.</span></div>

      <article class="sp-pwa-card">
        <div class="sp-download-title"><Globe2 :size="25"/><div><strong>Web App / PWA</strong><span>Android, iOS, Windows, Linux e macOS</span></div></div>
        <p>Instale a própria WebApp deste tenant. Ela acompanha as atualizações do site automaticamente e não depende dos binários nativos.</p>
        <div class="sp-pwa-actions">
          <span v-if="pwaState.installed" class="sp-pwa-installed"><CheckCircle2 :size="17"/> Instalado neste dispositivo</span>
          <button v-else type="button" :disabled="installingPwa" @click="installPwa"><Share2 v-if="pwaState.platform==='ios'" :size="17"/><Download v-else :size="17"/>{{ installingPwa ? 'Preparando...' : pwaLabel() }}</button>
        </div>
        <p v-if="showPwaHelp && !pwaState.installed" class="sp-pwa-help">{{ pwaInstallInstructions(pwaState.platform) }}</p>
      </article>

      <div class="sp-download-columns">
        <article>
          <div class="sp-download-title"><MonitorSmartphone :size="24"/><div><strong>Desktop</strong><span>Contêiner universal da WebApp</span></div></div>
          <p>{{ catalog?.setup.desktop || 'Configure a URL uma única vez.' }}</p>
          <div class="sp-download-list"><a v-for="item in desktopArtifacts" :key="item.id" :href="item.download_url || '#'" target="_blank" rel="noopener"><div><strong>{{ item.target.replace('desktop-','').toUpperCase() }}</strong><span>{{ item.name }} · {{ formatBytes(item.size_bytes) }}</span></div><Download :size="18"/></a><span v-if="catalog && !desktopArtifacts.length" class="empty">Nenhum instalador Desktop espelhado no bucket interno para a release atual.</span></div>
        </article>
        <article>
          <div class="sp-download-title"><Smartphone :size="24"/><div><strong>Mobile nativo</strong><span>Interface própria Android/iOS</span></div></div>
          <p>{{ catalog?.setup.mobile || 'Configure a URL uma única vez.' }}</p>
          <div class="sp-download-list"><a v-for="item in mobileArtifacts" :key="item.id" :href="item.download_url || '#'" target="_blank" rel="noopener"><div><strong>{{ item.target.toUpperCase() }}</strong><span>{{ item.name }} · {{ formatBytes(item.size_bytes) }}</span></div><Download :size="18"/></a><span v-if="catalog && !mobileArtifacts.length" class="empty">Nenhum artefato Mobile espelhado no bucket interno para a release atual.</span></div>
        </article>
      </div>
    </section>
  </Teleport>
</template>

<style>
body.sp-universal-downloads-open .tenant-console .main-content>.view-stack{display:none!important}body.sp-universal-downloads-open .tenant-console .page-actions{display:none!important}.sp-universal-downloads{margin-top:18px;border:1px solid #dfe7f1;border-radius:20px;background:#fff;padding:22px;box-shadow:0 12px 32px rgba(20,42,80,.07)}.sp-universal-downloads>header{display:flex;justify-content:space-between;gap:18px;align-items:flex-start}.sp-universal-downloads header span{display:block;color:#2563eb;text-transform:uppercase;letter-spacing:.12em;font-size:10px;font-weight:900}.sp-universal-downloads h2{margin:5px 0 5px;color:#10213b}.sp-universal-downloads header p{margin:0;color:#65758d;font-size:12px;line-height:1.55}.sp-universal-downloads header button{display:flex;align-items:center;gap:7px;border:1px solid #dfe7f1;background:#fff;border-radius:10px;padding:9px 12px;font-weight:800;color:#253954}.sp-download-release{margin:16px 0;padding:12px 14px;border-radius:13px;background:#eff6ff;color:#1d4ed8;display:flex;gap:12px;align-items:center}.sp-download-release span{color:#526a8b;font-size:12px}.sp-pwa-card{margin:14px 0;border:1px solid #bfdbfe;border-radius:16px;padding:18px;background:linear-gradient(135deg,#eff6ff,#f8fbff)}.sp-pwa-card>p{margin:10px 0;color:#526a8b;font-size:12px;line-height:1.55}.sp-pwa-actions{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.sp-pwa-actions button,.sp-pwa-installed{display:inline-flex;align-items:center;gap:8px;border-radius:11px;padding:10px 13px;font-weight:850;font-size:12px}.sp-pwa-actions button{border:1px solid #2563eb;background:#2563eb;color:#fff;cursor:pointer}.sp-pwa-actions button:disabled{opacity:.65}.sp-pwa-installed{background:#ecfdf5;color:#047857;border:1px solid #a7f3d0}.sp-pwa-card .sp-pwa-help{margin-top:10px;padding:10px 12px;border:1px solid #dbeafe;border-radius:11px;background:#fff;color:#475569}.sp-download-columns{display:grid;grid-template-columns:1fr 1fr;gap:14px}.sp-download-columns>article{border:1px solid #e3eaf3;border-radius:16px;padding:18px}.sp-download-title{display:flex;gap:10px;align-items:center;color:#2563eb}.sp-download-title strong,.sp-download-title span{display:block}.sp-download-title strong{color:#10213b}.sp-download-title span{color:#748399;font-size:11px;margin-top:2px}.sp-download-columns article>p{color:#65758d;font-size:12px;line-height:1.5}.sp-download-list{display:grid;gap:8px}.sp-download-list a{display:flex;align-items:center;justify-content:space-between;gap:12px;border:1px solid #dfe7f1;border-radius:12px;padding:11px 12px;color:#1d4ed8;text-decoration:none}.sp-download-list a:hover{background:#f7faff}.sp-download-list a strong,.sp-download-list a span{display:block}.sp-download-list a span{margin-top:3px;color:#77879b;font-size:10px;overflow-wrap:anywhere}.sp-download-list .empty{color:#8795a8;font-size:12px;padding:10px}.sp-download-error{background:#fef2f2;color:#b91c1c;border:1px solid #fecaca;border-radius:12px;padding:11px 13px}.spin{animation:sp-download-spin .8s linear infinite}@keyframes sp-download-spin{to{transform:rotate(360deg)}}@media(max-width:800px){.sp-universal-downloads{padding:16px}.sp-universal-downloads>header{display:grid}.sp-universal-downloads header button{width:100%;justify-content:center}.sp-download-columns{grid-template-columns:1fr}.sp-download-release{display:grid}.sp-download-list a{align-items:flex-start}.sp-pwa-actions button{width:100%;justify-content:center}}
</style>
