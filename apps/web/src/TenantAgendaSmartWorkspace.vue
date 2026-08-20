<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import {
  CalendarDays,
  CalendarPlus,
  Check,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Copy,
  Pencil,
  RefreshCw,
  RotateCcw,
  Search,
  Trash2,
  UserRound,
  Users,
  X,
} from 'lucide-vue-next'

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
  customer_email?: string | null
  service_name: string
  duration_minutes?: number
  price?: number | null
  professional_name: string
}
type Customer = { id: string; name: string; phone?: string | null; email?: string | null }
type Service = { id: string; name: string; duration_minutes: number; price?: number | null; active: boolean }
type Professional = { id: string; name: string; email?: string | null; phone?: string | null }
type Lookup = { customers: Customer[]; services: Service[]; professionals: Professional[] }
type Envelope<T> = { data: T; error?: { message?: string; code?: string } }
type EditorMode = '' | 'new' | 'edit' | 'reuse'

const visible = ref(window.location.hash === '#agenda')
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const toast = ref('')
const appointments = ref<Appointment[]>([])
const customers = ref<Customer[]>([])
const services = ref<Service[]>([])
const professionals = ref<Professional[]>([])
const query = ref('')
const selectedDay = ref(todayKey())
const selectedStatus = ref('')
const selectedProfessionalFilter = ref('')
const editorMode = ref<EditorMode>('')
const editing = ref<Appointment | null>(null)
const customerMode = ref<'existing' | 'new'>('existing')
const customerSearch = ref('')
const serviceSearch = ref('')
const professionalSearch = ref('')
const selectedCustomerId = ref('')
const selectedServiceId = ref('')
const selectedProfessionalId = ref('')
const form = ref({ customer_name: '', customer_phone: '', customer_email: '', starts_at: '' })

const terminal = new Set(['COMPLETED', 'CANCELLED', 'NO_SHOW'])
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

const statusOptions = Object.entries(statusLabels)
const filteredCustomers = computed(() => filterEntities(customers.value, customerSearch.value, (item) => `${item.name} ${item.phone || ''} ${item.email || ''}`))
const filteredServices = computed(() => filterEntities(services.value.filter((item) => item.active !== false), serviceSearch.value, (item) => `${item.name} ${item.duration_minutes}`))
const filteredProfessionals = computed(() => filterEntities(professionals.value, professionalSearch.value, (item) => `${item.name} ${item.email || ''} ${item.phone || ''}`))
const selectedDate = computed(() => selectedDay.value ? new Date(`${selectedDay.value}T12:00:00`) : new Date())
const monthTitle = computed(() => selectedDate.value.toLocaleDateString('pt-BR', { month: 'long', year: 'numeric' }))
const selectedDateTitle = computed(() => selectedDay.value ? selectedDate.value.toLocaleDateString('pt-BR', { weekday: 'long', day: '2-digit', month: 'long', year: 'numeric' }) : 'Todos os dias')
const dayStrip = computed(() => {
  const base = selectedDay.value ? new Date(`${selectedDay.value}T12:00:00`) : new Date()
  return Array.from({ length: 7 }, (_, index) => {
    const date = new Date(base)
    date.setDate(base.getDate() + index - 3)
    const key = localDateKey(date)
    return {
      key,
      weekday: date.toLocaleDateString('pt-BR', { weekday: 'short' }).replace('.', ''),
      day: String(date.getDate()).padStart(2, '0'),
      month: date.toLocaleDateString('pt-BR', { month: 'short' }).replace('.', ''),
      count: appointments.value.filter((item) => dayKey(item.starts_at) === key).length,
      today: key === todayKey(),
    }
  })
})
const visibleAppointments = computed(() => {
  const needle = query.value.trim().toLocaleLowerCase('pt-BR')
  return [...appointments.value]
    .filter((item) => !selectedDay.value || dayKey(item.starts_at) === selectedDay.value)
    .filter((item) => !selectedStatus.value || item.status === selectedStatus.value)
    .filter((item) => !selectedProfessionalFilter.value || item.professional_id === selectedProfessionalFilter.value)
    .filter((item) => !needle || `${item.customer_name} ${item.customer_phone || ''} ${item.service_name} ${item.professional_name}`.toLocaleLowerCase('pt-BR').includes(needle))
    .sort((a, b) => +new Date(a.starts_at) - +new Date(b.starts_at))
})

function token(): string { return localStorage.getItem('scheduler_pro_access_token') || '' }
function localDateKey(value: Date): string { const offset = value.getTimezoneOffset() * 60_000; return new Date(value.getTime() - offset).toISOString().slice(0, 10) }
function todayKey(): string { return localDateKey(new Date()) }
function dayKey(value: string): string { return localDateKey(new Date(value)) }
function localInput(value: string): string { const date = new Date(value); date.setMinutes(date.getMinutes() - date.getTimezoneOffset()); return date.toISOString().slice(0, 16) }
function formatTime(value: string): string { return new Date(value).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }) }
function formatDate(value: string): string { return new Date(value).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric' }) }
function statusLabel(value: string): string { return statusLabels[value] || value }
function statusClass(value: string): string { return value.toLowerCase().replace(/[^a-z0-9]+/g, '-') }
function filterEntities<T>(items: T[], needle: string, text: (item: T) => string): T[] { const normalized = needle.trim().toLocaleLowerCase('pt-BR'); return items.filter((item) => !normalized || text(item).toLocaleLowerCase('pt-BR').includes(normalized)).slice(0, 80) }
function flash(message: string): void { toast.value = message; window.setTimeout(() => { if (toast.value === message) toast.value = '' }, 3500) }
function shiftDay(delta: number): void { const date = selectedDay.value ? new Date(`${selectedDay.value}T12:00:00`) : new Date(); date.setDate(date.getDate() + delta); selectedDay.value = localDateKey(date) }
function setToday(): void { selectedDay.value = todayKey() }

async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    ...init,
    headers: {
      Accept: 'application/json',
      ...(init.body ? { 'content-type': 'application/json' } : {}),
      Authorization: `Bearer ${token()}`,
      ...(init.headers || {}),
    },
  })
  const payload = await response.json().catch(() => ({})) as Partial<Envelope<T>>
  if (!response.ok) throw new Error(payload.error?.message || `Não foi possível concluir a operação (${response.status}).`)
  return payload.data as T
}

async function loadLookups(): Promise<void> {
  const data = await api<Lookup>('/appointments/smart/lookups')
  customers.value = data.customers || []
  services.value = data.services || []
  professionals.value = data.professionals || []
}

async function load(): Promise<void> {
  if (!visible.value) return
  loading.value = true
  error.value = ''
  try {
    const [items] = await Promise.all([
      api<Appointment[]>('/appointments'),
      loadLookups(),
    ])
    appointments.value = items
  } catch (exc) {
    error.value = exc instanceof Error ? exc.message : 'Falha ao carregar a agenda.'
  } finally {
    loading.value = false
  }
}

function resetEditor(): void {
  editorMode.value = ''
  editing.value = null
  customerMode.value = 'existing'
  customerSearch.value = ''
  serviceSearch.value = ''
  professionalSearch.value = ''
  selectedCustomerId.value = ''
  selectedServiceId.value = ''
  selectedProfessionalId.value = ''
  form.value = { customer_name: '', customer_phone: '', customer_email: '', starts_at: '' }
}
function openNew(): void {
  resetEditor()
  editorMode.value = 'new'
  selectedServiceId.value = services.value.find((item) => item.active !== false)?.id || ''
  selectedProfessionalId.value = professionals.value[0]?.id || ''
  form.value.starts_at = `${selectedDay.value || todayKey()}T08:00`
}
function openEdit(item: Appointment): void {
  resetEditor()
  editorMode.value = 'edit'
  editing.value = item
  selectedCustomerId.value = item.customer_id
  selectedServiceId.value = item.service_id
  selectedProfessionalId.value = item.professional_id
  form.value = { customer_name: item.customer_name, customer_phone: item.customer_phone || '', customer_email: item.customer_email || '', starts_at: localInput(item.starts_at) }
}
function openReuse(item: Appointment): void {
  resetEditor()
  editorMode.value = 'reuse'
  editing.value = item
  selectedServiceId.value = item.service_id
  selectedProfessionalId.value = item.professional_id
  form.value.starts_at = localInput(item.starts_at)
}
function chooseCustomer(id: string): void {
  selectedCustomerId.value = id
  const item = customers.value.find((row) => row.id === id)
  if (item) form.value = { ...form.value, customer_name: item.name, customer_phone: item.phone || '', customer_email: item.email || '' }
}

async function saveEditor(): Promise<void> {
  error.value = ''
  if (!form.value.starts_at) { error.value = 'Informe a data e o horário.'; return }
  if (customerMode.value === 'existing' && !selectedCustomerId.value) { error.value = 'Selecione um cliente existente ou escolha “Novo cliente”.'; return }
  if (customerMode.value === 'new' && !form.value.customer_name.trim()) { error.value = 'Informe o nome do novo cliente.'; return }
  saving.value = true
  try {
    if (editorMode.value === 'edit' && editing.value) {
      await api(`/appointments/${editing.value.id}/edit`, {
        method: 'PATCH',
        body: JSON.stringify({
          customer_id: selectedCustomerId.value || editing.value.customer_id,
          service_id: selectedServiceId.value || editing.value.service_id,
          professional_id: selectedProfessionalId.value || editing.value.professional_id,
          starts_at: new Date(form.value.starts_at).toISOString(),
          reason: 'Agendamento editado pelo gestor',
        }),
      })
      flash('Agendamento atualizado.')
    } else {
      const service = services.value.find((item) => item.id === selectedServiceId.value)
      const professional = professionals.value.find((item) => item.id === selectedProfessionalId.value)
      const payload = {
        customer_id: customerMode.value === 'existing' ? selectedCustomerId.value : null,
        customer_name: form.value.customer_name.trim() || 'Cliente',
        customer_phone: form.value.customer_phone.trim() || null,
        customer_email: form.value.customer_email.trim() || null,
        service_id: selectedServiceId.value || null,
        service_name: service?.name || editing.value?.service_name || 'Atendimento',
        duration_minutes: service?.duration_minutes || editing.value?.duration_minutes || 30,
        price: service?.price ?? editing.value?.price ?? null,
        professional_id: selectedProfessionalId.value || null,
        professional_name: professional?.name || editing.value?.professional_name || 'Agenda geral',
      }
      if (editorMode.value === 'reuse' && editing.value) {
        await api(`/appointments/${editing.value.id}/reuse`, { method: 'POST', body: JSON.stringify(payload) })
        flash('Horário reutilizado com o novo cliente.')
      } else {
        await api('/appointments/quick', { method: 'POST', body: JSON.stringify({ ...payload, starts_at: new Date(form.value.starts_at).toISOString(), source: 'tenant-web-smart' }) })
        flash('Agendamento criado.')
      }
    }
    resetEditor()
    await load()
  } catch (exc) {
    error.value = exc instanceof Error ? exc.message : 'Falha ao salvar agendamento.'
  } finally {
    saving.value = false
  }
}

async function action(item: Appointment, operation: 'confirm' | 'check-in' | 'start' | 'complete' | 'no-show'): Promise<void> {
  saving.value = true
  error.value = ''
  try { await api(`/appointments/${item.id}/${operation}`, { method: 'POST', body: '{}' }); await load(); flash('Agendamento atualizado.') }
  catch (exc) { error.value = exc instanceof Error ? exc.message : 'Falha ao atualizar.' }
  finally { saving.value = false }
}
async function cancel(item: Appointment): Promise<void> {
  if (!window.confirm(`Cancelar o agendamento de ${item.customer_name}?`)) return
  saving.value = true
  error.value = ''
  try { await api(`/appointments/${item.id}/cancel`, { method: 'POST', body: JSON.stringify({ reason: 'Cancelado pelo gestor' }) }); await load(); flash('Agendamento cancelado.') }
  catch (exc) { error.value = exc instanceof Error ? exc.message : 'Falha ao cancelar.' }
  finally { saving.value = false }
}
async function remove(item: Appointment): Promise<void> {
  if (!window.confirm(`Excluir definitivamente o registro de ${item.customer_name}?`)) return
  saving.value = true
  error.value = ''
  try { await api(`/appointments/${item.id}/permanent`, { method: 'DELETE' }); await load(); flash('Registro excluído com auditoria preservada.') }
  catch (exc) { error.value = exc instanceof Error ? exc.message : 'Falha ao excluir.' }
  finally { saving.value = false }
}
async function copyLink(item: Appointment): Promise<void> {
  try {
    const data = await api<{ enabled: boolean; request?: { url?: string } | null }>(`/appointment-confirmations/${item.id}`)
    if (!data.request?.url) throw new Error('Link de confirmação indisponível para este agendamento.')
    await navigator.clipboard.writeText(data.request.url)
    flash('Link de confirmação copiado.')
  } catch (exc) { error.value = exc instanceof Error ? exc.message : 'Falha ao copiar link.' }
}

function openAdvanced(): void { document.querySelector<HTMLButtonElement>('.sp-advanced-action')?.click() }
function openCalendar(): void { window.location.hash = 'calendar' }
function syncHash(): void {
  visible.value = window.location.hash === '#agenda'
  document.body.classList.toggle('sp-smart-agenda-open', visible.value)
  if (visible.value) void load()
  else resetEditor()
}

watch(visible, (value) => document.body.classList.toggle('sp-smart-agenda-open', value), { immediate: true })
onMounted(() => { window.addEventListener('hashchange', syncHash); syncHash() })
onUnmounted(() => { window.removeEventListener('hashchange', syncHash); document.body.classList.remove('sp-smart-agenda-open') })
</script>

<template>
  <Teleport v-if="visible" to=".tenant-console .main-content">
    <section class="sp-smart-agenda">
      <header class="sp-smart-head">
        <div>
          <span>Agenda operacional</span>
          <h2>Atendimentos</h2>
          <p>Pesquise, crie, edite, reagende e acompanhe o dia em uma única tela.</p>
        </div>
        <div class="sp-smart-head-actions">
          <button @click="openCalendar"><CalendarDays :size="16" /> Calendário mensal</button>
          <button @click="openAdvanced"><CalendarPlus :size="16" /> Recorrência / permuta</button>
          <button class="primary" @click="openNew"><CalendarPlus :size="16" /> Novo</button>
        </div>
      </header>

      <p v-if="toast" class="sp-smart-success"><Check :size="16" /> {{ toast }}</p>
      <p v-if="error" class="sp-smart-error">{{ error }}</p>

      <section class="sp-smart-toolbar">
        <label class="search"><Search :size="16" /><input v-model="query" placeholder="Cliente, telefone, serviço ou profissional" /></label>
        <select v-model="selectedProfessionalFilter"><option value="">Todos os profissionais</option><option v-for="item in professionals" :key="item.id" :value="item.id">{{ item.name }}</option></select>
        <select v-model="selectedStatus"><option value="">Todos os status</option><option v-for="[key, label] in statusOptions" :key="key" :value="key">{{ label }}</option></select>
        <button title="Atualizar" @click="load"><RefreshCw :size="16" :class="{ spin: loading }" /></button>
      </section>

      <section class="sp-period-card">
        <div class="sp-period-heading">
          <button title="Dia anterior" @click="shiftDay(-1)"><ChevronLeft :size="18" /></button>
          <div><span>{{ monthTitle }}</span><strong>{{ selectedDateTitle }}</strong></div>
          <button title="Próximo dia" @click="shiftDay(1)"><ChevronRight :size="18" /></button>
        </div>
        <div class="sp-period-actions">
          <input v-model="selectedDay" type="date" aria-label="Selecionar data" />
          <button @click="setToday">Hoje</button>
          <button :class="{ active: !selectedDay }" @click="selectedDay = ''">Todos os dias</button>
        </div>
      </section>

      <section class="sp-day-strip">
        <button v-for="day in dayStrip" :key="day.key" :class="{ active: selectedDay === day.key, today: day.today }" @click="selectedDay = day.key">
          <span>{{ day.weekday }}</span>
          <strong>{{ day.day }}</strong>
          <em>{{ day.month }}</em>
          <small>{{ day.count }} agenda(s)</small>
        </button>
      </section>

      <section v-if="editorMode" class="sp-smart-editor">
        <header>
          <div><span>{{ editorMode === 'edit' ? 'Editar' : editorMode === 'reuse' ? 'Reutilizar horário' : 'Novo agendamento' }}</span><h3>{{ editing?.customer_name || 'Agendamento rápido e inteligente' }}</h3></div>
          <button @click="resetEditor"><X :size="18" /></button>
        </header>
        <div v-if="editorMode !== 'edit'" class="sp-segment"><button :class="{ active: customerMode === 'existing' }" @click="customerMode = 'existing'">Cliente existente</button><button :class="{ active: customerMode === 'new' }" @click="customerMode = 'new'">Novo cliente</button></div>
        <div v-if="customerMode === 'existing' || editorMode === 'edit'" class="sp-smart-field-group">
          <label>Localizar cliente<input v-model="customerSearch" placeholder="Nome, telefone ou e-mail" /></label>
          <div class="sp-choice-list"><button v-for="item in filteredCustomers" :key="item.id" :class="{ selected: selectedCustomerId === item.id }" @click="chooseCustomer(item.id)"><Users :size="16" /><span><strong>{{ item.name }}</strong><small>{{ item.phone || item.email || 'Sem contato' }}</small></span></button><p v-if="!filteredCustomers.length">Nenhum cliente encontrado.</p></div>
        </div>
        <div v-else class="sp-smart-grid"><label>Nome<input v-model="form.customer_name" /></label><label>Telefone / WhatsApp<input v-model="form.customer_phone" /></label><label>E-mail<input v-model="form.customer_email" type="email" /></label></div>
        <div class="sp-smart-grid">
          <label>Serviço<input v-model="serviceSearch" placeholder="Pesquisar serviço" /><select v-model="selectedServiceId"><option value="">Atendimento rápido</option><option v-for="item in filteredServices" :key="item.id" :value="item.id">{{ item.name }} · {{ item.duration_minutes }} min</option></select></label>
          <label>Profissional<input v-model="professionalSearch" placeholder="Pesquisar profissional" /><select v-model="selectedProfessionalId"><option value="">Agenda geral</option><option v-for="item in filteredProfessionals" :key="item.id" :value="item.id">{{ item.name }}</option></select></label>
          <label>Data e hora<input v-model="form.starts_at" type="datetime-local" /></label>
        </div>
        <footer><button @click="resetEditor">Cancelar</button><button class="primary" :disabled="saving" @click="saveEditor">{{ saving ? 'Salvando...' : editorMode === 'edit' ? 'Salvar alterações' : editorMode === 'reuse' ? 'Reutilizar horário' : 'Criar agendamento' }}</button></footer>
      </section>

      <div v-if="loading && !appointments.length" class="sp-smart-empty"><RefreshCw class="spin" /><strong>Carregando agenda...</strong></div>
      <div v-else-if="!visibleAppointments.length" class="sp-smart-empty"><CalendarDays :size="38" /><strong>Nenhum agendamento neste filtro.</strong><button @click="openNew">Criar agendamento</button></div>

      <section v-else class="sp-smart-list">
        <article v-for="item in visibleAppointments" :key="item.id" class="sp-smart-item">
          <div class="sp-smart-time"><strong>{{ formatTime(item.starts_at) }}</strong><span>{{ formatDate(item.starts_at) }}</span></div>
          <div class="sp-smart-main"><div class="title"><strong>{{ item.customer_name }}</strong><span :class="['status', statusClass(item.status)]">{{ statusLabel(item.status) }}</span></div><p>{{ item.service_name }} · {{ item.duration_minutes || 30 }} min</p><small><UserRound :size="13" /> {{ item.professional_name }}</small></div>
          <div class="sp-smart-actions">
            <button v-if="!terminal.has(item.status)" @click="openEdit(item)"><Pencil :size="14" /> Editar</button>
            <button v-if="['PENDING', 'AWAITING_CONFIRMATION', 'RESCHEDULED'].includes(item.status)" @click="copyLink(item)"><Copy :size="14" /> Link</button>
            <button v-if="['PENDING', 'AWAITING_CONFIRMATION', 'RESCHEDULED'].includes(item.status)" @click="action(item, 'confirm')"><Check :size="14" /> Confirmar</button>
            <button v-if="item.status === 'CONFIRMED'" @click="action(item, 'check-in')"><ChevronRight :size="14" /> Check-in</button>
            <button v-if="item.status === 'CHECKED_IN'" @click="action(item, 'start')"><Clock3 :size="14" /> Iniciar</button>
            <button v-if="item.status === 'IN_PROGRESS'" @click="action(item, 'complete')"><Check :size="14" /> Concluir</button>
            <button v-if="!terminal.has(item.status)" class="danger" @click="cancel(item)"><X :size="14" /> Cancelar</button>
            <button v-if="['CANCELLED', 'NO_SHOW'].includes(item.status)" @click="openReuse(item)"><RotateCcw :size="14" /> Reutilizar</button>
            <button v-if="terminal.has(item.status)" class="danger ghost" @click="remove(item)"><Trash2 :size="14" /> Excluir</button>
          </div>
        </article>
      </section>
    </section>
  </Teleport>
</template>

<style>
body.sp-smart-agenda-open .tenant-console .main-content > .view-stack,
.tenant-console .main-content:has(> .sp-smart-agenda) > .view-stack { display: none !important; }
body.sp-smart-agenda-open .tenant-console .page-actions { display: none !important; }
.sp-smart-agenda{display:grid;gap:14px}.sp-smart-head{display:flex;justify-content:space-between;gap:18px;align-items:flex-start;padding:20px 22px;border:1px solid #dfe7f1;border-radius:20px;background:#fff;box-shadow:0 10px 28px rgba(26,47,83,.06)}.sp-smart-head span{display:block;color:#2563eb;text-transform:uppercase;letter-spacing:.12em;font-size:10px;font-weight:900}.sp-smart-head h2{margin:4px 0;color:#10213b;font-size:24px}.sp-smart-head p{margin:0;color:#718096;font-size:12px}.sp-smart-head-actions{display:flex;flex-wrap:wrap;gap:8px}.sp-smart-head-actions button,.sp-smart-editor footer button,.sp-smart-empty button,.sp-period-card button{border:1px solid #dfe7f1;background:#fff;border-radius:11px;padding:9px 13px;display:inline-flex;align-items:center;gap:7px;color:#29405f;font-weight:850}.sp-smart-head-actions .primary,.sp-smart-editor footer .primary{background:linear-gradient(135deg,#2563eb,#06b6d4);border-color:#2563eb;color:#fff}.sp-smart-toolbar{display:grid;grid-template-columns:minmax(280px,1fr) minmax(180px,.45fr) minmax(180px,.4fr) 44px;gap:9px;padding:14px;border:1px solid #dfe7f1;border-radius:17px;background:#fff}.sp-smart-toolbar .search{display:flex;align-items:center;gap:8px;border:1px solid #dfe7f1;border-radius:11px;padding:0 12px}.sp-smart-toolbar input,.sp-smart-toolbar select,.sp-smart-editor input,.sp-smart-editor select,.sp-period-card input{height:44px;border:1px solid #dfe7f1;border-radius:11px;padding:0 12px;background:#fff;color:#203550;min-width:0}.sp-smart-toolbar .search input{border:0;padding:0;outline:0;width:100%}.sp-smart-toolbar>button{border:1px solid #dfe7f1;border-radius:11px;background:#fff;display:grid;place-items:center;color:#34506f}.sp-period-card{display:flex;justify-content:space-between;gap:14px;align-items:center;padding:15px 17px;border:1px solid #dfe7f1;border-radius:17px;background:#fff}.sp-period-heading{display:flex;align-items:center;gap:12px}.sp-period-heading>div{display:grid;gap:2px;min-width:260px;text-align:center}.sp-period-heading span{text-transform:capitalize;color:#2563eb;font-weight:900;font-size:12px}.sp-period-heading strong{color:#152b48;font-size:14px;text-transform:capitalize}.sp-period-heading button{width:40px;height:40px;padding:0;justify-content:center}.sp-period-actions{display:flex;gap:8px;align-items:center}.sp-period-actions input{height:40px}.sp-period-actions button.active{background:#eff6ff;border-color:#93c5fd;color:#1d4ed8}.sp-day-strip{display:grid;grid-template-columns:repeat(7,1fr);gap:8px}.sp-day-strip button{border:1px solid #dfe7f1;background:#fff;border-radius:14px;padding:10px 7px;color:#64748b;display:grid;gap:2px;text-align:center}.sp-day-strip button span{font-size:10px;text-transform:uppercase;font-weight:850}.sp-day-strip button strong{font-size:18px;color:#203550}.sp-day-strip button em{font-size:10px;font-style:normal;text-transform:uppercase}.sp-day-strip button small{font-size:9px}.sp-day-strip button.today{box-shadow:inset 0 0 0 1px #38bdf8}.sp-day-strip button.active{border-color:#2563eb;background:#eff6ff}.sp-smart-editor{border:1px solid #cfe0f4;background:#fff;border-radius:18px;padding:17px;box-shadow:0 12px 34px rgba(37,99,235,.09);display:grid;gap:14px}.sp-smart-editor>header{display:flex;justify-content:space-between;gap:14px}.sp-smart-editor>header span{display:block;color:#2563eb;font-size:10px;text-transform:uppercase;font-weight:900;letter-spacing:.1em}.sp-smart-editor h3{margin:4px 0;color:#142844}.sp-smart-editor>header>button{border:1px solid #dfe7f1;background:#fff;border-radius:10px;width:38px;height:38px;display:grid;place-items:center}.sp-segment{display:grid;grid-template-columns:1fr 1fr;max-width:430px;border:1px solid #dfe7f1;border-radius:12px;padding:4px}.sp-segment button{border:0;background:transparent;border-radius:9px;padding:9px;font-weight:850;color:#64748b}.sp-segment .active{background:#eff6ff;color:#1d4ed8}.sp-smart-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.sp-smart-grid label,.sp-smart-field-group label{display:grid;gap:6px;color:#304761;font-size:11px;font-weight:850}.sp-smart-grid label input:first-child:not(:last-child){margin-bottom:6px}.sp-choice-list{display:flex;gap:8px;overflow-x:auto;padding:2px 0 5px}.sp-choice-list button{min-width:190px;border:1px solid #dfe7f1;background:#fff;border-radius:12px;padding:10px;display:flex;align-items:center;gap:9px;text-align:left;color:#314a68}.sp-choice-list button.selected{border-color:#2563eb;background:#eff6ff}.sp-choice-list span{display:grid}.sp-choice-list small{color:#8391a4}.sp-smart-editor footer{display:flex;justify-content:flex-end;gap:8px}.sp-smart-list{display:grid;gap:9px}.sp-smart-item{display:grid;grid-template-columns:105px minmax(210px,1fr) minmax(300px,auto);gap:14px;align-items:center;border:1px solid #dfe7f1;border-radius:16px;background:#fff;padding:13px 14px}.sp-smart-time{display:grid}.sp-smart-time strong{font-size:20px;color:#1d4ed8}.sp-smart-time span{color:#8795a8;font-size:10px}.sp-smart-main .title{display:flex;align-items:center;gap:9px;flex-wrap:wrap}.sp-smart-main .title>strong{font-size:14px;color:#142844}.sp-smart-main p{margin:4px 0;color:#687990;font-size:11px}.sp-smart-main small{display:flex;align-items:center;gap:5px;color:#8090a4}.sp-smart-main .status{border-radius:999px;padding:4px 8px;background:#eef2f7;color:#52647a;font-size:9px;font-weight:900}.sp-smart-main .status.confirmed,.sp-smart-main .status.completed{background:#dcfce7;color:#166534}.sp-smart-main .status.cancelled,.sp-smart-main .status.no-show{background:#fee2e2;color:#991b1b}.sp-smart-main .status.awaiting-confirmation,.sp-smart-main .status.pending,.sp-smart-main .status.rescheduled{background:#fef3c7;color:#92400e}.sp-smart-actions{display:flex;justify-content:flex-end;flex-wrap:wrap;gap:6px}.sp-smart-actions button{border:1px solid #dfe7f1;background:#fff;border-radius:9px;padding:7px 9px;display:inline-flex;align-items:center;gap:5px;font-size:10px;font-weight:850;color:#304761}.sp-smart-actions button.danger{border-color:#fecaca;color:#b91c1c}.sp-smart-actions button.ghost{background:#fff7f7}.sp-smart-empty{min-height:180px;border:1px dashed #cbd7e6;border-radius:18px;display:grid;place-items:center;align-content:center;gap:9px;background:#fff;color:#718096;text-align:center}.sp-smart-success,.sp-smart-error{margin:0;padding:11px 13px;border-radius:12px;display:flex;align-items:center;gap:7px}.sp-smart-success{background:#ecfdf5;border:1px solid #bbf7d0;color:#166534}.sp-smart-error{background:#fef2f2;border:1px solid #fecaca;color:#991b1b}.spin{animation:sp-smart-spin .8s linear infinite}@keyframes sp-smart-spin{to{transform:rotate(360deg)}}
@media(max-width:900px){.sp-smart-head{display:grid}.sp-smart-head-actions{display:grid;grid-template-columns:1fr 1fr}.sp-smart-head-actions .primary{grid-column:1/-1}.sp-smart-toolbar{grid-template-columns:1fr 1fr}.sp-smart-toolbar .search{grid-column:1/-1}.sp-period-card{display:grid}.sp-period-heading{justify-content:space-between}.sp-period-heading>div{min-width:0;flex:1}.sp-period-actions{display:grid;grid-template-columns:1fr 1fr}.sp-period-actions input{grid-column:1/-1;width:100%;box-sizing:border-box}.sp-day-strip{grid-template-columns:repeat(4,1fr);overflow:visible}.sp-smart-grid{grid-template-columns:1fr}.sp-smart-item{grid-template-columns:78px 1fr}.sp-smart-actions{grid-column:1/-1;justify-content:flex-start;border-top:1px solid #eef2f7;padding-top:10px}.sp-smart-actions button{min-height:40px}.sp-choice-list{display:grid;overflow:visible}.sp-choice-list button{min-width:0;width:100%}.sp-smart-editor footer{display:grid;grid-template-columns:1fr 1fr}.sp-smart-editor footer button{justify-content:center}.sp-smart-head-actions button{justify-content:center}.sp-period-heading strong{font-size:12px}}
@media(max-width:560px){.sp-smart-head{padding:16px}.sp-smart-head h2{font-size:21px}.sp-smart-toolbar{grid-template-columns:1fr}.sp-smart-toolbar .search{grid-column:auto}.sp-day-strip{grid-template-columns:repeat(2,1fr)}.sp-period-actions{grid-template-columns:1fr}.sp-period-actions input{grid-column:auto}.sp-smart-item{grid-template-columns:1fr}.sp-smart-time{display:flex;gap:8px;align-items:baseline}.sp-smart-actions{grid-column:auto}.sp-smart-actions button{flex:1 1 calc(50% - 6px);justify-content:center}.sp-segment{max-width:none}.sp-smart-editor footer{grid-template-columns:1fr}}
</style>
