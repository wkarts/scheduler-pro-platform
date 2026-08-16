<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { applyBranding, loadBrandingManifest, type BrandingManifest } from './branding'

type TabKey = 'home' | 'agenda' | 'clientes' | 'whatsapp' | 'notificacoes' | 'perfil'
type ApiEnvelope<T> = { data: T }
type Appointment = { id: string; customer_id: string; service_id: string; professional_id: string; starts_at: string; ends_at: string; status: string; customer_name: string; service_name: string; professional_name: string }
type Customer = { id: string; name: string; phone?: string | null; email?: string | null }
type Service = { id: string; name: string; duration_minutes: number; price?: number | null; active: boolean }
type Professional = { id: string; name: string; email?: string | null; phone?: string | null }
type NotificationJob = { id: string; template_key: string; recipient: string; scheduled_at: string; status: string; error?: string | null }
type TenantSettings = { slug: string; hostname: string; timezone: string; preferences: Record<string, unknown> }
type QuickAction = { key: TabKey; label: string; icon: string }

const tabs: QuickAction[] = [
  { key: 'home', label: 'Início', icon: '▦' },
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
const actionError = ref('')
const toast = ref('')
const loading = ref(false)
const apiState = ref<'online' | 'offline' | 'checking'>('checking')
const appointments = ref<Appointment[]>([])
const customers = ref<Customer[]>([])
const services = ref<Service[]>([])
const professionals = ref<Professional[]>([])
const notifications = ref<NotificationJob[]>([])
const whatsapp = ref<{ status?: string; instance_name?: string; provider?: unknown }>({})
const tenantSettings = ref<TenantSettings | null>(null)
const showAppointmentForm = ref(false)
const showCustomerForm = ref(false)
const appointmentForm = ref({ customer_id: '', service_id: '', professional_id: '', starts_at: '', ends_at: '' })
const customerForm = ref({ name: '', phone: '', email: '' })
const messageForm = ref({ to: '', message: '' })
const lastSync = ref('Nunca')

const appName = computed(() => manifest.value?.app.public_name || manifest.value?.app.name || 'Scheduler Pro')
const slogan = computed(() => manifest.value?.app.slogan || 'Agenda, clientes, confirmações e WhatsApp no celular.')
const logged = computed(() => Boolean(token.value))
const activeTabLabel = computed(() => tabs.find((tab) => tab.key === activeTab.value)?.label || 'Início')
const nextAppointment = computed(() => appointments.value.find(item => new Date(item.ends_at).getTime() >= Date.now()) || null)
const confirmed = computed(() => appointments.value.filter((item) => item.status === 'CONFIRMED').length)
const pending = computed(() => appointments.value.filter((item) => ['PENDING', 'AWAITING_CONFIRMATION', 'RESCHEDULED'].includes(item.status)).length)

function endpoint(path: string): string { return `${apiUrl}${path}` }
function setTab(tab: TabKey): void { activeTab.value = tab; actionError.value = '' }
function showToast(message: string): void { toast.value = message; window.setTimeout(() => { if (toast.value === message) toast.value = '' }, 3500) }

async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response
  try {
    response = await fetch(endpoint(path), {
      ...init,
      headers: {
        ...(init.body instanceof FormData ? {} : { 'content-type': 'application/json' }),
        ...(token.value ? { authorization: `Bearer ${token.value}` } : {}),
        ...(init.headers || {}),
      },
    })
  } catch { throw new Error('Não foi possível conectar à plataforma. Verifique internet e SSL.') }
  const body = await response.json().catch(() => ({})) as Partial<ApiEnvelope<T>> & { error?: { message?: string } }
  if (!response.ok) throw new Error(body.error?.message || `Falha HTTP ${response.status}`)
  return body.data as T
}

async function boot(): Promise<void> {
  try { manifest.value = await loadBrandingManifest(); applyBranding(manifest.value) } catch { manifest.value = null }
  await checkApi()
  if (token.value) await syncAll()
}

async function checkApi(): Promise<void> {
  apiState.value = 'checking'
  try {
    const response = await fetch(endpoint('/health/ready'), { headers: { accept: 'application/json' } })
    apiState.value = response.ok ? 'online' : 'offline'
  } catch { apiState.value = 'offline' }
}

async function login(): Promise<void> {
  loading.value = true; authError.value = ''
  try {
    const data = await api<{ access_token: string; refresh_token: string }>('/auth/login', { method: 'POST', body: JSON.stringify({ email: email.value, password: password.value }) })
    token.value = data.access_token
    localStorage.setItem('scheduler_pro_mobile_access_token', data.access_token)
    localStorage.setItem('scheduler_pro_mobile_refresh_token', data.refresh_token)
    localStorage.setItem('scheduler_pro_mobile_email', email.value)
    password.value = ''
    await syncAll()
  } catch (error) { authError.value = error instanceof Error ? error.message : 'Não foi possível entrar.' }
  finally { loading.value = false }
}

function logout(): void {
  token.value = ''; appointments.value = []; customers.value = []; services.value = []; professionals.value = []; notifications.value = []
  localStorage.removeItem('scheduler_pro_mobile_access_token'); localStorage.removeItem('scheduler_pro_mobile_refresh_token')
}

async function syncAll(): Promise<void> {
  loading.value = true; actionError.value = ''
  try {
    const [a, c, s, p, n, ts] = await Promise.all([
      api<Appointment[]>('/appointments'), api<Customer[]>('/customers'), api<Service[]>('/services'), api<Professional[]>('/professionals'),
      api<NotificationJob[]>('/notifications?limit=100').catch(() => []), api<TenantSettings>('/settings/tenant').catch(() => null),
    ])
    appointments.value = a; customers.value = c; services.value = s; professionals.value = p; notifications.value = n; tenantSettings.value = ts
    try { whatsapp.value = await api('/integrations/whatsapp/status') } catch { whatsapp.value = { status: 'DISCONNECTED' } }
    apiState.value = 'online'; lastSync.value = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  } catch (error) { apiState.value = 'offline'; actionError.value = error instanceof Error ? error.message : 'Falha ao sincronizar.' }
  finally { loading.value = false }
}

async function createCustomer(): Promise<void> {
  actionError.value = ''
  try {
    await api('/customers', { method: 'POST', body: JSON.stringify({ name: customerForm.value.name, phone: customerForm.value.phone || null, email: customerForm.value.email || null }) })
    customerForm.value = { name: '', phone: '', email: '' }; showCustomerForm.value = false; customers.value = await api('/customers'); showToast('Cliente cadastrado.')
  } catch (error) { actionError.value = error instanceof Error ? error.message : 'Falha ao cadastrar cliente.' }
}

async function createAppointment(): Promise<void> {
  actionError.value = ''
  try {
    await api('/appointments', { method: 'POST', body: JSON.stringify({ ...appointmentForm.value, starts_at: new Date(appointmentForm.value.starts_at).toISOString(), ends_at: new Date(appointmentForm.value.ends_at).toISOString(), source: 'mobile' }) })
    appointmentForm.value = { customer_id: '', service_id: '', professional_id: '', starts_at: '', ends_at: '' }; showAppointmentForm.value = false
    appointments.value = await api('/appointments'); showToast('Agendamento criado.')
  } catch (error) { actionError.value = error instanceof Error ? error.message : 'Falha ao criar agendamento.' }
}

async function appointmentAction(id: string, action: 'confirm' | 'check-in' | 'start' | 'complete' | 'no-show'): Promise<void> {
  actionError.value = ''
  try { await api(`/appointments/${id}/${action}`, { method: 'POST', body: '{}' }); appointments.value = await api('/appointments'); showToast('Agendamento atualizado.') }
  catch (error) { actionError.value = error instanceof Error ? error.message : 'Falha ao atualizar agendamento.' }
}

async function cancelAppointment(id: string): Promise<void> {
  try { await api(`/appointments/${id}/cancel`, { method: 'POST', body: JSON.stringify({ reason: 'Cancelado pelo aplicativo mobile' }) }); appointments.value = await api('/appointments'); showToast('Agendamento cancelado.') }
  catch (error) { actionError.value = error instanceof Error ? error.message : 'Falha ao cancelar.' }
}

async function connectWhatsApp(): Promise<void> {
  try { const result = await api<{ instance_name?: string }>('/integrations/whatsapp/connect', { method: 'POST', body: '{}' }); whatsapp.value = { ...whatsapp.value, ...result, status: 'CONNECTING' }; showToast('Conexão WhatsApp iniciada.') }
  catch (error) { actionError.value = error instanceof Error ? error.message : 'Falha ao conectar WhatsApp.' }
}

async function sendWhatsApp(): Promise<void> {
  try { await api('/integrations/whatsapp/send-text', { method: 'POST', body: JSON.stringify(messageForm.value) }); messageForm.value.message = ''; showToast('Mensagem enviada.') }
  catch (error) { actionError.value = error instanceof Error ? error.message : 'Falha ao enviar mensagem.' }
}

onMounted(() => { void boot() })
</script>

<template>
  <main v-if="!logged" class="mobile-login">
    <section class="login-hero"><span class="app-mark">SP</span><p class="eyebrow">Aplicativo mobile</p><h1>{{ appName }}</h1><p>{{ slogan }}</p></section>
    <form class="mobile-card login-form" @submit.prevent="login"><label>E-mail<input v-model="email" type="email" autocomplete="username" required /></label><label>Senha<input v-model="password" type="password" autocomplete="current-password" required /></label><p v-if="authError" class="form-error">{{ authError }}</p><button class="primary-button" type="submit" :disabled="loading">{{ loading ? 'Conectando...' : 'Entrar' }}</button><small :class="['connection', apiState]">{{ apiState === 'online' ? 'API online' : apiState === 'checking' ? 'verificando' : 'API offline' }}</small></form>
  </main>

  <main v-else class="mobile-app">
    <header class="mobile-top"><div><p class="eyebrow">{{ activeTabLabel }}</p><h1>{{ appName }}</h1></div><button class="round-button" type="button" @click="syncAll">{{ loading ? '…' : '↻' }}</button></header>
    <p v-if="toast" class="floating-toast">{{ toast }}</p><p v-if="actionError" class="mobile-error">{{ actionError }}</p>

    <section v-if="activeTab === 'home'" class="mobile-content">
      <article class="hero-card"><div><span class="connection online">Operação do dia</span><h2>{{ appointments.length }} agendamentos</h2><p>{{ confirmed }} confirmados • {{ pending }} aguardando</p></div><button class="primary-button" type="button" @click="setTab('agenda')">Abrir agenda</button></article>
      <section class="stats-grid"><article><strong>{{ customers.length }}</strong><span>Clientes</span></article><article><strong>{{ notifications.filter(n => n.status === 'PENDING').length }}</strong><span>Avisos</span></article><article><strong>{{ lastSync }}</strong><span>Sync</span></article></section>
      <article class="mobile-card next-card"><p class="eyebrow">Próximo atendimento</p><template v-if="nextAppointment"><h3>{{ nextAppointment.customer_name }}</h3><p>{{ nextAppointment.service_name }} com {{ nextAppointment.professional_name }}</p><time>{{ new Date(nextAppointment.starts_at).toLocaleString() }}</time></template><p v-else class="empty">Nenhum atendimento próximo.</p></article>
      <section class="quick-grid"><button v-for="item in tabs.filter(t => t.key !== 'home')" :key="item.key" @click="setTab(item.key)"><span>{{ item.icon }}</span><strong>{{ item.label }}</strong></button></section>
    </section>

    <section v-else-if="activeTab === 'agenda'" class="mobile-content">
      <article class="mobile-card form-card"><div class="card-title"><div><p class="eyebrow">Agenda</p><h2>Atendimentos</h2></div><button class="mini-button" @click="showAppointmentForm=!showAppointmentForm">{{ showAppointmentForm ? 'Fechar' : 'Novo' }}</button></div>
        <form v-if="showAppointmentForm" class="stack-form" @submit.prevent="createAppointment"><select v-model="appointmentForm.customer_id" required><option value="">Cliente</option><option v-for="c in customers" :key="c.id" :value="c.id">{{ c.name }}</option></select><select v-model="appointmentForm.service_id" required><option value="">Serviço</option><option v-for="s in services.filter(s => s.active)" :key="s.id" :value="s.id">{{ s.name }}</option></select><select v-model="appointmentForm.professional_id" required><option value="">Profissional</option><option v-for="p in professionals" :key="p.id" :value="p.id">{{ p.name }}</option></select><label>Início<input v-model="appointmentForm.starts_at" type="datetime-local" required /></label><label>Fim<input v-model="appointmentForm.ends_at" type="datetime-local" required /></label><button class="primary-button">Salvar agendamento</button></form>
        <div class="appointment-cards"><article v-for="item in appointments" :key="item.id"><div class="appointment-time"><strong>{{ new Date(item.starts_at).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'}) }}</strong><small>{{ new Date(item.starts_at).toLocaleDateString() }}</small></div><div class="appointment-main"><strong>{{ item.customer_name }}</strong><small>{{ item.service_name }} • {{ item.professional_name }}</small><span class="status-pill">{{ item.status }}</span><div class="action-strip"><button v-if="['PENDING','AWAITING_CONFIRMATION','RESCHEDULED'].includes(item.status)" @click="appointmentAction(item.id,'confirm')">Confirmar</button><button v-if="item.status==='CONFIRMED'" @click="appointmentAction(item.id,'check-in')">Check-in</button><button v-if="item.status==='CHECKED_IN'" @click="appointmentAction(item.id,'start')">Iniciar</button><button v-if="item.status==='IN_PROGRESS'" @click="appointmentAction(item.id,'complete')">Concluir</button><button v-if="!['COMPLETED','CANCELLED','NO_SHOW'].includes(item.status)" class="danger-link" @click="cancelAppointment(item.id)">Cancelar</button></div></div></article><p v-if="!appointments.length" class="empty">Sem atendimentos.</p></div>
      </article>
    </section>

    <section v-else-if="activeTab === 'clientes'" class="mobile-content"><article class="mobile-card form-card"><div class="card-title"><div><p class="eyebrow">Clientes</p><h2>{{ customers.length }} cadastrados</h2></div><button class="mini-button" @click="showCustomerForm=!showCustomerForm">{{ showCustomerForm ? 'Fechar' : 'Novo' }}</button></div><form v-if="showCustomerForm" class="stack-form" @submit.prevent="createCustomer"><input v-model="customerForm.name" placeholder="Nome" required /><input v-model="customerForm.phone" inputmode="tel" placeholder="Telefone" /><input v-model="customerForm.email" type="email" placeholder="E-mail" /><button class="primary-button">Cadastrar</button></form><div class="simple-list"><article v-for="c in customers" :key="c.id"><div class="avatar-letter">{{ c.name.slice(0,1).toUpperCase() }}</div><div><strong>{{ c.name }}</strong><small>{{ c.phone || c.email || 'sem contato' }}</small></div></article></div></article></section>

    <section v-else-if="activeTab === 'whatsapp'" class="mobile-content"><article class="mobile-card form-card"><p class="eyebrow">Evolution API</p><h2>WhatsApp do negócio</h2><p class="muted">Instância: {{ whatsapp.instance_name || 'resolvida pelo tenant' }}</p><span :class="['connection', String(whatsapp.status).toUpperCase()==='CONNECTED' ? 'online':'offline']">{{ whatsapp.status || 'DISCONNECTED' }}</span><button class="primary-button full" @click="connectWhatsApp">Conectar / obter QR</button><form class="stack-form" @submit.prevent="sendWhatsApp"><input v-model="messageForm.to" placeholder="Número com DDD" inputmode="tel" required /><textarea v-model="messageForm.message" placeholder="Mensagem de teste" required></textarea><button class="ghost-button">Enviar mensagem</button></form></article></section>

    <section v-else-if="activeTab === 'notificacoes'" class="mobile-content"><article class="mobile-card form-card"><p class="eyebrow">Fila</p><h2>Lembretes e confirmações</h2><div class="simple-list vertical"><article v-for="n in notifications" :key="n.id"><div><strong>{{ n.template_key }}</strong><small>{{ n.recipient }} • {{ new Date(n.scheduled_at).toLocaleString() }}</small></div><span class="status-pill">{{ n.status }}</span></article><p v-if="!notifications.length" class="empty">Nenhuma notificação.</p></div></article></section>

    <section v-else class="mobile-content"><article class="mobile-card module-detail"><p class="eyebrow">Conta</p><h2>{{ email }}</h2><ul><li>Tenant: {{ tenantSettings?.slug || manifest?.tenant?.slug || '—' }}</li><li>Domínio: {{ tenantSettings?.hostname || '—' }}</li><li>Fuso: {{ tenantSettings?.timezone || 'America/Bahia' }}</li><li>API: {{ apiState }}</li><li>Última sync: {{ lastSync }}</li></ul><button class="ghost-button full" @click="logout">Sair</button></article></section>

    <nav class="bottom-nav"><button v-for="item in tabs" :key="item.key" :class="{active:activeTab===item.key}" @click="setTab(item.key)"><span>{{ item.icon }}</span><small>{{ item.label }}</small></button></nav>
  </main>
</template>
