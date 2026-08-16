<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { apiGet, apiPost, type ApiError } from './api/client'

type LoginResponse = {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
  user: { id: string; email: string; name?: string | null; roles?: string[]; permissions?: string[] }
}

type DashboardResponse = {
  totals: { tenants: number; active_tenants: number; provisioning_jobs: number; domains_pending: number; builds: number; build_artifacts: number; platform_users: number }
  health: Record<string, string>
  recent_tenants: Tenant[]
  recent_builds: BuildJob[]
  recent_provisioning: ProvisioningJob[]
}

type Tenant = { id: string; name: string; slug: string; status: string; created_at?: string | null; primary_hostname?: string | null; branding_name?: string | null }
type Domain = { id: string; tenant_id: string; tenant_name: string; hostname: string; is_primary: boolean; is_temporary: boolean; status: string; validation?: Record<string, unknown> | null }
type BuildJob = { id: string; target: string; status: string; created_at?: string | null; tenant_id?: string | null; tenant_slug?: string | null; source_ref?: string | null }
type BuildProfile = { id?: string; tenant_id?: string; name?: string; target?: string; platform?: string; package_name?: string; bundle_identifier?: string; api_url?: string; status?: string }
type ProvisioningJob = { id: string; status: string; correlation_id: string; created_at?: string | null }
type SessionState = { accessToken: string; refreshToken: string; userEmail: string }
type PwaInstaller = { canInstall: boolean; isInstalled: boolean; install: () => Promise<{ outcome?: string } | void> }
type ModuleKey = 'overview' | 'tenants' | 'provisioning' | 'domains' | 'builds' | 'branding' | 'plans' | 'integrations' | 'audit' | 'settings'
type ModuleItem = { key: ModuleKey; label: string; icon: string; description: string }

const storageKey = 'scheduler-pro-admin-session'

const modules: ModuleItem[] = [
  { key: 'overview', label: 'Visão geral', icon: '▦', description: 'Indicadores globais da plataforma' },
  { key: 'tenants', label: 'Clientes SaaS', icon: '▤', description: 'Clientes contratantes, domínios e provisionamento' },
  { key: 'provisioning', label: 'Provisionamento', icon: '⚙', description: 'Fila operacional de criação de ambientes' },
  { key: 'domains', label: 'Domínios', icon: '🌐', description: 'Domínios temporários, personalizados e validação Cloudflare' },
  { key: 'builds', label: 'Builds e artefatos', icon: '⬢', description: 'Aplicativos web, PWA, desktop, Android e iOS' },
  { key: 'branding', label: 'White-label', icon: '◇', description: 'Marca, ícones, app name e tema por cliente' },
  { key: 'plans', label: 'Planos e features', icon: '▣', description: 'Planos comerciais e recursos liberados' },
  { key: 'integrations', label: 'Integrações', icon: '⌁', description: 'Cloudflare, Evolution API, storage e filas' },
  { key: 'audit', label: 'Auditoria', icon: '☰', description: 'Eventos, sessões, segurança e alterações sensíveis' },
  { key: 'settings', label: 'Configurações', icon: '⚙', description: 'Parâmetros globais do Control Plane' },
]

const email = ref('')
const password = ref('')
const authenticating = ref(false)
const loadingDashboard = ref(false)
const loadingLists = ref(false)
const actionBusy = ref(false)
const errorMessage = ref('')
const toastMessage = ref('')
const session = ref<SessionState | null>(null)
const dashboard = ref<DashboardResponse | null>(null)
const tenants = ref<Tenant[]>([])
const domains = ref<Domain[]>([])
const buildJobs = ref<BuildJob[]>([])
const buildProfiles = ref<BuildProfile[]>([])
const activeModule = ref<ModuleKey>('overview')
const sidebarOpen = ref(false)
const search = ref('')
const installState = ref({ canInstall: false, isInstalled: false })

const tenantForm = ref({ name: '', slug: '', admin_email: '' })
const domainForm = ref({ tenant_id: '', hostname: '', make_primary: false })
const buildForm = ref({ tenant: '', target: 'pwa', source_ref: 'main' })

const selectedModule = computed(() => modules.find(module => module.key === activeModule.value) ?? modules[0])
const isAuthenticated = computed(() => Boolean(session.value?.accessToken))
const totals = computed(() => dashboard.value?.totals)
const activeTenantsRatio = computed(() => {
  const tenantTotal = Number(totals.value?.tenants || 0)
  if (!tenantTotal) return '0%'
  return `${Math.round((Number(totals.value?.active_tenants || 0) / tenantTotal) * 100)}%`
})
const healthRows = computed(() => Object.entries(dashboard.value?.health ?? {}).map(([key, value]) => ({ key, value })))
const filteredTenants = computed(() => filterBySearch(tenants.value, tenant => `${tenant.name} ${tenant.slug} ${tenant.primary_hostname ?? ''}`))
const filteredDomains = computed(() => filterBySearch(domains.value, domain => `${domain.hostname} ${domain.tenant_name} ${domain.status}`))
const filteredBuildJobs = computed(() => filterBySearch(buildJobs.value, job => `${job.target} ${job.status} ${job.id} ${job.source_ref ?? ''}`))
const selectedTenant = computed(() => tenants.value.find(tenant => tenant.id === domainForm.value.tenant_id || tenant.id === buildForm.value.tenant))

function filterBySearch<T>(items: T[], mapper: (item: T) => string): T[] {
  const query = search.value.trim().toLowerCase()
  if (!query) return items
  return items.filter(item => mapper(item).toLowerCase().includes(query))
}

function restoreSession(): void {
  const raw = localStorage.getItem(storageKey)
  if (!raw) return
  try { session.value = JSON.parse(raw) as SessionState } catch { localStorage.removeItem(storageKey) }
}

function persistSession(payload: LoginResponse): void {
  session.value = { accessToken: payload.access_token, refreshToken: payload.refresh_token, userEmail: payload.user?.email ?? email.value }
  localStorage.setItem(storageKey, JSON.stringify(session.value))
}

function clearSession(): void {
  session.value = null
  dashboard.value = null
  tenants.value = []
  domains.value = []
  buildJobs.value = []
  buildProfiles.value = []
  localStorage.removeItem(storageKey)
}

function describeError(error: unknown, fallback: string): string {
  const apiError = error as Partial<ApiError>
  if (apiError?.message === 'Failed to fetch') return 'Não foi possível conectar à API pelo domínio atual. Verifique o proxy /api/v1 no CloudPanel.'
  return apiError?.message || fallback
}

function showToast(message: string): void {
  toastMessage.value = message
  window.setTimeout(() => { if (toastMessage.value === message) toastMessage.value = '' }, 4500)
}

async function login(): Promise<void> {
  errorMessage.value = ''
  authenticating.value = true
  try {
    const payload = await apiPost<LoginResponse>('/auth/platform/login', { email: email.value, password: password.value })
    persistSession(payload)
    password.value = ''
    await refreshAll()
  } catch (error) { errorMessage.value = describeError(error, 'Não foi possível autenticar no painel administrativo.') }
  finally { authenticating.value = false }
}

async function refreshAll(): Promise<void> { await loadDashboard(); await loadOperationalLists() }

async function loadDashboard(): Promise<void> {
  if (!session.value?.accessToken) return
  errorMessage.value = ''
  loadingDashboard.value = true
  try { dashboard.value = await apiGet<DashboardResponse>('/platform/dashboard', session.value.accessToken) }
  catch (error) {
    const apiError = error as ApiError
    if (apiError.status === 401 || apiError.status === 403) clearSession()
    errorMessage.value = describeError(error, 'Não foi possível carregar os dados administrativos.')
  } finally { loadingDashboard.value = false }
}

async function loadOperationalLists(): Promise<void> {
  if (!session.value?.accessToken) return
  loadingLists.value = true
  try {
    const [tenantRows, domainRows, jobsPayload, profilesPayload] = await Promise.all([
      apiGet<Tenant[]>('/platform/tenants', session.value.accessToken),
      apiGet<Domain[]>('/platform/domains', session.value.accessToken),
      apiGet<{ jobs: BuildJob[] }>('/platform/builds/jobs', session.value.accessToken),
      apiGet<{ profiles: BuildProfile[] }>('/platform/builds/profiles', session.value.accessToken),
    ])
    tenants.value = tenantRows
    domains.value = domainRows
    buildJobs.value = jobsPayload.jobs ?? []
    buildProfiles.value = profilesPayload.profiles ?? []
  } catch (error) { errorMessage.value = describeError(error, 'Não foi possível carregar listas operacionais.') }
  finally { loadingLists.value = false }
}

async function createTenant(): Promise<void> {
  if (!session.value?.accessToken) return
  actionBusy.value = true
  errorMessage.value = ''
  try {
    await apiPost('/platform/tenants', { name: tenantForm.value.name, slug: tenantForm.value.slug || null, admin_email: tenantForm.value.admin_email }, session.value.accessToken)
    tenantForm.value = { name: '', slug: '', admin_email: '' }
    showToast('Cliente enviado para provisionamento.')
    await refreshAll()
    activeModule.value = 'provisioning'
  } catch (error) { errorMessage.value = describeError(error, 'Não foi possível criar o tenant.') }
  finally { actionBusy.value = false }
}

async function createTemporaryDomain(tenantId: string): Promise<void> {
  if (!session.value?.accessToken) return
  actionBusy.value = true
  errorMessage.value = ''
  try {
    await apiPost(`/platform/tenants/${tenantId}/domains/temporary`, {}, session.value.accessToken)
    showToast('Domínio temporário enviado para provisionamento.')
    await refreshAll()
    activeModule.value = 'domains'
  } catch (error) { errorMessage.value = describeError(error, 'Não foi possível criar domínio temporário.') }
  finally { actionBusy.value = false }
}

async function connectCustomDomain(): Promise<void> {
  if (!session.value?.accessToken) return
  actionBusy.value = true
  errorMessage.value = ''
  try {
    await apiPost(`/platform/tenants/${domainForm.value.tenant_id}/domains/custom`, { hostname: domainForm.value.hostname, make_primary: domainForm.value.make_primary }, session.value.accessToken)
    domainForm.value = { tenant_id: domainForm.value.tenant_id, hostname: '', make_primary: false }
    showToast('Domínio personalizado enviado para validação Cloudflare.')
    await refreshAll()
  } catch (error) { errorMessage.value = describeError(error, 'Não foi possível conectar o domínio personalizado.') }
  finally { actionBusy.value = false }
}

async function checkDomain(domainId: string): Promise<void> {
  if (!session.value?.accessToken) return
  actionBusy.value = true
  try { await apiPost(`/platform/domains/${domainId}/check`, {}, session.value.accessToken); showToast('Verificação de domínio executada.'); await refreshAll() }
  catch (error) { errorMessage.value = describeError(error, 'Não foi possível verificar o domínio.') }
  finally { actionBusy.value = false }
}

async function purgeDomainCache(domainId: string): Promise<void> {
  if (!session.value?.accessToken) return
  actionBusy.value = true
  try { await apiPost(`/platform/domains/${domainId}/purge-cache`, {}, session.value.accessToken); showToast('Purge de cache solicitado na Cloudflare.') }
  catch (error) { errorMessage.value = describeError(error, 'Não foi possível limpar o cache do domínio.') }
  finally { actionBusy.value = false }
}

async function createBuildRequest(): Promise<void> {
  if (!session.value?.accessToken) return
  actionBusy.value = true
  try {
    await apiPost('/platform/builds/requests', { tenant: buildForm.value.tenant, target: buildForm.value.target, source_ref: buildForm.value.source_ref || 'main', requested_by: session.value.userEmail, payload: {} }, session.value.accessToken)
    showToast('Build enviado para a fila.')
    await refreshAll()
  } catch (error) { errorMessage.value = describeError(error, 'Não foi possível criar o build.') }
  finally { actionBusy.value = false }
}

function updateInstallState(): void {
  const installer = (window as unknown as { schedulerProAdminPwa?: PwaInstaller }).schedulerProAdminPwa
  installState.value = { canInstall: Boolean(installer?.canInstall), isInstalled: Boolean(installer?.isInstalled) }
}

async function installPwa(): Promise<void> {
  const installer = (window as unknown as { schedulerProAdminPwa?: PwaInstaller }).schedulerProAdminPwa
  if (installer?.isInstalled) { showToast('WebApp administrativo já está instalado.'); return }
  if (installer?.canInstall) { await installer.install(); updateInstallState(); return }
  showToast('Instalação indisponível neste navegador neste momento.')
}

function selectModule(key: ModuleKey): void {
  activeModule.value = key
  sidebarOpen.value = false
  if (isAuthenticated.value && ['tenants', 'domains', 'builds', 'branding'].includes(key)) loadOperationalLists()
}

function formatDate(value?: string | null): string {
  if (!value) return '—'
  return new Date(value).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
}

function statusClass(status?: string | null): string { return String(status || '').toLowerCase().replace(/[^a-z0-9]+/g, '-') }
function tenantLabel(tenantId?: string | null): string { const tenant = tenants.value.find(item => item.id === tenantId); return tenant ? `${tenant.name} (${tenant.slug})` : tenantId || '—' }

onMounted(() => {
  restoreSession()
  updateInstallState()
  if (session.value?.accessToken) refreshAll()
  window.addEventListener('scheduler-pro-admin-install-state', updateInstallState)
  window.addEventListener('scheduler-pro-admin-install-ready', updateInstallState)
  window.addEventListener('scheduler-pro-admin-installed', updateInstallState)
})

onUnmounted(() => {
  window.removeEventListener('scheduler-pro-admin-install-state', updateInstallState)
  window.removeEventListener('scheduler-pro-admin-install-ready', updateInstallState)
  window.removeEventListener('scheduler-pro-admin-installed', updateInstallState)
})
</script>

<template>
  <main class="admin-root">
    <section v-if="!isAuthenticated" class="auth-page">
      <aside class="auth-visual">
        <div class="auth-brand"><div class="brand-mark">SP</div><div><strong>Scheduler Pro</strong><span>Control Plane</span></div></div>
        <h1>Controle a plataforma, clientes, domínios e artefatos em um painel central.</h1>
        <p>Gerencie clientes SaaS, provisionamento, white-label, builds, integrações e auditoria com uma interface administrativa instalável.</p>
      </aside>
      <form class="auth-card" @submit.prevent="login">
        <div class="mobile-brand"><div class="brand-mark">SP</div><div><strong>Scheduler Pro</strong><span>Administração da plataforma</span></div></div>
        <p class="eyebrow">Administração</p><h2>Entrar na plataforma</h2><p>Utilize suas credenciais administrativas do Control Plane.</p>
        <label for="email">E-mail</label><input id="email" v-model="email" autocomplete="username" placeholder="admin@empresa.com.br" required type="email" />
        <label for="password">Senha</label><input id="password" v-model="password" autocomplete="current-password" placeholder="••••••••" required type="password" />
        <p v-if="errorMessage" class="form-error">{{ errorMessage }}</p>
        <button class="btn primary full" :disabled="authenticating" type="submit">{{ authenticating ? 'Validando...' : 'Entrar' }}</button>
        <button v-if="installState.canInstall && !installState.isInstalled" class="btn full" type="button" @click="installPwa">Instalar WebApp administrativo</button>
        <p v-else-if="installState.isInstalled" class="install-state">WebApp administrativo instalado.</p>
      </form>
    </section>

    <section v-else class="admin-shell" :class="{ mobileOpen: sidebarOpen }">
      <aside class="sidebar">
        <div class="brand"><div class="brand-mark">SP</div><div><strong>Scheduler Pro</strong><small>Administração da plataforma</small></div></div>
        <nav class="nav-list"><button v-for="module in modules" :key="module.key" class="nav-item" :class="{ active: activeModule === module.key }" type="button" @click="selectModule(module.key)"><span class="nav-icon">{{ module.icon }}</span><span>{{ module.label }}</span></button></nav>
        <div class="sidebar-footer"><button v-if="installState.canInstall && !installState.isInstalled" class="nav-item install-action" type="button" @click="installPwa"><span class="nav-icon">⇩</span><span>Instalar PWA Admin</span></button><div v-else-if="installState.isInstalled" class="version-info"><strong>PWA instalado</strong><small>execução local do Control Plane</small></div><button class="nav-item" type="button" @click="clearSession"><span class="nav-icon">↩</span><span>Sair</span></button></div>
      </aside>
      <div v-if="sidebarOpen" class="mobile-backdrop" @click="sidebarOpen = false"></div>
      <div class="content-shell">
        <header class="topbar"><button class="icon-button" type="button" @click="sidebarOpen = !sidebarOpen">☰</button><label class="company-switcher"><span>Plataforma ativa</span><select disabled><option>ARGWS Scheduler Pro</option></select></label><div class="topbar-search"><span>⌕</span><input v-model="search" placeholder="Buscar cliente, domínio, build ou status" /></div><div class="topbar-spacer"></div><button class="btn" :disabled="loadingDashboard || loadingLists" type="button" @click="refreshAll">{{ loadingDashboard || loadingLists ? 'Atualizando...' : 'Atualizar' }}</button><div class="profile"><div><strong>{{ session?.userEmail }}</strong><small>platform_admin</small></div><div class="avatar">SP</div></div></header>
        <main class="main-content">
          <section class="page-header"><div><p class="eyebrow">Control Plane</p><h1>{{ selectedModule.label }}</h1><p>{{ selectedModule.description }}</p></div><div class="page-actions"><button class="btn" type="button" @click="selectModule('domains')">Domínios</button><button class="btn primary" type="button" @click="selectModule('tenants')">Novo tenant / cliente</button></div></section>
          <p v-if="toastMessage" class="toast-message">{{ toastMessage }}</p><p v-if="errorMessage" class="form-error wide">{{ errorMessage }}</p>

          <section v-if="activeModule === 'overview'" class="view-stack">
            <div class="metric-grid"><article class="metric-card blue"><div><span>Clientes SaaS</span><strong>{{ totals?.tenants ?? 0 }}</strong><small>{{ activeTenantsRatio }} ativos</small></div><b>▤</b></article><article class="metric-card violet"><div><span>Provisionamentos</span><strong>{{ totals?.provisioning_jobs ?? 0 }}</strong><small>jobs registrados</small></div><b>⚙</b></article><article class="metric-card green"><div><span>Domínios pendentes</span><strong>{{ totals?.domains_pending ?? 0 }}</strong><small>validação / SSL</small></div><b>🌐</b></article><article class="metric-card orange"><div><span>Builds e artefatos</span><strong>{{ totals ? `${totals.builds}/${totals.build_artifacts}` : '0/0' }}</strong><small>jobs / arquivos</small></div><b>⬢</b></article></div>
            <div class="dashboard-grid"><section class="panel span-2"><div class="panel-title"><div><h3>Clientes recentes</h3><p>Contratantes provisionados na plataforma</p></div><button class="btn small" type="button" @click="selectModule('tenants')">Ver todos</button></div><div class="list"><article v-for="tenant in dashboard?.recent_tenants ?? []" :key="tenant.id" class="row"><div class="time">{{ tenant.slug?.slice(0, 2).toUpperCase() || 'SP' }}</div><div><strong>{{ tenant.name }}</strong><small>{{ tenant.slug }} • {{ tenant.primary_hostname || 'sem domínio primário' }}</small></div><span class="status-pill" :class="statusClass(tenant.status)">{{ tenant.status }}</span></article><p v-if="!dashboard?.recent_tenants?.length" class="empty-state">Nenhum cliente encontrado no banco da plataforma.</p></div></section><section class="panel"><div class="panel-title"><div><h3>Saúde operacional</h3><p>Componentes principais</p></div></div><div class="health-list"><div v-for="item in healthRows" :key="item.key"><span><i class="ok"></i>{{ item.key }}</span><strong>{{ item.value }}</strong></div></div></section></div>
          </section>

          <section v-else-if="activeModule === 'tenants'" class="view-stack"><section class="panel form-panel"><div><p class="eyebrow">Novo cliente SaaS</p><h2>Criar tenant e iniciar provisionamento</h2><p>Gera job de provisionamento, slug único e prepara branding/build profiles para o cliente.</p></div><form class="inline-form" @submit.prevent="createTenant"><input v-model="tenantForm.name" placeholder="Nome do cliente / empresa" required /><input v-model="tenantForm.slug" placeholder="Slug opcional" /><input v-model="tenantForm.admin_email" placeholder="E-mail admin do cliente" required type="email" /><button class="btn primary" :disabled="actionBusy" type="submit">Criar cliente</button></form></section><section class="panel table-panel"><div class="panel-title"><div><h3>Clientes SaaS</h3><p>{{ filteredTenants.length }} registros carregados</p></div><button class="btn small" type="button" @click="loadOperationalLists">Atualizar</button></div><div class="responsive-table"><table><thead><tr><th>Cliente</th><th>Slug</th><th>Domínio</th><th>Status</th><th>Ações</th></tr></thead><tbody><tr v-for="tenant in filteredTenants" :key="tenant.id"><td><strong>{{ tenant.name }}</strong><small>{{ tenant.branding_name || 'branding inicial' }}</small></td><td>{{ tenant.slug }}</td><td>{{ tenant.primary_hostname || '—' }}</td><td><span class="status-pill" :class="statusClass(tenant.status)">{{ tenant.status }}</span></td><td><button class="btn small" :disabled="actionBusy" type="button" @click="createTemporaryDomain(tenant.id)">Domínio temporário</button></td></tr></tbody></table><p v-if="!filteredTenants.length" class="empty-state">Nenhum cliente encontrado.</p></div></section></section>

          <section v-else-if="activeModule === 'domains'" class="view-stack"><section class="panel form-panel"><div><p class="eyebrow">Domínio próprio</p><h2>Conectar domínio personalizado</h2><p>O cliente aponta CNAME para o proxy e o Control Plane valida via Cloudflare for SaaS.</p></div><form class="inline-form" @submit.prevent="connectCustomDomain"><select v-model="domainForm.tenant_id" required><option disabled value="">Selecione o cliente</option><option v-for="tenant in tenants" :key="tenant.id" :value="tenant.id">{{ tenant.name }} — {{ tenant.slug }}</option></select><input v-model="domainForm.hostname" placeholder="agenda.cliente.com.br" required /><label class="checkbox-line"><input v-model="domainForm.make_primary" type="checkbox" /> tornar primário</label><button class="btn primary" :disabled="actionBusy || !domainForm.tenant_id" type="submit">Conectar domínio</button></form><p v-if="selectedTenant" class="hint-line">Cliente selecionado: {{ selectedTenant.name }}</p></section><section class="panel table-panel"><div class="panel-title"><div><h3>Domínios</h3><p>Temporários e personalizados</p></div></div><div class="responsive-table"><table><thead><tr><th>Hostname</th><th>Cliente</th><th>Tipo</th><th>Status</th><th>Ações</th></tr></thead><tbody><tr v-for="domain in filteredDomains" :key="domain.id"><td><strong>{{ domain.hostname }}</strong><small>{{ domain.is_primary ? 'primário' : 'secundário' }}</small></td><td>{{ domain.tenant_name }}</td><td>{{ domain.is_temporary ? 'temporário' : 'custom' }}</td><td><span class="status-pill" :class="statusClass(domain.status)">{{ domain.status }}</span></td><td class="actions-cell"><button class="btn small" :disabled="actionBusy" type="button" @click="checkDomain(domain.id)">Verificar</button><button class="btn small" :disabled="actionBusy" type="button" @click="purgeDomainCache(domain.id)">Purge</button></td></tr></tbody></table><p v-if="!filteredDomains.length" class="empty-state">Nenhum domínio encontrado.</p></div></section></section>

          <section v-else-if="activeModule === 'builds'" class="view-stack"><section class="panel form-panel"><div><p class="eyebrow">Build Manager</p><h2>Solicitar build operacional</h2><p>Cria job de build por cliente/target. A geração pesada acontece em main/release/manual.</p></div><form class="inline-form" @submit.prevent="createBuildRequest"><select v-model="buildForm.tenant" required><option disabled value="">Selecione o cliente</option><option v-for="tenant in tenants" :key="tenant.id" :value="tenant.id">{{ tenant.name }} — {{ tenant.slug }}</option></select><select v-model="buildForm.target"><option value="web">web</option><option value="pwa">pwa</option><option value="desktop">desktop</option><option value="android">android</option><option value="ios">ios</option></select><input v-model="buildForm.source_ref" placeholder="main" /><button class="btn primary" :disabled="actionBusy || !buildForm.tenant" type="submit">Criar build</button></form></section><div class="dashboard-grid"><section class="panel table-panel"><div class="panel-title"><div><h3>Jobs de build</h3><p>{{ filteredBuildJobs.length }} jobs</p></div></div><div class="responsive-table"><table><thead><tr><th>Target</th><th>Cliente</th><th>Status</th><th>Criado em</th></tr></thead><tbody><tr v-for="job in filteredBuildJobs" :key="job.id"><td><strong>{{ job.target }}</strong><small>{{ job.id }}</small></td><td>{{ tenantLabel(job.tenant_id) }}</td><td><span class="status-pill" :class="statusClass(job.status)">{{ job.status }}</span></td><td>{{ formatDate(job.created_at) }}</td></tr></tbody></table><p v-if="!filteredBuildJobs.length" class="empty-state">Nenhum build registrado.</p></div></section><section class="panel table-panel"><div class="panel-title"><div><h3>Perfis disponíveis</h3><p>Web, PWA, desktop, Android e iOS</p></div></div><div class="list compact-list"><article v-for="profile in buildProfiles" :key="profile.id || `${profile.tenant_id}-${profile.target}`" class="row"><div class="time">{{ profile.target?.slice(0, 2).toUpperCase() || 'AP' }}</div><div><strong>{{ profile.name || profile.target || 'Perfil' }}</strong><small>{{ profile.package_name || profile.bundle_identifier || profile.api_url || 'perfil de build' }}</small></div><span class="status-pill">{{ profile.status || 'ready' }}</span></article><p v-if="!buildProfiles.length" class="empty-state">Nenhum perfil carregado ainda.</p></div></section></div></section>

          <section v-else-if="activeModule === 'provisioning'" class="view-stack"><section class="panel table-panel"><div class="panel-title"><div><h3>Provisionamentos recentes</h3><p>Criação de banco, domínio, storage, branding e admin do cliente</p></div></div><div class="list"><article v-for="job in dashboard?.recent_provisioning ?? []" :key="job.id" class="row"><div class="time">JOB</div><div><strong>{{ job.correlation_id }}</strong><small>{{ job.id }} • {{ formatDate(job.created_at) }}</small></div><span class="status-pill" :class="statusClass(job.status)">{{ job.status }}</span></article><p v-if="!dashboard?.recent_provisioning?.length" class="empty-state">Nenhum provisionamento registrado.</p></div></section></section>

          <section v-else class="cards-grid"><article class="panel card"><p class="eyebrow">{{ selectedModule.label }}</p><h3>{{ selectedModule.description }}</h3><p>Este módulo agora possui tela própria no Control Plane. Os dados globais já estão conectados ao dashboard e às listas operacionais disponíveis na API.</p></article><article class="panel card"><p class="eyebrow">Integrações</p><h3>Cloudflare, Evolution API, MinIO e RabbitMQ</h3><p>Use os módulos de Domínios e Builds para executar as operações já expostas pelos endpoints reais.</p></article><article class="panel card"><p class="eyebrow">Próxima conexão</p><h3>Plano comercial e auditoria detalhada</h3><p>As telas permanecem navegáveis e prontas para receber endpoints dedicados sem quebrar a experiência do painel.</p></article></section>
        </main>
      </div>
    </section>
  </main>
</template>
