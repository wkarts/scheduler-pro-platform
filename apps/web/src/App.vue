<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import {
  Bell,
  CalendarClock,
  CalendarDays,
  CheckCircle2,
  ChevronDown,
  Clock3,
  Download,
  Globe2,
  LayoutDashboard,
  Link2,
  LogOut,
  Menu,
  MessageCircle,
  MonitorSmartphone,
  PackageCheck,
  Palette,
  Plus,
  Search,
  Settings,
  Smartphone,
  UserRoundCheck,
  Users,
  Wrench,
} from 'lucide-vue-next'
import { applyBranding, loadBrandingManifest, type BrandingManifest } from './branding'

type ViewKey = 'dashboard' | 'agenda' | 'clientes' | 'servicos' | 'profissionais' | 'landing' | 'whatsapp' | 'branding' | 'dominios' | 'builds' | 'configuracoes'
type InstallPromptEvent = Event & { prompt: () => Promise<void>; userChoice: Promise<{ outcome: 'accepted' | 'dismissed'; platform: string }> }

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

const appointments = [
  { hour: '08:30', customer: 'Mariana Almeida', service: 'Corte feminino', professional: 'Ana Souza', status: 'Confirmado' },
  { hour: '09:15', customer: 'João Pereira', service: 'Barba completa', professional: 'Carlos Lima', status: 'Aguardando' },
  { hour: '10:00', customer: 'Clínica Vida', service: 'Avaliação', professional: 'Dra. Helena', status: 'Confirmado' },
  { hour: '11:30', customer: 'Pedro Santos', service: 'Corte masculino', professional: 'Carlos Lima', status: 'Novo' },
]
const services = [
  { name: 'Corte masculino', duration: '30 min', price: 'R$ 45,00', active: true },
  { name: 'Barba completa', duration: '40 min', price: 'R$ 55,00', active: true },
  { name: 'Avaliação inicial', duration: '50 min', price: 'R$ 120,00', active: true },
]
const builds = [
  { target: 'Web PWA', status: 'Instalável', artifact: 'scheduler-pro-web.tar.gz' },
  { target: 'Desktop', status: 'Shell preparado', artifact: 'desktop-source.tar.gz' },
  { target: 'Android APK', status: 'Pipeline em preparação', artifact: 'apk pendente' },
  { target: 'iOS', status: 'Requer runner macOS', artifact: 'ipa pendente' },
]

const companies = ['Barbearia do João', 'Clínica Vida', 'Studio Agenda Pro']
const activeCompany = ref(companies[0])
const view = ref<ViewKey>(hashToView())
const collapsed = ref(false)
const mobileOpen = ref(false)
const manifest = ref<BrandingManifest | null>(null)
const apiStatus = ref<'connected' | 'fallback'>('fallback')
const installPrompt = ref<InstallPromptEvent | null>(null)
const installing = ref(false)
const logged = ref(!location.pathname.endsWith('/login') && location.hash !== '#login')

const appName = computed(() => manifest.value?.app?.public_name || manifest.value?.app?.name || 'Scheduler Pro')
const slogan = computed(() => manifest.value?.app?.slogan || 'Plataforma inteligente de agendamentos')
const activeTitle = computed(() => navItems.find((item) => item.key === view.value)?.label || 'Visão geral')
const confirmedToday = computed(() => appointments.filter((item) => item.status === 'Confirmado').length)
const isStandalone = computed(() => window.matchMedia('(display-mode: standalone)').matches || Boolean((window.navigator as Navigator & { standalone?: boolean }).standalone))

function hashToView(): ViewKey {
  const current = (location.hash || '#dashboard').replace('#', '')
  return navItems.some((item) => item.key === current) ? (current as ViewKey) : 'dashboard'
}
function go(key: ViewKey): void {
  view.value = key
  mobileOpen.value = false
  if (location.hash !== `#${key}`) history.replaceState(null, '', `#${key}`)
}
function onHashChange(): void { view.value = hashToView() }
function login(): void { logged.value = true; go('dashboard') }
function onBeforeInstallPrompt(event: Event): void { event.preventDefault(); installPrompt.value = event as InstallPromptEvent }
async function installWebApp(): Promise<void> {
  if (!installPrompt.value) return
  installing.value = true
  try { await installPrompt.value.prompt(); await installPrompt.value.userChoice; installPrompt.value = null } finally { installing.value = false }
}
async function loadBranding(): Promise<void> {
  try { const data = await loadBrandingManifest(); manifest.value = data; applyBranding(data); apiStatus.value = 'connected' } catch { apiStatus.value = 'fallback' }
}
function slugCompany(value: string): string { return value.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '') }

onMounted(() => { loadBranding(); window.addEventListener('hashchange', onHashChange); window.addEventListener('beforeinstallprompt', onBeforeInstallPrompt) })
onUnmounted(() => { window.removeEventListener('hashchange', onHashChange); window.removeEventListener('beforeinstallprompt', onBeforeInstallPrompt) })
</script>

<template>
  <section v-if="!logged" class="auth-page">
    <aside class="auth-visual">
      <div class="auth-brand"><div class="brand-mark"><CalendarClock :size="28" /></div><div><strong>{{ appName }}</strong><span>{{ slogan }}</span></div></div>
      <h1>Agendamentos, clientes e confirmação por WhatsApp em uma plataforma escalável.</h1>
      <p>Controle sua agenda, publique landing pages e distribua web app, desktop e mobile white-label.</p>
    </aside>
    <form class="auth-card" @submit.prevent="login">
      <h2>Entrar na plataforma</h2><p>Acesse o painel gerencial da sua empresa.</p>
      <label>E-mail<input type="email" value="admin@schedulerpro.local" /></label>
      <label>Senha<input type="password" value="schedulerpro" /></label>
      <button class="btn primary full" type="submit">Entrar</button>
    </form>
  </section>

  <div v-else class="app-shell" :class="{ collapsed, mobileOpen }">
    <aside class="sidebar">
      <div class="brand"><div class="brand-mark"><CalendarClock :size="24" /></div><div v-if="!collapsed"><strong>{{ appName }}</strong><small>{{ slogan }}</small></div></div>
      <nav class="nav-list">
        <button v-for="item in navItems" :key="item.key" class="nav-item" :class="{ active: view === item.key }" type="button" @click="go(item.key)"><component :is="item.icon" :size="19" /><span v-if="!collapsed">{{ item.label }}</span></button>
      </nav>
      <div class="sidebar-footer">
        <button v-if="installPrompt && !isStandalone" class="nav-item install-action" type="button" @click="installWebApp"><Download :size="19" /><span v-if="!collapsed">{{ installing ? 'Instalando...' : 'Instalar web app' }}</span></button>
        <a class="nav-item" href="/docs" target="_blank"><MonitorSmartphone :size="19" /><span v-if="!collapsed">Documentação API</span></a>
        <button class="nav-item" type="button" @click="logged = false"><LogOut :size="19" /><span v-if="!collapsed">Sair</span></button>
        <div v-if="!collapsed" class="version-info"><strong>Versão 0.1.0-alpha</strong><small>{{ apiStatus === 'connected' ? 'API conectada' : 'modo visual sem dados da API' }}</small></div>
      </div>
    </aside>

    <div class="content-shell">
      <header class="topbar">
        <button class="icon-button" type="button" @click="collapsed = !collapsed; mobileOpen = !mobileOpen"><Menu :size="20" /></button>
        <label class="company-switcher"><span>Empresa ativa</span><select v-model="activeCompany"><option v-for="company in companies" :key="company">{{ company }}</option></select><ChevronDown :size="16" /></label>
        <div class="topbar-search"><Search :size="17" /><input placeholder="Buscar cliente, serviço ou horário" /></div>
        <div class="topbar-spacer"></div>
        <button v-if="installPrompt && !isStandalone" class="btn install-top" type="button" @click="installWebApp"><Smartphone :size="16" /> Instalar</button>
        <button class="icon-button notification" type="button"><Bell :size="20" /><i></i></button>
        <div class="profile"><div class="avatar">W</div><div><strong>Wallace Kleiton</strong><small>Gestor da plataforma</small></div></div>
      </header>

      <main class="main-content">
        <section class="page-header"><div><p class="eyebrow">Scheduler Pro</p><h1>{{ activeTitle }}</h1><p>{{ view === 'dashboard' ? 'Acompanhe agenda, clientes, WhatsApp, landing page e distribuição dos aplicativos.' : 'Gerencie este recurso com interface profissional, responsiva e preparada para produção.' }}</p></div><div class="page-actions"><button class="btn"><Clock3 :size="16" /> Hoje</button><button class="btn primary"><Plus :size="16" /> Novo agendamento</button></div></section>

        <section v-if="view === 'dashboard'" class="view-stack">
          <div class="metric-grid"><article class="metric-card blue"><div><span>Agendamentos hoje</span><strong>{{ appointments.length }}</strong><small>{{ confirmedToday }} confirmados</small></div><CalendarDays /></article><article class="metric-card violet"><div><span>Clientes ativos</span><strong>248</strong><small>base em crescimento</small></div><Users /></article><article class="metric-card green"><div><span>WhatsApp</span><strong>Online</strong><small>confirmações habilitadas</small></div><MessageCircle /></article><article class="metric-card orange"><div><span>Artefatos</span><strong>4</strong><small>web, admin, desktop, mobile</small></div><PackageCheck /></article></div>
          <div class="dashboard-grid"><section class="panel span-2"><div class="panel-title"><div><h3>Próximos atendimentos</h3><p>Agenda operacional do dia</p></div><button class="btn small">Abrir agenda</button></div><div class="list"><article v-for="item in appointments" :key="`${item.hour}-${item.customer}`" class="row"><div class="time">{{ item.hour }}</div><div><strong>{{ item.customer }}</strong><small>{{ item.service }} • {{ item.professional }}</small></div><span class="status-pill" :class="item.status.toLowerCase()">{{ item.status }}</span></article></div></section><section class="panel chart-panel"><div class="panel-title"><div><h3>Ocupação</h3><p>Distribuição por status</p></div></div><div class="donut"><span>72%</span></div></section><section class="panel"><div class="panel-title"><div><h3>Saúde da plataforma</h3><p>Serviços essenciais</p></div></div><div class="health"><div><span><i class="ok"></i>API FastAPI</span><b>OK</b></div><div><span><i class="ok"></i>PWA instalável</span><b>OK</b></div><div><span><i class="warn"></i>APK Android</span><b>Pendente</b></div><div><span><i class="ok"></i>CloudPanel/Dockge</span><b>OK</b></div></div></section></div>
        </section>

        <section v-else-if="view === 'agenda'" class="view-stack"><div class="panel"><div class="panel-title"><div><h3>Agenda do dia</h3><p>Confirme, reagende ou cancele atendimentos.</p></div><button class="btn primary">Criar horário</button></div><div class="list"><article v-for="item in appointments" :key="item.customer" class="row"><div class="time">{{ item.hour }}</div><div><strong>{{ item.customer }}</strong><small>{{ item.service }} com {{ item.professional }}</small></div><button class="btn small">Detalhes</button></article></div></div></section>
        <section v-else-if="view === 'clientes'" class="view-stack"><div class="panel table-panel"><div class="panel-title"><div><h3>Clientes</h3><p>Cadastro centralizado para agendamentos e WhatsApp.</p></div><button class="btn primary">Novo cliente</button></div><table><thead><tr><th>Nome</th><th>Contato</th><th>Último atendimento</th><th>Status</th></tr></thead><tbody><tr><td>Mariana Almeida</td><td>(11) 99999-0101</td><td>Corte feminino</td><td><span class="status-pill confirmado">Ativa</span></td></tr><tr><td>João Pereira</td><td>(75) 98888-0202</td><td>Barba completa</td><td><span class="status-pill novo">Novo</span></td></tr></tbody></table></div></section>
        <section v-else-if="view === 'servicos'" class="cards-grid"><article v-for="service in services" :key="service.name" class="panel card"><h3>{{ service.name }}</h3><p>{{ service.duration }} • {{ service.price }}</p><span class="status-pill confirmado">Ativo</span></article></section>
        <section v-else-if="view === 'profissionais'" class="cards-grid"><article class="panel card"><div class="avatar big">A</div><h3>Ana Souza</h3><p>Profissional master</p><strong>6 atendimentos hoje</strong></article><article class="panel card"><div class="avatar big">C</div><h3>Carlos Lima</h3><p>Atendimento e agenda</p><strong>8 atendimentos hoje</strong></article></section>
        <section v-else-if="view === 'landing'" class="view-stack"><div class="panel feature-panel"><div><p class="eyebrow">Landing Page Builder</p><h2>Landing pública com blocos e botão de agendamento</h2><p>Hero, serviços, profissionais, mapa, WhatsApp e CTA versionados por publicação.</p></div><button class="btn primary">Editar landing</button></div><div class="landing-preview"><strong>{{ activeCompany }}</strong><h3>Agende seu horário online</h3><p>Escolha serviço, profissional e receba confirmação pelo WhatsApp.</p><button>Agendar agora</button></div></section>
        <section v-else-if="view === 'whatsapp'" class="cards-grid"><article class="panel card"><MessageCircle :size="42" /><h3>WhatsApp API</h3><p>Conexão por provider abstrato e webhooks idempotentes.</p><span class="status-pill confirmado">Conectado</span></article><article class="panel card"><div class="qr"></div><h3>QR Code da instância</h3><p>Repareamento seguro quando necessário.</p></article></section>
        <section v-else-if="view === 'branding'" class="view-stack"><div class="panel feature-panel"><div><p class="eyebrow">White-label</p><h2>Marca, cores, nome do app e pacote por empresa</h2><p>Configuração usada no PWA, desktop, mobile e landing page.</p></div><button class="btn primary">Publicar identidade</button></div></section>
        <section v-else-if="view === 'dominios'" class="view-stack"><div class="panel table-panel"><div class="panel-title"><div><h3>Domínios</h3><p>Domínio provisório e domínio próprio com Cloudflare.</p></div><button class="btn primary">Adicionar domínio</button></div><table><tbody><tr><td>scheduler.argws.com.br</td><td>Principal</td><td><span class="status-pill confirmado">Ativo</span></td></tr><tr><td>{{ slugCompany(activeCompany) }}.schedulerpro.app</td><td>Provisório</td><td><span class="status-pill confirmado">Ativo</span></td></tr></tbody></table></div></section>
        <section v-else-if="view === 'builds'" class="view-stack"><div class="panel table-panel"><div class="panel-title"><div><h3>Builds e artefatos</h3><p>Web PWA, Desktop, Android, iOS e pacotes CloudPanel/Dockge.</p></div><button class="btn primary">Solicitar build</button></div><table><thead><tr><th>Target</th><th>Artefato</th><th>Status</th></tr></thead><tbody><tr v-for="item in builds" :key="item.target"><td>{{ item.target }}</td><td>{{ item.artifact }}</td><td><span class="status-pill aguardando">{{ item.status }}</span></td></tr></tbody></table></div></section>
        <section v-else class="view-stack"><div class="panel feature-panel"><div><h2>Configurações da empresa</h2><p>Horários, políticas de confirmação, lembretes, permissões, integrações e recursos do plano.</p></div><button class="btn primary">Abrir configurações</button></div></section>
      </main>
    </div>
  </div>
</template>
