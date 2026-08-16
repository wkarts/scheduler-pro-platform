<script setup lang="ts">
import { computed, ref } from 'vue'

type ModuleKey = 'overview' | 'clientes' | 'dominios' | 'builds' | 'provisionamento' | 'logs' | 'integracoes' | 'auditoria'
type ApiEnvelope<T> = { data: T }
type Dashboard = {
  totals: { tenants: number; active_tenants: number; domains_pending: number; builds: number; build_artifacts: number; provisioning_jobs: number }
  recent_tenants: Array<{ id: string; name: string; slug: string; status: string }>
  recent_builds: Array<{ id: string; target: string; status: string }>
  recent_provisioning: Array<{ id: string; status: string; correlation_id: string }>
}
type LogEntry = { id: string; tenant_name?: string | null; tenant_slug?: string | null; source: string; service: string; level: string; event: string; message: string; integration?: string | null; error_code?: string | null; created_at?: string | null }
type LogSummary = { last_24h: { total: number; errors: number; docker: number; integrations: number; tenant_scoped: number }; tenant_boundaries: Array<{ tenant_id: string; tenant_name: string; slug: string; database_name: string; storage_bucket: string; artifact_prefix: string; isolation_status: string }> }

const modules = [
  { key: 'overview', label: 'Visão geral', icon: '▦' },
  { key: 'clientes', label: 'Clientes SaaS', icon: '▤' },
  { key: 'dominios', label: 'Domínios', icon: '◎' },
  { key: 'builds', label: 'Builds', icon: '⬢' },
  { key: 'provisionamento', label: 'Provisionamento', icon: '⚙' },
  { key: 'logs', label: 'Logs', icon: '◫' },
  { key: 'integracoes', label: 'Integrações', icon: '⌁' },
  { key: 'auditoria', label: 'Auditoria', icon: '☰' },
] as const

const apiBase = (import.meta.env.VITE_ADMIN_API_BASE_URL || 'https://admin.scheduler.argws.com.br/api/v1').replace(/\/$/, '')
const active = ref<ModuleKey>('overview')
const email = ref('')
const password = ref('')
const token = ref(localStorage.getItem('scheduler_admin_desktop_token') || '')
const error = ref('')
const loading = ref(false)
const dashboard = ref<Dashboard | null>(null)
const logs = ref<LogEntry[]>([])
const logSummary = ref<LogSummary | null>(null)
const logged = computed(() => Boolean(token.value))
const selectedModule = computed(() => modules.find((item) => item.key === active.value) || modules[0])

async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${apiBase}${path}`, {
      ...init,
      headers: { 'content-type': 'application/json', ...(token.value ? { authorization: `Bearer ${token.value}` } : {}), ...(init.headers || {}) },
    })
  } catch {
    throw new Error('Não foi possível conectar à API. Verifique internet, SSL, Cloudflare/proxy e liberação CORS para o aplicativo instalado.')
  }
  const body = await response.json().catch(() => ({})) as Partial<ApiEnvelope<T>> & { error?: { message?: string } }
  if (!response.ok) throw new Error(body.error?.message || 'Falha ao comunicar com o Control Plane')
  return body.data as T
}

async function login(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    const data = await api<{ access_token: string }>('/auth/platform/login', { method: 'POST', body: JSON.stringify({ email: email.value, password: password.value }) })
    token.value = data.access_token
    localStorage.setItem('scheduler_admin_desktop_token', data.access_token)
    await loadDashboard()
  } catch (err) { error.value = err instanceof Error ? err.message : 'Não foi possível entrar' }
  finally { loading.value = false }
}

async function loadDashboard(): Promise<void> { dashboard.value = await api<Dashboard>('/platform/dashboard') }
async function loadLogs(): Promise<void> { const [rows, summary] = await Promise.all([api<LogEntry[]>('/platform/observability/logs?limit=200'), api<LogSummary>('/platform/observability/logs/summary')]); logs.value = rows; logSummary.value = summary }
async function openModule(key: ModuleKey): Promise<void> { active.value = key; if (key === 'logs') await loadLogs(); else if (!dashboard.value) await loadDashboard() }
function logout(): void { token.value = ''; dashboard.value = null; logs.value = []; localStorage.removeItem('scheduler_admin_desktop_token') }
function formatDate(value?: string | null): string { return value ? new Date(value).toLocaleString('pt-BR') : '—' }
</script>

<template>
  <main v-if="!logged" class="auth-screen">
    <section class="auth-hero"><div class="brand-mark">SP</div><p class="eyebrow">Control Plane Desktop</p><h1>Administração da plataforma com distribuição própria.</h1><p>Gerencie clientes, domínios, logs, provisionamentos e builds em um aplicativo instalado.</p></section>
    <form class="login-card" @submit.prevent="login"><h2>Entrar</h2><label>E-mail<input v-model="email" type="email" autocomplete="username" required /></label><label>Senha<input v-model="password" type="password" autocomplete="current-password" required /></label><p v-if="error" class="error">{{ error }}</p><button type="submit" :disabled="loading">{{ loading ? 'Validando...' : 'Entrar no painel' }}</button></form>
  </main>

  <main v-else class="shell">
    <aside class="sidebar"><div class="brand"><span>SP</span><div><strong>Scheduler Pro</strong><small>Control Plane</small></div></div><button v-for="item in modules" :key="item.key" :class="{ active: active === item.key }" type="button" @click="openModule(item.key)"><span>{{ item.icon }}</span>{{ item.label }}</button><button class="logout" type="button" @click="logout">Sair</button></aside>
    <section class="workspace">
      <header><div><p class="eyebrow">{{ selectedModule.label }}</p><h1>{{ selectedModule.label }}</h1></div><button type="button" @click="active === 'logs' ? loadLogs() : loadDashboard()">Atualizar</button></header>
      <section v-if="active === 'overview'" class="grid"><article><span>Clientes</span><strong>{{ dashboard?.totals.tenants ?? '—' }}</strong></article><article><span>Ativos</span><strong>{{ dashboard?.totals.active_tenants ?? '—' }}</strong></article><article><span>Domínios pendentes</span><strong>{{ dashboard?.totals.domains_pending ?? '—' }}</strong></article><article><span>Artefatos</span><strong>{{ dashboard?.totals.build_artifacts ?? '—' }}</strong></article></section>
      <section v-else-if="active === 'logs'" class="grid"><article><span>Logs 24h</span><strong>{{ logSummary?.last_24h.total ?? 0 }}</strong></article><article><span>Erros</span><strong>{{ logSummary?.last_24h.errors ?? 0 }}</strong></article><article><span>Integrações</span><strong>{{ logSummary?.last_24h.integrations ?? 0 }}</strong></article><article><span>Tenant scoped</span><strong>{{ logSummary?.last_24h.tenant_scoped ?? 0 }}</strong></article></section>
      <section class="panel">
        <h2>{{ selectedModule.label }}</h2>
        <p v-if="active !== 'logs'">Operação conectada aos endpoints administrativos do Control Plane.</p>
        <div v-if="active === 'logs'" class="rows"><article v-for="log in logs" :key="log.id"><strong>{{ log.level }} • {{ log.source }} • {{ log.event }}</strong><small>{{ formatDate(log.created_at) }} • {{ log.tenant_name || log.tenant_slug || 'plataforma' }} • {{ log.message }}</small></article><p v-if="!logs.length" class="empty">Nenhum log carregado.</p></div>
        <div v-else class="rows"><article v-for="tenant in dashboard?.recent_tenants ?? []" :key="tenant.id"><strong>{{ tenant.name }}</strong><small>{{ tenant.slug }} • {{ tenant.status }}</small></article><p v-if="!dashboard?.recent_tenants?.length" class="empty">Carregue o painel para visualizar dados reais.</p></div>
      </section>
    </section>
  </main>
</template>
