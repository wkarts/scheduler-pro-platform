<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { apiDelete, apiGet, apiPost, apiPut, type ApiError } from './api/client'

type LoginResponse = {
  access_token: string
  refresh_token: string
  user: {
    id: string
    email: string
    permissions?: string[]
    roles?: string[]
    is_super_admin?: boolean
  }
}

type SessionState = {
  accessToken: string
  refreshToken: string
  userEmail: string
}

type Principal = {
  id: string
  email: string
  roles: string[]
  permissions: string[]
  tenant_ids: string[]
  is_super_admin: boolean
}

type Tenant = {
  id: string
  name: string
  slug: string
  status: string
  created_at?: string | null
  primary_hostname?: string | null
  branding_name?: string | null
  capabilities_enabled?: number
}

type Domain = {
  id: string
  tenant_id: string
  tenant_name?: string
  hostname: string
  is_primary: boolean
  is_temporary: boolean
  status: string
  validation?: Record<string, unknown>
}

type ProvisioningStep = {
  id: string
  name: string
  status: string
  error?: string | null
}

type ProvisioningJob = {
  id: string
  tenant_id: string
  tenant_name: string
  slug: string
  status: string
  correlation_id: string
  created_at?: string | null
  updated_at?: string | null
  steps: ProvisioningStep[]
}

type BuildArtifact = {
  id?: string
  name: string
  download_url?: string | null
  artifact_type?: string
  size_bytes?: number
}

type BuildJob = {
  id: string
  tenant?: string
  target: string
  status: string
  created_at?: string | null
  source_ref?: string | null
  workflow_run_id?: string | null
  error?: string | null
  artifacts?: BuildArtifact[]
}

type BuildProfile = {
  id: string
  tenant: string
  name: string
  target: string
  api_url: string
  bundle_identifier?: string | null
  package_name?: string | null
  config?: Record<string, unknown>
}

type Dashboard = {
  totals: {
    tenants: number
    active_tenants: number
    provisioning_jobs: number
    domains_pending: number
    builds: number
    build_artifacts: number
    platform_users: number
  }
  health: Record<string, string>
  recent_tenants?: Tenant[]
}

type Permission = {
  key: string
  description: string
  group_name: string
}

type PlatformRole = {
  id: string
  name: string
  description?: string | null
  is_system: boolean
  permissions: string[]
}

type PlatformUser = {
  id: string
  email: string
  display_name: string
  is_super_admin: boolean
  is_active: boolean
  must_change_password: boolean
  created_at?: string | null
  roles: Array<{ id: string; name: string }>
  tenants: Array<{ id: string; name: string; slug: string }>
  initial_password?: string | null
}

type Capability = {
  key: string
  enabled: boolean
  config: Record<string, unknown>
  updated_at?: string | null
}

type LogEntry = {
  id: string
  tenant_id?: string | null
  tenant_name?: string | null
  tenant_slug?: string | null
  source: string
  service: string
  level: string
  event: string
  message: string
  integration?: string | null
  error_code?: string | null
  correlation_id?: string | null
  request_id?: string | null
  actor?: string | null
  hostname?: string | null
  container_name?: string | null
  details?: Record<string, unknown>
  created_at?: string | null
}

type LogSummary = {
  last_24h: {
    total: number
    errors: number
    docker: number
    integrations: number
    tenant_scoped: number
  }
  by_source?: Array<{ source: string; level: string; total: number }>
  by_service?: Array<{ service: string; total: number; errors: number }>
  tenant_boundaries: Array<{
    tenant_id: string
    tenant_name: string
    slug: string
    database_name: string
    database_user: string
    storage_bucket: string
    storage_prefix: string
    artifact_prefix: string
    isolation_status: string
  }>
}

type AuditEntry = {
  id: string
  user_id?: string | null
  email?: string | null
  action: string
  result: string
  ip_address?: string | null
  correlation_id?: string | null
  metadata: Record<string, unknown>
  created_at: string
}

type DockerContainer = {
  id: string
  container_id: string
  name: string
  service?: string | null
  project?: string | null
  image?: string | null
  state?: string | null
  status?: string | null
}

type DockerLogEntry = {
  timestamp: string
  stream: string
  message: string
}

type FeatureFlag = {
  key: string
  enabled: boolean
  rules: Record<string, unknown>
}

type CreatedTenant = {
  tenant_id: string
  tenant_code: string
  job_id: string
  admin_email: string
  initial_admin_password: string
  hostname: string
  status: string
}

type PwaInstaller = {
  canInstall: boolean
  isInstalled: boolean
  install: () => Promise<unknown>
}

type ModuleKey =
  | 'overview'
  | 'tenants'
  | 'access'
  | 'provisioning'
  | 'domains'
  | 'capabilities'
  | 'builds'
  | 'logs'
  | 'branding'
  | 'integrations'
  | 'audit'
  | 'settings'

type LogTab = 'platform' | 'tenant' | 'integrations' | 'audit' | 'tenant-audit' | 'docker'

type NavItem = {
  key: ModuleKey
  label: string
  icon: string
  description: string
  permissions: string[]
}

const storageKey = 'scheduler-pro-admin-session'

const modules: NavItem[] = [
  { key: 'overview', label: 'Visão geral', icon: '▦', description: 'Indicadores operacionais', permissions: ['platform.dashboard.read'] },
  { key: 'tenants', label: 'Tenants / Clientes', icon: '▤', description: 'Clientes e ciclo de vida', permissions: ['tenants.read'] },
  { key: 'access', label: 'Usuários e acessos', icon: '♙', description: 'Usuários, perfis e escopos', permissions: ['platform.users.manage', 'platform.roles.manage'] },
  { key: 'provisioning', label: 'Provisionamento', icon: '◉', description: 'Banco, storage, DNS e seed', permissions: ['tenants.read'] },
  { key: 'domains', label: 'Domínios e SSL', icon: '◎', description: 'DNS, SSL e cache', permissions: ['domains.read'] },
  { key: 'capabilities', label: 'Recursos do tenant', icon: '◈', description: 'Recursos e integrações liberados', permissions: ['tenant.capabilities.manage'] },
  { key: 'builds', label: 'Builds e distribuições', icon: '⬢', description: 'PWA, desktop e mobile', permissions: ['builds.read'] },
  { key: 'logs', label: 'Logs e observabilidade', icon: '◫', description: 'Plataforma, tenants e console', permissions: ['observability.read'] },
  { key: 'branding', label: 'Marca e aplicativos', icon: '◇', description: 'Perfis de distribuição', permissions: ['builds.read', 'branding.manage'] },
  { key: 'integrations', label: 'Integrações', icon: '⌁', description: 'Cloudflare, Evolution, storage e filas', permissions: ['integrations.read'] },
  { key: 'audit', label: 'Auditoria', icon: '☷', description: 'Ações administrativas', permissions: ['audit.read'] },
  { key: 'settings', label: 'Configurações', icon: '⚙', description: 'Feature flags e parâmetros', permissions: ['settings.manage'] },
]

const capabilityLabels: Record<string, string> = {
  appointments: 'Agenda e agendamentos',
  customers: 'Clientes',
  services: 'Serviços',
  professionals: 'Profissionais',
  landing_pages: 'Landing pages',
  notifications: 'Notificações',
  automations: 'Automações',
  whatsapp: 'WhatsApp',
  evolution: 'Evolution API',
  storage: 'Storage / arquivos',
  custom_domains: 'Domínio próprio',
  dns: 'Provisionamento DNS',
  ssl: 'SSL / ACME',
  cloudflare: 'Cloudflare',
  branding: 'Marca e aplicativos',
  builds: 'Build Manager',
  desktop_apps: 'Aplicativos desktop',
  android_app: 'Aplicativo Android',
  ios_app: 'Aplicativo iOS',
  observability: 'Logs e observabilidade',
  audit: 'Auditoria do tenant',
}

const email = ref('')
const password = ref('')
const session = ref<SessionState | null>(null)
const principal = ref<Principal | null>(null)
const errorMessage = ref('')
const toastMessage = ref('')
const loading = ref(false)
const activeModule = ref<ModuleKey>('overview')
const sidebarOpen = ref(false)
const search = ref('')
const tenantContext = ref('')
const installState = ref({ canInstall: false, isInstalled: false })

const dashboard = ref<Dashboard | null>(null)
const tenants = ref<Tenant[]>([])
const domains = ref<Domain[]>([])
const provisioning = ref<ProvisioningJob[]>([])
const builds = ref<BuildJob[]>([])
const profiles = ref<BuildProfile[]>([])
const integrations = ref<Record<string, unknown>>({})
const flags = ref<FeatureFlag[]>([])
const auditEntries = ref<AuditEntry[]>([])
const createdTenant = ref<CreatedTenant | null>(null)

const permissions = ref<Permission[]>([])
const roles = ref<PlatformRole[]>([])
const platformUsers = ref<PlatformUser[]>([])
const credentialReveal = ref<{ label: string; value: string } | null>(null)
const userForm = ref({
  id: '',
  email: '',
  display_name: '',
  password: '',
  role_ids: [] as string[],
  tenant_ids: [] as string[],
  is_active: true,
})
const roleForm = ref({ id: '', name: '', description: '', permissions: [] as string[] })

const capabilities = ref<Capability[]>([])
const tenantForm = ref({ name: '', slug: '', admin_email: '', admin_password: '' })
const domainForm = ref({ tenant_id: '', hostname: '', make_primary: true })
const buildForm = ref({ tenant: '', target: 'desktop', source_ref: 'main' })
const flagForm = ref({ key: '', enabled: true, rules: '{}' })

const logTab = ref<LogTab>('platform')
const structuredLogs = ref<LogEntry[]>([])
const logSummary = ref<LogSummary | null>(null)
const logAudit = ref<AuditEntry[]>([])
const dockerContainers = ref<DockerContainer[]>([])
const dockerEntries = ref<DockerLogEntry[]>([])
const dockerContainer = ref('')
const dockerTail = ref(500)
const logAutoRefresh = ref(false)
const logFilters = ref({ source: '', service: '', level: '', integration: '', search: '' })
let logTimer: number | undefined

const isAuthenticated = computed(() => Boolean(session.value?.accessToken))
const profileInitial = computed(() => (principal.value?.email || session.value?.userEmail || 'A').charAt(0).toUpperCase())
const selectedTenant = computed(() => tenants.value.find(item => item.id === tenantContext.value) ?? null)
const query = computed(() => search.value.trim().toLowerCase())

function hasPermission(permission: string): boolean {
  return Boolean(principal.value?.is_super_admin || principal.value?.permissions.includes(permission))
}

function hasAnyPermission(values: string[]): boolean {
  return Boolean(principal.value?.is_super_admin || values.some(hasPermission))
}

const visibleModules = computed(() => modules.filter(item => hasAnyPermission(item.permissions)))
const selectedModule = computed(() => modules.find(item => item.key === activeModule.value) ?? modules[0])
const filteredTenants = computed(() => tenants.value.filter(item => {
  if (tenantContext.value && item.id !== tenantContext.value) return false
  const haystack = `${item.name} ${item.slug} ${item.primary_hostname || ''} ${item.status}`.toLowerCase()
  return !query.value || haystack.includes(query.value)
}))
const filteredDomains = computed(() => domains.value.filter(item => {
  if (tenantContext.value && item.tenant_id !== tenantContext.value) return false
  const haystack = `${item.hostname} ${item.tenant_name || ''} ${item.status}`.toLowerCase()
  return !query.value || haystack.includes(query.value)
}))
const filteredProvisioning = computed(() => provisioning.value.filter(item => {
  if (tenantContext.value && item.tenant_id !== tenantContext.value) return false
  return !query.value || `${item.tenant_name} ${item.slug} ${item.status}`.toLowerCase().includes(query.value)
}))
const filteredBuilds = computed(() => builds.value.filter(item => {
  if (tenantContext.value && String(item.tenant || '') !== tenantContext.value) return false
  return !query.value || `${item.target} ${item.status} ${item.source_ref || ''}`.toLowerCase().includes(query.value)
}))
const filteredProfiles = computed(() => profiles.value.filter(item => {
  if (tenantContext.value && String(item.tenant) !== tenantContext.value) return false
  return !query.value || `${item.name} ${item.target} ${item.api_url}`.toLowerCase().includes(query.value)
}))
const groupedPermissions = computed(() => {
  const groups = new Map<string, Permission[]>()
  for (const permission of permissions.value) {
    const rows = groups.get(permission.group_name) ?? []
    rows.push(permission)
    groups.set(permission.group_name, rows)
  }
  return [...groups.entries()]
})

function token(): string {
  return session.value?.accessToken || ''
}

function formatDate(value?: string | null): string {
  return value ? new Date(value).toLocaleString('pt-BR') : '—'
}

function statusClass(value?: string | null): string {
  return String(value || '').toLowerCase().replace(/[^a-z0-9]+/g, '-')
}

function canRetryProvision(job: ProvisioningJob): boolean {
  if (job.status === 'FAILED') return true
  if (!['PENDING', 'PROVISIONING'].includes(job.status) || !job.updated_at) return false
  const updatedAt = new Date(job.updated_at).getTime()
  return Number.isFinite(updatedAt) && Date.now() - updatedAt >= 10 * 60 * 1000
}

function describeError(error: unknown, fallback: string): string {
  const value = error as Partial<ApiError>
  if (value?.message && value?.code) return `${value.message} (${value.code})`
  return value?.message || fallback
}

function showToast(message: string): void {
  toastMessage.value = message
  window.setTimeout(() => {
    if (toastMessage.value === message) toastMessage.value = ''
  }, 4000)
}

function saveSession(value: SessionState): void {
  session.value = value
  localStorage.setItem(storageKey, JSON.stringify(value))
}

function restoreSession(): void {
  const raw = localStorage.getItem(storageKey)
  if (!raw) return
  try {
    session.value = JSON.parse(raw) as SessionState
  } catch {
    localStorage.removeItem(storageKey)
  }
}

function clearSession(): void {
  session.value = null
  principal.value = null
  localStorage.removeItem(storageKey)
}

function handleApiError(error: unknown, fallback: string): void {
  const apiError = error as Partial<ApiError>
  if (apiError.status === 401) {
    clearSession()
    errorMessage.value = 'Sessão expirada. Entre novamente.'
    return
  }
  errorMessage.value = describeError(error, fallback)
}

function ensureActiveModule(): void {
  if (visibleModules.value.some(item => item.key === activeModule.value)) return
  activeModule.value = visibleModules.value[0]?.key ?? 'overview'
}

async function loadPrincipal(): Promise<void> {
  principal.value = await apiGet<Principal>('/platform/access/me', token())
  ensureActiveModule()
}

async function login(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    const payload = await apiPost<LoginResponse>('/auth/platform/login', {
      email: email.value,
      password: password.value,
    })
    saveSession({
      accessToken: payload.access_token,
      refreshToken: payload.refresh_token,
      userEmail: payload.user.email || email.value,
    })
    password.value = ''
    await loadPrincipal()
    await refreshBase()
    await refreshCurrentModule()
  } catch (error) {
    handleApiError(error, 'Não foi possível entrar na plataforma.')
  } finally {
    loading.value = false
  }
}

async function refreshBase(): Promise<void> {
  if (!token() || !principal.value) return
  const failures: string[] = []
  const tasks: Array<Promise<void>> = []

  if (hasPermission('platform.dashboard.read')) {
    tasks.push(apiGet<Dashboard>('/platform/dashboard', token())
      .then(value => { dashboard.value = value })
      .catch(error => { failures.push(`Dashboard: ${describeError(error, 'indisponível')}`) }))
  }
  if (hasPermission('tenants.read')) {
    tasks.push(apiGet<Tenant[]>('/platform/tenants', token())
      .then(value => {
        tenants.value = value
        if (tenantContext.value && !value.some(item => item.id === tenantContext.value)) {
          tenantContext.value = ''
        }
      })
      .catch(error => { failures.push(`Tenants: ${describeError(error, 'indisponível')}`) }))
  }
  if (hasPermission('domains.read')) {
    tasks.push(apiGet<Domain[]>('/platform/domains', token())
      .then(value => { domains.value = value })
      .catch(error => { failures.push(`Domínios: ${describeError(error, 'indisponível')}`) }))
  }
  if (hasPermission('tenants.read')) {
    tasks.push(apiGet<ProvisioningJob[]>('/platform/provisioning', token())
      .then(value => { provisioning.value = value })
      .catch(error => { failures.push(`Provisionamento: ${describeError(error, 'indisponível')}`) }))
  }
  if (hasPermission('builds.read')) {
    tasks.push(apiGet<{ jobs: BuildJob[] }>('/platform/builds/jobs?limit=200', token())
      .then(value => { builds.value = value.jobs || [] })
      .catch(error => { failures.push(`Builds: ${describeError(error, 'indisponível')}`) }))
    tasks.push(apiGet<{ profiles: BuildProfile[] }>('/platform/builds/profiles', token())
      .then(value => { profiles.value = value.profiles || [] })
      .catch(error => { failures.push(`Perfis: ${describeError(error, 'indisponível')}`) }))
  }

  await Promise.all(tasks)
  errorMessage.value = failures.length ? `Alguns dados não puderam ser atualizados. ${failures[0]}` : ''
}

async function refreshCurrentModule(): Promise<void> {
  try {
    if (activeModule.value === 'access') await loadAccess()
    if (activeModule.value === 'capabilities') await loadCapabilities()
    if (activeModule.value === 'logs') await loadLogView()
    if (activeModule.value === 'integrations' && hasPermission('integrations.read')) {
      integrations.value = await apiGet('/platform/integrations/status', token())
    }
    if (activeModule.value === 'audit' && hasPermission('audit.read')) {
      auditEntries.value = await apiGet('/platform/audit?limit=1000', token())
    }
    if (activeModule.value === 'settings' && hasPermission('settings.manage')) {
      flags.value = await apiGet('/platform/feature-flags', token())
    }
  } catch (error) {
    handleApiError(error, `Falha ao carregar ${selectedModule.value.label}.`)
  }
}

async function refreshAll(): Promise<void> {
  if (!token()) return
  loading.value = true
  try {
    if (!principal.value) await loadPrincipal()
    await refreshBase()
    await refreshCurrentModule()
  } finally {
    loading.value = false
  }
}

async function selectModule(key: ModuleKey): Promise<void> {
  activeModule.value = key
  sidebarOpen.value = false
  search.value = ''
  await refreshCurrentModule()
}

async function chooseTenant(): Promise<void> {
  search.value = ''
  if (activeModule.value === 'capabilities') await loadCapabilities()
  if (activeModule.value === 'logs' && ['tenant', 'tenant-audit'].includes(logTab.value)) {
    await loadLogView()
  }
}

async function createTenant(): Promise<void> {
  try {
    createdTenant.value = await apiPost('/platform/tenants', {
      name: tenantForm.value.name,
      slug: tenantForm.value.slug || null,
      admin_email: tenantForm.value.admin_email,
      admin_password: tenantForm.value.admin_password || null,
    }, token())
    tenantForm.value = { name: '', slug: '', admin_email: '', admin_password: '' }
    showToast('Tenant criado e provisionamento iniciado.')
    await refreshBase()
  } catch (error) {
    handleApiError(error, 'Falha ao criar tenant.')
  }
}

async function tenantAction(action: 'suspend' | 'restore', tenant: Tenant): Promise<void> {
  if (!window.confirm(`${action === 'suspend' ? 'Suspender' : 'Restaurar'} ${tenant.name}?`)) return
  try {
    await apiPost(`/platform/tenants/${tenant.id}/${action}`, {}, token())
    showToast(action === 'suspend' ? 'Tenant suspenso.' : 'Tenant restaurado.')
    await refreshBase()
  } catch (error) {
    handleApiError(error, 'Falha ao alterar tenant.')
  }
}

async function deleteTenant(tenant: Tenant): Promise<void> {
  if (!window.confirm(`Excluir logicamente ${tenant.name}? Os recursos serão preservados para recuperação.`)) return
  try {
    await apiDelete(`/platform/tenants/${tenant.id}`, token())
    showToast('Tenant excluído logicamente.')
    await refreshBase()
  } catch (error) {
    handleApiError(error, 'Falha ao excluir tenant.')
  }
}

async function purgeTenant(tenant: Tenant): Promise<void> {
  const confirmation = window.prompt(`EXPURGO IRREVERSÍVEL. Digite exatamente: ${tenant.slug}`)
  if (confirmation !== tenant.slug) return
  try {
    await apiPost(`/platform/tenants/${tenant.id}/purge`, { confirmation, force: false }, token())
    showToast('Tenant expurgado.')
    tenantContext.value = ''
    await refreshBase()
  } catch (error) {
    const apiError = error as Partial<ApiError>
    if (apiError.code === 'TENANT_PURGE_INCOMPLETE' && window.confirm('Existem recursos externos pendentes. Forçar expurgo local mesmo assim?')) {
      try {
        await apiPost(`/platform/tenants/${tenant.id}/purge`, { confirmation, force: true }, token())
        showToast('Expurgo forçado concluído com avisos registrados na auditoria.')
        tenantContext.value = ''
        await refreshBase()
        return
      } catch (forceError) {
        handleApiError(forceError, 'Falha no expurgo forçado.')
        return
      }
    }
    handleApiError(error, 'Falha ao expurgar tenant.')
  }
}

async function retryProvision(jobId: string): Promise<void> {
  try {
    await apiPost(`/platform/provisioning/${jobId}/retry`, {}, token())
    showToast('Provisionamento reenfileirado.')
    await refreshBase()
  } catch (error) {
    handleApiError(error, 'Falha ao reenfileirar provisionamento.')
  }
}

async function temporaryDomain(tenantId: string): Promise<void> {
  try {
    await apiPost(`/platform/tenants/${tenantId}/domains/temporary`, {}, token())
    showToast('DNS temporário verificado.')
    await refreshBase()
  } catch (error) {
    handleApiError(error, 'Falha no DNS temporário.')
  }
}

async function customDomain(): Promise<void> {
  try {
    await apiPost(`/platform/tenants/${domainForm.value.tenant_id}/domains/custom`, {
      hostname: domainForm.value.hostname,
      make_primary: domainForm.value.make_primary,
    }, token())
    domainForm.value.hostname = ''
    showToast('Domínio enviado para validação.')
    await refreshBase()
  } catch (error) {
    handleApiError(error, 'Falha ao conectar domínio.')
  }
}

async function checkDomain(id: string): Promise<void> {
  try {
    await apiPost(`/platform/domains/${id}/check`, {}, token())
    showToast('Verificação concluída.')
    await refreshBase()
  } catch (error) {
    handleApiError(error, 'Falha na verificação.')
  }
}

async function purgeDomain(id: string): Promise<void> {
  try {
    const result = await apiPost<{ purge?: { success?: boolean; error?: unknown } }>(`/platform/domains/${id}/purge-cache`, {}, token())
    if (result.purge?.success === false) {
      errorMessage.value = 'A Cloudflare recusou o purge. Consulte Integrações/Logs para o erro completo.'
    } else {
      showToast('Cache invalidado.')
    }
  } catch (error) {
    handleApiError(error, 'Falha ao invalidar cache.')
  }
}

async function createBuild(): Promise<void> {
  try {
    await apiPost('/platform/builds/requests', {
      tenant: buildForm.value.tenant,
      target: buildForm.value.target,
      source_ref: buildForm.value.source_ref,
      payload: { origin: 'admin-control-plane' },
    }, token())
    showToast('Build solicitado.')
    await refreshBase()
  } catch (error) {
    handleApiError(error, 'Falha ao solicitar build.')
  }
}

async function refreshBuild(id: string): Promise<void> {
  try {
    await apiPost(`/platform/builds/jobs/${id}/refresh`, {}, token())
    showToast('Build sincronizado.')
    await refreshBase()
  } catch (error) {
    handleApiError(error, 'Falha ao sincronizar build.')
  }
}

async function loadAccess(): Promise<void> {
  const tasks: Promise<unknown>[] = []
  if (hasPermission('platform.users.manage')) {
    tasks.push(apiGet<PlatformUser[]>('/platform/access/users', token()).then(value => { platformUsers.value = value }))
  }
  if (hasPermission('platform.roles.manage')) {
    tasks.push(apiGet<PlatformRole[]>('/platform/access/roles', token()).then(value => { roles.value = value }))
    tasks.push(apiGet<Permission[]>('/platform/access/permissions', token()).then(value => { permissions.value = value }))
  }
  await Promise.all(tasks)
}

function resetUserForm(): void {
  userForm.value = {
    id: '', email: '', display_name: '', password: '', role_ids: [], tenant_ids: [], is_active: true,
  }
}

function editUser(user: PlatformUser): void {
  userForm.value = {
    id: user.id,
    email: user.email,
    display_name: user.display_name,
    password: '',
    role_ids: user.roles.map(item => item.id),
    tenant_ids: user.tenants.map(item => item.id),
    is_active: user.is_active,
  }
}

async function saveUser(): Promise<void> {
  try {
    if (userForm.value.id) {
      await apiPut(`/platform/access/users/${userForm.value.id}`, {
        display_name: userForm.value.display_name || null,
        is_active: userForm.value.is_active,
        role_ids: userForm.value.role_ids,
        tenant_ids: userForm.value.tenant_ids,
      }, token())
      showToast('Usuário atualizado.')
    } else {
      const user = await apiPost<PlatformUser>('/platform/access/users', {
        email: userForm.value.email,
        display_name: userForm.value.display_name || null,
        password: userForm.value.password || null,
        role_ids: userForm.value.role_ids,
        tenant_ids: userForm.value.tenant_ids,
      }, token())
      if (user.initial_password) credentialReveal.value = { label: user.email, value: user.initial_password }
      showToast('Usuário administrativo criado.')
    }
    resetUserForm()
    await loadAccess()
  } catch (error) {
    handleApiError(error, 'Falha ao salvar usuário.')
  }
}

async function toggleUser(user: PlatformUser): Promise<void> {
  try {
    await apiPut(`/platform/access/users/${user.id}`, {
      display_name: user.display_name,
      is_active: !user.is_active,
      role_ids: user.roles.map(item => item.id),
      tenant_ids: user.tenants.map(item => item.id),
    }, token())
    await loadAccess()
  } catch (error) {
    handleApiError(error, 'Falha ao alterar usuário.')
  }
}

async function resetUserPassword(user: PlatformUser): Promise<void> {
  if (!window.confirm(`Gerar nova senha para ${user.email}? Todas as sessões serão revogadas.`)) return
  try {
    const result = await apiPost<{ password: string }>(`/platform/access/users/${user.id}/reset-password`, {}, token())
    credentialReveal.value = { label: user.email, value: result.password }
    showToast('Senha redefinida e sessões revogadas.')
  } catch (error) {
    handleApiError(error, 'Falha ao redefinir senha.')
  }
}

async function deleteUser(user: PlatformUser): Promise<void> {
  if (!window.confirm(`Excluir definitivamente o usuário administrativo ${user.email}?`)) return
  try {
    await apiDelete(`/platform/access/users/${user.id}`, token())
    showToast('Usuário excluído.')
    await loadAccess()
  } catch (error) {
    handleApiError(error, 'Falha ao excluir usuário.')
  }
}

function resetRoleForm(): void {
  roleForm.value = { id: '', name: '', description: '', permissions: [] }
}

function editRole(role: PlatformRole): void {
  roleForm.value = {
    id: role.id,
    name: role.name,
    description: role.description || '',
    permissions: [...role.permissions],
  }
}

async function saveRole(): Promise<void> {
  try {
    const payload = {
      name: roleForm.value.name,
      description: roleForm.value.description || null,
      permissions: roleForm.value.permissions,
    }
    if (roleForm.value.id) await apiPut(`/platform/access/roles/${roleForm.value.id}`, payload, token())
    else await apiPost('/platform/access/roles', payload, token())
    showToast('Perfil de acesso salvo.')
    resetRoleForm()
    await loadAccess()
  } catch (error) {
    handleApiError(error, 'Falha ao salvar perfil.')
  }
}

async function deleteRole(role: PlatformRole): Promise<void> {
  if (!window.confirm(`Excluir o perfil ${role.name}?`)) return
  try {
    await apiDelete(`/platform/access/roles/${role.id}`, token())
    showToast('Perfil excluído.')
    await loadAccess()
  } catch (error) {
    handleApiError(error, 'Falha ao excluir perfil.')
  }
}

async function loadCapabilities(): Promise<void> {
  capabilities.value = []
  if (!tenantContext.value || !hasPermission('tenant.capabilities.manage')) return
  capabilities.value = await apiGet(`/platform/access/tenants/${tenantContext.value}/capabilities`, token())
}

async function toggleCapability(capability: Capability): Promise<void> {
  if (!tenantContext.value) return
  try {
    const updated = await apiPut<Capability>(
      `/platform/access/tenants/${tenantContext.value}/capabilities/${encodeURIComponent(capability.key)}`,
      { enabled: !capability.enabled, config: capability.config || {} },
      token(),
    )
    const index = capabilities.value.findIndex(item => item.key === updated.key)
    if (index >= 0) capabilities.value[index] = updated
    showToast(`${capabilityLabels[updated.key] || updated.key}: ${updated.enabled ? 'liberado' : 'bloqueado'}.`)
  } catch (error) {
    handleApiError(error, 'Falha ao alterar recurso do tenant.')
  }
}

function logQuery(extra: Record<string, string> = {}): string {
  const params = new URLSearchParams()
  params.set('limit', '1000')
  for (const [key, value] of Object.entries({ ...logFilters.value, ...extra })) {
    if (value) params.set(key, value)
  }
  return params.toString()
}

async function loadPlatformStructured(extra: Record<string, string> = {}): Promise<void> {
  structuredLogs.value = await apiGet(`/platform/observability/logs?${logQuery(extra)}`, token())
  logSummary.value = await apiGet('/platform/observability/logs/summary', token())
}

async function loadTenantStructured(): Promise<void> {
  structuredLogs.value = []
  if (!tenantContext.value) return
  structuredLogs.value = await apiGet(
    `/platform/observability/tenant/${tenantContext.value}/logs?${logQuery()}`,
    token(),
  )
}

async function loadDockerContainers(): Promise<void> {
  dockerContainers.value = await apiGet('/platform/observability/docker/containers', token())
  if (!dockerContainer.value && dockerContainers.value.length) {
    const apiContainer = dockerContainers.value.find(item => item.service === 'scheduler-api')
    dockerContainer.value = (apiContainer || dockerContainers.value[0]).service || (apiContainer || dockerContainers.value[0]).name
  }
}

async function loadDockerLogs(): Promise<void> {
  dockerEntries.value = []
  if (!dockerContainer.value) return
  const params = new URLSearchParams({
    container: dockerContainer.value,
    tail: String(dockerTail.value),
  })
  if (logFilters.value.search) params.set('search', logFilters.value.search)
  const result = await apiGet<{ entries: DockerLogEntry[] }>(`/platform/observability/docker/logs?${params}`, token())
  dockerEntries.value = result.entries || []
}

async function loadLogView(): Promise<void> {
  if (!hasPermission('observability.read') && !hasPermission('audit.read')) return
  try {
    if (logTab.value === 'platform') await loadPlatformStructured()
    if (logTab.value === 'integrations') await loadPlatformStructured({ source: 'integration' })
    if (logTab.value === 'tenant') await loadTenantStructured()
    if (logTab.value === 'audit') {
      logAudit.value = await apiGet('/platform/audit?limit=1000', token())
    }
    if (logTab.value === 'tenant-audit') {
      logAudit.value = tenantContext.value
        ? await apiGet(`/platform/observability/tenant/${tenantContext.value}/audit?limit=1000`, token())
        : []
    }
    if (logTab.value === 'docker') {
      await loadDockerContainers()
      await loadDockerLogs()
    }
  } catch (error) {
    handleApiError(error, 'Falha ao carregar observabilidade.')
  }
}

async function selectLogTab(tab: LogTab): Promise<void> {
  logTab.value = tab
  structuredLogs.value = []
  logAudit.value = []
  dockerEntries.value = []
  await loadLogView()
}

async function saveFlag(): Promise<void> {
  try {
    let rulesValue: Record<string, unknown>
    try {
      rulesValue = JSON.parse(flagForm.value.rules) as Record<string, unknown>
    } catch {
      throw new Error('As regras devem ser um JSON válido.')
    }
    await apiPut(`/platform/feature-flags/${encodeURIComponent(flagForm.value.key)}`, {
      enabled: flagForm.value.enabled,
      rules: rulesValue,
    }, token())
    flagForm.value = { key: '', enabled: true, rules: '{}' }
    flags.value = await apiGet('/platform/feature-flags', token())
    showToast('Configuração salva.')
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Falha ao salvar configuração.'
  }
}

function updateInstallState(): void {
  const installer = (window as unknown as { schedulerProAdminPwa?: PwaInstaller }).schedulerProAdminPwa
  installState.value = {
    canInstall: Boolean(installer?.canInstall),
    isInstalled: Boolean(installer?.isInstalled),
  }
}

async function installPwa(): Promise<void> {
  const installer = (window as unknown as { schedulerProAdminPwa?: PwaInstaller }).schedulerProAdminPwa
  if (installer?.canInstall) await installer.install()
  updateInstallState()
}

function logout(): void {
  clearSession()
  dashboard.value = null
}

onMounted(async () => {
  restoreSession()
  updateInstallState()
  window.addEventListener('scheduler-pro-admin-install-state', updateInstallState)
  logTimer = window.setInterval(() => {
    if (isAuthenticated.value && activeModule.value === 'logs' && logAutoRefresh.value) {
      void loadLogView()
    }
  }, 5000)
  if (token()) {
    try {
      await loadPrincipal()
      await refreshBase()
      await refreshCurrentModule()
    } catch (error) {
      handleApiError(error, 'Não foi possível restaurar a sessão administrativa.')
    }
  }
})

onUnmounted(() => {
  window.removeEventListener('scheduler-pro-admin-install-state', updateInstallState)
  if (logTimer !== undefined) window.clearInterval(logTimer)
})
</script>

<template>
  <main class="admin-root enterprise-admin">
    <section v-if="!isAuthenticated" class="auth-page">
      <aside class="auth-visual">
        <div class="auth-brand auth-brand-centered">
          <div class="brand-mark">SP</div>
          <div><strong>Scheduler Pro</strong><span>Control Plane</span></div>
        </div>
      </aside>
      <form class="auth-card" @submit.prevent="login">
        <div class="mobile-brand">
          <div class="brand-mark">SP</div>
          <div><strong>Scheduler Pro</strong><span>Control Plane</span></div>
        </div>
        <h2>Entrar na plataforma</h2>
        <p>Utilize suas credenciais administrativas.</p>
        <label>E-mail</label>
        <input v-model="email" type="email" autocomplete="username" required />
        <label>Senha</label>
        <input v-model="password" type="password" autocomplete="current-password" required />
        <p v-if="errorMessage" class="form-error">{{ errorMessage }}</p>
        <button class="btn primary full" :disabled="loading">{{ loading ? 'Validando...' : 'Entrar' }}</button>
      </form>
    </section>

    <div v-else class="admin-shell" :class="{ mobileOpen: sidebarOpen }">
      <aside class="sidebar">
        <div class="brand">
          <div class="brand-mark">SP</div>
          <div><strong>Scheduler Pro</strong><small>Control Plane</small></div>
        </div>
        <nav class="nav-list">
          <button
            v-for="item in visibleModules"
            :key="item.key"
            class="nav-item"
            :class="{ active: activeModule === item.key }"
            @click="selectModule(item.key)"
          >
            <span class="nav-icon">{{ item.icon }}</span><span>{{ item.label }}</span>
          </button>
        </nav>
        <div class="sidebar-footer">
          <button class="nav-item" @click="logout"><span class="nav-icon">⇥</span><span>Sair</span></button>
          <div class="sidebar-identity">
            <strong>{{ principal?.email || session?.userEmail }}</strong>
            <small>{{ principal?.roles.join(', ') || 'Administrador da plataforma' }}</small>
          </div>
        </div>
      </aside>
      <div v-if="sidebarOpen" class="mobile-backdrop" @click="sidebarOpen = false"></div>

      <section class="content-shell">
        <header class="topbar">
          <button class="icon-button" @click="sidebarOpen = !sidebarOpen">☰</button>
          <div v-if="hasPermission('tenants.read')" class="company-switcher">
            <span>Tenant</span>
            <select v-model="tenantContext" @change="chooseTenant">
              <option value="">Todos os clientes</option>
              <option v-for="tenant in tenants" :key="tenant.id" :value="tenant.id">{{ tenant.name }}</option>
            </select>
          </div>
          <div class="topbar-search"><span>⌕</span><input v-model="search" placeholder="Buscar tenant, domínio, build ou evento" /></div>
          <div class="topbar-spacer"></div>
          <button v-if="installState.canInstall && !installState.isInstalled" class="btn" @click="installPwa">Instalar</button>
          <button class="icon-button" title="Atualizar" @click="refreshAll">↻</button>
          <div class="profile">
            <div><strong>{{ principal?.email }}</strong><small>{{ principal?.roles.join(', ') || 'platform_admin' }}</small></div>
            <div class="avatar">{{ profileInitial }}</div>
          </div>
        </header>

        <main class="main-content">
          <section class="page-header">
            <div>
              <p class="eyebrow">{{ selectedTenant ? 'Tenant selecionado' : 'Plataforma' }}</p>
              <h1>{{ selectedModule.label }}</h1>
              <p>{{ selectedModule.description }}</p>
            </div>
            <div v-if="selectedTenant" class="tenant-context-card">
              <strong>{{ selectedTenant.name }}</strong><small>{{ selectedTenant.primary_hostname || selectedTenant.slug }}</small>
            </div>
          </section>

          <p v-if="toastMessage" class="toast-message">{{ toastMessage }}</p>
          <p v-if="errorMessage" class="form-error wide">{{ errorMessage }}</p>

          <section v-if="hasPermission('platform.dashboard.read')" class="metric-grid">
            <article class="metric-card"><div><span>Tenants / Clientes</span><strong>{{ selectedTenant ? 1 : (dashboard?.totals.tenants ?? tenants.length) }}</strong><small>{{ dashboard?.totals.active_tenants ?? 0 }} ativos</small></div><b>▤</b></article>
            <article class="metric-card violet"><div><span>Provisionamentos</span><strong>{{ selectedTenant ? filteredProvisioning.length : (dashboard?.totals.provisioning_jobs ?? provisioning.length) }}</strong><small>jobs registrados</small></div><b>◉</b></article>
            <article class="metric-card green"><div><span>Domínios pendentes</span><strong>{{ selectedTenant ? filteredDomains.filter(item => item.status !== 'ACTIVE').length : (dashboard?.totals.domains_pending ?? 0) }}</strong><small>DNS / SSL</small></div><b>◎</b></article>
            <article class="metric-card orange"><div><span>Artefatos</span><strong>{{ selectedTenant ? filteredBuilds.reduce((sum, item) => sum + (item.artifacts?.length || 0), 0) : (dashboard?.totals.build_artifacts ?? 0) }}</strong><small>{{ selectedTenant ? filteredBuilds.length : (dashboard?.totals.builds ?? builds.length) }} builds</small></div><b>⬢</b></article>
          </section>

          <section v-if="activeModule === 'overview'" class="dashboard-grid">
            <article class="panel">
              <div class="panel-title"><div><h3>Tenants recentes</h3><p>Ambientes sob administração</p></div></div>
              <div class="list">
                <div v-for="tenant in tenants.slice(0, 10)" :key="tenant.id" class="row">
                  <span class="time">{{ tenant.slug.slice(0, 3).toUpperCase() }}</span>
                  <div><strong>{{ tenant.name }}</strong><small>{{ tenant.primary_hostname || tenant.slug }}</small></div>
                  <span class="status-pill" :class="statusClass(tenant.status)">{{ tenant.status }}</span>
                </div>
                <div v-if="!tenants.length" class="empty-state">Nenhum tenant disponível para este perfil.</div>
              </div>
            </article>
            <article class="panel">
              <div class="panel-title"><div><h3>Saúde da plataforma</h3><p>Dependências essenciais</p></div></div>
              <div class="health-list">
                <div v-for="(value, key) in dashboard?.health || {}" :key="key"><span><i class="ok"></i>{{ key }}</span><strong>{{ value }}</strong></div>
              </div>
            </article>
          </section>

          <section v-else-if="activeModule === 'tenants'" class="view-stack">
            <article v-if="hasPermission('tenants.create')" class="panel form-panel">
              <div><h2>Novo tenant / cliente</h2><p>Crie o cliente e inicie o provisionamento isolado.</p></div>
              <form class="inline-form" @submit.prevent="createTenant">
                <input v-model="tenantForm.name" placeholder="Nome da empresa" required />
                <input v-model="tenantForm.slug" placeholder="Código opcional" />
                <input v-model="tenantForm.admin_email" type="email" placeholder="E-mail do administrador" required />
                <input v-model="tenantForm.admin_password" type="password" minlength="12" placeholder="Senha opcional" />
                <button class="btn primary">Criar e provisionar</button>
              </form>
              <div v-if="createdTenant" class="credential-card">
                <strong>Credencial inicial do tenant</strong><span>{{ createdTenant.admin_email }}</span><code>{{ createdTenant.initial_admin_password }}</code><small>Copie agora e entregue ao cliente.</small>
              </div>
            </article>
            <article class="panel table-panel">
              <div class="panel-title"><div><h3>Tenants / Clientes</h3><p>{{ filteredTenants.length }} registro(s)</p></div></div>
              <div class="responsive-table"><table><thead><tr><th>Cliente</th><th>Domínio principal</th><th>Código</th><th>Status</th><th>Ações</th></tr></thead><tbody>
                <tr v-for="tenant in filteredTenants" :key="tenant.id">
                  <td><strong>{{ tenant.name }}</strong><small>{{ tenant.branding_name || tenant.name }}</small></td>
                  <td>{{ tenant.primary_hostname || '—' }}</td><td>{{ tenant.slug }}</td>
                  <td><span class="status-pill" :class="statusClass(tenant.status)">{{ tenant.status }}</span></td>
                  <td class="actions-cell">
                    <button class="btn small" @click="tenantContext = tenant.id">Selecionar</button>
                    <button v-if="hasPermission('domains.manage')" class="btn small" @click="temporaryDomain(tenant.id)">DNS</button>
                    <button v-if="hasPermission('tenants.update') && tenant.status !== 'SUSPENDED'" class="btn small" @click="tenantAction('suspend', tenant)">Suspender</button>
                    <button v-if="hasPermission('tenants.update') && ['SUSPENDED','DELETED'].includes(tenant.status)" class="btn small" @click="tenantAction('restore', tenant)">Restaurar</button>
                    <button v-if="hasPermission('tenants.delete') && tenant.status !== 'DELETED'" class="btn small danger-outline" @click="deleteTenant(tenant)">Excluir</button>
                    <button v-if="hasPermission('tenants.purge')" class="btn small danger" @click="purgeTenant(tenant)">Expurgar</button>
                  </td>
                </tr>
              </tbody></table></div>
            </article>
          </section>

          <section v-else-if="activeModule === 'access'" class="view-stack">
            <div class="access-grid">
              <article v-if="hasPermission('platform.users.manage')" class="panel card access-editor">
                <div class="panel-title"><div><h3>{{ userForm.id ? 'Editar usuário' : 'Novo usuário administrativo' }}</h3><p>Perfil e escopo de tenants definem a área de atuação.</p></div></div>
                <form class="stack-form" @submit.prevent="saveUser">
                  <input v-model="userForm.email" type="email" placeholder="E-mail" :disabled="Boolean(userForm.id)" required />
                  <input v-model="userForm.display_name" placeholder="Nome de exibição" />
                  <input v-if="!userForm.id" v-model="userForm.password" type="password" minlength="12" placeholder="Senha opcional — gera automática" />
                  <label class="form-label">Perfis</label>
                  <select v-model="userForm.role_ids" multiple size="5"><option v-for="role in roles" :key="role.id" :value="role.id">{{ role.name }}</option></select>
                  <label class="form-label">Tenants permitidos</label>
                  <select v-model="userForm.tenant_ids" multiple size="6"><option v-for="tenant in tenants" :key="tenant.id" :value="tenant.id">{{ tenant.name }} — {{ tenant.slug }}</option></select>
                  <label v-if="userForm.id" class="checkbox-line"><input v-model="userForm.is_active" type="checkbox" /> Usuário ativo</label>
                  <div class="actions-cell"><button class="btn primary">{{ userForm.id ? 'Salvar alterações' : 'Criar usuário' }}</button><button v-if="userForm.id" type="button" class="btn" @click="resetUserForm">Cancelar</button></div>
                </form>
                <div v-if="credentialReveal" class="credential-card"><strong>Senha gerada — {{ credentialReveal.label }}</strong><code>{{ credentialReveal.value }}</code><small>Exibida somente nesta sessão administrativa.</small></div>
              </article>

              <article v-if="hasPermission('platform.roles.manage')" class="panel card access-editor">
                <div class="panel-title"><div><h3>{{ roleForm.id ? 'Editar perfil' : 'Novo perfil de acesso' }}</h3><p>Permissões granulares do Control Plane.</p></div></div>
                <form class="stack-form" @submit.prevent="saveRole">
                  <input v-model="roleForm.name" placeholder="Nome do perfil" required />
                  <textarea v-model="roleForm.description" rows="2" placeholder="Descrição"></textarea>
                  <div class="permission-groups">
                    <fieldset v-for="[group, rows] in groupedPermissions" :key="group" class="permission-group">
                      <legend>{{ group }}</legend>
                      <label v-for="permission in rows" :key="permission.key" class="permission-check"><input v-model="roleForm.permissions" type="checkbox" :value="permission.key" /><span><strong>{{ permission.key }}</strong><small>{{ permission.description }}</small></span></label>
                    </fieldset>
                  </div>
                  <div class="actions-cell"><button class="btn primary">Salvar perfil</button><button v-if="roleForm.id" type="button" class="btn" @click="resetRoleForm">Cancelar</button></div>
                </form>
              </article>
            </div>

            <article v-if="hasPermission('platform.users.manage')" class="panel table-panel">
              <div class="panel-title"><div><h3>Usuários administrativos</h3><p>{{ platformUsers.length }} conta(s)</p></div></div>
              <div class="responsive-table"><table><thead><tr><th>Usuário</th><th>Perfis</th><th>Tenants</th><th>Status</th><th>Ações</th></tr></thead><tbody>
                <tr v-for="user in platformUsers" :key="user.id">
                  <td><strong>{{ user.display_name || user.email }}</strong><small>{{ user.email }}{{ user.is_super_admin ? ' • superadmin' : '' }}</small></td>
                  <td><span class="tag" v-for="role in user.roles" :key="role.id">{{ role.name }}</span><span v-if="!user.roles.length && !user.is_super_admin">—</span></td>
                  <td><span class="tag" v-for="tenant in user.tenants.slice(0, 4)" :key="tenant.id">{{ tenant.name }}</span><small v-if="user.tenants.length > 4">+{{ user.tenants.length - 4 }}</small></td>
                  <td><span class="status-pill" :class="user.is_active ? 'active' : 'failed'">{{ user.is_active ? 'ATIVO' : 'BLOQUEADO' }}</span></td>
                  <td class="actions-cell"><button class="btn small" @click="editUser(user)">Editar</button><button v-if="!user.is_super_admin" class="btn small" @click="toggleUser(user)">{{ user.is_active ? 'Bloquear' : 'Ativar' }}</button><button class="btn small" @click="resetUserPassword(user)">Nova senha</button><button v-if="!user.is_super_admin" class="btn small danger-outline" @click="deleteUser(user)">Excluir</button></td>
                </tr>
              </tbody></table></div>
            </article>

            <article v-if="hasPermission('platform.roles.manage')" class="panel table-panel">
              <div class="panel-title"><div><h3>Perfis de acesso</h3><p>Conjuntos reutilizáveis de permissões</p></div></div>
              <div class="responsive-table"><table><thead><tr><th>Perfil</th><th>Permissões</th><th>Tipo</th><th>Ações</th></tr></thead><tbody>
                <tr v-for="role in roles" :key="role.id"><td><strong>{{ role.name }}</strong><small>{{ role.description || '—' }}</small></td><td>{{ role.permissions.length }} permissões</td><td>{{ role.is_system ? 'Sistema' : 'Personalizado' }}</td><td class="actions-cell"><button class="btn small" @click="editRole(role)">Editar</button><button v-if="!role.is_system" class="btn small danger-outline" @click="deleteRole(role)">Excluir</button></td></tr>
              </tbody></table></div>
            </article>
          </section>

          <section v-else-if="activeModule === 'provisioning'" class="view-stack">
            <article v-for="job in filteredProvisioning" :key="job.id" class="panel provisioning-card">
              <div class="panel-title"><div><h3>{{ job.tenant_name }}</h3><p>{{ job.slug }} • {{ formatDate(job.created_at) }} • {{ job.correlation_id }}</p></div><div class="actions-cell"><span class="status-pill" :class="statusClass(job.status)">{{ job.status }}</span><button v-if="hasPermission('tenants.provision') && canRetryProvision(job)" class="btn small" @click="retryProvision(job.id)">{{ job.status === 'FAILED' ? 'Tentar novamente' : 'Reprocessar' }}</button></div></div>
              <div class="step-grid"><article v-for="step in job.steps" :key="step.id" class="step" :class="statusClass(step.status)"><strong>{{ step.name }}</strong><span>{{ step.status }}</span><small v-if="step.error">{{ step.error }}</small></article></div>
            </article>
            <div v-if="!filteredProvisioning.length" class="empty-state">Nenhum job de provisionamento neste escopo.</div>
          </section>

          <section v-else-if="activeModule === 'domains'" class="view-stack">
            <article v-if="hasPermission('domains.manage')" class="panel form-panel">
              <div><h2>Domínio próprio</h2><p>Associe domínio, valide SSL e mantenha o DNS auditável.</p></div>
              <form class="inline-form" @submit.prevent="customDomain"><select v-model="domainForm.tenant_id" required><option value="">Selecione o tenant</option><option v-for="tenant in tenants" :key="tenant.id" :value="tenant.id">{{ tenant.name }}</option></select><input v-model="domainForm.hostname" placeholder="agenda.cliente.com.br" required /><label class="checkbox-line"><input v-model="domainForm.make_primary" type="checkbox" /> Tornar primário</label><button class="btn primary">Conectar</button></form>
            </article>
            <article class="panel table-panel"><div class="panel-title"><div><h3>Domínios registrados</h3><p>DNS, validação e cache</p></div></div><div class="responsive-table"><table><thead><tr><th>Hostname</th><th>Tenant</th><th>Tipo</th><th>Status</th><th>Ações</th></tr></thead><tbody><tr v-for="domain in filteredDomains" :key="domain.id"><td><strong>{{ domain.hostname }}</strong><small>{{ domain.is_primary ? 'Primário' : '' }}</small></td><td>{{ domain.tenant_name }}</td><td>{{ domain.is_temporary ? 'Temporário' : 'Personalizado' }}</td><td><span class="status-pill" :class="statusClass(domain.status)">{{ domain.status }}</span></td><td class="actions-cell"><button v-if="hasPermission('domains.manage')" class="btn small" @click="checkDomain(domain.id)">Verificar</button><button v-if="hasPermission('cache.purge')" class="btn small" @click="purgeDomain(domain.id)">Purge cache</button></td></tr></tbody></table></div></article>
          </section>

          <section v-else-if="activeModule === 'capabilities'" class="view-stack">
            <article v-if="!selectedTenant" class="empty-state">Selecione um tenant no topo para administrar os recursos disponíveis.</article>
            <article v-else class="panel capability-panel"><div class="panel-title"><div><h3>Recursos liberados — {{ selectedTenant.name }}</h3><p>Bloquear um recurso impede o uso da respectiva API pelo tenant.</p></div></div><div class="capability-grid"><button v-for="capability in capabilities" :key="capability.key" class="capability-card" :class="{ enabled: capability.enabled }" @click="toggleCapability(capability)"><div><strong>{{ capabilityLabels[capability.key] || capability.key }}</strong><small>{{ capability.key }}</small></div><span>{{ capability.enabled ? 'LIBERADO' : 'BLOQUEADO' }}</span></button></div></article>
          </section>

          <section v-else-if="activeModule === 'builds'" class="view-stack">
            <article v-if="hasPermission('builds.manage')" class="panel form-panel"><div><h2>Solicitar distribuição</h2><p>Dispare builds rastreáveis pelo GitHub Actions.</p></div><form class="inline-form" @submit.prevent="createBuild"><select v-model="buildForm.tenant" required><option value="">Tenant</option><option v-for="tenant in tenants" :key="tenant.id" :value="tenant.id">{{ tenant.name }}</option></select><select v-model="buildForm.target"><option value="web">Web</option><option value="pwa">PWA</option><option value="desktop">Desktop cliente</option><option value="android">Android cliente</option><option value="ios">iOS cliente</option><option value="admin-desktop">Desktop admin</option><option value="admin-android">Android admin</option><option value="admin-ios">iOS admin</option></select><input v-model="buildForm.source_ref" placeholder="main" /><button class="btn primary">Disparar build</button></form></article>
            <article class="panel table-panel"><div class="panel-title"><div><h3>Jobs de build</h3><p>{{ filteredBuilds.length }} job(s)</p></div></div><div class="responsive-table"><table><thead><tr><th>Alvo</th><th>Tenant</th><th>Status</th><th>Run</th><th>Artefatos</th><th>Ação</th></tr></thead><tbody><tr v-for="build in filteredBuilds" :key="build.id"><td><strong>{{ build.target }}</strong><small>{{ formatDate(build.created_at) }}</small></td><td>{{ tenants.find(item => item.id === build.tenant)?.name || build.tenant }}</td><td><span class="status-pill" :class="statusClass(build.status)">{{ build.status }}</span></td><td>{{ build.workflow_run_id || '—' }}</td><td>{{ build.artifacts?.length || 0 }}</td><td><button v-if="hasPermission('builds.manage')" class="btn small" @click="refreshBuild(build.id)">Sincronizar</button></td></tr></tbody></table></div></article>
          </section>

          <section v-else-if="activeModule === 'logs'" class="view-stack">
            <article class="panel observability-toolbar">
              <div class="tabs">
                <button :class="{ active: logTab === 'platform' }" @click="selectLogTab('platform')">Plataforma</button>
                <button :class="{ active: logTab === 'tenant' }" @click="selectLogTab('tenant')">Tenant</button>
                <button :class="{ active: logTab === 'integrations' }" @click="selectLogTab('integrations')">Integrações</button>
                <button v-if="hasPermission('audit.read')" :class="{ active: logTab === 'audit' }" @click="selectLogTab('audit')">Auditoria admin</button>
                <button v-if="hasPermission('audit.read')" :class="{ active: logTab === 'tenant-audit' }" @click="selectLogTab('tenant-audit')">Auditoria tenant</button>
                <button :class="{ active: logTab === 'docker' }" @click="selectLogTab('docker')">Docker / Console</button>
              </div>
              <div class="log-filter-grid" v-if="!['audit','tenant-audit'].includes(logTab)">
                <input v-model="logFilters.search" placeholder="Buscar mensagem, evento, erro..." @keyup.enter="loadLogView" />
                <select v-if="logTab !== 'docker'" v-model="logFilters.level"><option value="">Todos os níveis</option><option>INFO</option><option>WARNING</option><option>ERROR</option><option>CRITICAL</option></select>
                <input v-if="!['docker','integrations'].includes(logTab)" v-model="logFilters.service" placeholder="Serviço" />
                <input v-if="logTab === 'integrations'" v-model="logFilters.integration" placeholder="cloudflare, evolution..." />
                <select v-if="logTab === 'docker'" v-model="dockerContainer" @change="loadDockerLogs"><option v-for="container in dockerContainers" :key="container.container_id" :value="container.service || container.name">{{ container.service || container.name }} — {{ container.status }}</option></select>
                <select v-if="logTab === 'docker'" v-model.number="dockerTail" @change="loadDockerLogs"><option :value="100">100 linhas</option><option :value="500">500 linhas</option><option :value="1000">1.000 linhas</option><option :value="5000">5.000 linhas</option></select>
                <button class="btn primary" @click="loadLogView">Consultar</button>
                <label class="checkbox-line"><input v-model="logAutoRefresh" type="checkbox" /> Atualizar a cada 5s</label>
              </div>
            </article>

            <section v-if="logTab === 'docker'" class="panel console-panel">
              <div class="panel-title"><div><h3>Console Docker</h3><p>stdout/stderr do projeto Scheduler Pro. Somente leitura.</p></div><span class="status-pill active">{{ dockerEntries.length }} linhas</span></div>
              <div class="docker-console"><div v-for="(entry, index) in dockerEntries" :key="`${entry.timestamp}-${index}`" class="console-line" :class="entry.stream"><time>{{ entry.timestamp || '—' }}</time><span>{{ entry.stream }}</span><pre>{{ entry.message }}</pre></div><div v-if="!dockerEntries.length" class="console-empty">Nenhuma linha para o filtro atual.</div></div>
            </section>

            <section v-else-if="['audit','tenant-audit'].includes(logTab)" class="panel table-panel">
              <div class="panel-title"><div><h3>{{ logTab === 'audit' ? 'Auditoria administrativa' : 'Auditoria do tenant' }}</h3><p>Ator, ação, resultado, IP e correlação.</p></div></div>
              <div class="responsive-table"><table><thead><tr><th>Data</th><th>Usuário</th><th>Ação</th><th>Resultado</th><th>Correlação</th><th>Detalhes</th></tr></thead><tbody><tr v-for="entry in logAudit" :key="entry.id"><td>{{ formatDate(entry.created_at) }}</td><td>{{ entry.email || entry.user_id || 'sistema' }}</td><td>{{ entry.action }}</td><td><span class="status-pill" :class="statusClass(entry.result)">{{ entry.result }}</span></td><td>{{ entry.correlation_id || '—' }}</td><td><details><summary>JSON</summary><pre class="json-details">{{ JSON.stringify(entry.metadata, null, 2) }}</pre></details></td></tr></tbody></table></div>
            </section>

            <section v-else class="panel table-panel">
              <div class="panel-title"><div><h3>Eventos registrados</h3><p>{{ structuredLogs.length }} evento(s) • request_id, correlation_id, ator e tenant preservados</p></div></div>
              <div class="responsive-table"><table class="logs-table"><thead><tr><th>Data</th><th>Nível</th><th>Origem / serviço</th><th>Tenant</th><th>Evento</th><th>Mensagem</th><th>Correlação</th></tr></thead><tbody><tr v-for="log in structuredLogs" :key="log.id"><td>{{ formatDate(log.created_at) }}</td><td><span class="status-pill" :class="statusClass(log.level)">{{ log.level }}</span></td><td><strong>{{ log.source }}</strong><small>{{ log.service }}{{ log.integration ? ` • ${log.integration}` : '' }}</small></td><td>{{ log.tenant_name || log.tenant_slug || 'plataforma' }}</td><td>{{ log.event }}<small v-if="log.error_code">{{ log.error_code }}</small></td><td><details><summary>{{ log.message }}</summary><pre class="json-details">{{ JSON.stringify({ request_id: log.request_id, correlation_id: log.correlation_id, actor: log.actor, hostname: log.hostname, container: log.container_name, details: log.details }, null, 2) }}</pre></details></td><td>{{ log.correlation_id || '—' }}</td></tr></tbody></table></div>
            </section>

            <article v-if="logSummary" class="panel table-panel"><div class="panel-title"><div><h3>Isolamento por tenant</h3><p>Banco, storage e artefatos individualizados</p></div></div><div class="responsive-table"><table><thead><tr><th>Tenant</th><th>Banco</th><th>Storage</th><th>Artefatos</th><th>Status</th></tr></thead><tbody><tr v-for="boundary in logSummary.tenant_boundaries" :key="boundary.tenant_id"><td>{{ boundary.tenant_name }}</td><td><strong>{{ boundary.database_name }}</strong><small>{{ boundary.database_user }}</small></td><td><strong>{{ boundary.storage_bucket }}</strong><small>{{ boundary.storage_prefix }}</small></td><td>{{ boundary.artifact_prefix }}</td><td><span class="status-pill" :class="statusClass(boundary.isolation_status)">{{ boundary.isolation_status }}</span></td></tr></tbody></table></div></article>
          </section>

          <section v-else-if="activeModule === 'branding'" class="panel table-panel"><div class="panel-title"><div><h3>Perfis de distribuição</h3><p>Desktop reflete Web; mobile permanece dedicado.</p></div></div><div class="responsive-table"><table><thead><tr><th>Tenant</th><th>Alvo</th><th>Nome</th><th>Endpoint</th></tr></thead><tbody><tr v-for="profile in filteredProfiles" :key="profile.id"><td>{{ tenants.find(item => item.id === profile.tenant)?.name || profile.tenant }}</td><td>{{ profile.target }}</td><td>{{ profile.name }}</td><td>{{ profile.api_url }}</td></tr></tbody></table></div></section>

          <section v-else-if="activeModule === 'integrations'" class="integration-cards"><article v-for="(value, key) in integrations" :key="key" class="panel integration-card"><div class="panel-title"><div><h3>{{ key }}</h3><p>Status operacional</p></div></div><div class="integration-body"><div v-if="typeof value === 'object' && value" class="kv-list"><div v-for="(fieldValue, field) in value as Record<string, unknown>" :key="field"><span>{{ field }}</span><strong :class="{ ok: field === 'ok' && fieldValue === true, bad: (field === 'ok' && fieldValue === false) || field === 'error' }">{{ typeof fieldValue === 'object' ? JSON.stringify(fieldValue) : fieldValue }}</strong></div></div><pre v-else class="json-details">{{ JSON.stringify(value, null, 2) }}</pre></div></article></section>

          <section v-else-if="activeModule === 'audit'" class="panel table-panel"><div class="panel-title"><div><h3>Auditoria da plataforma</h3><p>Ações sensíveis e autenticação</p></div></div><div class="responsive-table"><table><thead><tr><th>Data</th><th>Usuário</th><th>Ação</th><th>Resultado</th><th>IP</th><th>Detalhes</th></tr></thead><tbody><tr v-for="entry in auditEntries" :key="entry.id"><td>{{ formatDate(entry.created_at) }}</td><td>{{ entry.email || entry.user_id || 'sistema' }}</td><td>{{ entry.action }}</td><td><span class="status-pill" :class="statusClass(entry.result)">{{ entry.result }}</span></td><td>{{ entry.ip_address || '—' }}</td><td><details><summary>Ver</summary><pre class="json-details">{{ JSON.stringify(entry.metadata, null, 2) }}</pre></details></td></tr></tbody></table></div></section>

          <section v-else-if="activeModule === 'settings'" class="view-stack"><article class="panel form-panel"><div><h2>Feature flag global</h2><p>Configuração de rollout da plataforma.</p></div><form class="inline-form" @submit.prevent="saveFlag"><input v-model="flagForm.key" placeholder="chave" required /><label class="checkbox-line"><input v-model="flagForm.enabled" type="checkbox" /> Habilitada</label><input v-model="flagForm.rules" placeholder="{}" /><button class="btn primary">Salvar</button></form></article><article class="panel table-panel"><div class="panel-title"><div><h3>Flags cadastradas</h3></div></div><div class="responsive-table"><table><thead><tr><th>Chave</th><th>Status</th><th>Regras</th></tr></thead><tbody><tr v-for="flag in flags" :key="flag.key"><td>{{ flag.key }}</td><td><span class="status-pill" :class="flag.enabled ? 'active' : 'failed'">{{ flag.enabled ? 'ON' : 'OFF' }}</span></td><td><code>{{ JSON.stringify(flag.rules) }}</code></td></tr></tbody></table></div></article></section>
        </main>
      </section>
    </div>
  </main>
</template>
