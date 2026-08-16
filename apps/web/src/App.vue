<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { Bell, CalendarClock, CalendarDays, Download, Globe2, LayoutDashboard, Link2, LogOut, Menu, MessageCircle, MonitorSmartphone, PackageCheck, Palette, Plus, Search, Settings, Smartphone, UserRoundCheck, Users, Wrench } from 'lucide-vue-next'
import { applyBranding, loadBrandingManifest, type BrandingManifest } from './branding'

type ViewKey = 'dashboard' | 'agenda' | 'clientes' | 'servicos' | 'profissionais' | 'landing' | 'whatsapp' | 'branding' | 'dominios' | 'builds' | 'configuracoes'
type InstallPromptEvent = Event & { prompt: () => Promise<void>; userChoice: Promise<{ outcome: 'accepted' | 'dismissed'; platform: string }> }

type ApiEnvelope<T> = { data: T }
type Appointment = { id: string; starts_at: string; ends_at: string; status: string; customer_name: string; service_name: string; professional_name: string }

const navItems = [
  { key: 'dashboard', label: 'Visão geral', icon: LayoutDashboard },
  { key: 'agenda', label: 'Agenda', icon: CalendarDays },
  { key: 'clientes', label: 'Clientes', icon: Users },
  { key: 'servicos', label: 'Serviços', icon: Wrench },
  { key: 'profissionais', label: 'Profissionais', icon: UserRoundCheck },
  { key: 'landing', label: 'Landing page', icon: Globe2 },
  { key: 'whatsapp', label: 'WhatsApp API', icon: MessageCircle },
  { key: 'branding', label: 'Marca e aplicativo', icon: Palette },
  { key: 'dominios', label: 'Domínios', icon: Link2 },
  { key: 'builds', label: 'Builds e artefatos', icon: PackageCheck },
  { key: 'configuracoes', label: 'Configurações', icon: Settings },
] as const

const view = ref<ViewKey>(hashToView())
const collapsed = ref(false)
const mobileOpen = ref(false)
const manifest = ref<BrandingManifest | null>(null)
const apiStatus = ref<'connected' | 'fallback'>('fallback')
const installPrompt = ref<InstallPromptEvent | null>(null)
const installing = ref(false)
const email = ref('')
const password = ref('')
const authError = ref('')
const token = ref(localStorage.getItem('scheduler_pro_access_token') || '')
const logged = computed(() => Boolean(token.value))
const appointments = ref<Appointment[]>([])
const loading = ref(false)
const activeCompany = ref('Minha empresa')

const appName = computed(() => manifest.value?.app?.public_name || manifest.value?.app?.name || 'Scheduler Pro')
const slogan = computed(() => manifest.value?.app?.slogan || 'Plataforma inteligente de agendamentos')
const activeTitle = computed(() => navItems.find((item) => item.key === view.value)?.label || 'Visão geral')
const isStandalone = computed(() => window.matchMedia('(display-mode: standalone)').matches || Boolean((window.navigator as Navigator & { standalone?: boolean }).standalone))
const todayAppointments = computed(() => appointments.value.length)
const confirmedToday = computed(() => appointments.value.filter((item) => item.status === 'CONFIRMED').length)

function apiBase(): string { return `${location.origin}/api/v1` }
function hashToView(): ViewKey { const current = (location.hash || '#dashboard').replace('#', ''); return navItems.some((item) => item.key === current) ? (current as ViewKey) : 'dashboard' }
function go(key: ViewKey): void { view.value = key; mobileOpen.value = false; if (location.hash !== `#${key}`) history.replaceState(null, '', `#${key}`) }
function onHashChange(): void { view.value = hashToView() }
function onBeforeInstallPrompt(event: Event): void { event.preventDefault(); installPrompt.value = event as InstallPromptEvent }
async function installWebApp(): Promise<void> { if (!installPrompt.value) return; installing.value = true; try { await installPrompt.value.prompt(); await installPrompt.value.userChoice; installPrompt.value = null } finally { installing.value = false } }
async function loadBranding(): Promise<void> { try { const data = await loadBrandingManifest(); manifest.value = data; applyBranding(data); activeCompany.value = data.app?.public_name || activeCompany.value; apiStatus.value = 'connected' } catch { apiStatus.value = 'fallback' } }
async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${apiBase()}${path}`, { ...init, headers: { 'content-type': 'application/json', ...(token.value ? { authorization: `Bearer ${token.value}` } : {}), ...(init.headers || {}) } })
  const body = await response.json().catch(() => ({})) as Partial<ApiEnvelope<T>> & { error?: { message?: string } }
  if (!response.ok) throw new Error(body.error?.message || 'Falha na API')
  return body.data as T
}
async function login(): Promise<void> {
  authError.value = ''
  loading.value = true
  try {
    const data = await api<{ access_token: string; refresh_token: string; user: { email: string } }>('/auth/login', { method: 'POST', body: JSON.stringify({ email: email.value, password: password.value }) })
    token.value = data.access_token
    localStorage.setItem('scheduler_pro_access_token', data.access_token)
    localStorage.setItem('scheduler_pro_refresh_token', data.refresh_token)
    await loadDashboard()
    go('dashboard')
  } catch (error) {
    authError.value = error instanceof Error ? error.message : 'Login inválido'
  } finally { loading.value = false }
}
function logout(): void { token.value = ''; localStorage.removeItem('scheduler_pro_access_token'); localStorage.removeItem('scheduler_pro_refresh_token') }
async function loadDashboard(): Promise<void> {
  if (!token.value) return
  try { appointments.value = await api<Appointment[]>('/appointments') } catch { appointments.value = [] }
}

onMounted(() => { loadBranding(); loadDashboard(); window.addEventListener('hashchange', onHashChange); window.addEventListener('beforeinstallprompt', onBeforeInstallPrompt) })
onUnmounted(() => { window.removeEventListener('hashchange', onHashChange); window.removeEventListener('beforeinstallprompt', onBeforeInstallPrompt) })
</script>

<template>
  <section v-if="!logged" class="auth-page">
    <aside class="auth-visual">
      <div class="auth-brand"><div class="brand-mark"><CalendarClock :size="28" /></div><div><strong>{{ appName }}</strong><span>{{ slogan }}</span></div></div>
      <h1>Agendamentos, clientes e confirmação por WhatsApp em uma plataforma escalável.</h1>
      <p>Acesse o painel da empresa para administrar agenda, clientes, serviços e confirmações.</p>
    </aside>
    <form class="auth-card" @submit.prevent="login">
      <h2>Entrar na plataforma</h2><p>Acesse o painel gerencial da sua empresa.</p>
      <label>E-mail<input v-model="email" type="email" autocomplete="username" required placeholder="admin@empresa.com.br" /></label>
      <label>Senha<input v-model="password" type="password" autocomplete="current-password" required placeholder="Sua senha" /></label>
      <p v-if="authError" class="form-error">{{ authError }}</p>
      <button class="btn primary full" type="submit" :disabled="loading">{{ loading ? 'Entrando...' : 'Entrar' }}</button>
      <button v-if="installPrompt && !isStandalone" class="btn full" type="button" @click="installWebApp">Instalar web app</button>
    </form>
  </section>

  <div v-else class="app-shell" :class="{ collapsed, mobileOpen }">
    <aside class="sidebar">
      <div class="brand"><div class="brand-mark"><CalendarClock :size="24" /></div><div v-if="!collapsed"><strong>{{ appName }}</strong><small>{{ slogan }}</small></div></div>
      <nav class="nav-list"><button v-for="item in navItems" :key="item.key" class="nav-item" :class="{ active: view === item.key }" type="button" @click="go(item.key)"><component :is="item.icon" :size="19" /><span v-if="!collapsed">{{ item.label }}</span></button></nav>
      <div class="sidebar-footer"><button v-if="installPrompt && !isStandalone" class="nav-item install-action" type="button" @click="installWebApp"><Download :size="19" /><span v-if="!collapsed">{{ installing ? 'Instalando...' : 'Instalar web app' }}</span></button><a class="nav-item" href="/docs" target="_blank"><MonitorSmartphone :size="19" /><span v-if="!collapsed">Documentação API</span></a><button class="nav-item" type="button" @click="logout"><LogOut :size="19" /><span v-if="!collapsed">Sair</span></button><div v-if="!collapsed" class="version-info"><strong>Versão 0.1.0-alpha</strong><small>{{ apiStatus === 'connected' ? 'API conectada' : 'aguardando API' }}</small></div></div>
    </aside>

    <div class="content-shell">
      <header class="topbar"><button class="icon-button" type="button" @click="collapsed = !collapsed; mobileOpen = !mobileOpen"><Menu :size="20" /></button><label class="company-switcher"><span>Empresa ativa</span><strong>{{ activeCompany }}</strong></label><div class="topbar-search"><Search :size="17" /><input placeholder="Buscar cliente, serviço ou horário" /></div><div class="topbar-spacer"></div><button v-if="installPrompt && !isStandalone" class="btn install-top" type="button" @click="installWebApp"><Smartphone :size="16" /> Instalar</button><button class="icon-button notification" type="button"><Bell :size="20" /><i></i></button><div class="profile"><div class="avatar">SP</div><div><strong>Gestor</strong><small>Operação da agenda</small></div></div></header>
      <main class="main-content">
        <section class="page-header"><div><p class="eyebrow">Scheduler Pro</p><h1>{{ activeTitle }}</h1><p>Motor real conectado à API: agenda, disponibilidade, clientes, WhatsApp, notificações e artefatos.</p></div><div class="page-actions"><button class="btn">Hoje</button><button class="btn primary"><Plus :size="16" /> Novo agendamento</button></div></section>
        <section v-if="view === 'dashboard'" class="view-stack"><div class="metric-grid"><article class="metric-card blue"><div><span>Agendamentos hoje</span><strong>{{ todayAppointments }}</strong><small>{{ confirmedToday }} confirmados</small></div><CalendarDays /></article><article class="metric-card green"><div><span>WhatsApp</span><strong>API</strong><small>Evolution configurável</small></div><MessageCircle /></article><article class="metric-card orange"><div><span>Artefatos</span><strong>Release</strong><small>web, admin, desktop, mobile</small></div><PackageCheck /></article></div><section class="panel span-2"><div class="panel-title"><div><h3>Próximos atendimentos</h3><p>Dados reais da API</p></div><button class="btn small" @click="loadDashboard">Atualizar</button></div><div class="list"><article v-for="item in appointments" :key="item.id" class="row"><div class="time">{{ new Date(item.starts_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }}</div><div><strong>{{ item.customer_name }}</strong><small>{{ item.service_name }} • {{ item.professional_name }}</small></div><span class="status-pill">{{ item.status }}</span></article><p v-if="appointments.length === 0" class="empty-state">Nenhum agendamento carregado.</p></div></section></section>
        <section v-else class="view-stack"><div class="panel feature-panel"><div><p class="eyebrow">{{ activeTitle }}</p><h2>{{ activeTitle }} em evolução operacional</h2><p>Este módulo usa autenticação real e será alimentado pelos endpoints dedicados da API.</p></div><button class="btn primary">Abrir recurso</button></div></section>
      </main>
    </div>
  </div>
</template>
