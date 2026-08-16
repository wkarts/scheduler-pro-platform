<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { applyBranding, loadBrandingManifest, type BrandingManifest } from './branding'

type TabKey = 'home' | 'agenda' | 'clientes' | 'whatsapp' | 'notificacoes' | 'perfil'
type ApiEnvelope<T> = { data: T }
type Appointment = { id: string; starts_at: string; ends_at: string; status: string; customer_name: string; service_name: string; professional_name: string }

type QuickAction = { key: TabKey; label: string; icon: string; accent?: boolean }

const tabs: QuickAction[] = [
  { key: 'home', label: 'Início', icon: '▦', accent: true },
  { key: 'agenda', label: 'Agenda', icon: '◷' },
  { key: 'clientes', label: 'Clientes', icon: '◎' },
  { key: 'whatsapp', label: 'WhatsApp', icon: '☏' },
  { key: 'notificacoes', label: 'Avisos', icon: '✉' },
  { key: 'perfil', label: 'Perfil', icon: '⚙' },
]

const manifest = ref<BrandingManifest | null>(null)
const activeTab = ref<TabKey>('home')
const apiUrl = (import.meta.env.VITE_API_BASE_URL || 'https://scheduler.argws.com.br/api/v1').replace(/\/$/, '')
const email = ref(localStorage.getItem('scheduler_pro_mobile_email') || '')
const password = ref('')
const token = ref(localStorage.getItem('scheduler_pro_mobile_access_token') || '')
const authError = ref('')
const loading = ref(false)
const apiState = ref<'online' | 'offline' | 'checking'>('checking')
const appointments = ref<Appointment[]>([])
const lastSync = ref('Nunca')

const appName = computed(() => manifest.value?.app.public_name || manifest.value?.app.name || 'Scheduler Pro')
const slogan = computed(() => manifest.value?.app.slogan || 'Agenda, clientes, confirmações e WhatsApp no celular.')
const logged = computed(() => Boolean(token.value))
const activeTabLabel = computed(() => tabs.find((tab) => tab.key === activeTab.value)?.label || 'Início')
const nextAppointment = computed(() => appointments.value[0] || null)
const confirmed = computed(() => appointments.value.filter((item) => item.status === 'CONFIRMED').length)
const pending = computed(() => appointments.value.filter((item) => item.status.includes('PENDING') || item.status.includes('AWAITING')).length)

function endpoint(path: string): string { return `${apiUrl}${path}` }
function setTab(tab: TabKey): void { activeTab.value = tab }

async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response
  try {
    response = await fetch(endpoint(path), {
      ...init,
      headers: {
        'content-type': 'application/json',
        ...(token.value ? { authorization: `Bearer ${token.value}` } : {}),
        ...(init.headers || {}),
      },
    })
  } catch {
    throw new Error('Não foi possível conectar à API. Verifique internet, SSL, Cloudflare/proxy e liberação CORS para o aplicativo instalado.')
  }
  const body = await response.json().catch(() => ({})) as Partial<ApiEnvelope<T>> & { error?: { message?: string } }
  if (!response.ok) throw new Error(body.error?.message || `Falha HTTP ${response.status}`)
  return body.data as T
}

async function boot(): Promise<void> {
  manifest.value = await loadBrandingManifest()
  applyBranding(manifest.value)
  await checkApi()
  if (token.value) await syncAgenda()
}

async function checkApi(): Promise<void> {
  apiState.value = 'checking'
  try {
    await fetch(endpoint('/health/ready'), { headers: { accept: 'application/json' } })
    apiState.value = 'online'
  } catch {
    apiState.value = 'offline'
  }
}

async function login(): Promise<void> {
  loading.value = true
  authError.value = ''
  try {
    const data = await api<{ access_token: string; refresh_token: string }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email: email.value, password: password.value }),
    })
    token.value = data.access_token
    localStorage.setItem('scheduler_pro_mobile_access_token', data.access_token)
    localStorage.setItem('scheduler_pro_mobile_refresh_token', data.refresh_token)
    localStorage.setItem('scheduler_pro_mobile_email', email.value)
    await syncAgenda()
  } catch (error) {
    authError.value = error instanceof Error ? error.message : 'Não foi possível entrar.'
  } finally {
    loading.value = false
  }
}

function logout(): void {
  token.value = ''
  appointments.value = []
  localStorage.removeItem('scheduler_pro_mobile_access_token')
  localStorage.removeItem('scheduler_pro_mobile_refresh_token')
}

async function syncAgenda(): Promise<void> {
  loading.value = true
  try {
    appointments.value = await api<Appointment[]>('/appointments')
    apiState.value = 'online'
    lastSync.value = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  } catch {
    apiState.value = 'offline'
  } finally {
    loading.value = false
  }
}

onMounted(() => { void boot() })
</script>

<template>
  <main v-if="!logged" class="mobile-login">
    <section class="login-hero">
      <span class="app-mark">SP</span>
      <p class="eyebrow">Aplicativo mobile</p>
      <h1>{{ appName }}</h1>
      <p>{{ slogan }}</p>
    </section>
    <form class="mobile-card login-form" @submit.prevent="login">
      <label>E-mail<input v-model="email" type="email" autocomplete="username" required /></label>
      <label>Senha<input v-model="password" type="password" autocomplete="current-password" required /></label>
      <p v-if="authError" class="form-error">{{ authError }}</p>
      <button class="primary-button" type="submit" :disabled="loading">{{ loading ? 'Conectando...' : 'Entrar' }}</button>
      <button class="ghost-button" type="button" @click="checkApi">Testar conexão</button>
      <small :class="['connection', apiState]">{{ apiState === 'online' ? 'API online' : apiState === 'checking' ? 'verificando' : 'API offline' }}</small>
    </form>
  </main>

  <main v-else class="mobile-app">
    <header class="mobile-top">
      <div><p class="eyebrow">{{ activeTabLabel }}</p><h1>{{ appName }}</h1></div>
      <button class="round-button" type="button" @click="syncAgenda">{{ loading ? '…' : '↻' }}</button>
    </header>

    <section v-if="activeTab === 'home'" class="mobile-content">
      <article class="hero-card">
        <div><span class="connection online">Operação do dia</span><h2>{{ appointments.length }} agendamentos</h2><p>{{ confirmed }} confirmados • {{ pending }} pendentes</p></div>
        <button class="primary-button" type="button" @click="setTab('agenda')">Abrir agenda</button>
      </article>
      <section class="stats-grid">
        <article><strong>{{ appointments.length }}</strong><span>Hoje</span></article>
        <article><strong>{{ confirmed }}</strong><span>Confirmados</span></article>
        <article><strong>{{ lastSync }}</strong><span>Sync</span></article>
      </section>
      <article class="mobile-card next-card">
        <p class="eyebrow">Próximo atendimento</p>
        <template v-if="nextAppointment">
          <h3>{{ nextAppointment.customer_name }}</h3>
          <p>{{ nextAppointment.service_name }} com {{ nextAppointment.professional_name }}</p>
          <time>{{ new Date(nextAppointment.starts_at).toLocaleString() }}</time>
        </template>
        <p v-else class="empty">Nenhum atendimento carregado.</p>
      </article>
      <section class="quick-grid">
        <button v-for="item in tabs.filter((tab) => tab.key !== 'home')" :key="item.key" type="button" @click="setTab(item.key)"><span>{{ item.icon }}</span><strong>{{ item.label }}</strong></button>
      </section>
    </section>

    <section v-else-if="activeTab === 'agenda'" class="mobile-content">
      <article class="mobile-card"><div class="card-title"><div><p class="eyebrow">Agenda</p><h2>Atendimentos sincronizados</h2></div><button class="mini-button" type="button">Novo</button></div><div class="mobile-list"><article v-for="item in appointments" :key="item.id"><time>{{ new Date(item.starts_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }}</time><div><strong>{{ item.customer_name }}</strong><small>{{ item.service_name }} • {{ item.professional_name }}</small></div><span>{{ item.status }}</span></article><p v-if="appointments.length === 0" class="empty">Sem atendimentos na agenda.</p></div></article>
    </section>

    <section v-else class="mobile-content">
      <article class="mobile-card module-detail"><p class="eyebrow">{{ activeTabLabel }}</p><h2>{{ activeTabLabel }} no aplicativo</h2><p>Superfície mobile preparada para operar o tenant autenticado, com API real, sessão local e visual responsivo.</p><ul><li>Status: {{ apiState }}</li><li>Última sincronização: {{ lastSync }}</li></ul><button v-if="activeTab === 'perfil'" class="ghost-button" type="button" @click="logout">Sair</button></article>
    </section>

    <nav class="bottom-nav">
      <button v-for="tab in tabs" :key="tab.key" type="button" :class="{ active: activeTab === tab.key }" @click="setTab(tab.key)"><span>{{ tab.icon }}</span><small>{{ tab.label }}</small></button>
    </nav>
  </main>
</template>
