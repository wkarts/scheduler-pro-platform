<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

type ModuleKey = 'overview' | 'clientes' | 'dominios' | 'builds' | 'provisionamento' | 'logs' | 'integracoes' | 'auditoria'
type AuthMode = 'login' | 'forgot' | 'reset'
type ApiEnvelope<T> = { data: T }
type Tenant = { id: string; name: string; slug: string; status: string; primary_hostname?: string | null; created_at?: string | null }
type Domain = { id: string; tenant_id: string; tenant_name?: string | null; hostname: string; status: string; is_temporary: boolean; is_primary: boolean }
type BuildJob = { id: string; target: string; status: string; source_ref?: string | null; created_at?: string | null }
type LogEntry = { id: string; tenant_name?: string | null; tenant_slug?: string | null; source: string; service?: string | null; level: string; event: string; message: string; integration?: string | null; error_code?: string | null; created_at?: string | null }
type LogSummary = { last_24h: { total: number; errors: number; docker: number; integrations: number; tenant_scoped: number } }
type Dashboard = {
  totals: { tenants: number; active_tenants: number; domains_pending: number; builds: number; build_artifacts: number; provisioning_jobs: number }
  health?: Record<string, string>
  recent_tenants: Tenant[]
  recent_builds: BuildJob[]
  recent_provisioning: Array<{ id: string; status: string; correlation_id: string; created_at?: string | null }>
}
type ModuleItem = { key: ModuleKey; label: string; icon: string; description: string }

const modules: ModuleItem[] = [
  { key: 'overview', label: 'Visão geral', icon: '▦', description: 'Indicadores globais e saúde operacional' },
  { key: 'clientes', label: 'Clientes SaaS', icon: '▤', description: 'Tenants, bancos e recursos isolados' },
  { key: 'dominios', label: 'Domínios', icon: '◎', description: 'DNS, SSL, Cloudflare e cache' },
  { key: 'builds', label: 'Builds', icon: '⬢', description: 'Artefatos web, desktop, Android e iOS' },
  { key: 'provisionamento', label: 'Provisionamento', icon: '⚙', description: 'Fila de criação e bootstrap de ambientes' },
  { key: 'logs', label: 'Logs', icon: '◫', description: 'Eventos Docker, API, tenants e integrações' },
  { key: 'integracoes', label: 'Integrações', icon: '⌁', description: 'Cloudflare, Evolution API, storage e filas' },
  { key: 'auditoria', label: 'Auditoria', icon: '☰', description: 'Eventos sensíveis e rastreabilidade' },
]

const apiBase = (import.meta.env.VITE_ADMIN_API_BASE_URL || 'https://admin.scheduler.argws.com.br/api/v1').replace(/\/$/, '')
const initialResetToken = new URLSearchParams(window.location.search).get('reset-token') || ''
const active = ref<ModuleKey>('overview')
const collapsed = ref(false)
const email = ref(localStorage.getItem('scheduler_admin_desktop_email') || '')
const password = ref('')
const token = ref(localStorage.getItem('scheduler_admin_desktop_token') || '')
const authMode = ref<AuthMode>(initialResetToken ? 'reset' : 'login')
const resetToken = ref(initialResetToken)
const newPassword = ref('')
const confirmPassword = ref('')
const recoveryMessage = ref('')
const error = ref('')
const toast = ref('')
const loading = ref(false)
const dashboard = ref<Dashboard | null>(null)
const tenants = ref<Tenant[]>([])
const domains = ref<Domain[]>([])
const buildJobs = ref<BuildJob[]>([])
const logs = ref<LogEntry[]>([])
const logSummary = ref<LogSummary | null>(null)

const logged = computed(() => Boolean(token.value))
const selectedModule = computed(() => modules.find((item) => item.key === active.value) || modules[0])
const healthRows = computed(() => Object.entries(dashboard.value?.health || { platform: 'online', queue: 'configured', storage: 'configured', release: 'available' }))
const recentTenants = computed<Tenant[]>(() => tenants.value.length ? tenants.value.slice(0, 8) : (dashboard.value?.recent_tenants || []))
const visibleJobs = computed<BuildJob[]>(() => buildJobs.value.length ? buildJobs.value.slice(0, 8) : (dashboard.value?.recent_builds || []))
const metricTotals = computed(() => dashboard.value?.totals || { tenants: 0, active_tenants: 0, domains_pending: 0, builds: 0, build_artifacts: 0, provisioning_jobs: 0 })

function connectionError(): string {
  return 'Não foi possível conectar à API administrativa. Verifique HTTPS, proxy /api/v1, CORS nativo e se a imagem API foi atualizada.'
}

async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${apiBase}${path}`, {
      ...init,
      headers: { 'content-type': 'application/json', ...(token.value ? { authorization: `Bearer ${token.value}` } : {}), ...(init.headers || {}) },
    })
  } catch {
    throw new Error(connectionError())
  }
  const body = await response.json().catch(() => ({})) as Partial<ApiEnvelope<T>> & { error?: { message?: string } }
  if (!response.ok) throw new Error(body.error?.message || `Falha HTTP ${response.status}`)
  return body.data as T
}

function setToast(message: string): void {
  toast.value = message
  window.setTimeout(() => { if (toast.value === message) toast.value = '' }, 4500)
}
function statusClass(value?: string | null): string { return String(value || '').toLowerCase().replace(/[^a-z0-9]+/g, '-') }
function formatDate(value?: string | null): string { return value ? new Date(value).toLocaleString('pt-BR') : '—' }
function setAuthMode(mode: AuthMode): void { authMode.value = mode; error.value = ''; recoveryMessage.value = ''; password.value = ''; newPassword.value = ''; confirmPassword.value = '' }

async function login(): Promise<void> {
  loading.value = true
  error.value = ''
  recoveryMessage.value = ''
  try {
    const data = await api<{ access_token: string }>('/auth/platform/login', { method: 'POST', body: JSON.stringify({ email: email.value, password: password.value }) })
    token.value = data.access_token
    localStorage.setItem('scheduler_admin_desktop_token', data.access_token)
    localStorage.setItem('scheduler_admin_desktop_email', email.value)
    password.value = ''
    await refreshAll()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Não foi possível entrar.'
  } finally {
    loading.value = false
  }
}
async function forgotPassword(): Promise<void> {
  loading.value = true
  error.value = ''
  recoveryMessage.value = ''
  try {
    const data = await api<{ accepted: boolean; message: string }>('/auth/platform/password/forgot', { method: 'POST', body: JSON.stringify({ email: email.value }) })
    recoveryMessage.value = data.message || 'Se a conta existir, enviaremos as instruções por e-mail.'
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Não foi possível solicitar a recuperação.'
  } finally {
    loading.value = false
  }
}
async function resetPassword(): Promise<void> {
  error.value = ''
  recoveryMessage.value = ''
  if (newPassword.value.length < 12) { error.value = 'A nova senha deve possuir pelo menos 12 caracteres.'; return }
  if (newPassword.value !== confirmPassword.value) { error.value = 'A confirmação da senha não confere.'; return }
  loading.value = true
  try {
    const data = await api<{ password_reset: boolean; message: string }>('/auth/platform/password/reset', { method: 'POST', body: JSON.stringify({ token: resetToken.value, new_password: newPassword.value }) })
    recoveryMessage.value = data.message || 'Senha redefinida. Entre novamente.'
    history.replaceState({}, document.title, window.location.pathname)
    resetToken.value = ''
    authMode.value = 'login'
    newPassword.value = ''
    confirmPassword.value = ''
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Não foi possível redefinir a senha.'
  } finally {
    loading.value = false
  }
}
async function submitAuth(): Promise<void> {
  if (authMode.value === 'login') await login()
  else if (authMode.value === 'forgot') await forgotPassword()
  else await resetPassword()
}
function logout(): void {
  token.value = ''
  dashboard.value = null
  tenants.value = []
  domains.value = []
  buildJobs.value = []
  logs.value = []
  localStorage.removeItem('scheduler_admin_desktop_token')
}
async function loadDashboard(): Promise<void> { dashboard.value = await api<Dashboard>('/platform/dashboard') }
async function loadLists(): Promise<void> {
  const [tenantRows, domainRows, jobPayload] = await Promise.all([
    api<Tenant[]>('/platform/tenants'),
    api<Domain[]>('/platform/domains'),
    api<{ jobs: BuildJob[] }>('/platform/builds/jobs'),
  ])
  tenants.value = tenantRows
  domains.value = domainRows
  buildJobs.value = jobPayload.jobs || []
}
async function loadLogs(): Promise<void> {
  const [rows, summary] = await Promise.all([
    api<LogEntry[]>('/platform/observability/logs?limit=200'),
    api<LogSummary>('/platform/observability/logs/summary'),
  ])
  logs.value = rows
  logSummary.value = summary
}
async function refreshAll(): Promise<void> {
  error.value = ''
  loading.value = true
  try {
    await loadDashboard()
    await loadLists()
    if (active.value === 'logs') await loadLogs()
  } catch (err) {
    error.value = err instanceof Error ? err.message : connectionError()
  } finally {
    loading.value = false
  }
}
async function openModule(key: ModuleKey): Promise<void> {
  active.value = key
  if (key === 'logs') await loadLogs()
  else if (!dashboard.value || !tenants.value.length) await refreshAll()
}
async function checkDomain(id: string): Promise<void> {
  await api(`/platform/domains/${id}/check`, { method: 'POST', body: '{}' })
  setToast('Verificação executada.')
  await refreshAll()
}
async function purgeDomain(id: string): Promise<void> {
  await api(`/platform/domains/${id}/purge-cache`, { method: 'POST', body: '{}' })
  setToast('Purge solicitado.')
  await loadLogs()
}

onMounted(() => { if (token.value) void refreshAll() })
</script>

<template>
  <main v-if="!logged" class="login-shell">
    <section class="login-brand panel-card">
      <div class="brand-mark">SP</div>
      <p class="eyebrow">Control Plane Desktop</p>
      <h1>Scheduler Pro Admin</h1>
      <p>Administração da plataforma com o mesmo padrão visual do Hub Fiscal: sidebar escura, cards brancos, tabelas, logs e operação SaaS em uma aplicação instalada.</p>
      <div class="proof-grid"><span>Tenants</span><span>Domínios</span><span>Builds</span><span>Logs</span></div>
    </section>
    <form class="login-card panel-card" @submit.prevent="submitAuth">
      <p class="eyebrow">{{ authMode === 'login' ? 'Entrar' : authMode === 'forgot' ? 'Recuperar acesso' : 'Nova senha' }}</p>
      <h2>{{ authMode === 'login' ? 'Acessar Control Plane' : authMode === 'forgot' ? 'Esqueci minha senha' : 'Redefinir senha' }}</h2>
      <label v-if="authMode !== 'reset'">E-mail<input v-model="email" type="email" autocomplete="username" required /></label>
      <label v-if="authMode === 'login'">Senha<input v-model="password" type="password" autocomplete="current-password" required /></label>
      <template v-if="authMode === 'reset'">
        <label>Nova senha<input v-model="newPassword" type="password" autocomplete="new-password" minlength="12" required /></label>
        <label>Confirmar nova senha<input v-model="confirmPassword" type="password" autocomplete="new-password" minlength="12" required /></label>
      </template>
      <p v-if="error" class="error-box">{{ error }}</p>
      <p v-if="recoveryMessage" class="toast-box">{{ recoveryMessage }}</p>
      <button class="btn primary" type="submit" :disabled="loading">{{ loading ? 'Processando...' : authMode === 'login' ? 'Entrar no painel' : authMode === 'forgot' ? 'Enviar link de recuperação' : 'Salvar nova senha' }}</button>
      <button v-if="authMode === 'login'" class="btn" type="button" @click="setAuthMode('forgot')">Esqueci minha senha</button>
      <button v-else class="btn" type="button" @click="setAuthMode('login')">Voltar para o login</button>
    </form>
  </main>

  <main v-else class="app-shell" :class="{ collapsed }">
    <aside class="sidebar">
      <div class="brand"><div class="brand-mark small">SP</div><div><strong>Scheduler Pro</strong><small>Control Plane</small></div></div>
      <nav class="nav-list">
        <button v-for="item in modules" :key="item.key" class="nav-item" :class="{ active: active === item.key }" type="button" @click="openModule(item.key)"><span>{{ item.icon }}</span><div><strong>{{ item.label }}</strong><small>{{ item.description }}</small></div></button>
      </nav>
      <div class="sidebar-footer"><button class="nav-item" type="button" @click="logout"><span>⇥</span><div><strong>Sair</strong><small>Encerrar sessão local</small></div></button></div>
    </aside>

    <section class="content-shell">
      <header class="topbar"><button class="icon-button" type="button" @click="collapsed=!collapsed">☰</button><div class="tenant-switcher"><span>Plataforma ativa</span><strong>ARGWS Scheduler Pro</strong></div><div class="topbar-spacer"></div><button class="btn" type="button" @click="refreshAll">Atualizar</button><div class="profile"><div class="avatar">SP</div><div><strong>{{ email }}</strong><small>platform_admin</small></div></div></header>
      <main class="main-content">
        <section class="page-header"><div><p class="eyebrow">{{ selectedModule.label }}</p><h1>{{ selectedModule.description }}</h1></div><div class="page-actions"><button class="btn" type="button" @click="openModule('logs')">Logs</button><button class="btn primary" type="button" @click="openModule('clientes')">Clientes</button></div></section>
        <p v-if="error" class="error-box">{{ error }}</p><p v-if="toast" class="toast-box">{{ toast }}</p>

        <section class="metric-grid">
          <article class="metric-card blue"><div><span>Clientes SaaS</span><strong>{{ metricTotals.tenants }}</strong><small>{{ metricTotals.active_tenants }} ativos</small></div><i>▤</i></article>
          <article class="metric-card violet"><div><span>Provisionamentos</span><strong>{{ metricTotals.provisioning_jobs }}</strong><small>jobs registrados</small></div><i>⚙</i></article>
          <article class="metric-card green"><div><span>Domínios pendentes</span><strong>{{ metricTotals.domains_pending }}</strong><small>DNS / SSL</small></div><i>◎</i></article>
          <article class="metric-card orange"><div><span>Builds e artefatos</span><strong>{{ metricTotals.builds }}/{{ metricTotals.build_artifacts }}</strong><small>jobs / arquivos</small></div><i>⬢</i></article>
        </section>

        <section v-if="active === 'overview'" class="dashboard-grid">
          <article class="panel span-2"><div class="panel-title"><div><h3>Clientes recentes</h3><p>Ambientes SaaS provisionados na plataforma</p></div></div><div class="job-list"><div v-for="tenant in recentTenants" :key="tenant.id" class="job-row"><div><strong>{{ tenant.name }}</strong><small>{{ tenant.slug }} • {{ tenant.primary_hostname || 'sem domínio primário' }}</small></div><span class="status" :class="statusClass(tenant.status)">{{ tenant.status }}</span></div><p v-if="!recentTenants.length" class="empty-inline">Nenhum cliente carregado.</p></div></article>
          <article class="panel"><div class="panel-title"><div><h3>Saúde operacional</h3><p>Componentes principais</p></div></div><div class="health-list"><div v-for="[name, status] in healthRows" :key="name"><span><i class="healthy"></i>{{ name }}</span><strong>{{ status }}</strong></div></div></article>
        </section>

        <section v-else-if="active === 'dominios'" class="panel"><div class="panel-title"><div><h3>Domínios</h3><p>DNS, verificação e purge Cloudflare</p></div></div><div class="data-table"><div class="table-head"><span>Hostname</span><span>Cliente</span><span>Status</span><span>Ações</span></div><div v-for="domain in domains" :key="domain.id" class="table-row"><span><strong>{{ domain.hostname }}</strong><small>{{ domain.is_temporary ? 'temporário' : 'personalizado' }} {{ domain.is_primary ? '• primário' : '' }}</small></span><span>{{ domain.tenant_name || domain.tenant_id }}</span><span class="status" :class="statusClass(domain.status)">{{ domain.status }}</span><span class="actions"><button class="btn small" @click="checkDomain(domain.id)">Verificar</button><button class="btn small" @click="purgeDomain(domain.id)">Purge</button></span></div></div></section>

        <section v-else-if="active === 'builds'" class="panel"><div class="panel-title"><div><h3>Builds e artefatos</h3><p>Distribuições web, desktop, Android e iOS</p></div></div><div class="job-list"><div v-for="job in visibleJobs" :key="job.id" class="job-row"><div><strong>{{ job.target }}</strong><small>{{ job.source_ref || 'main' }} • {{ formatDate(job.created_at) }}</small></div><span class="status" :class="statusClass(job.status)">{{ job.status }}</span></div><p v-if="!visibleJobs.length" class="empty-inline">Nenhum build registrado.</p></div></section>

        <section v-else-if="active === 'logs'" class="panel"><div class="panel-title"><div><h3>Logs registrados</h3><p>{{ logs.length }} eventos carregados</p></div><button class="btn small" @click="loadLogs">Atualizar</button></div><div class="log-list"><details v-for="log in logs" :key="log.id" class="log-row"><summary><strong>{{ log.level }} • {{ log.source }} • {{ log.event }}</strong><small>{{ formatDate(log.created_at) }} • {{ log.tenant_name || log.tenant_slug || 'plataforma' }} • {{ log.message }}</small></summary><pre>{{ log.error_code || log.integration || log.service || 'sem detalhes' }}</pre></details><p v-if="!logs.length" class="empty-inline">Nenhum log carregado.</p></div></section>

        <section v-else class="panel"><div class="panel-title"><div><h3>{{ selectedModule.label }}</h3><p>{{ selectedModule.description }}</p></div></div><div class="ops-grid"><article><strong>Operação</strong><span>Conectada ao Control Plane por API absoluta.</span></article><article><strong>Segurança</strong><span>Sessão local, Bearer token e logs auditáveis.</span></article><article><strong>Entrega</strong><span>Mesmo padrão visual do painel web administrativo.</span></article></div></section>
      </main>
    </section>
  </main>
</template>
