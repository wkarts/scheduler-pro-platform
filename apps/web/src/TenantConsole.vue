<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import {
  Bell,
  CalendarClock,
  CalendarDays,
  Check,
  CheckCircle2,
  ChevronRight,
  CircleAlert,
  Copy,
  Download,
  ExternalLink,
  Globe2,
  LayoutDashboard,
  Link2,
  LogOut,
  Menu,
  MessageCircle,
  MonitorSmartphone,
  PackageCheck,
  Palette,
  Pencil,
  Plus,
  RefreshCw,
  Search,
  Settings,
  Smartphone,
  Trash2,
  UserRoundCheck,
  Users,
  Wrench,
  X,
} from 'lucide-vue-next'
import { applyBranding, loadBrandingManifest, type BrandingManifest } from './branding'
import {
  disableWebPush,
  enableWebPush,
  pushSubscriptionEnabled,
  startRealtimeStream,
  type RealtimeConnectionState,
  type TenantRealtimeEvent,
} from './tenantRealtime'

type ViewKey =
  | 'dashboard'
  | 'agenda'
  | 'clientes'
  | 'servicos'
  | 'profissionais'
  | 'landing'
  | 'whatsapp'
  | 'branding'
  | 'dominios'
  | 'builds'
  | 'configuracoes'

type InstallPromptEvent = Event & {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed'; platform: string }>
}

type ApiEnvelope<T> = { data: T }
type ApiFailure = { error?: { message?: string; code?: string; details?: unknown } }

type Appointment = {
  id: string
  customer_id: string
  service_id: string
  professional_id: string
  starts_at: string
  ends_at: string
  status: string
  customer_name: string
  customer_phone?: string | null
  service_name: string
  duration_minutes?: number
  price?: number | null
  professional_name: string
}

type Customer = { id: string; name: string; phone?: string | null; email?: string | null; notes?: string | null; created_at?: string | null }
type Service = { id: string; name: string; duration_minutes: number; price?: number | null; active: boolean }
type Professional = { id: string; name: string; email?: string | null; phone?: string | null }
type NotificationJob = { id: string; template_key: string; recipient: string; scheduled_at: string; status: string; error?: string | null }
type TenantSettings = { tenant_id: string; slug: string; hostname: string; timezone: string; preferences: Record<string, unknown> }
type TenantCapabilities = { tenant_id: string; enabled: string[]; capabilities: Array<{ key: string; enabled: boolean; config: Record<string, unknown> }> }
type BusinessHour = { id: string; professional_id?: string | null; professional_name?: string | null; day_of_week: number; opens_at: string; closes_at: string; is_open: boolean }
type BlockedPeriod = { id: string; professional_id?: string | null; professional_name?: string | null; starts_at: string; ends_at: string; reason?: string | null }
type WhatsAppQr = { base64?: string | null; pairing_code?: string | null; code?: string | null; count?: number | null }
type WhatsAppState = { instance_name?: string; status?: string; qr?: WhatsAppQr | null; provider?: Record<string, unknown>; [key: string]: unknown }
type LandingState = { slug: string; status: string; version_number?: number | null; content?: { version?: number; sections?: Array<Record<string, unknown>> }; versions?: Array<{ id: string; version_number: number; created_at: string }> }
type DistributionArtifact = { id: string; build_job_id: string; target: string; artifact_type: string; name: string; download_url?: string | null; checksum_sha256?: string | null; size_bytes?: number; created_at?: string }
type DistributionJob = { id: string; target: string; status: string; workflow_run_id?: string | null; source_ref?: string | null; error?: string | null; created_at?: string }
type DistributionState = { tenant_id?: string; hostname?: string; profiles?: Array<Record<string, unknown>>; jobs?: DistributionJob[]; artifacts?: DistributionArtifact[] }
type LoginResponse = { access_token: string; refresh_token: string; user?: { email?: string; display_name?: string; permissions?: string[] } }
type ConfirmationLinkResponse = { enabled: boolean; request?: { url?: string; confirmation_deadline?: string } | null }

type NavItem = { key: ViewKey; label: string; icon: unknown; capability?: string }

const navItems: NavItem[] = [
  { key: 'dashboard', label: 'Visão geral', icon: LayoutDashboard },
  { key: 'agenda', label: 'Agenda', icon: CalendarDays, capability: 'appointments' },
  { key: 'clientes', label: 'Clientes', icon: Users, capability: 'customers' },
  { key: 'servicos', label: 'Serviços', icon: Wrench, capability: 'services' },
  { key: 'profissionais', label: 'Profissionais', icon: UserRoundCheck, capability: 'professionals' },
  { key: 'landing', label: 'Landing page', icon: Globe2, capability: 'landing_pages' },
  { key: 'whatsapp', label: 'WhatsApp API', icon: MessageCircle, capability: 'whatsapp' },
  { key: 'branding', label: 'Marca e aplicativo', icon: Palette, capability: 'branding' },
  { key: 'dominios', label: 'Domínio e distribuição', icon: Link2, capability: 'custom_domains' },
  { key: 'builds', label: 'Aplicativos', icon: PackageCheck, capability: 'builds' },
  { key: 'configuracoes', label: 'Configurações', icon: Settings },
]

const statusLabels: Record<string, string> = {
  DRAFT: 'Rascunho',
  PENDING: 'Pendente',
  AWAITING_CONFIRMATION: 'Aguardando confirmação',
  CONFIRMED: 'Confirmado',
  CHECKED_IN: 'Check-in',
  IN_PROGRESS: 'Em atendimento',
  COMPLETED: 'Concluído',
  CANCELLED: 'Cancelado',
  RESCHEDULED: 'Reagendado',
  NO_SHOW: 'Não compareceu',
}

const terminalStatuses = new Set(['COMPLETED', 'CANCELLED', 'NO_SHOW'])
const dayLabels = ['Domingo', 'Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado']

const view = ref<ViewKey>(hashToView())
const collapsed = ref(false)
const mobileOpen = ref(false)
const manifest = ref<BrandingManifest | null>(null)
const apiStatus = ref<'connected' | 'degraded' | 'fallback'>('fallback')
const installPrompt = ref<InstallPromptEvent | null>(null)
const installing = ref(false)
const email = ref(localStorage.getItem('scheduler_pro_email') || '')
const displayName = ref(localStorage.getItem('scheduler_pro_display_name') || '')
const password = ref('')
const token = ref(localStorage.getItem('scheduler_pro_access_token') || '')
const authError = ref('')
const actionError = ref('')
const toast = ref('')
const loading = ref(false)
const searchTerm = ref('')
const syncWarnings = ref<string[]>([])
const capabilities = ref<TenantCapabilities | null>(null)

const realtimeState = ref<RealtimeConnectionState>('idle')
const realtimeLastSequence = ref(Number(localStorage.getItem('scheduler_pro_realtime_sequence') || 0) || 0)
const pushEnabled = ref(false)
const pushBusy = ref(false)
let stopRealtime: (() => void) | undefined

const appointments = ref<Appointment[]>([])
const customers = ref<Customer[]>([])
const services = ref<Service[]>([])
const professionals = ref<Professional[]>([])
const notifications = ref<NotificationJob[]>([])
const tenantSettings = ref<TenantSettings | null>(null)
const businessHours = ref<BusinessHour[]>([])
const blockedPeriods = ref<BlockedPeriod[]>([])
const whatsapp = ref<WhatsAppState>({ status: 'DISCONNECTED' })
const landingState = ref<LandingState | null>(null)
const distribution = ref<DistributionState>({ profiles: [], jobs: [], artifacts: [] })

const agendaDay = ref(todayKey())
const agendaStatus = ref('')
const showEditor = ref(false)
const editorKind = ref<'appointment' | 'customer' | 'service' | 'professional' | 'reschedule' | 'business-hour' | 'blocked-period' | ''>('')
const editingId = ref('')

const appointmentForm = ref({
  customer_name: '',
  customer_phone: '',
  customer_email: '',
  service_name: 'Atendimento',
  duration_minutes: 30,
  price: null as number | null,
  professional_name: 'Agenda geral',
  starts_at: '',
})
const rescheduleForm = ref({ appointment_id: '', starts_at: '', professional_id: '' })
const customerForm = ref({ name: '', phone: '', email: '', notes: '' })
const serviceForm = ref({ name: '', duration_minutes: 30, price: null as number | null, active: true })
const professionalForm = ref({ name: '', email: '', phone: '' })
const businessHourForm = ref({ professional_id: '', day_of_week: 1, opens_at: '08:00', closes_at: '18:00', is_open: true })
const blockedPeriodForm = ref({ professional_id: '', starts_at: '', ends_at: '', reason: '' })
const messageForm = ref({ to: '', message: '' })
const landingForm = ref({ title: 'Agende seu atendimento', subtitle: 'Escolha o melhor horário para você.', cta: 'Agendar agora' })
const brandingForm = ref({ public_name: '', slogan: '', logo_url: '', icon_url: '', primary_color: '#2563eb', secondary_color: '#0f172a', accent_color: '#06b6d4', background_color: '#f8fafc', text_color: '#0f172a', theme_mode: 'system' })
const settingForm = ref({ key: '', value: '' })
const bookingPrefs = ref({ booking_buffer_minutes: 0, minimum_notice_minutes: 60, max_advance_days: 90, cancellation_window_hours: 12, default_country_code: '55' })
const confirmationPrefs = ref({
  confirmation_required: true,
  confirmation_deadline_minutes: 60,
  confirmation_link_ttl_hours: 168,
  tenant_notification_whatsapp: '',
  confirmation_page_title: 'Confirme seu atendimento',
  confirmation_page_message: 'Revise os dados abaixo e confirme ou cancele seu horário.',
  confirmation_confirm_label: 'Confirmar agendamento',
  confirmation_cancel_label: 'Cancelar agendamento',
})

const logged = computed(() => Boolean(token.value))
const enabledCapabilities = computed(() => new Set(capabilities.value?.enabled || []))
const visibleNavItems = computed(() => navItems.filter((item) => !item.capability || enabledCapabilities.value.has(item.capability)))
const activeTitle = computed(() => navItems.find((item) => item.key === view.value)?.label || 'Visão geral')
const appName = computed(() => manifest.value?.app?.public_name || manifest.value?.app?.name || 'Scheduler Pro')
const slogan = computed(() => manifest.value?.app?.slogan || 'Plataforma inteligente de agendamentos')
const browserHostname = window.location.hostname
const isStandalone = computed(() => window.matchMedia('(display-mode: standalone)').matches || Boolean((window.navigator as Navigator & { standalone?: boolean }).standalone))
const normalizedSearch = computed(() => searchTerm.value.trim().toLocaleLowerCase('pt-BR'))
const whatsappStatus = computed(() => String(whatsapp.value.status || 'DISCONNECTED').toUpperCase())
const whatsappQr = computed(() => whatsapp.value.qr?.base64 || '')
const whatsappPairingCode = computed(() => whatsapp.value.qr?.pairing_code || '')
const filteredCustomers = computed(() => customers.value.filter((item) => matchSearch(`${item.name} ${item.phone || ''} ${item.email || ''}`)))
const filteredServices = computed(() => services.value.filter((item) => matchSearch(`${item.name} ${item.duration_minutes} ${item.price ?? ''}`)))
const filteredProfessionals = computed(() => professionals.value.filter((item) => matchSearch(`${item.name} ${item.email || ''} ${item.phone || ''}`)))
const filteredAppointments = computed(() => appointments.value.filter((item) => {
  if (agendaDay.value && localDayKey(item.starts_at) !== agendaDay.value) return false
  if (agendaStatus.value && item.status !== agendaStatus.value) return false
  return matchSearch(`${item.customer_name} ${item.service_name} ${item.professional_name} ${item.status}`)
}))
const todayAppointments = computed(() => appointments.value.filter((item) => localDayKey(item.starts_at) === todayKey()))
const confirmedToday = computed(() => todayAppointments.value.filter((item) => item.status === 'CONFIRMED').length)
const pendingToday = computed(() => todayAppointments.value.filter((item) => ['PENDING', 'AWAITING_CONFIRMATION', 'RESCHEDULED'].includes(item.status)).length)
const upcomingAppointments = computed(() => [...appointments.value]
  .filter((item) => new Date(item.starts_at).getTime() >= Date.now() && !terminalStatuses.has(item.status))
  .sort((a, b) => new Date(a.starts_at).getTime() - new Date(b.starts_at).getTime())
  .slice(0, 8))
const pendingNotifications = computed(() => notifications.value.filter((item) => ['PENDING', 'QUEUED', 'SCHEDULED'].includes(String(item.status).toUpperCase())).length)
const latestArtifacts = computed(() => distribution.value.artifacts || [])
const latestJobs = computed(() => distribution.value.jobs || [])
const realtimeLabel = computed(() => realtimeState.value === 'connected' ? 'Tempo real conectado' : realtimeState.value === 'connecting' ? 'Conectando tempo real' : 'Tempo real reconectando')

function hasCapability(key: string): boolean { return enabledCapabilities.value.has(key) }
function todayKey(): string { const now = new Date(); const offset = now.getTimezoneOffset() * 60_000; return new Date(now.getTime() - offset).toISOString().slice(0, 10) }
function localDayKey(value: string): string { const date = new Date(value); const offset = date.getTimezoneOffset() * 60_000; return new Date(date.getTime() - offset).toISOString().slice(0, 10) }
function hashToView(): ViewKey { const current = (window.location.hash || '#dashboard').replace('#', ''); return navItems.some((item) => item.key === current) ? current as ViewKey : 'dashboard' }
function matchSearch(value: string): boolean { return !normalizedSearch.value || value.toLocaleLowerCase('pt-BR').includes(normalizedSearch.value) }
function statusClass(value?: string | null): string { return String(value || '').toLowerCase().replace(/[^a-z0-9]+/g, '-') }
function appointmentStatusLabel(value: string): string { return statusLabels[value] || value }
function formatDateTime(value?: string | null): string { return value ? new Date(value).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' }) : '—' }
function formatTime(value?: string | null): string { return value ? new Date(value).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }) : '—' }
function formatMoney(value?: number | null): string { return value == null ? 'Não informado' : new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value) }
function formatBytes(value?: number | null): string { if (!value) return '—'; const units = ['B', 'KB', 'MB', 'GB']; let size = value; let unit = 0; while (size >= 1024 && unit < units.length - 1) { size /= 1024; unit += 1 } return `${size.toFixed(unit ? 1 : 0)} ${units[unit]}` }
function apiBase(): string { return `${window.location.origin}/api/v1` }

function showToast(message: string): void {
  toast.value = message
  window.setTimeout(() => { if (toast.value === message) toast.value = '' }, 4000)
}

function go(key: ViewKey): void {
  const item = navItems.find((candidate) => candidate.key === key)
  if (item?.capability && !hasCapability(item.capability)) {
    showToast('Este recurso ainda não foi liberado pelo administrador da plataforma.')
    return
  }
  view.value = key
  mobileOpen.value = false
  closeEditor()
  actionError.value = ''
  searchTerm.value = ''
  if (window.location.hash !== `#${key}`) history.replaceState(null, '', `#${key}`)
  if (key === 'whatsapp') void loadWhatsAppStatus()
  if (key === 'landing') void loadLanding()
  if (key === 'builds') void loadDistribution()
}

function onHashChange(): void {
  const candidate = hashToView()
  const item = navItems.find((entry) => entry.key === candidate)
  view.value = item?.capability && !hasCapability(item.capability) ? 'dashboard' : candidate
}
function onBeforeInstallPrompt(event: Event): void { event.preventDefault(); installPrompt.value = event as InstallPromptEvent }

async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${apiBase()}${path}`, {
      ...init,
      headers: {
        Accept: 'application/json',
        ...(init.body instanceof FormData ? {} : { 'content-type': 'application/json' }),
        ...(token.value ? { authorization: `Bearer ${token.value}` } : {}),
        ...(init.headers || {}),
      },
    })
  } catch {
    throw new Error('Não foi possível conectar à API.')
  }
  const body = await response.json().catch(() => ({})) as Partial<ApiEnvelope<T>> & ApiFailure
  if (response.status === 401 && token.value) logout(false)
  if (!response.ok) {
    const code = body.error?.code ? ` (${body.error.code})` : ''
    throw new Error(`${body.error?.message || `Falha HTTP ${response.status}`}${code}`)
  }
  return body.data as T
}

async function installWebApp(): Promise<void> {
  if (!installPrompt.value) return
  installing.value = true
  try { await installPrompt.value.prompt(); await installPrompt.value.userChoice; installPrompt.value = null } finally { installing.value = false }
}

async function loadBranding(): Promise<void> {
  try {
    const data = await loadBrandingManifest()
    manifest.value = data
    applyBranding(data)
    brandingForm.value = {
      public_name: data.app.public_name,
      slogan: data.app.slogan || '',
      logo_url: data.assets.logo_url || '',
      icon_url: data.assets.icon_url || '',
      primary_color: data.theme.colors.primary,
      secondary_color: data.theme.colors.secondary,
      accent_color: data.theme.colors.accent,
      background_color: data.theme.colors.background,
      text_color: data.theme.colors.text,
      theme_mode: data.theme.mode,
    }
  } catch { /* fallback local */ }
}

async function login(): Promise<void> {
  authError.value = ''
  loading.value = true
  try {
    const data = await api<LoginResponse>('/auth/login', { method: 'POST', body: JSON.stringify({ email: email.value, password: password.value }) })
    token.value = data.access_token
    localStorage.setItem('scheduler_pro_access_token', data.access_token)
    localStorage.setItem('scheduler_pro_refresh_token', data.refresh_token)
    localStorage.setItem('scheduler_pro_email', data.user?.email || email.value)
    displayName.value = data.user?.display_name || ''
    localStorage.setItem('scheduler_pro_display_name', displayName.value)
    password.value = ''
    await syncAll()
    go('dashboard')
  } catch (error) { authError.value = error instanceof Error ? error.message : 'Login inválido.' } finally { loading.value = false }
}

function stopRealtimeConnection(): void { stopRealtime?.(); stopRealtime = undefined; realtimeState.value = 'idle' }
function logout(reload = true): void {
  stopRealtimeConnection()
  token.value = ''
  localStorage.removeItem('scheduler_pro_access_token')
  localStorage.removeItem('scheduler_pro_refresh_token')
  if (reload) window.location.hash = '#dashboard'
}

async function handleRealtimeEvent(event: TenantRealtimeEvent): Promise<void> {
  if (event.event_type.startsWith('appointment.') && hasCapability('appointments')) {
    appointments.value = await api<Appointment[]>('/appointments').catch(() => appointments.value)
  }
  if (hasCapability('notifications')) {
    notifications.value = await api<NotificationJob[]>('/notifications?limit=100').catch(() => notifications.value)
  }
  showToast(event.message || 'Agenda atualizada em tempo real.')
}

function startTenantRealtime(): void {
  stopRealtimeConnection()
  if (!token.value || !hasCapability('appointments')) return
  stopRealtime = startRealtimeStream({
    apiBase: apiBase(),
    token: token.value,
    after: realtimeLastSequence.value,
    onState: (state) => { realtimeState.value = state },
    onSequence: (sequence) => {
      realtimeLastSequence.value = sequence
      localStorage.setItem('scheduler_pro_realtime_sequence', String(sequence))
    },
    onEvent: handleRealtimeEvent,
  })
}

async function refreshPushState(): Promise<void> {
  pushEnabled.value = hasCapability('notifications') ? await pushSubscriptionEnabled().catch(() => false) : false
}

async function enablePushNotifications(): Promise<void> {
  if (!hasCapability('notifications')) {
    showToast('Notificações não foram liberadas para este tenant.')
    return
  }
  pushBusy.value = true
  actionError.value = ''
  try {
    await enableWebPush(apiBase(), token.value, displayName.value || email.value)
    pushEnabled.value = true
    showToast('Notificações push ativadas neste dispositivo.')
  } catch (error) { actionError.value = error instanceof Error ? error.message : 'Falha ao ativar notificações push.' } finally { pushBusy.value = false }
}

async function disablePushNotifications(): Promise<void> {
  pushBusy.value = true
  try {
    await disableWebPush(apiBase(), token.value)
    pushEnabled.value = false
    showToast('Notificações push desativadas neste dispositivo.')
  } finally { pushBusy.value = false }
}

async function syncAll(): Promise<void> {
  if (!token.value) return
  loading.value = true
  actionError.value = ''
  const warnings: string[] = []
  const load = async (label: string, task: () => Promise<void>) => {
    try { await task() } catch (error) { warnings.push(`${label}: ${error instanceof Error ? error.message : 'indisponível'}`) }
  }

  await load('Configurações', async () => {
    tenantSettings.value = await api<TenantSettings>('/settings/tenant')
    hydratePreferences()
  })
  await load('Recursos liberados', async () => { capabilities.value = await api<TenantCapabilities>('/settings/capabilities') })

  const tasks: Promise<void>[] = []
  if (hasCapability('appointments')) {
    tasks.push(load('Agenda', async () => { appointments.value = await api<Appointment[]>('/appointments') }))
    tasks.push(load('Expediente', async () => { businessHours.value = await api<BusinessHour[]>('/schedule/business-hours') }))
    tasks.push(load('Bloqueios', async () => { blockedPeriods.value = await api<BlockedPeriod[]>('/schedule/blocked-periods') }))
  }
  if (hasCapability('customers')) tasks.push(load('Clientes', async () => { customers.value = await api<Customer[]>('/customers') }))
  if (hasCapability('services')) tasks.push(load('Serviços', async () => { services.value = await api<Service[]>('/services') }))
  if (hasCapability('professionals')) tasks.push(load('Profissionais', async () => { professionals.value = await api<Professional[]>('/professionals') }))
  if (hasCapability('notifications')) tasks.push(load('Notificações', async () => { notifications.value = await api<NotificationJob[]>('/notifications?limit=100') }))
  if (hasCapability('whatsapp')) tasks.push(load('WhatsApp', loadWhatsAppStatus))
  if (hasCapability('landing_pages')) tasks.push(load('Landing', loadLanding))
  if (hasCapability('builds')) tasks.push(load('Distribuições', loadDistribution))
  await Promise.all(tasks)

  const current = navItems.find((item) => item.key === view.value)
  if (current?.capability && !hasCapability(current.capability)) go('dashboard')
  syncWarnings.value = warnings
  apiStatus.value = warnings.length === 0 ? 'connected' : warnings.length < 3 ? 'degraded' : 'fallback'
  if (warnings.length) actionError.value = `Algumas funções não responderam. ${warnings[0]}`
  loading.value = false
  startTenantRealtime()
  await refreshPushState()
}

function hydratePreferences(): void {
  const prefs = tenantSettings.value?.preferences || {}
  const numberValue = (key: string, fallback: number) => { const value = Number(prefs[key]); return Number.isFinite(value) ? value : fallback }
  const boolValue = (key: string, fallback: boolean) => {
    const value = prefs[key]
    if (typeof value === 'boolean') return value
    if (typeof value === 'string') return !['false', '0', 'off', 'no', 'nao', 'não'].includes(value.toLowerCase())
    return value == null ? fallback : Boolean(value)
  }
  bookingPrefs.value = {
    booking_buffer_minutes: numberValue('booking_buffer_minutes', 0),
    minimum_notice_minutes: numberValue('minimum_notice_minutes', 60),
    max_advance_days: numberValue('max_advance_days', 90),
    cancellation_window_hours: numberValue('cancellation_window_hours', 12),
    default_country_code: String(prefs.default_country_code || '55'),
  }
  confirmationPrefs.value = {
    confirmation_required: boolValue('confirmation_required', true),
    confirmation_deadline_minutes: numberValue('confirmation_deadline_minutes', 60),
    confirmation_link_ttl_hours: numberValue('confirmation_link_ttl_hours', 168),
    tenant_notification_whatsapp: String(prefs.tenant_notification_whatsapp || ''),
    confirmation_page_title: String(prefs.confirmation_page_title || 'Confirme seu atendimento'),
    confirmation_page_message: String(prefs.confirmation_page_message || 'Revise os dados abaixo e confirme ou cancele seu horário.'),
    confirmation_confirm_label: String(prefs.confirmation_confirm_label || 'Confirmar agendamento'),
    confirmation_cancel_label: String(prefs.confirmation_cancel_label || 'Cancelar agendamento'),
  }
}

function closeEditor(): void { showEditor.value = false; editorKind.value = ''; editingId.value = '' }
function openNew(): void {
  actionError.value = ''
  editingId.value = ''
  if (view.value === 'agenda') {
    editorKind.value = 'appointment'
    appointmentForm.value = { customer_name: '', customer_phone: '', customer_email: '', service_name: 'Atendimento', duration_minutes: 30, price: null, professional_name: 'Agenda geral', starts_at: '' }
  } else if (view.value === 'clientes') { editorKind.value = 'customer'; customerForm.value = { name: '', phone: '', email: '', notes: '' } }
  else if (view.value === 'servicos') { editorKind.value = 'service'; serviceForm.value = { name: '', duration_minutes: 30, price: null, active: true } }
  else if (view.value === 'profissionais') { editorKind.value = 'professional'; professionalForm.value = { name: '', email: '', phone: '' } }
  else return
  showEditor.value = true
}

async function saveAppointment(): Promise<void> {
  const startsAt = new Date(appointmentForm.value.starts_at)
  if (!appointmentForm.value.customer_name.trim() || Number.isNaN(startsAt.getTime())) {
    actionError.value = 'Informe o nome do cliente e um horário válido.'
    return
  }
  try {
    await api('/appointments/quick', {
      method: 'POST',
      body: JSON.stringify({
        starts_at: startsAt.toISOString(),
        customer_name: appointmentForm.value.customer_name.trim(),
        customer_phone: appointmentForm.value.customer_phone.trim() || null,
        customer_email: appointmentForm.value.customer_email.trim() || null,
        service_name: appointmentForm.value.service_name.trim() || 'Atendimento',
        duration_minutes: Number(appointmentForm.value.duration_minutes) || 30,
        price: appointmentForm.value.price,
        professional_name: appointmentForm.value.professional_name.trim() || 'Agenda geral',
        source: 'tenant-web-quick',
      }),
    })
    appointments.value = await api('/appointments')
    closeEditor()
    showToast('Agendamento criado. Se houver WhatsApp/notificações liberados, a confirmação será enviada automaticamente.')
  } catch (error) { actionError.value = error instanceof Error ? error.message : 'Falha ao criar agendamento.' }
}

async function appointmentAction(item: Appointment, action: string): Promise<void> {
  try { await api(`/appointments/${item.id}/${action}`, { method: 'POST', body: '{}' }); appointments.value = await api('/appointments'); showToast('Agendamento atualizado e cliente notificado conforme as regras do tenant.') }
  catch (error) { actionError.value = error instanceof Error ? error.message : 'Falha ao atualizar agendamento.' }
}

async function copyConfirmationLink(item: Appointment): Promise<void> {
  try {
    const data = await api<ConfirmationLinkResponse>(`/appointment-confirmations/${item.id}`)
    const url = data.request?.url
    if (!data.enabled || !url) throw new Error('Confirmação por link está desativada para este tenant.')
    await copyText(url)
    showToast('Link de confirmação copiado.')
  } catch (error) { actionError.value = error instanceof Error ? error.message : 'Falha ao gerar link de confirmação.' }
}

async function cancelAppointment(item: Appointment): Promise<void> {
  if (!window.confirm(`Cancelar o atendimento de ${item.customer_name}?`)) return
  try {
    await api(`/appointments/${item.id}/cancel`, { method: 'POST', body: JSON.stringify({ reason: 'Cancelado pelo painel do tenant' }) })
    appointments.value = await api('/appointments')
    showToast('Agendamento cancelado. O cliente será notificado se o canal estiver liberado.')
  } catch (error) { actionError.value = error instanceof Error ? error.message : 'Falha ao cancelar.' }
}

function openReschedule(item: Appointment): void {
  editorKind.value = 'reschedule'; editingId.value = item.id
  const local = new Date(item.starts_at); local.setMinutes(local.getMinutes() - local.getTimezoneOffset())
  rescheduleForm.value = { appointment_id: item.id, starts_at: local.toISOString().slice(0, 16), professional_id: item.professional_id }
  showEditor.value = true
}

async function saveReschedule(): Promise<void> {
  const item = appointments.value.find((row) => row.id === rescheduleForm.value.appointment_id)
  const startsAt = new Date(rescheduleForm.value.starts_at)
  if (!item || Number.isNaN(startsAt.getTime())) return
  const duration = Number(item.duration_minutes) || Math.max(5, Math.round((new Date(item.ends_at).getTime() - new Date(item.starts_at).getTime()) / 60_000))
  const endsAt = new Date(startsAt.getTime() + duration * 60_000)
  try {
    await api(`/appointments/${item.id}/reschedule`, { method: 'POST', body: JSON.stringify({ starts_at: startsAt.toISOString(), ends_at: endsAt.toISOString(), professional_id: rescheduleForm.value.professional_id || item.professional_id, reason: 'Reagendado pelo painel do tenant' }) })
    appointments.value = await api('/appointments')
    closeEditor()
    showToast('Reagendado. O cliente recebe o novo horário e deve confirmar novamente.')
  } catch (error) { actionError.value = error instanceof Error ? error.message : 'Falha ao reagendar.' }
}

function editCustomer(item: Customer): void { editorKind.value = 'customer'; editingId.value = item.id; customerForm.value = { name: item.name, phone: item.phone || '', email: item.email || '', notes: item.notes || '' }; showEditor.value = true }
async function saveCustomer(): Promise<void> { try { await api(editingId.value ? `/customers/${editingId.value}` : '/customers', { method: editingId.value ? 'PATCH' : 'POST', body: JSON.stringify({ ...customerForm.value, phone: customerForm.value.phone || null, email: customerForm.value.email || null, notes: customerForm.value.notes || null }) }); customers.value = await api('/customers'); closeEditor(); showToast(editingId.value ? 'Cliente atualizado.' : 'Cliente cadastrado.') } catch (error) { actionError.value = error instanceof Error ? error.message : 'Falha ao salvar cliente.' } }
async function deleteCustomer(item: Customer): Promise<void> { if (!window.confirm(`Excluir o cliente ${item.name}?`)) return; try { await api(`/customers/${item.id}`, { method: 'DELETE' }); customers.value = await api('/customers'); showToast('Cliente excluído.') } catch (error) { actionError.value = error instanceof Error ? error.message : 'Falha ao excluir cliente.' } }
function editService(item: Service): void { editorKind.value = 'service'; editingId.value = item.id; serviceForm.value = { ...item, price: item.price ?? null }; showEditor.value = true }
async function saveService(): Promise<void> { try { await api(editingId.value ? `/services/${editingId.value}` : '/services', { method: editingId.value ? 'PATCH' : 'POST', body: JSON.stringify(serviceForm.value) }); services.value = await api('/services'); closeEditor(); showToast(editingId.value ? 'Serviço atualizado.' : 'Serviço cadastrado.') } catch (error) { actionError.value = error instanceof Error ? error.message : 'Falha ao salvar serviço.' } }
async function toggleService(item: Service): Promise<void> { try { await api(`/services/${item.id}`, { method: 'PATCH', body: JSON.stringify({ active: !item.active }) }); services.value = await api('/services') } catch (error) { actionError.value = error instanceof Error ? error.message : 'Falha ao alterar serviço.' } }
async function deleteService(item: Service): Promise<void> { if (!window.confirm(`Excluir o serviço ${item.name}?`)) return; try { await api(`/services/${item.id}`, { method: 'DELETE' }); services.value = await api('/services') } catch (error) { actionError.value = error instanceof Error ? error.message : 'Falha ao excluir serviço.' } }
function editProfessional(item: Professional): void { editorKind.value = 'professional'; editingId.value = item.id; professionalForm.value = { name: item.name, email: item.email || '', phone: item.phone || '' }; showEditor.value = true }
async function saveProfessional(): Promise<void> { try { await api(editingId.value ? `/professionals/${editingId.value}` : '/professionals', { method: editingId.value ? 'PATCH' : 'POST', body: JSON.stringify({ ...professionalForm.value, email: professionalForm.value.email || null, phone: professionalForm.value.phone || null }) }); professionals.value = await api('/professionals'); closeEditor(); showToast(editingId.value ? 'Profissional atualizado.' : 'Profissional cadastrado.') } catch (error) { actionError.value = error instanceof Error ? error.message : 'Falha ao salvar profissional.' } }
async function deleteProfessional(item: Professional): Promise<void> { if (!window.confirm(`Excluir o profissional ${item.name}?`)) return; try { await api(`/professionals/${item.id}`, { method: 'DELETE' }); professionals.value = await api('/professionals') } catch (error) { actionError.value = error instanceof Error ? error.message : 'Falha ao excluir profissional.' } }

function openBusinessHour(item?: BusinessHour): void { editorKind.value = 'business-hour'; editingId.value = item?.id || ''; businessHourForm.value = item ? { professional_id: item.professional_id || '', day_of_week: item.day_of_week, opens_at: String(item.opens_at).slice(0, 5), closes_at: String(item.closes_at).slice(0, 5), is_open: item.is_open } : { professional_id: '', day_of_week: 1, opens_at: '08:00', closes_at: '18:00', is_open: true }; showEditor.value = true }
async function saveBusinessHour(): Promise<void> { try { await api(editingId.value ? `/schedule/business-hours/${editingId.value}` : '/schedule/business-hours', { method: editingId.value ? 'PUT' : 'POST', body: JSON.stringify({ ...businessHourForm.value, professional_id: businessHourForm.value.professional_id || null }) }); businessHours.value = await api('/schedule/business-hours'); closeEditor(); showToast('Expediente salvo.') } catch (error) { actionError.value = error instanceof Error ? error.message : 'Falha ao salvar expediente.' } }
async function deleteBusinessHour(item: BusinessHour): Promise<void> { if (!window.confirm('Excluir esta faixa de expediente?')) return; try { await api(`/schedule/business-hours/${item.id}`, { method: 'DELETE' }); businessHours.value = await api('/schedule/business-hours') } catch (error) { actionError.value = error instanceof Error ? error.message : 'Falha ao excluir expediente.' } }
function openBlockedPeriod(): void { editorKind.value = 'blocked-period'; editingId.value = ''; blockedPeriodForm.value = { professional_id: '', starts_at: '', ends_at: '', reason: '' }; showEditor.value = true }
async function saveBlockedPeriod(): Promise<void> { try { await api('/schedule/blocked-periods', { method: 'POST', body: JSON.stringify({ professional_id: blockedPeriodForm.value.professional_id || null, starts_at: new Date(blockedPeriodForm.value.starts_at).toISOString(), ends_at: new Date(blockedPeriodForm.value.ends_at).toISOString(), reason: blockedPeriodForm.value.reason || null }) }); blockedPeriods.value = await api('/schedule/blocked-periods'); closeEditor(); showToast('Bloqueio cadastrado.') } catch (error) { actionError.value = error instanceof Error ? error.message : 'Falha ao criar bloqueio.' } }
async function deleteBlockedPeriod(item: BlockedPeriod): Promise<void> { if (!window.confirm('Remover este bloqueio?')) return; try { await api(`/schedule/blocked-periods/${item.id}`, { method: 'DELETE' }); blockedPeriods.value = await api('/schedule/blocked-periods') } catch (error) { actionError.value = error instanceof Error ? error.message : 'Falha ao remover bloqueio.' } }

async function loadLanding(): Promise<void> { if (!token.value || !hasCapability('landing_pages')) return; const state = await api<LandingState>('/landing-pages/home'); landingState.value = state; const sections = Array.isArray(state.content?.sections) ? state.content?.sections || [] : []; const hero = sections.find((item) => item.type === 'hero') || {}; landingForm.value = { title: String(hero.title || 'Agende seu atendimento'), subtitle: String(hero.subtitle || 'Escolha o melhor horário para você.'), cta: String(hero.cta || 'Agendar agora') } }
async function saveLanding(publish = false): Promise<void> { try { const version = Number(landingState.value?.version_number || landingState.value?.content?.version || 0) + 1; await api('/landing-pages/home/draft', { method: 'POST', body: JSON.stringify({ version, sections: [{ type: 'hero', title: landingForm.value.title, subtitle: landingForm.value.subtitle, cta: landingForm.value.cta }, { type: 'booking', enabled: true }] }) }); if (publish) await api('/landing-pages/home/publish', { method: 'POST', body: '{}' }); await loadLanding(); showToast(publish ? 'Landing publicada.' : 'Rascunho salvo.') } catch (error) { actionError.value = error instanceof Error ? error.message : 'Falha na landing.' } }

async function loadWhatsAppStatus(): Promise<void> { if (!token.value || !hasCapability('whatsapp')) return; whatsapp.value = await api<WhatsAppState>('/integrations/whatsapp/status') }
async function connectWhatsApp(): Promise<void> { whatsapp.value = { ...whatsapp.value, status: 'CONNECTING' }; try { whatsapp.value = await api<WhatsAppState>('/integrations/whatsapp/connect', { method: 'POST', body: '{}' }); showToast(whatsappQr.value ? 'QR Code gerado.' : 'Conexão iniciada.'); if (!whatsappQr.value) { window.setTimeout(() => void loadWhatsAppStatus(), 1800); window.setTimeout(() => void loadWhatsAppStatus(), 4200) } } catch (error) { actionError.value = error instanceof Error ? error.message : 'Falha no WhatsApp.' } }
async function sendMessage(): Promise<void> { if (whatsappStatus.value !== 'CONNECTED') { actionError.value = 'Conecte o WhatsApp antes de enviar.'; return } try { await api('/integrations/whatsapp/send-text', { method: 'POST', body: JSON.stringify(messageForm.value) }); messageForm.value.message = ''; showToast('Mensagem enviada.') } catch (error) { actionError.value = error instanceof Error ? error.message : 'Falha no envio.' } }

async function saveBranding(publish = false): Promise<void> { try { await api('/branding/profile', { method: 'PUT', body: JSON.stringify(brandingForm.value) }); if (publish) await api('/branding/publish', { method: 'POST', body: '{}' }); await loadBranding(); showToast(publish ? 'Marca publicada.' : 'Marca salva.') } catch (error) { actionError.value = error instanceof Error ? error.message : 'Falha ao salvar marca.' } }
async function loadDistribution(): Promise<void> { if (!token.value || !hasCapability('builds')) return; distribution.value = await api<DistributionState>('/branding/distribution') }

async function saveObjectSettings(values: Record<string, unknown>, message: string): Promise<void> {
  try {
    for (const [key, value] of Object.entries(values)) await api(`/settings/tenant/${encodeURIComponent(key)}`, { method: 'PUT', body: JSON.stringify(value) })
    tenantSettings.value = await api('/settings/tenant')
    hydratePreferences()
    showToast(message)
  } catch (error) { actionError.value = error instanceof Error ? error.message : 'Falha ao salvar configurações.' }
}
async function saveBookingPreferences(): Promise<void> { await saveObjectSettings(bookingPrefs.value, 'Regras de agenda salvas.') }
async function saveConfirmationPreferences(): Promise<void> { await saveObjectSettings(confirmationPrefs.value, 'Fluxo de confirmação salvo.') }
async function saveAdvancedSetting(): Promise<void> { if (!settingForm.value.key.trim()) return; let value: unknown = settingForm.value.value; try { value = JSON.parse(settingForm.value.value) } catch { /* texto */ } await saveObjectSettings({ [settingForm.value.key]: value }, 'Configuração avançada salva.'); settingForm.value = { key: '', value: '' } }
async function copyText(value: string): Promise<void> { await navigator.clipboard.writeText(value); showToast('Copiado para a área de transferência.') }
function openHostname(): void { const hostname = tenantSettings.value?.hostname || manifest.value?.tenant.hostname || browserHostname; window.open(`https://${hostname}`, '_blank', 'noopener,noreferrer') }
function desktopInstructions(): string { return `O Desktop carrega https://${tenantSettings.value?.hostname || browserHostname} diretamente. Publicações do WebApp aparecem sem duplicar a interface.` }

let whatsappPoll: number | undefined
onMounted(async () => {
  await loadBranding()
  window.addEventListener('hashchange', onHashChange)
  window.addEventListener('beforeinstallprompt', onBeforeInstallPrompt)
  whatsappPoll = window.setInterval(() => { if (logged.value && view.value === 'whatsapp' && whatsappStatus.value !== 'CONNECTED') void loadWhatsAppStatus().catch(() => undefined) }, 5000)
  if (token.value) await syncAll()
})
onUnmounted(() => { stopRealtimeConnection(); window.removeEventListener('hashchange', onHashChange); window.removeEventListener('beforeinstallprompt', onBeforeInstallPrompt); if (whatsappPoll !== undefined) window.clearInterval(whatsappPoll) })
</script>

<template>
  <section v-if="!logged" class="auth-page">
    <aside class="auth-visual"><div class="auth-brand"><div class="brand-mark"><CalendarClock :size="28" /></div><div><strong>{{ appName }}</strong><span>{{ slogan }}</span></div></div><h1>Agenda viva, confirmações automáticas e operação em tempo real.</h1><p>Entre no ambiente exclusivo da sua empresa para acompanhar cada mudança do atendimento.</p></aside>
    <form class="auth-card" @submit.prevent="login"><h2>Entrar na plataforma</h2><p>Acesse o painel gerencial da sua empresa.</p><label>E-mail<input v-model="email" type="email" autocomplete="username" required /></label><label>Senha<input v-model="password" type="password" autocomplete="current-password" required /></label><p v-if="authError" class="form-error">{{ authError }}</p><button class="btn primary full" :disabled="loading">{{ loading ? 'Entrando...' : 'Entrar' }}</button><button v-if="installPrompt && !isStandalone" class="btn full" type="button" @click="installWebApp">Instalar web app</button></form>
  </section>

  <div v-else class="app-shell tenant-console" :class="{ collapsed, mobileOpen }">
    <aside class="sidebar">
      <div class="brand"><div class="brand-mark"><CalendarClock :size="24" /></div><div v-if="!collapsed"><strong>{{ appName }}</strong><small>{{ slogan }}</small></div></div>
      <nav class="nav-list"><button v-for="item in visibleNavItems" :key="item.key" class="nav-item" :class="{ active: view === item.key }" @click="go(item.key)"><component :is="item.icon" :size="19" /><span v-if="!collapsed">{{ item.label }}</span></button></nav>
      <div class="sidebar-footer"><button v-if="installPrompt && !isStandalone" class="nav-item" @click="installWebApp"><Download :size="19" /><span v-if="!collapsed">Instalar web app</span></button><button class="nav-item" @click="logout()"><LogOut :size="19" /><span v-if="!collapsed">Sair</span></button><div v-if="!collapsed" class="version-info"><strong>{{ appName }}</strong><small>{{ apiStatus === 'connected' ? 'Operação conectada' : apiStatus === 'degraded' ? 'Conectado com avisos' : 'API indisponível' }}</small></div></div>
    </aside>

    <div class="content-shell">
      <header class="topbar">
        <button class="icon-button" @click="collapsed = !collapsed; mobileOpen = !mobileOpen"><Menu :size="20" /></button>
        <div class="company-switcher"><span>Empresa ativa</span><strong>{{ appName }}</strong></div>
        <div class="topbar-search"><Search :size="17" /><input v-model="searchTerm" placeholder="Buscar na operação" /></div><div class="topbar-spacer"></div>
        <button v-if="installPrompt && !isStandalone" class="btn install-top" @click="installWebApp"><Smartphone :size="16" /> {{ installing ? 'Instalando...' : 'Instalar' }}</button>
        <button v-if="hasCapability('notifications')" class="icon-button notification" :title="pushEnabled ? 'Push ativo neste dispositivo' : 'Ativar notificações push'" @click="pushEnabled ? go('configuracoes') : enablePushNotifications()"><Bell :size="20" /><i v-if="pendingNotifications || !pushEnabled"></i></button>
        <div class="profile"><div class="avatar">{{ (displayName || email).slice(0, 1).toUpperCase() }}</div><div><strong>{{ displayName || email }}</strong><small>Gestor</small></div></div>
      </header>

      <main class="main-content">
        <section class="page-header"><div><p class="eyebrow">Scheduler Pro</p><h1>{{ activeTitle }}</h1><p>Recursos exibidos conforme a liberação do administrador da plataforma.</p></div><div class="page-actions"><button class="btn" :disabled="loading" @click="syncAll"><RefreshCw :size="15" /> Atualizar</button><button v-if="['agenda', 'clientes', 'servicos', 'profissionais'].includes(view)" class="btn primary" @click="openNew"><Plus :size="16" /> Novo</button></div></section>
        <p v-if="toast" class="success-banner"><CheckCircle2 :size="17" /> {{ toast }}</p><p v-if="actionError" class="error-banner"><CircleAlert :size="17" /> {{ actionError }}</p>

        <section v-if="view === 'dashboard'" class="view-stack">
          <div class="metric-grid tenant-metrics">
            <article class="metric-card"><div><span>Agendamentos hoje</span><strong>{{ hasCapability('appointments') ? todayAppointments.length : '—' }}</strong><small>{{ hasCapability('appointments') ? `${confirmedToday} confirmados • ${pendingToday} pendentes` : 'recurso não liberado' }}</small></div><CalendarDays :size="23" /></article>
            <article class="metric-card green"><div><span>Clientes</span><strong>{{ hasCapability('customers') ? customers.length : '—' }}</strong><small>{{ hasCapability('customers') ? 'cadastros da empresa' : 'cadastro opcional' }}</small></div><Users :size="23" /></article>
            <article class="metric-card violet"><div><span>Serviços</span><strong>{{ hasCapability('services') ? services.filter((item) => item.active).length : '—' }}</strong><small>{{ hasCapability('services') ? 'serviços ativos' : 'cadastro opcional' }}</small></div><Wrench :size="23" /></article>
            <article class="metric-card orange"><div><span>Notificações</span><strong>{{ hasCapability('notifications') ? pendingNotifications : '—' }}</strong><small>{{ hasCapability('notifications') ? (pushEnabled ? 'push ativo neste dispositivo' : 'push disponível') : 'recurso não liberado' }}</small></div><Bell :size="23" /></article>
          </div>
          <div class="dashboard-grid">
            <article v-if="hasCapability('appointments')" class="panel"><div class="panel-title"><div><h3>Próximos agendamentos</h3><p>Atualização automática em tempo real</p></div><button class="btn small" @click="go('agenda')">Abrir agenda <ChevronRight :size="14" /></button></div><div class="list"><div v-for="item in upcomingAppointments" :key="item.id" class="row"><span class="time">{{ formatTime(item.starts_at) }}</span><div><strong>{{ item.customer_name }}</strong><small>{{ item.service_name }} • {{ item.professional_name }} • {{ formatDateTime(item.starts_at) }}</small></div><span class="status-pill" :class="statusClass(item.status)">{{ appointmentStatusLabel(item.status) }}</span></div><div v-if="!upcomingAppointments.length" class="empty-state compact"><CalendarDays :size="34" /><strong>Nenhum atendimento futuro.</strong><button class="btn primary small" @click="go('agenda'); openNew()"><Plus :size="14" /> Criar agendamento</button></div></div></article>
            <article class="panel quick-panel"><div class="panel-title"><div><h3>Status da operação</h3><p>Recursos e conectividade</p></div></div><div class="health"><div><span><i :class="apiStatus === 'connected' ? 'ok' : 'warn'"></i>API do tenant</span><strong>{{ apiStatus === 'connected' ? 'Online' : 'Atenção' }}</strong></div><div v-if="hasCapability('appointments')"><span><i :class="realtimeState === 'connected' ? 'ok' : 'warn'"></i>Agenda em tempo real</span><strong>{{ realtimeLabel }}</strong></div><div v-if="hasCapability('notifications')"><span><i :class="pushEnabled ? 'ok' : 'warn'"></i>Push Web/PWA</span><strong>{{ pushEnabled ? 'Ativo' : 'Disponível' }}</strong></div><div v-if="hasCapability('whatsapp')"><span><i :class="whatsappStatus === 'CONNECTED' ? 'ok' : 'warn'"></i>WhatsApp</span><strong>{{ whatsappStatus === 'CONNECTED' ? 'Conectado' : 'Desconectado' }}</strong></div></div></article>
          </div>
        </section>

        <section v-else-if="view === 'agenda'" class="view-stack">
          <article v-if="showEditor && editorKind === 'appointment'" class="panel operational-form editor-panel"><div class="editor-title"><div><h3>Novo agendamento rápido</h3><p>Não exige cadastro prévio de cliente, serviço ou profissional. O Scheduler cria/reaproveita os registros mínimos internamente.</p></div><button class="icon-button" @click="closeEditor"><X :size="17" /></button></div><div class="form-grid"><label>Cliente<input v-model="appointmentForm.customer_name" placeholder="Nome do cliente" required /></label><label>WhatsApp / telefone<input v-model="appointmentForm.customer_phone" placeholder="5575999999999" /></label><label>E-mail<input v-model="appointmentForm.customer_email" type="email" /></label><label>Serviço<input v-model="appointmentForm.service_name" list="service-suggestions" /></label><label>Duração (min)<input v-model.number="appointmentForm.duration_minutes" type="number" min="5" max="720" /></label><label>Profissional / agenda<input v-model="appointmentForm.professional_name" list="professional-suggestions" /></label><label>Início<input v-model="appointmentForm.starts_at" type="datetime-local" required /></label><label>Valor opcional<input v-model.number="appointmentForm.price" type="number" min="0" step="0.01" /></label></div><datalist id="service-suggestions"><option v-for="item in services" :key="item.id" :value="item.name" /></datalist><datalist id="professional-suggestions"><option v-for="item in professionals" :key="item.id" :value="item.name" /></datalist><div class="actions"><button class="btn" @click="closeEditor">Cancelar</button><button class="btn primary" @click="saveAppointment"><Check :size="15" /> Agendar</button></div></article>
          <article v-if="showEditor && editorKind === 'reschedule'" class="panel operational-form editor-panel"><div class="editor-title"><div><h3>Reagendar atendimento</h3><p>O cliente receberá o novo horário e deverá confirmar novamente.</p></div><button class="icon-button" @click="closeEditor"><X :size="17" /></button></div><div class="form-grid"><label>Novo início<input v-model="rescheduleForm.starts_at" type="datetime-local" required /></label><label v-if="hasCapability('professionals')">Profissional<select v-model="rescheduleForm.professional_id"><option v-for="item in professionals" :key="item.id" :value="item.id">{{ item.name }}</option></select></label></div><div class="actions"><button class="btn" @click="closeEditor">Cancelar</button><button class="btn primary" @click="saveReschedule">Reagendar e pedir confirmação</button></div></article>
          <article class="panel filter-panel"><div class="realtime-strip" :class="realtimeState"><span class="live-dot"></span><strong>{{ realtimeLabel }}</strong><small>Alterações de confirmação, cancelamento e expiração atualizam esta tela automaticamente.</small></div><div class="filter-grid"><label>Data<input v-model="agendaDay" type="date" /></label><label>Status<select v-model="agendaStatus"><option value="">Todos</option><option v-for="(label, key) in statusLabels" :key="key" :value="key">{{ label }}</option></select></label><button class="btn" @click="agendaDay = todayKey()">Hoje</button><button class="btn" @click="agendaDay = ''; agendaStatus = ''">Limpar filtros</button></div></article>
          <article class="panel table-panel operational-table"><div class="panel-title"><div><h3>Agenda</h3><p>{{ filteredAppointments.length }} atendimento(s)</p></div></div><div class="responsive-table"><table><thead><tr><th>Horário</th><th>Cliente / serviço</th><th>Profissional</th><th>Status</th><th>Ações</th></tr></thead><tbody><tr v-for="item in filteredAppointments" :key="item.id"><td><strong>{{ formatTime(item.starts_at) }}</strong><small>{{ formatDateTime(item.starts_at) }}</small></td><td><strong>{{ item.customer_name }}</strong><small>{{ item.service_name }} • {{ item.duration_minutes || '—' }} min</small></td><td>{{ item.professional_name }}</td><td><span class="status-pill" :class="statusClass(item.status)">{{ appointmentStatusLabel(item.status) }}</span></td><td><div class="table-actions"><button v-if="['PENDING','AWAITING_CONFIRMATION','RESCHEDULED'].includes(item.status)" class="btn small" @click="copyConfirmationLink(item)"><Copy :size="13" /> Link</button><button v-if="['PENDING','AWAITING_CONFIRMATION','RESCHEDULED'].includes(item.status)" class="btn small primary" @click="appointmentAction(item, 'confirm')">Confirmar</button><button v-if="item.status === 'CONFIRMED'" class="btn small" @click="appointmentAction(item, 'check-in')">Check-in</button><button v-if="item.status === 'CHECKED_IN'" class="btn small" @click="appointmentAction(item, 'start')">Iniciar</button><button v-if="item.status === 'IN_PROGRESS'" class="btn small primary" @click="appointmentAction(item, 'complete')">Concluir</button><button v-if="!terminalStatuses.has(item.status)" class="btn small" @click="openReschedule(item)">Reagendar</button><button v-if="!terminalStatuses.has(item.status)" class="btn small" @click="appointmentAction(item, 'no-show')">Faltou</button><button v-if="!terminalStatuses.has(item.status)" class="btn small danger" @click="cancelAppointment(item)">Cancelar</button></div></td></tr></tbody></table></div><div v-if="!filteredAppointments.length" class="empty-state"><CalendarDays :size="42" /><strong>Nenhum agendamento neste filtro.</strong><p>A agenda funciona mesmo sem os módulos opcionais de cadastros.</p><button class="btn primary" @click="openNew"><Plus :size="15" /> Novo agendamento</button></div></article>
        </section>

        <section v-else-if="view === 'clientes'" class="view-stack"><article v-if="showEditor && editorKind === 'customer'" class="panel operational-form editor-panel"><div class="editor-title"><div><h3>{{ editingId ? 'Editar cliente' : 'Novo cliente' }}</h3><p>Módulo opcional; a agenda rápida não depende dele.</p></div><button class="icon-button" @click="closeEditor"><X :size="17" /></button></div><div class="form-grid"><label>Nome<input v-model="customerForm.name" required /></label><label>Telefone<input v-model="customerForm.phone" /></label><label>E-mail<input v-model="customerForm.email" type="email" /></label></div><label>Observações<textarea v-model="customerForm.notes"></textarea></label><div class="actions"><button class="btn" @click="closeEditor">Cancelar</button><button class="btn primary" @click="saveCustomer">Salvar</button></div></article><article class="panel table-panel operational-table"><div class="panel-title"><div><h3>Clientes</h3><p>{{ filteredCustomers.length }} cadastro(s)</p></div></div><div class="responsive-table"><table><thead><tr><th>Cliente</th><th>Telefone</th><th>E-mail</th><th>Observações</th><th>Ações</th></tr></thead><tbody><tr v-for="item in filteredCustomers" :key="item.id"><td><strong>{{ item.name }}</strong></td><td>{{ item.phone || '—' }}</td><td>{{ item.email || '—' }}</td><td>{{ item.notes || '—' }}</td><td><div class="table-actions"><button class="btn small" @click="editCustomer(item)"><Pencil :size="13" /> Editar</button><button class="btn small danger" @click="deleteCustomer(item)"><Trash2 :size="13" /></button></div></td></tr></tbody></table></div></article></section>

        <section v-else-if="view === 'servicos'" class="view-stack"><article v-if="showEditor && editorKind === 'service'" class="panel operational-form editor-panel"><div class="editor-title"><div><h3>{{ editingId ? 'Editar serviço' : 'Novo serviço' }}</h3><p>Módulo opcional para catálogo estruturado.</p></div><button class="icon-button" @click="closeEditor"><X :size="17" /></button></div><div class="form-grid"><label>Nome<input v-model="serviceForm.name" required /></label><label>Duração<input v-model.number="serviceForm.duration_minutes" type="number" min="5" /></label><label>Preço<input v-model.number="serviceForm.price" type="number" min="0" step="0.01" /></label></div><label class="checkbox-line"><input v-model="serviceForm.active" type="checkbox" /> Ativo</label><div class="actions"><button class="btn" @click="closeEditor">Cancelar</button><button class="btn primary" @click="saveService">Salvar</button></div></article><section class="entity-grid"><article v-for="item in filteredServices" :key="item.id" class="entity-card"><Wrench /><div class="entity-main"><strong>{{ item.name }}</strong><small>{{ item.duration_minutes }} min • {{ formatMoney(item.price) }}</small><div class="entity-actions"><button class="btn small" @click="editService(item)">Editar</button><button class="btn small" @click="toggleService(item)">{{ item.active ? 'Desativar' : 'Ativar' }}</button><button class="btn small danger" @click="deleteService(item)"><Trash2 :size="13" /></button></div></div></article></section></section>

        <section v-else-if="view === 'profissionais'" class="view-stack"><article v-if="showEditor && editorKind === 'professional'" class="panel operational-form editor-panel"><div class="editor-title"><div><h3>{{ editingId ? 'Editar profissional' : 'Novo profissional' }}</h3></div><button class="icon-button" @click="closeEditor"><X :size="17" /></button></div><div class="form-grid"><label>Nome<input v-model="professionalForm.name" /></label><label>E-mail<input v-model="professionalForm.email" type="email" /></label><label>Telefone<input v-model="professionalForm.phone" /></label></div><div class="actions"><button class="btn primary" @click="saveProfessional">Salvar</button></div></article><article v-if="showEditor && editorKind === 'business-hour'" class="panel operational-form editor-panel"><div class="editor-title"><div><h3>Expediente</h3></div><button class="icon-button" @click="closeEditor"><X :size="17" /></button></div><div class="form-grid four"><label>Profissional<select v-model="businessHourForm.professional_id"><option value="">Geral</option><option v-for="item in professionals" :key="item.id" :value="item.id">{{ item.name }}</option></select></label><label>Dia<select v-model.number="businessHourForm.day_of_week"><option v-for="(label,index) in dayLabels" :key="index" :value="index">{{ label }}</option></select></label><label>Abre<input v-model="businessHourForm.opens_at" type="time" /></label><label>Fecha<input v-model="businessHourForm.closes_at" type="time" /></label></div><button class="btn primary" @click="saveBusinessHour">Salvar</button></article><article v-if="showEditor && editorKind === 'blocked-period'" class="panel operational-form editor-panel"><div class="editor-title"><div><h3>Bloquear período</h3></div><button class="icon-button" @click="closeEditor"><X :size="17" /></button></div><div class="form-grid"><label>Profissional<select v-model="blockedPeriodForm.professional_id"><option value="">Geral</option><option v-for="item in professionals" :key="item.id" :value="item.id">{{ item.name }}</option></select></label><label>Início<input v-model="blockedPeriodForm.starts_at" type="datetime-local" /></label><label>Fim<input v-model="blockedPeriodForm.ends_at" type="datetime-local" /></label><label>Motivo<input v-model="blockedPeriodForm.reason" /></label></div><button class="btn primary" @click="saveBlockedPeriod">Criar bloqueio</button></article><section class="entity-grid"><article v-for="item in filteredProfessionals" :key="item.id" class="entity-card"><div class="entity-avatar">{{ item.name.slice(0,2).toUpperCase() }}</div><div class="entity-main"><strong>{{ item.name }}</strong><small>{{ item.email || item.phone || 'Sem contato' }}</small><div class="entity-actions"><button class="btn small" @click="editProfessional(item)">Editar</button><button class="btn small danger" @click="deleteProfessional(item)">Excluir</button></div></div></article></section><article class="panel table-panel"><div class="panel-title"><div><h3>Expediente</h3></div><div class="table-actions"><button class="btn small" @click="openBusinessHour()"><Plus :size="13" /> Faixa</button><button class="btn small" @click="openBlockedPeriod"><Plus :size="13" /> Bloqueio</button></div></div><div class="responsive-table"><table><thead><tr><th>Dia</th><th>Profissional</th><th>Horário</th><th>Ações</th></tr></thead><tbody><tr v-for="item in businessHours" :key="item.id"><td>{{ dayLabels[item.day_of_week] }}</td><td>{{ item.professional_name || 'Geral' }}</td><td>{{ String(item.opens_at).slice(0,5) }} – {{ String(item.closes_at).slice(0,5) }}</td><td><button class="btn small" @click="openBusinessHour(item)">Editar</button><button class="btn small danger" @click="deleteBusinessHour(item)">Excluir</button></td></tr></tbody></table></div></article><article v-if="blockedPeriods.length" class="panel table-panel"><div class="responsive-table"><table><thead><tr><th>Bloqueio</th><th>Início</th><th>Fim</th><th>Ação</th></tr></thead><tbody><tr v-for="item in blockedPeriods" :key="item.id"><td>{{ item.reason || item.professional_name || 'Geral' }}</td><td>{{ formatDateTime(item.starts_at) }}</td><td>{{ formatDateTime(item.ends_at) }}</td><td><button class="btn small danger" @click="deleteBlockedPeriod(item)">Remover</button></td></tr></tbody></table></div></article></section>

        <section v-else-if="view === 'landing'" class="view-stack"><article class="panel operational-form editor-panel"><div><h3>Landing page opcional</h3><p>A página de confirmação/cancelamento funciona independentemente desta landing.</p></div><label>Título<input v-model="landingForm.title" /></label><label>Subtítulo<input v-model="landingForm.subtitle" /></label><label>CTA<input v-model="landingForm.cta" /></label><div class="actions"><button class="btn" @click="saveLanding(false)">Salvar rascunho</button><button class="btn primary" @click="saveLanding(true)">Publicar</button></div></article><article class="landing-preview"><p class="eyebrow">Prévia</p><h2>{{ landingForm.title }}</h2><p>{{ landingForm.subtitle }}</p><button class="btn primary">{{ landingForm.cta }}</button></article></section>

        <section v-else-if="view === 'whatsapp'" class="view-stack"><div class="integration-grid whatsapp-grid"><article class="panel whatsapp-card"><div class="panel-title no-pad"><div><p class="eyebrow">Evolution API</p><h3>WhatsApp do tenant</h3><p>{{ whatsapp.instance_name || 'Instância será criada ao conectar' }}</p></div><span class="status-pill" :class="statusClass(whatsappStatus)">{{ whatsappStatus }}</span></div><div v-if="whatsappStatus === 'CONNECTED'" class="whatsapp-connected"><CheckCircle2 :size="52" /><strong>WhatsApp conectado</strong><p>Pronto para confirmações, remarcações e cancelamentos.</p></div><div v-else class="qr-stage"><div v-if="whatsappQr" class="qr-image-wrap"><img :src="whatsappQr" alt="QR Code WhatsApp" /><small>WhatsApp → Aparelhos conectados → Conectar aparelho.</small></div><div v-else class="qr-placeholder"><MessageCircle :size="48" /><strong>{{ whatsappStatus === 'CONNECTING' ? 'Gerando QR Code...' : 'WhatsApp não conectado' }}</strong></div><div v-if="whatsappPairingCode" class="pairing-code"><span>Código</span><strong>{{ whatsappPairingCode }}</strong><button class="btn small" @click="copyText(whatsappPairingCode)">Copiar</button></div></div><div class="actions"><button class="btn primary" @click="connectWhatsApp"><RefreshCw :size="15" /> Conectar / gerar QR</button><button class="btn" @click="loadWhatsAppStatus">Atualizar</button></div></article><form class="panel operational-form" @submit.prevent="sendMessage"><h3>Mensagem de teste</h3><label>Número<input v-model="messageForm.to" required /></label><label>Mensagem<textarea v-model="messageForm.message" required></textarea></label><button class="btn primary" :disabled="whatsappStatus !== 'CONNECTED'">Enviar</button></form></div></section>

        <section v-else-if="view === 'branding'" class="view-stack"><div class="branding-layout"><article class="panel operational-form editor-panel"><h3>Identidade visual</h3><div class="form-grid"><label>Nome público<input v-model="brandingForm.public_name" /></label><label>Slogan<input v-model="brandingForm.slogan" /></label><label>Logo URL<input v-model="brandingForm.logo_url" /></label></div><div class="form-grid"><label>Principal<input v-model="brandingForm.primary_color" type="color" /></label><label>Secundária<input v-model="brandingForm.secondary_color" type="color" /></label><label>Destaque<input v-model="brandingForm.accent_color" type="color" /></label></div><div class="actions"><button class="btn" @click="saveBranding(false)">Salvar</button><button class="btn primary" @click="saveBranding(true)">Publicar</button></div></article><article class="brand-preview-card" :style="{ background: `linear-gradient(135deg, ${brandingForm.primary_color}, ${brandingForm.accent_color})`, color: brandingForm.text_color }"><Palette :size="34" /><span>PRÉVIA</span><h2>{{ brandingForm.public_name || appName }}</h2><p>{{ brandingForm.slogan || slogan }}</p></article></div></section>

        <section v-else-if="view === 'dominios'" class="view-stack"><article class="panel domain-panel"><div class="panel-title no-pad"><div><h3>Domínio ativo</h3><p>Endereço principal deste tenant.</p></div><span class="status-pill confirmed">HTTPS</span></div><div class="domain-card"><Globe2 /><div><strong>{{ tenantSettings?.hostname || manifest?.tenant.hostname || browserHostname }}</strong><small>{{ tenantSettings?.slug || manifest?.tenant.slug }}</small></div><div class="table-actions"><button class="btn small" @click="copyText(tenantSettings?.hostname || browserHostname)"><Copy :size="13" /> Copiar</button><button class="btn small primary" @click="openHostname"><ExternalLink :size="13" /> Abrir</button></div></div></article></section>

        <section v-else-if="view === 'builds'" class="view-stack"><article class="panel distribution-panel"><div class="panel-title no-pad"><div><h3>Aplicativos e distribuições</h3><p>{{ desktopInstructions() }}</p></div><button class="btn" @click="loadDistribution"><RefreshCw :size="14" /> Atualizar</button></div><div class="distribution-grid"><article><MonitorSmartphone /><strong>Desktop</strong><small>Windows • Linux • macOS</small></article><article><Smartphone /><strong>Mobile</strong><small>Android • iOS</small></article><article><Download /><strong>PWA</strong><small>Instalável no navegador</small><button v-if="installPrompt && !isStandalone" class="btn small primary" @click="installWebApp">Instalar</button></article></div></article><article class="panel table-panel"><div class="responsive-table"><table><thead><tr><th>Arquivo</th><th>Plataforma</th><th>Tipo</th><th>Tamanho</th><th>Download</th></tr></thead><tbody><tr v-for="item in latestArtifacts" :key="item.id"><td>{{ item.name }}</td><td>{{ item.target }}</td><td>{{ item.artifact_type }}</td><td>{{ formatBytes(item.size_bytes) }}</td><td><a v-if="item.download_url" class="btn small primary" :href="item.download_url" target="_blank">Baixar</a></td></tr></tbody></table></div></article><article v-if="latestJobs.length" class="panel table-panel"><div class="responsive-table"><table><thead><tr><th>Alvo</th><th>Status</th><th>Data</th><th>Erro</th></tr></thead><tbody><tr v-for="item in latestJobs" :key="item.id"><td>{{ item.target }}</td><td>{{ item.status }}</td><td>{{ formatDateTime(item.created_at) }}</td><td>{{ item.error || '—' }}</td></tr></tbody></table></div></article></section>

        <section v-else-if="view === 'configuracoes'" class="view-stack">
          <article class="panel settings-overview"><div class="panel-title no-pad"><div><h3>Recursos liberados</h3><p>O administrador da plataforma controla quais módulos este tenant possui.</p></div></div><div class="capability-summary"><span v-for="key in capabilities?.enabled || []" :key="key" class="status-pill confirmed">{{ key }}</span><span v-if="!(capabilities?.enabled || []).length" class="status-pill cancelled">Nenhum módulo liberado</span></div></article>
          <article v-if="hasCapability('appointments')" class="panel operational-form editor-panel"><div><h3>Confirmação, cancelamento e remarcação</h3><p>O cliente recebe um link próprio <strong>/a/&lt;token&gt;</strong>. Encurtador externo permanece opcional e desativado nesta versão.</p></div><label class="checkbox-line"><input v-model="confirmationPrefs.confirmation_required" type="checkbox" /> Exigir confirmação do cliente</label><div class="form-grid"><label>Liberar horário se não confirmar até (min antes)<input v-model.number="confirmationPrefs.confirmation_deadline_minutes" type="number" min="0" /></label><label>Validade máxima do link (h)<input v-model.number="confirmationPrefs.confirmation_link_ttl_hours" type="number" min="1" /></label><label>WhatsApp que recebe respostas<input v-model="confirmationPrefs.tenant_notification_whatsapp" placeholder="5575999999999" /></label></div><div class="form-grid"><label>Título da página<input v-model="confirmationPrefs.confirmation_page_title" /></label><label>Mensagem<input v-model="confirmationPrefs.confirmation_page_message" /></label><label>Botão confirmar<input v-model="confirmationPrefs.confirmation_confirm_label" /></label><label>Botão cancelar<input v-model="confirmationPrefs.confirmation_cancel_label" /></label></div><button class="btn primary" @click="saveConfirmationPreferences">Salvar fluxo de confirmação</button></article>
          <article v-if="hasCapability('notifications')" class="panel push-settings"><div><h3>Notificações Push Web/PWA</h3><p>Receba confirmação, cancelamento, expiração e remarcação mesmo com a agenda em segundo plano.</p></div><span class="status-pill" :class="pushEnabled ? 'confirmed' : 'awaiting-confirmation'">{{ pushEnabled ? 'ATIVO NESTE DISPOSITIVO' : 'DESATIVADO NESTE DISPOSITIVO' }}</span><button v-if="!pushEnabled" class="btn primary" :disabled="pushBusy" @click="enablePushNotifications">Ativar notificações</button><button v-else class="btn" :disabled="pushBusy" @click="disablePushNotifications">Desativar neste dispositivo</button></article>
          <article v-if="hasCapability('appointments')" class="panel operational-form editor-panel"><div><h3>Regras da agenda</h3></div><div class="form-grid"><label>Intervalo entre atendimentos (min)<input v-model.number="bookingPrefs.booking_buffer_minutes" type="number" min="0" /></label><label>Antecedência mínima (min)<input v-model.number="bookingPrefs.minimum_notice_minutes" type="number" min="0" /></label><label>Agenda aberta por (dias)<input v-model.number="bookingPrefs.max_advance_days" type="number" min="1" /></label><label>Janela de cancelamento (h)<input v-model.number="bookingPrefs.cancellation_window_hours" type="number" min="0" /></label></div><button class="btn primary" @click="saveBookingPreferences">Salvar regras</button></article>
          <article class="panel operational-form editor-panel"><div><h3>Configuração avançada</h3><p>Parâmetros específicos em texto, número, booleano ou JSON.</p></div><div class="inline-form"><label>Chave<input v-model="settingForm.key" /></label><label>Valor<input v-model="settingForm.value" /></label><button class="btn primary" @click="saveAdvancedSetting">Salvar</button></div></article>
        </section>
      </main>
    </div>
  </div>
</template>
