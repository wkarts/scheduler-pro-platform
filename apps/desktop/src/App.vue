<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { applyBranding, loadBrandingManifest, type BrandingManifest } from './branding'

type ViewKey = 'dashboard' | 'agenda' | 'clientes' | 'servicos' | 'profissionais' | 'whatsapp' | 'notificacoes' | 'branding' | 'sync' | 'configuracoes'
type AuthMode = 'login' | 'forgot' | 'reset'
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

const configuredApiUrl = (import.meta.env.VITE_API_BASE_URL || 'https://scheduler.argws.com.br/api/v1').replace(/\/$/, '')
const configuredHostname = new URL(configuredApiUrl).hostname.toLowerCase()
const genericDistribution = configuredHostname === 'scheduler.argws.com.br'
const initialResetToken = new URLSearchParams(window.location.search).get('reset-token') || ''
const manifest = ref<BrandingManifest | null>(null)
const activeView = ref<ViewKey>('dashboard')
const collapsed = ref(false)
const tenantAddress = ref(localStorage.getItem('scheduler_pro_desktop_tenant') || (genericDistribution ? '' : configuredHostname))
const email = ref(localStorage.getItem('scheduler_pro_desktop_email') || '')
const password = ref('')
const token = ref(localStorage.getItem('scheduler_pro_desktop_access_token') || '')
const authMode = ref<AuthMode>(initialResetToken ? 'reset' : 'login')
const resetToken = ref(initialResetToken)
const newPassword = ref('')
const confirmPassword = ref('')
const recoveryMessage = ref('')
const authError = ref('')
const loading = ref(false)
const apiState = ref<'online' | 'offline' | 'checking'>('checking')
const appointments = ref<Appointment[]>([])
const customers = ref<Customer[]>([])
const lastSync = ref<string>('Nunca sincronizado')

function normalizeTenantApi(value: string): string {
  const trimmed = value.trim()
  if (!trimmed) return configuredApiUrl
  const url = new URL(trimmed.includes('://') ? trimmed : `https://${trimmed}`)
  if (url.protocol !== 'https:' && !['localhost', '127.0.0.1'].includes(url.hostname)) throw new Error('O endereço do tenant deve utilizar HTTPS.')
  const pathname = url.pathname.replace(/\/$/, '')
  url.pathname = /\/api\/v1$/.test(pathname) ? pathname : '/api/v1'
  url.search = ''
  url.hash = ''
  return url.toString().replace(/\/$/, '')
}

const apiUrl = computed(() => genericDistribution ? normalizeTenantApi(tenantAddress.value) : configuredApiUrl)
const tenantConfigured = computed(() => !genericDistribution || Boolean(tenantAddress.value.trim()))
const appName = computed(() => manifest.value?.app.public_name || manifest.value?.app.name || 'Scheduler Pro Desktop')
const slogan = computed(() => manifest.value?.app.slogan || 'Aplicativo gerencial para agenda, clientes, WhatsApp e notificações.')
const logged = computed(() => Boolean(token.value))
const activeNav = computed(() => navItems.find((item) => item.key === activeView.value) || navItems[0])
const todayAppointments = computed(() => appointments.value.length)
const confirmedCount = computed(() => appointments.value.filter((item) => item.status === 'CONFIRMED').length)
const pendingCount = computed(() => appointments.value.filter((item) => item.status.includes('PENDING') || item.status.includes('AWAITING')).length)

function setView(key: ViewKey): void { activeView.value = key }
function endpoint(path: string): string { return `${apiUrl.value}${path}` }
function setAuthMode(mode: AuthMode): void { authMode.value = mode; authError.value = ''; recoveryMessage.value = ''; password.value = ''; newPassword.value = ''; confirmPassword.value = '' }

async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  if (!tenantConfigured.value) throw new Error('Informe o endereço do tenant recebido no e-mail de acesso.')
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
  } catch (error) {
    if (error instanceof Error && error.message.includes('tenant')) throw error
    throw new Error('Não foi possível conectar à API. Verifique o endereço do tenant, internet, SSL e Cloudflare/proxy.')
  }
  const body = await response.json().catch(() => ({})) as Partial<ApiEnvelope<T>> & { error?: { message?: string } }
  if (!response.ok) throw new Error(body.error?.message || `Falha HTTP ${response.status}`)
  return body.data as T
}

async function refreshBranding(): Promise<void> {
  if (!tenantConfigured.value) return
  manifest.value = await loadBrandingManifest(apiUrl.value)
  applyBranding(manifest.value)
}
async function boot(): Promise<void> {
  if (tenantConfigured.value) {
    await refreshBranding()
    await checkApi()
    if (token.value) await syncData()
  } else {
    apiState.value = 'offline'
  }
}
async function checkApi(): Promise<void> {
  if (!tenantConfigured.value) { apiState.value = 'offline'; authError.value = 'Informe o endereço do tenant.'; return }
  apiState.value = 'checking'
  try {
    const response = await fetch(endpoint('/health/ready'), { headers: { accept: 'application/json' } })
    apiState.value = response.ok ? 'online' : 'offline'
  } catch { apiState.value = 'offline' }
}
async function login(): Promise<void> {
  loading.value = true
  authError.value = ''
  recoveryMessage.value = ''
  try {
    if (!tenantConfigured.value) throw new Error('Informe o endereço do tenant recebido no e-mail de acesso.')
    const data = await api<{ access_token: string; refresh_token: string }>('/auth/login', { method: 'POST', body: JSON.stringify({ email: email.value, password: password.value }) })
    token.value = data.access_token
    localStorage.setItem('scheduler_pro_desktop_access_token', data.access_token)
    localStorage.setItem('scheduler_pro_desktop_refresh_token', data.refresh_token)
    localStorage.setItem('scheduler_pro_desktop_email', email.value)
    localStorage.setItem('scheduler_pro_desktop_tenant', tenantAddress.value.trim())
    password.value = ''
    await refreshBranding()
    await syncData()
  } catch (error) {
    authError.value = error instanceof Error ? error.message : 'Não foi possível entrar.'
  } finally { loading.value = false }
}
async function forgotPassword(): Promise<void> {
  loading.value = true
  authError.value = ''
  recoveryMessage.value = ''
  try {
    if (!tenantConfigured.value) throw new Error('Informe o endereço do tenant antes de recuperar a senha.')
    const data = await api<{ accepted: boolean; message: string }>('/auth/password/forgot', { method: 'POST', body: JSON.stringify({ email: email.value }) })
    localStorage.setItem('scheduler_pro_desktop_tenant', tenantAddress.value.trim())
    recoveryMessage.value = data.message || 'Se a conta existir, enviaremos as instruções por e-mail.'
  } catch (error) {
    authError.value = error instanceof Error ? error.message : 'Não foi possível solicitar a recuperação.'
  } finally { loading.value = false }
}
async function resetPassword(): Promise<void> {
  authError.value = ''
  recoveryMessage.value = ''
  if (newPassword.value.length < 12) { authError.value = 'A nova senha deve possuir pelo menos 12 caracteres.'; return }
  if (newPassword.value !== confirmPassword.value) { authError.value = 'A confirmação da senha não confere.'; return }
  loading.value = true
  try {
    const data = await api<{ password_reset: boolean; message: string }>('/auth/password/reset', { method: 'POST', body: JSON.stringify({ token: resetToken.value, new_password: newPassword.value }) })
    recoveryMessage.value = data.message || 'Senha redefinida. Entre novamente.'
    history.replaceState({}, document.title, window.location.pathname)
    resetToken.value = ''
    authMode.value = 'login'
    newPassword.value = ''
    confirmPassword.value = ''
  } catch (error) {
    authError.value = error instanceof Error ? error.message : 'Não foi possível redefinir a senha.'
  } finally { loading.value = false }
}
async function submitAuth(): Promise<void> {
  if (authMode.value === 'login') await login()
  else if (authMode.value === 'forgot') await forgotPassword()
  else await resetPassword()
}
function logout(): void { token.value = ''; appointments.value = []; customers.value = []; localStorage.removeItem('scheduler_pro_desktop_access_token'); localStorage.removeItem('scheduler_pro_desktop_refresh_token') }
async function syncData(): Promise<void> { loading.value = true; try { appointments.value = await api<Appointment[]>('/appointments'); try { customers.value = await api<Customer[]>('/customers') } catch { customers.value = [] }; apiState.value = 'online'; lastSync.value = new Date().toLocaleString() } catch { apiState.value = 'offline' } finally { loading.value = false } }
onMounted(() => { void boot() })
</script>

<template>
  <section v-if="!logged" class="desktop-auth">
    <div class="auth-hero">
      <div class="product-badge"><span>SP</span><strong>{{ appName }}</strong></div>
      <p class="eyebrow">Aplicativo desktop</p>
      <h1>Gestão da agenda com operação local, API remota e experiência profissional.</h1>
      <p>{{ slogan }}</p>
      <div class="auth-proof"><span>Agenda transacional</span><span>WhatsApp Evolution</span><span>Marca do cliente</span></div>
    </div>
    <form class="login-panel" @submit.prevent="submitAuth">
      <p class="eyebrow">{{ authMode === 'login' ? 'Conectar' : authMode === 'forgot' ? 'Recuperar acesso' : 'Nova senha' }}</p>
      <h2>{{ authMode === 'login' ? 'Entrar no aplicativo' : authMode === 'forgot' ? 'Esqueci minha senha' : 'Redefinir senha' }}</h2>
      <label v-if="genericDistribution">Endereço do tenant<input v-model="tenantAddress" type="text" autocomplete="url" placeholder="cliente.scheduler.argws.com.br" :required="genericDistribution" /></label>
      <label v-if="authMode !== 'reset'">E-mail<input v-model="email" type="email" autocomplete="username" placeholder="admin@empresa.com.br" required /></label>
      <label v-if="authMode === 'login'">Senha<input v-model="password" type="password" autocomplete="current-password" required /></label>
      <template v-if="authMode === 'reset'">
        <label>Nova senha<input v-model="newPassword" type="password" autocomplete="new-password" minlength="12" required /></label>
        <label>Confirmar nova senha<input v-model="confirmPassword" type="password" autocomplete="new-password" minlength="12" required /></label>
      </template>
      <p v-if="authError" class="form-error">{{ authError }}</p>
      <p v-if="recoveryMessage" class="api-dot online">{{ recoveryMessage }}</p>
      <button class="primary-action" type="submit" :disabled="loading">{{ loading ? 'Processando...' : authMode === 'login' ? 'Entrar e sincronizar' : authMode === 'forgot' ? 'Enviar link de recuperação' : 'Salvar nova senha' }}</button>
      <button v-if="authMode === 'login'" class="secondary-action" type="button" @click="setAuthMode('forgot')">Esqueci minha senha</button>
      <button v-else class="secondary-action" type="button" @click="setAuthMode('login')">Voltar para o login</button>
      <button class="secondary-action" type="button" @click="checkApi">Testar conexão</button>
      <small :class="['api-dot', apiState]">{{ apiState === 'online' ? 'API online' : apiState === 'checking' ? 'verificando API' : 'API offline' }}</small>
    </form>
  </section>

  <div v-else class="desktop-shell">
    <aside class="rail" :class="{ collapsed }"><button class="collapse-button" type="button" @click="collapsed = !collapsed">{{ collapsed ? '›' : '‹' }}</button><div class="brand-block"><div class="brand-icon">SP</div><div><strong>{{ appName }}</strong><small>{{ slogan }}</small></div></div><nav><button v-for="item in navItems" :key="item.key" type="button" :class="['nav-button', { active: activeView === item.key }]" @click="setView(item.key)"><span>{{ item.icon }}</span><div><strong>{{ item.label }}</strong><small>{{ item.hint }}</small></div></button></nav><div class="rail-footer"><button class="nav-button" type="button" @click="logout"><span>⇥</span><div><strong>Sair</strong><small>Encerrar sessão local</small></div></button></div></aside>
    <section class="workspace"><header class="workspace-topbar"><div><p class="eyebrow">{{ activeNav.label }}</p><h1>{{ activeNav.hint }}</h1></div><div class="top-actions"><span :class="['api-chip', apiState]">{{ apiState }}</span><button class="secondary-action" type="button" @click="syncData">Sincronizar</button></div></header>
      <main class="workspace-content">
        <section v-if="activeView === 'dashboard'" class="dashboard-grid"><article class="metric-card"><span>Agendamentos</span><strong>{{ todayAppointments }}</strong><small>{{ confirmedCount }} confirmados hoje</small></article><article class="metric-card"><span>Pendências</span><strong>{{ pendingCount }}</strong><small>confirmações e retornos</small></article><article class="metric-card"><span>Clientes</span><strong>{{ customers.length }}</strong><small>base sincronizada</small></article><article class="metric-card accent"><span>Última sincronização</span><strong>{{ lastSync }}</strong><small>desktop conectado ao tenant</small></article><section class="panel wide"><div class="panel-title"><div><h2>Próximos atendimentos</h2><p>Lista real de agendamentos retornada pela API.</p></div><button class="secondary-action" type="button" @click="setView('agenda')">Abrir agenda</button></div><div class="rows"><article v-for="item in appointments" :key="item.id" class="data-row"><time>{{ new Date(item.starts_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }}</time><div><strong>{{ item.customer_name }}</strong><small>{{ item.service_name }} • {{ item.professional_name }}</small></div><span>{{ item.status }}</span></article><p v-if="appointments.length === 0" class="empty">Nenhum agendamento carregado. Sincronize a API ou cadastre horários no WebApp.</p></div></section><section class="panel"><h2>Saúde operacional</h2><ul class="health-list"><li><span>API</span><strong>{{ apiState }}</strong></li><li><span>Autenticação</span><strong>Sessão local</strong></li><li><span>Fila</span><strong>Workers</strong></li><li><span>Distribuição</span><strong>Instalável</strong></li></ul></section></section>
        <section v-else-if="activeView === 'agenda'" class="panel full"><div class="panel-title"><div><h2>Agenda operacional</h2><p>Conflitos, status e disponibilidade do motor de agenda.</p></div><button class="primary-action compact" type="button">Novo agendamento</button></div><div class="timeline"><article v-for="item in appointments" :key="item.id"><time>{{ new Date(item.starts_at).toLocaleString() }}</time><div><strong>{{ item.customer_name }}</strong><small>{{ item.service_name }} com {{ item.professional_name }}</small></div><span>{{ item.status }}</span></article><p v-if="appointments.length === 0" class="empty">Sem atendimentos sincronizados.</p></div></section>
        <section v-else class="module-grid"><article class="module-card"><p class="eyebrow">{{ activeNav.label }}</p><h2>{{ activeNav.hint }}</h2><p>Módulo nativo conectado ao tenant autenticado, com sessão local, sincronização e visual consistente com o WebApp.</p><button class="primary-action compact" type="button" @click="syncData">Sincronizar dados</button></article><article class="module-card muted"><h3>Contexto sincronizado</h3><ul><li>Status: {{ apiState }}</li><li>Última sync: {{ lastSync }}</li><li>Tenant: {{ manifest?.tenant?.slug || tenantAddress || 'resolvido pela distribuição' }}</li></ul></article></section>
      </main>
    </section>
  </div>
</template>
