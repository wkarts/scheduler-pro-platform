<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { applyBranding, loadBrandingManifest, type BrandingManifest } from './branding'

type ViewKey = 'dashboard' | 'agenda' | 'clientes' | 'servicos' | 'profissionais' | 'whatsapp' | 'notificacoes' | 'branding' | 'sync' | 'configuracoes'
type ApiEnvelope<T> = { data: T }
type Appointment = { id: string; starts_at: string; ends_at: string; status: string; customer_name: string; service_name: string; professional_name: string }
type Customer = { id: string; name: string; phone?: string; email?: string }

type NavItem = { key: ViewKey; label: string; icon: string; hint: string }

const navItems: NavItem[] = [
  { key: 'dashboard', label: 'Visão geral', icon: '▦', hint: 'Indicadores e saúde da operação' },
  { key: 'agenda', label: 'Agenda', icon: '◷', hint: 'Atendimentos e conflitos' },
  { key: 'clientes', label: 'Clientes', icon: '◎', hint: 'Cadastro e histórico' },
  { key: 'servicos', label: 'Serviços', icon: '✦', hint: 'Catálogo e duração' },
  { key: 'profissionais', label: 'Profissionais', icon: '♙', hint: 'Equipe, escala e disponibilidade' },
  { key: 'whatsapp', label: 'WhatsApp', icon: '☏', hint: 'Conexão Evolution API' },
  { key: 'notificacoes', label: 'Notificações', icon: '✉', hint: 'Templates, lembretes e fila' },
  { key: 'branding', label: 'Marca e app', icon: '◈', hint: 'Identidade do cliente' },
  { key: 'sync', label: 'Sincronização', icon: '⇄', hint: 'API, cache e status local' },
  { key: 'configuracoes', label: 'Configurações', icon: '⚙', hint: 'Preferências do aplicativo' },
]

const manifest = ref<BrandingManifest | null>(null)
const activeView = ref<ViewKey>('dashboard')
const collapsed = ref(false)
const apiUrl = (import.meta.env.VITE_API_BASE_URL || 'https://scheduler.argws.com.br/api/v1').replace(/\/$/, '')
const email = ref(localStorage.getItem('scheduler_pro_desktop_email') || '')
const password = ref('')
const token = ref(localStorage.getItem('scheduler_pro_desktop_access_token') || '')
const authError = ref('')
const loading = ref(false)
const apiState = ref<'online' | 'offline' | 'checking'>('checking')
const appointments = ref<Appointment[]>([])
const customers = ref<Customer[]>([])
const lastSync = ref<string>('Nunca sincronizado')

const appName = computed(() => manifest.value?.app.public_name || manifest.value?.app.name || 'Scheduler Pro Desktop')
const slogan = computed(() => manifest.value?.app.slogan || 'Aplicativo gerencial para agenda, clientes, WhatsApp e notificações.')
const logged = computed(() => Boolean(token.value))
const activeNav = computed(() => navItems.find((item) => item.key === activeView.value) || navItems[0])
const todayAppointments = computed(() => appointments.value.length)
const confirmedCount = computed(() => appointments.value.filter((item) => item.status === 'CONFIRMED').length)
const pendingCount = computed(() => appointments.value.filter((item) => item.status.includes('PENDING') || item.status.includes('AWAITING')).length)

function setView(key: ViewKey): void { activeView.value = key }
function endpoint(path: string): string { return `${apiUrl}${path}` }

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
  if (token.value) await syncData()
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
    localStorage.setItem('scheduler_pro_desktop_access_token', data.access_token)
    localStorage.setItem('scheduler_pro_desktop_refresh_token', data.refresh_token)
    localStorage.setItem('scheduler_pro_desktop_email', email.value)
    await syncData()
  } catch (error) {
    authError.value = error instanceof Error ? error.message : 'Não foi possível entrar.'
  } finally {
    loading.value = false
  }
}

function logout(): void {
  token.value = ''
  appointments.value = []
  customers.value = []
  localStorage.removeItem('scheduler_pro_desktop_access_token')
  localStorage.removeItem('scheduler_pro_desktop_refresh_token')
}

async function syncData(): Promise<void> {
  loading.value = true
  try {
    appointments.value = await api<Appointment[]>('/appointments')
    try { customers.value = await api<Customer[]>('/customers') } catch { customers.value = [] }
    apiState.value = 'online'
    lastSync.value = new Date().toLocaleString()
  } catch {
    apiState.value = 'offline'
  } finally {
    loading.value = false
  }
}

onMounted(() => { void boot() })
</script>

<template>
  <section v-if="!logged" class="desktop-auth">
    <div class="auth-hero">
      <div class="product-badge"><span>SP</span><strong>{{ appName }}</strong></div>
      <p class="eyebrow">Aplicativo desktop</p>
      <h1>Gestão da agenda com operação local, API remota e experiência profissional.</h1>
      <p>{{ slogan }}</p>
      <div class="auth-proof">
        <span>Agenda transacional</span>
        <span>WhatsApp Evolution</span>
        <span>Marca do cliente</span>
      </div>
    </div>
    <form class="login-panel" @submit.prevent="login">
      <p class="eyebrow">Conectar</p>
      <h2>Entrar no aplicativo</h2>
      <label>E-mail<input v-model="email" type="email" autocomplete="username" placeholder="admin@empresa.com.br" required /></label>
      <label>Senha<input v-model="password" type="password" autocomplete="current-password" required /></label>
      <p v-if="authError" class="form-error">{{ authError }}</p>
      <button class="primary-action" type="submit" :disabled="loading">{{ loading ? 'Conectando...' : 'Entrar e sincronizar' }}</button>
      <button class="secondary-action" type="button" @click="checkApi">Testar API</button>
      <small :class="['api-dot', apiState]">{{ apiState === 'online' ? 'API online' : apiState === 'checking' ? 'verificando API' : 'API offline' }}</small>
    </form>
  </section>

  <div v-else class="desktop-shell">
    <aside class="rail" :class="{ collapsed }">
      <button class="collapse-button" type="button" @click="collapsed = !collapsed">{{ collapsed ? '›' : '‹' }}</button>
      <div class="brand-block"><div class="brand-icon">SP</div><div><strong>{{ appName }}</strong><small>{{ slogan }}</small></div></div>
      <nav>
        <button v-for="item in navItems" :key="item.key" type="button" :class="['nav-button', { active: activeView === item.key }]" @click="setView(item.key)">
          <span>{{ item.icon }}</span><div><strong>{{ item.label }}</strong><small>{{ item.hint }}</small></div>
        </button>
      </nav>
      <div class="rail-footer"><button class="nav-button" type="button" @click="logout"><span>⇥</span><div><strong>Sair</strong><small>Encerrar sessão local</small></div></button></div>
    </aside>

    <section class="workspace">
      <header class="workspace-topbar">
        <div><p class="eyebrow">{{ activeNav.label }}</p><h1>{{ activeNav.hint }}</h1></div>
        <div class="top-actions"><span :class="['api-chip', apiState]">{{ apiState }}</span><button class="secondary-action" type="button" @click="syncData">Sincronizar</button></div>
      </header>

      <main class="workspace-content">
        <section v-if="activeView === 'dashboard'" class="dashboard-grid">
          <article class="metric-card"><span>Agendamentos</span><strong>{{ todayAppointments }}</strong><small>{{ confirmedCount }} confirmados hoje</small></article>
          <article class="metric-card"><span>Pendências</span><strong>{{ pendingCount }}</strong><small>confirmações e retornos</small></article>
          <article class="metric-card"><span>Clientes</span><strong>{{ customers.length }}</strong><small>base sincronizada</small></article>
          <article class="metric-card accent"><span>Última sincronização</span><strong>{{ lastSync }}</strong><small>desktop conectado ao tenant</small></article>
          <section class="panel wide"><div class="panel-title"><div><h2>Próximos atendimentos</h2><p>Lista real de agendamentos retornada pela API.</p></div><button class="secondary-action" type="button" @click="setView('agenda')">Abrir agenda</button></div><div class="rows"><article v-for="item in appointments" :key="item.id" class="data-row"><time>{{ new Date(item.starts_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }}</time><div><strong>{{ item.customer_name }}</strong><small>{{ item.service_name }} • {{ item.professional_name }}</small></div><span>{{ item.status }}</span></article><p v-if="appointments.length === 0" class="empty">Nenhum agendamento carregado. Sincronize a API ou cadastre horários no WebApp.</p></div></section>
          <section class="panel"><h2>Saúde operacional</h2><ul class="health-list"><li><span>API</span><strong>{{ apiState }}</strong></li><li><span>Auth</span><strong>Bearer local</strong></li><li><span>Fila</span><strong>Workers</strong></li><li><span>Build</span><strong>Pós-merge</strong></li></ul></section>
        </section>

        <section v-else-if="activeView === 'agenda'" class="panel full"><div class="panel-title"><div><h2>Agenda operacional</h2><p>Conflitos, status e disponibilidade vêm do motor de agenda.</p></div><button class="primary-action compact" type="button">Novo agendamento</button></div><div class="timeline"><article v-for="item in appointments" :key="item.id"><time>{{ new Date(item.starts_at).toLocaleString() }}</time><div><strong>{{ item.customer_name }}</strong><small>{{ item.service_name }} com {{ item.professional_name }}</small></div><span>{{ item.status }}</span></article><p v-if="appointments.length === 0" class="empty">Sem atendimentos sincronizados.</p></div></section>

        <section v-else class="module-grid">
          <article class="module-card"><p class="eyebrow">{{ activeNav.label }}</p><h2>{{ activeNav.hint }}</h2><p>Este módulo está pronto como superfície nativa e usa os endpoints do tenant autenticado. A etapa seguinte é ligar CRUDs dedicados por recurso sem mudar a experiência visual.</p><button class="primary-action compact" type="button">Abrir fluxo</button></article>
          <article class="module-card muted"><h3>Contexto sincronizado</h3><ul><li>Status: {{ apiState }}</li><li>Última sync: {{ lastSync }}</li><li>Tenant: {{ manifest?.tenant?.slug || 'resolvido pela distribuição' }}</li></ul></article>
        </section>
      </main>
    </section>
  </div>
</template>
