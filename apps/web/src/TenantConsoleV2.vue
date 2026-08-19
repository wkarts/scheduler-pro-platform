<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import {
  Bell,
  CalendarClock,
  CalendarDays,
  CheckCircle2,
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

type ApiEnvelope<T> = { data: T }
type ApiFailure = { error?: { message?: string; code?: string } }
type InstallPromptEvent = Event & {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed'; platform: string }>
}

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
  professional_name: string
}

type Customer = { id: string; name: string; phone?: string | null; email?: string | null; notes?: string | null; created_at?: string | null }
type Service = { id: string; name: string; duration_minutes: number; price?: number | null; active: boolean }
type Professional = { id: string; name: string; email?: string | null; phone?: string | null }
type BusinessHour = { id: string; professional_id?: string | null; professional_name?: string | null; day_of_week: number; opens_at: string; closes_at: string; is_open: boolean }
type BlockedPeriod = { id: string; professional_id?: string | null; professional_name?: string | null; starts_at: string; ends_at: string; reason?: string | null }
type NotificationJob = { id: string; template_key: string; recipient: string; scheduled_at: string; status: string; error?: string | null }
type TenantSettings = { tenant_id: string; slug: string; hostname: string; timezone: string; preferences: Record<string, unknown> }
type CapabilityResponse = { tenant_id: string; enabled: string[]; capabilities: Array<{ key: string; enabled: boolean; config?: Record<string, unknown> }> }
type WhatsAppQr = { base64?: string | null; pairing_code?: string | null; code?: string | null; count?: number | null }
type WhatsAppState = { instance_name?: string; status?: string; qr?: WhatsAppQr | null; provider?: Record<string, unknown>; [key: string]: unknown }
type LandingState = { slug: string; status: string; version_number?: number | null; content?: { version?: number; sections?: Array<Record<string, unknown>> }; versions?: Array<Record<string, unknown>> }
type Artifact = { id: string; name: string; target: string; artifact_type: string; download_url?: string | null; size_bytes?: number; created_at?: string }
type BuildJob = { id: string; target: string; status: string; source_ref?: string | null; error?: string | null; created_at?: string }
type DistributionState = { profiles?: Array<Record<string, unknown>>; jobs?: BuildJob[]; artifacts?: Artifact[] }
type ConfirmationLink = { enabled: boolean; request?: { url?: string; canonical_url?: string; confirmation_deadline?: string; expires_at?: string } | null }
type LoginResponse = { access_token: string; refresh_token: string; user?: { email?: string; display_name?: string } }

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
  { key: 'dominios', label: 'Domínio', icon: Link2, capability: 'custom_domains' },
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
const finalStatuses = new Set(['COMPLETED', 'CANCELLED', 'NO_SHOW'])
const dayLabels = ['Domingo', 'Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado']

const view = ref<ViewKey>(hashToView())
const collapsed = ref(false)
const mobileOpen = ref(false)
const loading = ref(false)
const apiStatus = ref<'connected' | 'degraded' | 'fallback'>('fallback')
const token = ref(localStorage.getItem('scheduler_pro_access_token') || '')
const email = ref(localStorage.getItem('scheduler_pro_email') || '')
const displayName = ref(localStorage.getItem('scheduler_pro_display_name') || '')
const password = ref('')
const authError = ref('')
const actionError = ref('')
const toast = ref('')
const searchTerm = ref('')
const manifest = ref<BrandingManifest | null>(null)
const installPrompt = ref<InstallPromptEvent | null>(null)
const enabledCapabilities = ref<string[]>([])
const capabilitiesLoaded = ref(false)

const appointments = ref<Appointment[]>([])
const customers = ref<Customer[]>([])
const services = ref<Service[]>([])
const professionals = ref<Professional[]>([])
const businessHours = ref<BusinessHour[]>([])
const blockedPeriods = ref<BlockedPeriod[]>([])
const notifications = ref<NotificationJob[]>([])
const tenantSettings = ref<TenantSettings | null>(null)
const whatsapp = ref<WhatsAppState>({ status: 'DISCONNECTED' })
const landingState = ref<LandingState | null>(null)
const distribution = ref<DistributionState>({ profiles: [], jobs: [], artifacts: [] })

const showEditor = ref(false)
const editorKind = ref<'appointment' | 'customer' | 'service' | 'professional' | 'reschedule' | 'business-hour' | 'blocked-period' | ''>('')
const editingId = ref('')
const appointmentMode = ref<'quick' | 'catalog'>('quick')
const agendaDay = ref(todayKey())
const agendaStatus = ref('')

const quickAppointmentForm = ref({ customer_name: '', customer_phone: '', customer_email: '', service_name: 'Atendimento', duration_minutes: 30, price: null as number | null, professional_name: 'Agenda geral', starts_at: '' })
const appointmentForm = ref({ customer_id: '', service_id: '', professional_id: '', starts_at: '' })
const rescheduleForm = ref({ appointment_id: '', starts_at: '', professional_id: '' })
const customerForm = ref({ name: '', phone: '', email: '', notes: '' })
const serviceForm = ref({ name: '', duration_minutes: 30, price: null as number | null, active: true })
const professionalForm = ref({ name: '', email: '', phone: '' })
const businessHourForm = ref({ professional_id: '', day_of_week: 1, opens_at: '08:00', closes_at: '18:00', is_open: true })
const blockedPeriodForm = ref({ professional_id: '', starts_at: '', ends_at: '', reason: '' })
const messageForm = ref({ to: '', message: '' })
const landingForm = ref({ title: 'Agende seu atendimento', subtitle: 'Escolha o melhor horário para você.', cta: 'Agendar agora' })
const brandingForm = ref({ public_name: '', slogan: '', logo_url: '', primary_color: '#2563eb', secondary_color: '#0f172a', accent_color: '#06b6d4', background_color: '#f8fafc', text_color: '#0f172a', theme_mode: 'system' })
const bookingPrefs = ref({ booking_buffer_minutes: 0, minimum_notice_minutes: 60, max_advance_days: 90, cancellation_window_hours: 12, default_country_code: '55' })
const confirmationPrefs = ref({ confirmation_required: true, confirmation_deadline_minutes: 60, confirmation_link_ttl_hours: 168, tenant_notification_whatsapp: '', confirmation_page_title: 'Confirme seu atendimento', confirmation_page_message: 'Revise os dados abaixo e confirme ou cancele seu horário.', confirmation_confirm_label: 'Confirmar agendamento', confirmation_cancel_label: 'Cancelar agendamento', short_links_enabled: false, short_links_provider: 'none' })

const logged = computed(() => Boolean(token.value))
const appName = computed(() => manifest.value?.app?.public_name || manifest.value?.app?.name || 'Scheduler Pro')
const slogan = computed(() => manifest.value?.app?.slogan || 'Plataforma inteligente de agendamentos')
const visibleNavItems = computed(() => navItems.filter((item) => !item.capability || hasCapability(item.capability)))
const activeTitle = computed(() => navItems.find((item) => item.key === view.value)?.label || 'Visão geral')
const normalizedSearch = computed(() => searchTerm.value.trim().toLocaleLowerCase('pt-BR'))
const whatsappStatus = computed(() => String(whatsapp.value.status || 'DISCONNECTED').toUpperCase())
const whatsappQr = computed(() => whatsapp.value.qr?.base64 || '')
const whatsappPairingCode = computed(() => whatsapp.value.qr?.pairing_code || '')
const canUseCatalogAppointment = computed(() => hasCapability('customers') && hasCapability('services') && hasCapability('professionals'))
const filteredAppointments = computed(() => appointments.value.filter((item) => {
  if (agendaDay.value && localDayKey(item.starts_at) !== agendaDay.value) return false
  if (agendaStatus.value && item.status !== agendaStatus.value) return false
  return matches(`${item.customer_name} ${item.customer_phone || ''} ${item.service_name} ${item.professional_name} ${item.status}`)
}))
const filteredCustomers = computed(() => customers.value.filter((item) => matches(`${item.name} ${item.phone || ''} ${item.email || ''}`)))
const filteredServices = computed(() => services.value.filter((item) => matches(`${item.name} ${item.duration_minutes} ${item.price ?? ''}`)))
const filteredProfessionals = computed(() => professionals.value.filter((item) => matches(`${item.name} ${item.phone || ''} ${item.email || ''}`)))
const todayAppointments = computed(() => appointments.value.filter((item) => localDayKey(item.starts_at) === todayKey()))
const upcomingAppointments = computed(() => appointments.value.filter((item) => new Date(item.starts_at).getTime() >= Date.now() && !finalStatuses.has(item.status)).sort((a, b) => new Date(a.starts_at).getTime() - new Date(b.starts_at).getTime()).slice(0, 8))
const pendingNotifications = computed(() => notifications.value.filter((item) => ['PENDING', 'QUEUED', 'SCHEDULED'].includes(String(item.status).toUpperCase())).length)
const artifacts = computed(() => distribution.value.artifacts || [])
const buildJobs = computed(() => distribution.value.jobs || [])
const isStandalone = computed(() => window.matchMedia('(display-mode: standalone)').matches || Boolean((window.navigator as Navigator & { standalone?: boolean }).standalone))

function hasCapability(key: string): boolean { return enabledCapabilities.value.includes(key) }
function matches(value: string): boolean { return !normalizedSearch.value || value.toLocaleLowerCase('pt-BR').includes(normalizedSearch.value) }
function todayKey(): string { const now = new Date(); return new Date(now.getTime() - now.getTimezoneOffset() * 60_000).toISOString().slice(0, 10) }
function localDayKey(value: string): string { const date = new Date(value); return new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 10) }
function hashToView(): ViewKey { const current = (window.location.hash || '#dashboard').replace('#', ''); return navItems.some((item) => item.key === current) ? current as ViewKey : 'dashboard' }
function formatDateTime(value?: string | null): string { return value ? new Date(value).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' }) : '—' }
function formatTime(value?: string | null): string { return value ? new Date(value).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }) : '—' }
function formatMoney(value?: number | null): string { return value == null ? 'Não informado' : new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value) }
function formatBytes(value?: number): string { if (!value) return '—'; const units = ['B', 'KB', 'MB', 'GB']; let size = value; let i = 0; while (size >= 1024 && i < units.length - 1) { size /= 1024; i += 1 } return `${size.toFixed(i ? 1 : 0)} ${units[i]}` }
function statusClass(value?: string | null): string { return String(value || '').toLowerCase().replace(/[^a-z0-9]+/g, '-') }
function statusLabel(value: string): string { return statusLabels[value] || value }
function apiBase(): string { return `${window.location.origin}/api/v1` }

function showToast(message: string): void { toast.value = message; window.setTimeout(() => { if (toast.value === message) toast.value = '' }, 3500) }
function closeEditor(): void { showEditor.value = false; editorKind.value = ''; editingId.value = '' }
function onHashChange(): void { view.value = hashToView(); enforceVisibleView() }
function onBeforeInstallPrompt(event: Event): void { event.preventDefault(); installPrompt.value = event as InstallPromptEvent }
function enforceVisibleView(): void { if (!capabilitiesLoaded.value) return; if (!visibleNavItems.value.some((item) => item.key === view.value)) go('dashboard') }
function go(key: ViewKey): void { const item = navItems.find((row) => row.key === key); if (item?.capability && !hasCapability(item.capability)) return; view.value = key; closeEditor(); mobileOpen.value = false; searchTerm.value = ''; if (window.location.hash !== `#${key}`) history.replaceState(null, '', `#${key}`); if (key === 'whatsapp') void loadWhatsApp(); if (key === 'landing') void loadLanding(); if (key === 'builds') void loadDistribution() }

async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${apiBase()}${path}`, { ...init, headers: { Accept: 'application/json', ...(init.body instanceof FormData ? {} : { 'content-type': 'application/json' }), ...(token.value ? { authorization: `Bearer ${token.value}` } : {}), ...(init.headers || {}) } })
  } catch { throw new Error('Não foi possível conectar à API.') }
  const body = await response.json().catch(() => ({})) as Partial<ApiEnvelope<T>> & ApiFailure
  if (response.status === 401 && token.value) logout(false)
  if (!response.ok) throw new Error(`${body.error?.message || `Falha HTTP ${response.status}`}${body.error?.code ? ` (${body.error.code})` : ''}`)
  return body.data as T
}

async function loadBranding(): Promise<void> {
  try {
    const data = await loadBrandingManifest(); manifest.value = data; applyBranding(data)
    brandingForm.value = { public_name: data.app.public_name, slogan: data.app.slogan || '', logo_url: data.assets.logo_url || '', primary_color: data.theme.colors.primary, secondary_color: data.theme.colors.secondary, accent_color: data.theme.colors.accent, background_color: data.theme.colors.background, text_color: data.theme.colors.text, theme_mode: data.theme.mode }
  } catch { /* fallback visual local */ }
}

async function login(): Promise<void> {
  authError.value = ''; loading.value = true
  try {
    const data = await api<LoginResponse>('/auth/login', { method: 'POST', body: JSON.stringify({ email: email.value, password: password.value }) })
    token.value = data.access_token; email.value = data.user?.email || email.value; displayName.value = data.user?.display_name || ''
    localStorage.setItem('scheduler_pro_access_token', data.access_token); localStorage.setItem('scheduler_pro_refresh_token', data.refresh_token); localStorage.setItem('scheduler_pro_email', email.value); localStorage.setItem('scheduler_pro_display_name', displayName.value)
    password.value = ''; await syncAll(); go('dashboard')
  } catch (error) { authError.value = error instanceof Error ? error.message : 'Login inválido.' } finally { loading.value = false }
}

function logout(reload = true): void { token.value = ''; enabledCapabilities.value = []; capabilitiesLoaded.value = false; localStorage.removeItem('scheduler_pro_access_token'); localStorage.removeItem('scheduler_pro_refresh_token'); if (reload) window.location.hash = '#dashboard' }

async function loadCapabilities(): Promise<void> {
  const data = await api<CapabilityResponse>('/settings/capabilities')
  enabledCapabilities.value = Array.isArray(data.enabled) ? data.enabled : []
  capabilitiesLoaded.value = true
  enforceVisibleView()
}

function hydrateSettings(): void {
  const prefs = tenantSettings.value?.preferences || {}
  const numberValue = (key: string, fallback: number) => { const parsed = Number(prefs[key]); return Number.isFinite(parsed) ? parsed : fallback }
  const boolValue = (key: string, fallback: boolean) => { const value = prefs[key]; if (typeof value === 'boolean') return value; if (typeof value === 'string') return !['false', '0', 'no', 'off'].includes(value.toLowerCase()); return value == null ? fallback : Boolean(value) }
  bookingPrefs.value = { booking_buffer_minutes: numberValue('booking_buffer_minutes', 0), minimum_notice_minutes: numberValue('minimum_notice_minutes', 60), max_advance_days: numberValue('max_advance_days', 90), cancellation_window_hours: numberValue('cancellation_window_hours', 12), default_country_code: String(prefs.default_country_code || '55') }
  confirmationPrefs.value = { confirmation_required: boolValue('confirmation_required', true), confirmation_deadline_minutes: numberValue('confirmation_deadline_minutes', 60), confirmation_link_ttl_hours: numberValue('confirmation_link_ttl_hours', 168), tenant_notification_whatsapp: String(prefs.tenant_notification_whatsapp || ''), confirmation_page_title: String(prefs.confirmation_page_title || 'Confirme seu atendimento'), confirmation_page_message: String(prefs.confirmation_page_message || 'Revise os dados abaixo e confirme ou cancele seu horário.'), confirmation_confirm_label: String(prefs.confirmation_confirm_label || 'Confirmar agendamento'), confirmation_cancel_label: String(prefs.confirmation_cancel_label || 'Cancelar agendamento'), short_links_enabled: boolValue('short_links_enabled', false), short_links_provider: String(prefs.short_links_provider || 'none') }
}

async function syncAll(): Promise<void> {
  if (!token.value) return
  loading.value = true; actionError.value = ''; const warnings: string[] = []
  try { await loadCapabilities() } catch (error) { actionError.value = error instanceof Error ? error.message : 'Não foi possível carregar os recursos liberados.'; apiStatus.value = 'fallback'; loading.value = false; return }
  const safe = async (label: string, fn: () => Promise<void>) => { try { await fn() } catch (error) { warnings.push(`${label}: ${error instanceof Error ? error.message : 'indisponível'}`) } }
  await safe('Configurações', async () => { tenantSettings.value = await api<TenantSettings>('/settings/tenant'); hydrateSettings() })
  const jobs: Promise<void>[] = []
  if (hasCapability('appointments')) {
    jobs.push(safe('Agenda', async () => { appointments.value = await api('/appointments') }))
    jobs.push(safe('Expediente', async () => { businessHours.value = await api('/schedule/business-hours') }))
    jobs.push(safe('Bloqueios', async () => { blockedPeriods.value = await api('/schedule/blocked-periods') }))
  } else { appointments.value = []; businessHours.value = []; blockedPeriods.value = [] }
  if (hasCapability('customers')) jobs.push(safe('Clientes', async () => { customers.value = await api('/customers') })); else customers.value = []
  if (hasCapability('services')) jobs.push(safe('Serviços', async () => { services.value = await api('/services') })); else services.value = []
  if (hasCapability('professionals')) jobs.push(safe('Profissionais', async () => { professionals.value = await api('/professionals') })); else professionals.value = []
  if (hasCapability('notifications')) jobs.push(safe('Notificações', async () => { notifications.value = await api('/notifications?limit=100') })); else notifications.value = []
  if (hasCapability('whatsapp')) jobs.push(safe('WhatsApp', loadWhatsApp)); else whatsapp.value = { status: 'DISABLED' }
  if (hasCapability('landing_pages')) jobs.push(safe('Landing', loadLanding)); else landingState.value = null
  if (hasCapability('builds')) jobs.push(safe('Distribuições', loadDistribution)); else distribution.value = { profiles: [], jobs: [], artifacts: [] }
  await Promise.all(jobs)
  apiStatus.value = warnings.length === 0 ? 'connected' : warnings.length < 3 ? 'degraded' : 'fallback'
  if (warnings.length) actionError.value = `Alguns recursos liberados não responderam. ${warnings[0]}`
  loading.value = false
}

function openNew(): void {
  if (view.value === 'agenda') { editorKind.value = 'appointment'; appointmentMode.value = 'quick'; quickAppointmentForm.value = { customer_name: '', customer_phone: '', customer_email: '', service_name: 'Atendimento', duration_minutes: 30, price: null, professional_name: 'Agenda geral', starts_at: '' }; appointmentForm.value = { customer_id: '', service_id: '', professional_id: '', starts_at: '' } }
  else if (view.value === 'clientes') { editorKind.value = 'customer'; customerForm.value = { name: '', phone: '', email: '', notes: '' } }
  else if (view.value === 'servicos') { editorKind.value = 'service'; serviceForm.value = { name: '', duration_minutes: 30, price: null, active: true } }
  else if (view.value === 'profissionais') { editorKind.value = 'professional'; professionalForm.value = { name: '', email: '', phone: '' } }
  else return
  editingId.value = ''; showEditor.value = true
}

async function saveAppointment(): Promise<void> {
  try {
    if (appointmentMode.value === 'quick' || !canUseCatalogAppointment.value) {
      if (!quickAppointmentForm.value.starts_at || !quickAppointmentForm.value.customer_name.trim()) throw new Error('Informe o cliente e o horário.')
      await api('/appointments/quick', { method: 'POST', body: JSON.stringify({ ...quickAppointmentForm.value, customer_phone: quickAppointmentForm.value.customer_phone || null, customer_email: quickAppointmentForm.value.customer_email || null, starts_at: new Date(quickAppointmentForm.value.starts_at).toISOString() }) })
    } else {
      const start = new Date(appointmentForm.value.starts_at); const service = services.value.find((item) => item.id === appointmentForm.value.service_id); if (!service) throw new Error('Selecione um serviço.'); const end = new Date(start.getTime() + service.duration_minutes * 60_000)
      await api('/appointments', { method: 'POST', body: JSON.stringify({ ...appointmentForm.value, starts_at: start.toISOString(), ends_at: end.toISOString(), source: 'tenant-web' }) })
    }
    appointments.value = await api('/appointments'); closeEditor(); showToast('Agendamento criado. O fluxo de confirmação foi iniciado.')
  } catch (error) { actionError.value = error instanceof Error ? error.message : 'Falha ao criar agendamento.' }
}

async function appointmentAction(item: Appointment, action: string): Promise<void> { try { await api(`/appointments/${item.id}/${action}`, { method: 'POST', body: '{}' }); appointments.value = await api('/appointments'); showToast('Agendamento atualizado.') } catch (error) { actionError.value = error instanceof Error ? error.message : 'Falha ao atualizar.' } }
async function cancelAppointment(item: Appointment): Promise<void> { if (!window.confirm(`Cancelar o atendimento de ${item.customer_name}?`)) return; try { await api(`/appointments/${item.id}/cancel`, { method: 'POST', body: JSON.stringify({ reason: 'Cancelado pelo gestor do tenant' }) }); appointments.value = await api('/appointments'); showToast('Agendamento cancelado e horário liberado.') } catch (error) { actionError.value = error instanceof Error ? error.message : 'Falha ao cancelar.' } }
async function copyConfirmationLink(item: Appointment): Promise<void> { try { const data = await api<ConfirmationLink>(`/appointment-confirmations/${item.id}`); const url = data.request?.url; if (!url) throw new Error('Confirmação por link está desativada para este tenant.'); await navigator.clipboard.writeText(url); showToast('Link de confirmação copiado.') } catch (error) { actionError.value = error instanceof Error ? error.message : 'Falha ao gerar link.' } }
function openReschedule(item: Appointment): void { const local = new Date(item.starts_at); local.setMinutes(local.getMinutes() - local.getTimezoneOffset()); rescheduleForm.value = { appointment_id: item.id, starts_at: local.toISOString().slice(0, 16), professional_id: item.professional_id }; editorKind.value = 'reschedule'; showEditor.value = true }
async function saveReschedule(): Promise<void> { const item = appointments.value.find((row) => row.id === rescheduleForm.value.appointment_id); if (!item) return; const start = new Date(rescheduleForm.value.starts_at); const duration = item.duration_minutes || 30; try { await api(`/appointments/${item.id}/reschedule`, { method: 'POST', body: JSON.stringify({ starts_at: start.toISOString(), ends_at: new Date(start.getTime() + duration * 60_000).toISOString(), professional_id: rescheduleForm.value.professional_id || item.professional_id, reason: 'Reagendado pelo tenant' }) }); appointments.value = await api('/appointments'); closeEditor(); showToast('Reagendado. Um novo link de confirmação foi gerado.') } catch (error) { actionError.value = error instanceof Error ? error.message : 'Falha ao reagendar.' } }

function editCustomer(item: Customer): void { editingId.value = item.id; editorKind.value = 'customer'; customerForm.value = { name: item.name, phone: item.phone || '', email: item.email || '', notes: item.notes || '' }; showEditor.value = true }
async function saveCustomer(): Promise<void> { try { await api(editingId.value ? `/customers/${editingId.value}` : '/customers', { method: editingId.value ? 'PATCH' : 'POST', body: JSON.stringify({ ...customerForm.value, phone: customerForm.value.phone || null, email: customerForm.value.email || null, notes: customerForm.value.notes || null }) }); customers.value = await api('/customers'); closeEditor(); showToast('Cliente salvo.') } catch (error) { actionError.value = error instanceof Error ? error.message : 'Falha ao salvar cliente.' } }
async function deleteCustomer(item: Customer): Promise<void> { if (!window.confirm(`Excluir ${item.name}?`)) return; try { await api(`/customers/${item.id}`, { method: 'DELETE' }); customers.value = await api('/customers'); showToast('Cliente excluído.') } catch (error) { actionError.value = error instanceof Error ? error.message : 'Falha ao excluir.' } }
function editService(item: Service): void { editingId.value = item.id; editorKind.value = 'service'; serviceForm.value = { ...item, price: item.price ?? null }; showEditor.value = true }
async function saveService(): Promise<void> { try { await api(editingId.value ? `/services/${editingId.value}` : '/services', { method: editingId.value ? 'PATCH' : 'POST', body: JSON.stringify(serviceForm.value) }); services.value = await api('/services'); closeEditor(); showToast('Serviço salvo.') } catch (error) { actionError.value = error instanceof Error ? error.message : 'Falha ao salvar serviço.' } }
async function toggleService(item: Service): Promise<void> { try { await api(`/services/${item.id}`, { method: 'PATCH', body: JSON.stringify({ active: !item.active }) }); services.value = await api('/services') } catch (error) { actionError.value = error instanceof Error ? error.message : 'Falha ao alterar serviço.' } }
async function deleteService(item: Service): Promise<void> { if (!window.confirm(`Excluir ${item.name}?`)) return; try { await api(`/services/${item.id}`, { method: 'DELETE' }); services.value = await api('/services') } catch (error) { actionError.value = error instanceof Error ? error.message : 'Falha ao excluir.' } }
function editProfessional(item: Professional): void { editingId.value = item.id; editorKind.value = 'professional'; professionalForm.value = { name: item.name, email: item.email || '', phone: item.phone || '' }; showEditor.value = true }
async function saveProfessional(): Promise<void> { try { await api(editingId.value ? `/professionals/${editingId.value}` : '/professionals', { method: editingId.value ? 'PATCH' : 'POST', body: JSON.stringify({ ...professionalForm.value, email: professionalForm.value.email || null, phone: professionalForm.value.phone || null }) }); professionals.value = await api('/professionals'); closeEditor(); showToast('Profissional salvo.') } catch (error) { actionError.value = error instanceof Error ? error.message : 'Falha ao salvar profissional.' } }
async function deleteProfessional(item: Professional): Promise<void> { if (!window.confirm(`Excluir ${item.name}?`)) return; try { await api(`/professionals/${item.id}`, { method: 'DELETE' }); professionals.value = await api('/professionals') } catch (error) { actionError.value = error instanceof Error ? error.message : 'Falha ao excluir.' } }

function openBusinessHour(item?: BusinessHour): void { editingId.value = item?.id || ''; editorKind.value = 'business-hour'; businessHourForm.value = item ? { professional_id: item.professional_id || '', day_of_week: item.day_of_week, opens_at: String(item.opens_at).slice(0, 5), closes_at: String(item.closes_at).slice(0, 5), is_open: item.is_open } : { professional_id: '', day_of_week: 1, opens_at: '08:00', closes_at: '18:00', is_open: true }; showEditor.value = true }
async function saveBusinessHour(): Promise<void> { try { await api(editingId.value ? `/schedule/business-hours/${editingId.value}` : '/schedule/business-hours', { method: editingId.value ? 'PUT' : 'POST', body: JSON.stringify({ ...businessHourForm.value, professional_id: businessHourForm.value.professional_id || null }) }); businessHours.value = await api('/schedule/business-hours'); closeEditor(); showToast('Expediente salvo.') } catch (error) { actionError.value = error instanceof Error ? error.message : 'Falha no expediente.' } }
async function deleteBusinessHour(item: BusinessHour): Promise<void> { if (!window.confirm('Excluir esta faixa?')) return; try { await api(`/schedule/business-hours/${item.id}`, { method: 'DELETE' }); businessHours.value = await api('/schedule/business-hours') } catch (error) { actionError.value = error instanceof Error ? error.message : 'Falha ao excluir faixa.' } }
function openBlockedPeriod(): void { editorKind.value = 'blocked-period'; editingId.value = ''; blockedPeriodForm.value = { professional_id: '', starts_at: '', ends_at: '', reason: '' }; showEditor.value = true }
async function saveBlockedPeriod(): Promise<void> { try { await api('/schedule/blocked-periods', { method: 'POST', body: JSON.stringify({ professional_id: blockedPeriodForm.value.professional_id || null, starts_at: new Date(blockedPeriodForm.value.starts_at).toISOString(), ends_at: new Date(blockedPeriodForm.value.ends_at).toISOString(), reason: blockedPeriodForm.value.reason || null }) }); blockedPeriods.value = await api('/schedule/blocked-periods'); closeEditor(); showToast('Bloqueio salvo.') } catch (error) { actionError.value = error instanceof Error ? error.message : 'Falha no bloqueio.' } }
async function deleteBlockedPeriod(item: BlockedPeriod): Promise<void> { if (!window.confirm('Remover este bloqueio?')) return; try { await api(`/schedule/blocked-periods/${item.id}`, { method: 'DELETE' }); blockedPeriods.value = await api('/schedule/blocked-periods') } catch (error) { actionError.value = error instanceof Error ? error.message : 'Falha ao remover bloqueio.' } }

async function loadWhatsApp(): Promise<void> { if (!hasCapability('whatsapp')) return; whatsapp.value = await api('/integrations/whatsapp/status') }
async function connectWhatsApp(): Promise<void> { try { whatsapp.value = { ...whatsapp.value, status: 'CONNECTING' }; whatsapp.value = await api('/integrations/whatsapp/connect', { method: 'POST', body: '{}' }); showToast(whatsappQr.value ? 'QR Code gerado.' : 'Conexão iniciada. Aguardando QR Code.') } catch (error) { actionError.value = error instanceof Error ? error.message : 'Falha no WhatsApp.' } }
async function sendMessage(): Promise<void> { if (whatsappStatus.value !== 'CONNECTED') return; try { await api('/integrations/whatsapp/send-text', { method: 'POST', body: JSON.stringify(messageForm.value) }); messageForm.value.message = ''; showToast('Mensagem enviada.') } catch (error) { actionError.value = error instanceof Error ? error.message : 'Falha ao enviar.' } }

async function loadLanding(): Promise<void> { if (!hasCapability('landing_pages')) return; const state = await api<LandingState>('/landing-pages/home'); landingState.value = state; const sections = Array.isArray(state.content?.sections) ? state.content?.sections : []; const hero = sections?.find((item) => item.type === 'hero') || {}; landingForm.value = { title: String(hero.title || 'Agende seu atendimento'), subtitle: String(hero.subtitle || 'Escolha o melhor horário para você.'), cta: String(hero.cta || 'Agendar agora') } }
async function saveLanding(publish = false): Promise<void> { try { const version = Number(landingState.value?.version_number || landingState.value?.content?.version || 0) + 1; await api('/landing-pages/home/draft', { method: 'POST', body: JSON.stringify({ version, sections: [{ type: 'hero', ...landingForm.value }, { type: 'booking', enabled: true }] }) }); if (publish) await api('/landing-pages/home/publish', { method: 'POST', body: '{}' }); await loadLanding(); showToast(publish ? 'Landing publicada.' : 'Rascunho salvo.') } catch (error) { actionError.value = error instanceof Error ? error.message : 'Falha na landing.' } }
async function saveBranding(publish = false): Promise<void> { try { await api('/branding/profile', { method: 'PUT', body: JSON.stringify(brandingForm.value) }); if (publish) await api('/branding/publish', { method: 'POST', body: '{}' }); await loadBranding(); showToast(publish ? 'Marca publicada.' : 'Marca salva.') } catch (error) { actionError.value = error instanceof Error ? error.message : 'Falha na marca.' } }
async function loadDistribution(): Promise<void> { if (hasCapability('builds')) distribution.value = await api('/branding/distribution') }

async function saveSettingsGroup(values: Record<string, unknown>, successMessage: string): Promise<void> { try { for (const [key, value] of Object.entries(values)) await api(`/settings/tenant/${encodeURIComponent(key)}`, { method: 'PUT', body: JSON.stringify(value) }); tenantSettings.value = await api('/settings/tenant'); hydrateSettings(); showToast(successMessage) } catch (error) { actionError.value = error instanceof Error ? error.message : 'Falha ao salvar configurações.' } }
async function saveBookingPrefs(): Promise<void> { await saveSettingsGroup(bookingPrefs.value, 'Regras da agenda salvas.') }
async function saveConfirmationPrefs(): Promise<void> { await saveSettingsGroup({ ...confirmationPrefs.value, short_links_enabled: false, short_links_provider: 'none' }, 'Confirmação e avisos salvos.') }
async function copyText(value: string): Promise<void> { await navigator.clipboard.writeText(value); showToast('Copiado.') }
async function installWebApp(): Promise<void> { if (!installPrompt.value) return; await installPrompt.value.prompt(); await installPrompt.value.userChoice; installPrompt.value = null }
function openHostname(): void { window.open(`https://${tenantSettings.value?.hostname || window.location.hostname}`, '_blank', 'noopener,noreferrer') }

let whatsappPoll: number | undefined
onMounted(async () => { await loadBranding(); window.addEventListener('hashchange', onHashChange); window.addEventListener('beforeinstallprompt', onBeforeInstallPrompt); whatsappPoll = window.setInterval(() => { if (logged.value && view.value === 'whatsapp' && hasCapability('whatsapp') && whatsappStatus.value !== 'CONNECTED') void loadWhatsApp().catch(() => undefined) }, 5000); if (token.value) await syncAll() })
onUnmounted(() => { window.removeEventListener('hashchange', onHashChange); window.removeEventListener('beforeinstallprompt', onBeforeInstallPrompt); if (whatsappPoll !== undefined) window.clearInterval(whatsappPoll) })
</script>

<template>
  <section v-if="!logged" class="auth-page">
    <aside class="auth-visual"><div class="auth-brand"><div class="brand-mark"><CalendarClock :size="28" /></div><div><strong>{{ appName }}</strong><span>{{ slogan }}</span></div></div><h1>Sua agenda, confirmações e atendimento em um único lugar.</h1><p>Entre no ambiente exclusivo da empresa para acompanhar horários, clientes e comunicação.</p></aside>
    <form class="auth-card" @submit.prevent="login"><h2>Entrar na plataforma</h2><p>Acesse o painel gerencial da sua empresa.</p><label>E-mail<input v-model="email" type="email" autocomplete="username" required /></label><label>Senha<input v-model="password" type="password" autocomplete="current-password" required /></label><p v-if="authError" class="form-error">{{ authError }}</p><button class="btn primary full" :disabled="loading">{{ loading ? 'Entrando...' : 'Entrar' }}</button></form>
  </section>

  <div v-else class="app-shell tenant-console" :class="{ collapsed, mobileOpen }">
    <aside class="sidebar"><div class="brand"><div class="brand-mark"><CalendarClock :size="24" /></div><div v-if="!collapsed"><strong>{{ appName }}</strong><small>{{ slogan }}</small></div></div><nav class="nav-list"><button v-for="item in visibleNavItems" :key="item.key" class="nav-item" :class="{ active: view === item.key }" @click="go(item.key)"><component :is="item.icon" :size="19" /><span v-if="!collapsed">{{ item.label }}</span></button></nav><div class="sidebar-footer"><button v-if="installPrompt && !isStandalone" class="nav-item" @click="installWebApp"><Download :size="19" /><span v-if="!collapsed">Instalar web app</span></button><button class="nav-item" @click="logout()"><LogOut :size="19" /><span v-if="!collapsed">Sair</span></button><div v-if="!collapsed" class="version-info"><strong>{{ appName }}</strong><small>{{ enabledCapabilities.length }} recurso(s) liberado(s)</small></div></div></aside>
    <div class="content-shell">
      <header class="topbar"><button class="icon-button" @click="collapsed = !collapsed; mobileOpen = !mobileOpen"><Menu :size="20" /></button><div class="company-switcher"><span>Empresa ativa</span><strong>{{ appName }}</strong></div><div class="topbar-search"><Search :size="17" /><input v-model="searchTerm" placeholder="Buscar na operação" /></div><div class="topbar-spacer"></div><button v-if="installPrompt && !isStandalone" class="btn install-top" @click="installWebApp"><Smartphone :size="16" /> Instalar</button><button class="icon-button notification"><Bell :size="20" /><i v-if="pendingNotifications"></i></button><div class="profile"><div class="avatar">{{ (displayName || email).slice(0, 1).toUpperCase() }}</div><div><strong>{{ displayName || email }}</strong><small>Gestor</small></div></div></header>
      <main class="main-content">
        <section class="page-header"><div><p class="eyebrow">Scheduler Pro</p><h1>{{ activeTitle }}</h1><p>Agenda e recursos liberados para esta empresa.</p></div><div class="page-actions"><button class="btn" :disabled="loading" @click="syncAll"><RefreshCw :size="15" /> Atualizar</button><button v-if="['agenda','clientes','servicos','profissionais'].includes(view)" class="btn primary" @click="openNew"><Plus :size="15" /> Novo</button></div></section>
        <p v-if="toast" class="success-banner"><CheckCircle2 :size="17" /> {{ toast }}</p><p v-if="actionError" class="error-banner"><CircleAlert :size="17" /> {{ actionError }}</p>

        <section v-if="view === 'dashboard'" class="view-stack">
          <div v-if="capabilitiesLoaded && !hasCapability('appointments')" class="capability-notice"><CircleAlert :size="18" /><div><strong>Agenda ainda não liberada.</strong><br>O administrador da plataforma precisa liberar o recurso “Agenda e agendamentos” para este tenant.</div></div>
          <div class="metric-grid tenant-metrics"><article class="metric-card"><div><span>Agendamentos hoje</span><strong>{{ todayAppointments.length }}</strong><small>{{ todayAppointments.filter((i) => i.status === 'CONFIRMED').length }} confirmados</small></div><CalendarDays :size="23" /></article><article class="metric-card green"><div><span>Clientes</span><strong>{{ hasCapability('customers') ? customers.length : '—' }}</strong><small>{{ hasCapability('customers') ? 'módulo liberado' : 'recurso opcional' }}</small></div><Users :size="23" /></article><article class="metric-card violet"><div><span>WhatsApp</span><strong class="metric-word">{{ hasCapability('whatsapp') ? (whatsappStatus === 'CONNECTED' ? 'OK' : 'OFF') : '—' }}</strong><small>{{ hasCapability('whatsapp') ? whatsappStatus : 'recurso opcional' }}</small></div><MessageCircle :size="23" /></article><article class="metric-card orange"><div><span>Avisos pendentes</span><strong>{{ hasCapability('notifications') ? pendingNotifications : '—' }}</strong><small>{{ hasCapability('notifications') ? 'fila de notificações' : 'recurso opcional' }}</small></div><Bell :size="23" /></article></div>
          <div class="dashboard-grid"><article class="panel"><div class="panel-title"><div><h3>Próximos agendamentos</h3><p>O foco operacional da empresa</p></div><button v-if="hasCapability('appointments')" class="btn small" @click="go('agenda')">Abrir agenda</button></div><div class="list"><div v-for="item in upcomingAppointments" :key="item.id" class="row"><span class="time">{{ formatTime(item.starts_at) }}</span><div><strong>{{ item.customer_name }}</strong><small>{{ item.service_name }} • {{ item.professional_name }} • {{ formatDateTime(item.starts_at) }}</small></div><span class="status-pill" :class="statusClass(item.status)">{{ statusLabel(item.status) }}</span></div><div v-if="!upcomingAppointments.length" class="empty-state compact"><CalendarDays :size="36" /><strong>Nenhum atendimento futuro.</strong><button v-if="hasCapability('appointments')" class="btn primary small" @click="go('agenda'); openNew()">Criar agendamento</button></div></div></article><article class="panel quick-panel"><div class="panel-title"><div><h3>Recursos liberados</h3><p>Controlados pelo administrador da plataforma</p></div></div><div class="health"><div v-for="cap in enabledCapabilities.slice(0, 8)" :key="cap"><span><i class="ok"></i>{{ cap.replaceAll('_', ' ') }}</span><strong>Ativo</strong></div><div v-if="!enabledCapabilities.length"><span><i class="warn"></i>Nenhum recurso contratado</span><strong>Aguardando</strong></div></div></article></div>
        </section>

        <section v-else-if="view === 'agenda'" class="view-stack">
          <article v-if="showEditor && editorKind === 'appointment'" class="panel operational-form editor-panel"><div class="editor-title"><div><h3>Novo agendamento</h3><p>Você não precisa cadastrar cliente, serviço ou profissional antes.</p></div><button class="icon-button" @click="closeEditor"><X :size="17" /></button></div><div v-if="canUseCatalogAppointment" class="quick-mode"><button class="btn small" :class="{ active: appointmentMode === 'quick' }" @click="appointmentMode = 'quick'">Agendamento rápido</button><button class="btn small" :class="{ active: appointmentMode === 'catalog' }" @click="appointmentMode = 'catalog'">Usar cadastros</button></div><div v-if="appointmentMode === 'quick' || !canUseCatalogAppointment" class="form-grid four"><label>Cliente<input v-model="quickAppointmentForm.customer_name" placeholder="Nome do cliente" required /></label><label>WhatsApp / telefone<input v-model="quickAppointmentForm.customer_phone" placeholder="5575999999999" /></label><label>Serviço<input v-model="quickAppointmentForm.service_name" placeholder="Atendimento" /></label><label>Duração (min)<input v-model.number="quickAppointmentForm.duration_minutes" type="number" min="5" max="720" /></label><label>Profissional / agenda<input v-model="quickAppointmentForm.professional_name" placeholder="Agenda geral" /></label><label>Início<input v-model="quickAppointmentForm.starts_at" type="datetime-local" required /></label><label>E-mail opcional<input v-model="quickAppointmentForm.customer_email" type="email" /></label><label>Preço opcional<input v-model.number="quickAppointmentForm.price" type="number" min="0" step="0.01" /></label></div><div v-else class="form-grid four"><label>Cliente<select v-model="appointmentForm.customer_id"><option value="">Selecione</option><option v-for="item in customers" :key="item.id" :value="item.id">{{ item.name }}</option></select></label><label>Serviço<select v-model="appointmentForm.service_id"><option value="">Selecione</option><option v-for="item in services.filter((row) => row.active)" :key="item.id" :value="item.id">{{ item.name }}</option></select></label><label>Profissional<select v-model="appointmentForm.professional_id"><option value="">Selecione</option><option v-for="item in professionals" :key="item.id" :value="item.id">{{ item.name }}</option></select></label><label>Início<input v-model="appointmentForm.starts_at" type="datetime-local" /></label></div><div class="actions"><button class="btn" @click="closeEditor">Cancelar</button><button class="btn primary" @click="saveAppointment">Criar e solicitar confirmação</button></div></article>
          <article v-if="showEditor && editorKind === 'reschedule'" class="panel operational-form editor-panel"><div class="editor-title"><div><h3>Reagendar</h3><p>O link anterior será substituído e o cliente precisará confirmar novamente.</p></div><button class="icon-button" @click="closeEditor"><X :size="17" /></button></div><div class="form-grid"><label>Novo início<input v-model="rescheduleForm.starts_at" type="datetime-local" /></label><label v-if="professionals.length">Profissional<select v-model="rescheduleForm.professional_id"><option v-for="item in professionals" :key="item.id" :value="item.id">{{ item.name }}</option></select></label></div><div class="actions"><button class="btn" @click="closeEditor">Cancelar</button><button class="btn primary" @click="saveReschedule">Reagendar</button></div></article>
          <article v-if="showEditor && editorKind === 'business-hour'" class="panel operational-form editor-panel"><div class="editor-title"><div><h3>Faixa de expediente</h3><p>Sem profissional selecionado, vale para a agenda geral.</p></div><button class="icon-button" @click="closeEditor"><X :size="17" /></button></div><div class="form-grid four"><label v-if="professionals.length">Profissional<select v-model="businessHourForm.professional_id"><option value="">Agenda geral</option><option v-for="item in professionals" :key="item.id" :value="item.id">{{ item.name }}</option></select></label><label>Dia<select v-model.number="businessHourForm.day_of_week"><option v-for="(label, index) in dayLabels" :key="index" :value="index">{{ label }}</option></select></label><label>Abre<input v-model="businessHourForm.opens_at" type="time" /></label><label>Fecha<input v-model="businessHourForm.closes_at" type="time" /></label></div><div class="actions"><button class="btn" @click="closeEditor">Cancelar</button><button class="btn primary" @click="saveBusinessHour">Salvar</button></div></article>
          <article v-if="showEditor && editorKind === 'blocked-period'" class="panel operational-form editor-panel"><div class="editor-title"><div><h3>Novo bloqueio</h3><p>Férias, almoço ou indisponibilidade.</p></div><button class="icon-button" @click="closeEditor"><X :size="17" /></button></div><div class="form-grid four"><label v-if="professionals.length">Profissional<select v-model="blockedPeriodForm.professional_id"><option value="">Agenda geral</option><option v-for="item in professionals" :key="item.id" :value="item.id">{{ item.name }}</option></select></label><label>Início<input v-model="blockedPeriodForm.starts_at" type="datetime-local" /></label><label>Fim<input v-model="blockedPeriodForm.ends_at" type="datetime-local" /></label><label>Motivo<input v-model="blockedPeriodForm.reason" /></label></div><button class="btn primary" @click="saveBlockedPeriod">Criar bloqueio</button></article>
          <article class="panel filter-panel"><div class="filter-grid"><label>Data<input v-model="agendaDay" type="date" /></label><label>Status<select v-model="agendaStatus"><option value="">Todos</option><option v-for="(label, key) in statusLabels" :key="key" :value="key">{{ label }}</option></select></label><button class="btn" @click="agendaDay = todayKey()">Hoje</button><button class="btn" @click="agendaDay = ''; agendaStatus = ''">Todos</button></div></article>
          <article class="panel table-panel operational-table"><div class="panel-title"><div><h3>Agenda</h3><p>{{ filteredAppointments.length }} atendimento(s)</p></div></div><div class="responsive-table"><table><thead><tr><th>Horário</th><th>Cliente / serviço</th><th>Profissional</th><th>Status</th><th>Ações</th></tr></thead><tbody><tr v-for="item in filteredAppointments" :key="item.id"><td><strong>{{ formatTime(item.starts_at) }}</strong><small>{{ formatDateTime(item.starts_at) }}</small></td><td><strong>{{ item.customer_name }}</strong><small>{{ item.service_name }}<template v-if="item.customer_phone"> • {{ item.customer_phone }}</template></small></td><td>{{ item.professional_name }}</td><td><span class="status-pill" :class="statusClass(item.status)">{{ statusLabel(item.status) }}</span></td><td><div class="table-actions"><button v-if="['PENDING','AWAITING_CONFIRMATION','RESCHEDULED'].includes(item.status)" class="btn small primary" @click="appointmentAction(item, 'confirm')">Confirmar</button><button v-if="['PENDING','AWAITING_CONFIRMATION','RESCHEDULED'].includes(item.status)" class="btn small" @click="copyConfirmationLink(item)"><Copy :size="13" /> Link</button><button v-if="item.status === 'CONFIRMED'" class="btn small" @click="appointmentAction(item, 'check-in')">Check-in</button><button v-if="item.status === 'CHECKED_IN'" class="btn small" @click="appointmentAction(item, 'start')">Iniciar</button><button v-if="item.status === 'IN_PROGRESS'" class="btn small primary" @click="appointmentAction(item, 'complete')">Concluir</button><button v-if="!finalStatuses.has(item.status)" class="btn small" @click="openReschedule(item)">Reagendar</button><button v-if="!finalStatuses.has(item.status)" class="btn small danger" @click="cancelAppointment(item)">Cancelar</button></div></td></tr></tbody></table></div><div v-if="!filteredAppointments.length" class="empty-state"><CalendarDays :size="42" /><strong>Nenhum agendamento neste filtro.</strong><button class="btn primary" @click="openNew">Novo agendamento</button></div></article>
          <article class="panel table-panel operational-table"><div class="panel-title"><div><h3>Expediente e bloqueios</h3><p>Disponibilidade faz parte da Agenda, não depende do módulo Profissionais.</p></div><div class="table-actions"><button class="btn small" @click="openBusinessHour()"><Plus :size="13" /> Expediente</button><button class="btn small" @click="openBlockedPeriod"><Plus :size="13" /> Bloqueio</button></div></div><div class="responsive-table"><table><thead><tr><th>Dia</th><th>Agenda</th><th>Horário</th><th>Ações</th></tr></thead><tbody><tr v-for="item in businessHours" :key="item.id"><td>{{ dayLabels[item.day_of_week] }}</td><td>{{ item.professional_name || 'Geral' }}</td><td>{{ String(item.opens_at).slice(0,5) }} – {{ String(item.closes_at).slice(0,5) }}</td><td><div class="table-actions"><button class="btn small" @click="openBusinessHour(item)">Editar</button><button class="btn small danger" @click="deleteBusinessHour(item)">Excluir</button></div></td></tr></tbody></table></div><div v-if="blockedPeriods.length" class="blocked-strip"><span v-for="item in blockedPeriods.slice(0,10)" :key="item.id"><strong>{{ item.professional_name || 'Geral' }}</strong> {{ formatDateTime(item.starts_at) }} → {{ formatDateTime(item.ends_at) }} <button @click="deleteBlockedPeriod(item)">×</button></span></div></article>
        </section>

        <section v-else-if="view === 'clientes'" class="view-stack"><article v-if="showEditor && editorKind === 'customer'" class="panel operational-form editor-panel"><div class="editor-title"><h3>{{ editingId ? 'Editar cliente' : 'Novo cliente' }}</h3><button class="icon-button" @click="closeEditor"><X :size="17" /></button></div><div class="form-grid"><label>Nome<input v-model="customerForm.name" /></label><label>Telefone<input v-model="customerForm.phone" /></label><label>E-mail<input v-model="customerForm.email" type="email" /></label></div><label>Observações<textarea v-model="customerForm.notes"></textarea></label><button class="btn primary" @click="saveCustomer">Salvar</button></article><article class="panel table-panel operational-table"><div class="panel-title"><div><h3>Clientes</h3><p>Módulo opcional; a Agenda funciona sem cadastro prévio.</p></div></div><div class="responsive-table"><table><thead><tr><th>Nome</th><th>Telefone</th><th>E-mail</th><th>Ações</th></tr></thead><tbody><tr v-for="item in filteredCustomers" :key="item.id"><td><strong>{{ item.name }}</strong></td><td>{{ item.phone || '—' }}</td><td>{{ item.email || '—' }}</td><td><div class="table-actions"><button class="btn small" @click="editCustomer(item)"><Pencil :size="13" /> Editar</button><button class="btn small danger" @click="deleteCustomer(item)"><Trash2 :size="13" /></button></div></td></tr></tbody></table></div><div v-if="!filteredCustomers.length" class="empty-state"><Users :size="40" /><strong>Nenhum cliente cadastrado.</strong><p>Isso não impede o uso da Agenda.</p></div></article></section>

        <section v-else-if="view === 'servicos'" class="view-stack"><article v-if="showEditor && editorKind === 'service'" class="panel operational-form editor-panel"><div class="editor-title"><h3>{{ editingId ? 'Editar serviço' : 'Novo serviço' }}</h3><button class="icon-button" @click="closeEditor"><X :size="17" /></button></div><div class="form-grid"><label>Nome<input v-model="serviceForm.name" /></label><label>Duração<input v-model.number="serviceForm.duration_minutes" type="number" min="5" /></label><label>Preço<input v-model.number="serviceForm.price" type="number" min="0" step="0.01" /></label></div><button class="btn primary" @click="saveService">Salvar</button></article><section class="entity-grid"><article v-for="item in filteredServices" :key="item.id" class="entity-card"><Wrench /><div class="entity-main"><strong>{{ item.name }}</strong><small>{{ item.duration_minutes }} min • {{ formatMoney(item.price) }}</small><div class="entity-actions"><button class="btn small" @click="editService(item)">Editar</button><button class="btn small" @click="toggleService(item)">{{ item.active ? 'Desativar' : 'Ativar' }}</button><button class="btn small danger" @click="deleteService(item)">Excluir</button></div></div></article></section><div v-if="!filteredServices.length" class="panel empty-state"><Wrench :size="40" /><strong>Nenhum serviço cadastrado.</strong><p>A Agenda rápida permite informar o serviço no momento do agendamento.</p></div></section>

        <section v-else-if="view === 'profissionais'" class="view-stack"><article v-if="showEditor && editorKind === 'professional'" class="panel operational-form editor-panel"><div class="editor-title"><h3>{{ editingId ? 'Editar profissional' : 'Novo profissional' }}</h3><button class="icon-button" @click="closeEditor"><X :size="17" /></button></div><div class="form-grid"><label>Nome<input v-model="professionalForm.name" /></label><label>E-mail<input v-model="professionalForm.email" type="email" /></label><label>Telefone<input v-model="professionalForm.phone" /></label></div><button class="btn primary" @click="saveProfessional">Salvar</button></article><section class="entity-grid"><article v-for="item in filteredProfessionals" :key="item.id" class="entity-card"><div class="entity-avatar">{{ item.name.slice(0,2).toUpperCase() }}</div><div class="entity-main"><strong>{{ item.name }}</strong><small>{{ item.email || item.phone || 'Sem contato' }}</small><div class="entity-actions"><button class="btn small" @click="editProfessional(item)">Editar</button><button class="btn small danger" @click="deleteProfessional(item)">Excluir</button></div></div></article></section><div v-if="!filteredProfessionals.length" class="panel empty-state"><UserRoundCheck :size="40" /><strong>Nenhum profissional cadastrado.</strong><p>A Agenda rápida pode operar com “Agenda geral”.</p></div></section>

        <section v-else-if="view === 'landing'" class="view-stack"><article class="panel operational-form editor-panel"><div><h3>Landing page opcional</h3><p>A página de confirmação da Agenda é independente deste módulo.</p></div><label>Título<input v-model="landingForm.title" /></label><label>Subtítulo<input v-model="landingForm.subtitle" /></label><label>Botão<input v-model="landingForm.cta" /></label><div class="actions"><button class="btn" @click="saveLanding(false)">Salvar rascunho</button><button class="btn primary" @click="saveLanding(true)">Publicar</button></div></article><article class="landing-preview"><p class="eyebrow">Prévia</p><h2>{{ landingForm.title }}</h2><p>{{ landingForm.subtitle }}</p><button class="btn primary">{{ landingForm.cta }}</button></article></section>

        <section v-else-if="view === 'whatsapp'" class="view-stack"><div class="integration-grid whatsapp-grid"><article class="panel whatsapp-card"><div class="panel-title no-pad"><div><p class="eyebrow">Evolution API</p><h3>WhatsApp do tenant</h3><p>{{ whatsapp.instance_name || 'Instância do tenant' }}</p></div><span class="status-pill" :class="statusClass(whatsappStatus)">{{ whatsappStatus }}</span></div><div v-if="whatsappStatus === 'CONNECTED'" class="whatsapp-connected"><CheckCircle2 :size="52" /><strong>WhatsApp conectado</strong><p>Pronto para confirmações, avisos e mensagens.</p></div><div v-else class="qr-stage"><div v-if="whatsappQr" class="qr-image-wrap"><img :src="whatsappQr" alt="QR Code do WhatsApp" /><small>WhatsApp → Aparelhos conectados → Conectar aparelho.</small></div><div v-else class="qr-placeholder"><MessageCircle :size="50" /><strong>{{ whatsappStatus === 'CONNECTING' ? 'Gerando QR Code...' : 'WhatsApp desconectado' }}</strong><p>Clique em conectar. O QR será atualizado automaticamente.</p></div><div v-if="whatsappPairingCode" class="pairing-code"><span>Código de pareamento</span><strong>{{ whatsappPairingCode }}</strong><button class="btn small" @click="copyText(whatsappPairingCode)">Copiar</button></div></div><div class="actions"><button class="btn primary" @click="connectWhatsApp">Conectar / gerar QR Code</button><button class="btn" @click="loadWhatsApp">Atualizar</button></div><details class="diagnostic-details"><summary>Diagnóstico técnico</summary><pre class="status-box">{{ JSON.stringify(whatsapp.provider || whatsapp, null, 2) }}</pre></details></article><form class="panel operational-form message-panel" @submit.prevent="sendMessage"><h3>Mensagem de teste</h3><label>Número<input v-model="messageForm.to" placeholder="5575999999999" required /></label><label>Mensagem<textarea v-model="messageForm.message" required></textarea></label><button class="btn primary" :disabled="whatsappStatus !== 'CONNECTED'">Enviar</button></form></div></section>

        <section v-else-if="view === 'branding'" class="view-stack"><div class="branding-layout"><article class="panel operational-form editor-panel"><h3>Identidade visual</h3><div class="form-grid"><label>Nome público<input v-model="brandingForm.public_name" /></label><label>Slogan<input v-model="brandingForm.slogan" /></label><label>Logo URL<input v-model="brandingForm.logo_url" /></label></div><div class="form-grid"><label>Principal<input v-model="brandingForm.primary_color" type="color" /></label><label>Secundária<input v-model="brandingForm.secondary_color" type="color" /></label><label>Destaque<input v-model="brandingForm.accent_color" type="color" /></label></div><div class="actions"><button class="btn" @click="saveBranding(false)">Salvar</button><button class="btn primary" @click="saveBranding(true)">Publicar</button></div></article><article class="brand-preview-card" :style="{ background: `linear-gradient(135deg,${brandingForm.primary_color},${brandingForm.accent_color})` }"><span>PRÉVIA</span><h2>{{ brandingForm.public_name || appName }}</h2><p>{{ brandingForm.slogan || slogan }}</p></article></div></section>

        <section v-else-if="view === 'dominios'" class="view-stack"><article class="panel domain-panel"><div class="panel-title no-pad"><div><h3>Domínio do tenant</h3><p>DNS e SSL são provisionados pelo Control Plane.</p></div><span class="status-pill confirmed">HTTPS</span></div><div class="domain-card"><Globe2 /><div><strong>{{ tenantSettings?.hostname || window.location.hostname }}</strong><small>{{ tenantSettings?.slug }}</small></div><div class="table-actions"><button class="btn small" @click="copyText(tenantSettings?.hostname || window.location.hostname)"><Copy :size="13" /> Copiar</button><button class="btn small primary" @click="openHostname"><ExternalLink :size="13" /> Abrir</button></div></div></article></section>

        <section v-else-if="view === 'builds'" class="view-stack"><article class="panel distribution-panel"><div class="panel-title no-pad"><div><h3>Aplicativos publicados</h3><p>Instaladores produzidos para este tenant.</p></div><button class="btn" @click="loadDistribution"><RefreshCw :size="14" /> Atualizar</button></div></article><article class="panel table-panel operational-table"><div class="responsive-table"><table><thead><tr><th>Arquivo</th><th>Alvo</th><th>Tipo</th><th>Tamanho</th><th>Data</th><th></th></tr></thead><tbody><tr v-for="item in artifacts" :key="item.id"><td><strong>{{ item.name }}</strong></td><td>{{ item.target }}</td><td>{{ item.artifact_type }}</td><td>{{ formatBytes(item.size_bytes) }}</td><td>{{ formatDateTime(item.created_at) }}</td><td><a v-if="item.download_url" class="btn small primary" :href="item.download_url" target="_blank" rel="noopener"><Download :size="13" /> Baixar</a></td></tr></tbody></table></div><div v-if="!artifacts.length" class="empty-state compact"><PackageCheck :size="38" /><strong>Nenhum artefato publicado.</strong></div></article><article v-if="buildJobs.length" class="panel table-panel operational-table"><div class="panel-title"><div><h3>Histórico de builds</h3></div></div><div class="responsive-table"><table><thead><tr><th>Alvo</th><th>Status</th><th>Origem</th><th>Data</th><th>Erro</th></tr></thead><tbody><tr v-for="job in buildJobs" :key="job.id"><td>{{ job.target }}</td><td><span class="status-pill" :class="statusClass(job.status)">{{ job.status }}</span></td><td>{{ job.source_ref || '—' }}</td><td>{{ formatDateTime(job.created_at) }}</td><td>{{ job.error || '—' }}</td></tr></tbody></table></div></article></section>

        <section v-else-if="view === 'configuracoes'" class="view-stack"><article class="panel settings-overview"><div class="panel-title no-pad"><div><h3>Tenant</h3><p>Informações básicas da operação.</p></div></div><div class="settings-list"><div><strong>Slug</strong><span>{{ tenantSettings?.slug || '—' }}</span></div><div><strong>Hostname</strong><span>{{ tenantSettings?.hostname || '—' }}</span></div><div><strong>Fuso</strong><span>{{ tenantSettings?.timezone || 'America/Bahia' }}</span></div><div><strong>Recursos liberados</strong><span>{{ enabledCapabilities.length }}</span></div></div></article><article v-if="hasCapability('appointments')" class="panel operational-form editor-panel"><h3>Regras da Agenda</h3><div class="form-grid four"><label>Intervalo entre atendimentos (min)<input v-model.number="bookingPrefs.booking_buffer_minutes" type="number" min="0" /></label><label>Antecedência mínima (min)<input v-model.number="bookingPrefs.minimum_notice_minutes" type="number" min="0" /></label><label>Agenda aberta por (dias)<input v-model.number="bookingPrefs.max_advance_days" type="number" min="1" /></label><label>Cancelamento pelo gestor (h)<input v-model.number="bookingPrefs.cancellation_window_hours" type="number" min="0" /></label></div><button class="btn primary" @click="saveBookingPrefs">Salvar regras</button></article><article v-if="hasCapability('appointments')" class="panel operational-form editor-panel"><div><h3>Confirmação do cliente</h3><p>Página pública independente de Landing Page. Se não houver resposta no prazo, o horário é liberado automaticamente.</p></div><label class="checkbox-line"><input v-model="confirmationPrefs.confirmation_required" type="checkbox" /> Exigir confirmação do cliente</label><div class="form-grid"><label>Liberar se não confirmar X min antes<input v-model.number="confirmationPrefs.confirmation_deadline_minutes" type="number" min="0" /></label><label>WhatsApp que recebe a resposta<input v-model="confirmationPrefs.tenant_notification_whatsapp" placeholder="5575999999999" /></label><label>Validade máxima do link (h)<input v-model.number="confirmationPrefs.confirmation_link_ttl_hours" type="number" min="1" /></label></div><div class="confirmation-settings"><div class="operational-form"><label>Título da página<input v-model="confirmationPrefs.confirmation_page_title" /></label><label>Mensagem<textarea v-model="confirmationPrefs.confirmation_page_message"></textarea></label><div class="form-grid"><label>Botão confirmar<input v-model="confirmationPrefs.confirmation_confirm_label" /></label><label>Botão cancelar<input v-model="confirmationPrefs.confirmation_cancel_label" /></label></div></div><div class="confirmation-preview"><span class="eyebrow">Prévia</span><h3>{{ confirmationPrefs.confirmation_page_title }}</h3><p>{{ confirmationPrefs.confirmation_page_message }}</p><div class="preview-actions"><button class="yes">{{ confirmationPrefs.confirmation_confirm_label }}</button><button class="no">{{ confirmationPrefs.confirmation_cancel_label }}</button></div></div></div><div class="info-callout"><Link2 :size="18" /><div><strong>Encurtador externo opcional</strong><p>O motor já existe, mas providers pagos/limitados permanecem desativados. Hoje o Scheduler usa seu próprio link curto <code>/a/&lt;token&gt;</code>.</p></div></div><button class="btn primary" @click="saveConfirmationPrefs">Salvar confirmação e avisos</button></article></section>
      </main>
    </div>
  </div>
</template>
