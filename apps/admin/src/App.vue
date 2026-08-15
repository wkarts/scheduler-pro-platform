<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { apiGet, apiPost, type ApiError } from './api/client'

type LoginResponse = {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
  user: {
    id: string
    email: string
    name?: string | null
    roles?: string[]
    permissions?: string[]
  }
}

type DashboardResponse = {
  totals: {
    tenants: number
    active_tenants: number
    provisioning_jobs: number
    domains_pending: number
    builds: number
    build_artifacts: number
    platform_users: number
  }
  health: {
    platform: string
    queue: string
    storage: string
    release: string
  }
  recent_tenants: Array<{ id: string; name: string; slug: string; status: string; created_at?: string | null }>
  recent_builds: Array<{ id: string; target: string; status: string; created_at?: string | null }>
  recent_provisioning: Array<{ id: string; status: string; correlation_id: string; created_at?: string | null }>
}

type SessionState = {
  accessToken: string
  refreshToken: string
  userEmail: string
}

const storageKey = 'scheduler-pro-admin-session'
const email = ref('')
const password = ref('')
const authenticating = ref(false)
const loadingDashboard = ref(false)
const errorMessage = ref('')
const installMessage = ref('')
const session = ref<SessionState | null>(null)
const dashboard = ref<DashboardResponse | null>(null)
const activeModule = ref('overview')
const sidebarOpen = ref(false)

const modules = [
  { key: 'overview', label: 'Visão geral', icon: '▦', description: 'Indicadores globais da plataforma' },
  { key: 'tenants', label: 'Tenants / Clientes', icon: '▤', description: 'Clientes SaaS, status, plano e acesso' },
  { key: 'provisioning', label: 'Provisionamento', icon: '⚙', description: 'Fila de criação de ambientes e bancos' },
  { key: 'domains', label: 'Domínios', icon: '🌐', description: 'Domínios provisórios, custom hostnames e SSL' },
  { key: 'builds', label: 'Builds e artefatos', icon: '⬢', description: 'Web, PWA, desktop, Android, iOS e releases' },
  { key: 'branding', label: 'White-label', icon: '◇', description: 'Marca, app name, ícones e tema por cliente' },
  { key: 'plans', label: 'Planos e features', icon: '▣', description: 'Planos comerciais e feature flags' },
  { key: 'integrations', label: 'Integrações', icon: '⌁', description: 'WhatsApp, Cloudflare, storage e webhooks' },
  { key: 'audit', label: 'Auditoria', icon: '☰', description: 'Eventos sensíveis, sessão, alterações e IP' },
  { key: 'settings', label: 'Configurações', icon: '⚙', description: 'Parâmetros globais e segurança' },
]

const selectedModule = computed(() => modules.find(module => module.key === activeModule.value) ?? modules[0])
const isAuthenticated = computed(() => Boolean(session.value?.accessToken))
const totals = computed(() => dashboard.value?.totals)
const activeTenantsRatio = computed(() => {
  if (!totals.value?.tenants) return '0%'
  return `${Math.round((totals.value.active_tenants / totals.value.tenants) * 100)}%`
})

function restoreSession() {
  const raw = localStorage.getItem(storageKey)
  if (!raw) return
  try {
    session.value = JSON.parse(raw) as SessionState
  } catch {
    localStorage.removeItem(storageKey)
  }
}

function persistSession(payload: LoginResponse) {
  session.value = {
    accessToken: payload.access_token,
    refreshToken: payload.refresh_token,
    userEmail: payload.user?.email ?? email.value,
  }
  localStorage.setItem(storageKey, JSON.stringify(session.value))
}

function clearSession() {
  session.value = null
  dashboard.value = null
  localStorage.removeItem(storageKey)
}

async function login() {
  errorMessage.value = ''
  authenticating.value = true
  try {
    const payload = await apiPost<LoginResponse>('/auth/platform/login', { email: email.value, password: password.value })
    persistSession(payload)
    password.value = ''
    await loadDashboard()
  } catch (error) {
    const apiError = error as ApiError
    errorMessage.value = apiError.message || 'Não foi possível autenticar no painel administrativo.'
  } finally {
    authenticating.value = false
  }
}

async function loadDashboard() {
  if (!session.value?.accessToken) return
  errorMessage.value = ''
  loadingDashboard.value = true
  try {
    dashboard.value = await apiGet<DashboardResponse>('/platform/dashboard', session.value.accessToken)
  } catch (error) {
    const apiError = error as ApiError
    if (apiError.status === 401 || apiError.status === 403) clearSession()
    errorMessage.value = apiError.message || 'Não foi possível carregar os dados administrativos.'
  } finally {
    loadingDashboard.value = false
  }
}

function installPwa() {
  const installer = (window as any).schedulerProAdminPwa
  if (installer?.install) {
    installer.install()
    return
  }
  installMessage.value = 'Instalação indisponível neste navegador neste momento. Use o menu do navegador e escolha instalar aplicativo.'
}

function selectModule(key: string) {
  activeModule.value = key
  sidebarOpen.value = false
}

onMounted(() => {
  restoreSession()
  if (session.value?.accessToken) loadDashboard()
  window.addEventListener('scheduler-pro-admin-install-ready', () => {
    installMessage.value = 'WebApp administrativo pronto para instalação.'
  })
})
</script>

<template>
  <main class="min-h-screen bg-[#eef3f9] text-slate-950">
    <section v-if="!isAuthenticated" class="grid min-h-screen lg:grid-cols-[1.15fr_0.85fr]">
      <aside class="relative hidden overflow-hidden bg-[#092449] text-white lg:flex lg:items-center">
        <div class="absolute inset-0 bg-[radial-gradient(circle_at_85%_85%,rgba(96,165,250,0.18),transparent_34%),radial-gradient(circle_at_15%_20%,rgba(34,211,238,0.16),transparent_28%)]"></div>
        <div class="relative mx-auto max-w-2xl px-12">
          <div class="flex items-center gap-4">
            <div class="flex h-14 w-14 items-center justify-center rounded-2xl bg-blue-500 shadow-2xl shadow-blue-900/40">SP</div>
            <div>
              <p class="text-2xl font-black tracking-tight">Scheduler Pro</p>
              <p class="text-sm text-blue-100">Control Plane SaaS</p>
            </div>
          </div>
          <h1 class="mt-16 text-5xl font-black leading-tight tracking-tight">Controle a plataforma, clientes, domínios e artefatos em um painel central.</h1>
          <p class="mt-8 max-w-xl text-lg leading-8 text-blue-100">Gerencie tenants, provisionamento, white-label, builds, integrações e auditoria com uma interface administrativa instalável.</p>
        </div>
      </aside>

      <section class="flex items-center justify-center bg-white px-6 py-12">
        <form class="w-full max-w-md" @submit.prevent="login">
          <div class="mb-10 lg:hidden">
            <div class="flex items-center gap-3">
              <div class="flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-600 font-black text-white">SP</div>
              <div>
                <p class="text-2xl font-black">Scheduler Pro</p>
                <p class="text-sm text-slate-500">Control Plane</p>
              </div>
            </div>
          </div>

          <p class="text-sm font-semibold uppercase tracking-[0.28em] text-blue-600">Administração</p>
          <h2 class="mt-3 text-4xl font-black tracking-tight text-slate-950">Entrar na plataforma</h2>
          <p class="mt-3 text-slate-500">Utilize suas credenciais administrativas do Control Plane.</p>

          <label class="mt-10 block text-sm font-bold text-slate-700" for="email">E-mail</label>
          <input id="email" v-model="email" autocomplete="username" class="mt-2 w-full rounded-xl border border-slate-200 px-4 py-3 outline-none transition focus:border-blue-500 focus:ring-4 focus:ring-blue-100" placeholder="admin@empresa.com.br" required type="email" />

          <label class="mt-5 block text-sm font-bold text-slate-700" for="password">Senha</label>
          <input id="password" v-model="password" autocomplete="current-password" class="mt-2 w-full rounded-xl border border-slate-200 px-4 py-3 outline-none transition focus:border-blue-500 focus:ring-4 focus:ring-blue-100" placeholder="••••••••" required type="password" />

          <p v-if="errorMessage" class="mt-5 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700">{{ errorMessage }}</p>

          <button class="mt-7 w-full rounded-xl bg-blue-600 px-5 py-3.5 font-black text-white shadow-xl shadow-blue-500/20 transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-70" :disabled="authenticating" type="submit">
            {{ authenticating ? 'Validando...' : 'Entrar' }}
          </button>

          <button class="mt-3 w-full rounded-xl border border-slate-200 px-5 py-3 text-sm font-bold text-slate-600 transition hover:bg-slate-50" type="button" @click="installPwa">Instalar WebApp administrativo</button>
          <p v-if="installMessage" class="mt-3 text-xs text-slate-500">{{ installMessage }}</p>
        </form>
      </section>
    </section>

    <section v-else class="min-h-screen lg:grid lg:grid-cols-[292px_1fr]">
      <aside :class="['fixed inset-y-0 left-0 z-40 w-[292px] transform bg-[#092449] text-white transition lg:static lg:translate-x-0', sidebarOpen ? 'translate-x-0' : '-translate-x-full']">
        <div class="flex h-full flex-col">
          <div class="flex items-center gap-3 px-6 py-6">
            <div class="flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-500 font-black shadow-xl shadow-blue-950/30">SP</div>
            <div>
              <p class="text-xl font-black leading-tight">Scheduler Pro</p>
              <p class="text-xs text-blue-100">Administração da plataforma</p>
            </div>
          </div>

          <nav class="flex-1 space-y-1 px-4">
            <button v-for="module in modules" :key="module.key" :class="['flex w-full items-center gap-3 rounded-xl px-4 py-3 text-left text-sm font-bold transition', activeModule === module.key ? 'bg-blue-500 text-white shadow-lg shadow-blue-950/30' : 'text-blue-50 hover:bg-white/10']" type="button" @click="selectModule(module.key)">
              <span class="flex h-7 w-7 items-center justify-center rounded-lg bg-white/10 text-xs">{{ module.icon }}</span>
              <span>{{ module.label }}</span>
            </button>
          </nav>

          <div class="border-t border-white/10 p-4">
            <button class="mb-3 w-full rounded-xl bg-white/10 px-4 py-3 text-sm font-bold text-white transition hover:bg-white/15" type="button" @click="installPwa">Instalar PWA Admin</button>
            <button class="w-full rounded-xl px-4 py-3 text-left text-sm font-semibold text-blue-100 transition hover:bg-white/10" type="button" @click="clearSession">Sair</button>
          </div>
        </div>
      </aside>

      <div v-if="sidebarOpen" class="fixed inset-0 z-30 bg-slate-950/50 lg:hidden" @click="sidebarOpen = false"></div>

      <section class="min-w-0">
        <header class="sticky top-0 z-20 flex h-20 items-center justify-between border-b border-slate-200 bg-white/90 px-5 backdrop-blur lg:px-8">
          <div class="flex items-center gap-4">
            <button class="rounded-xl border border-slate-200 bg-white p-3 text-slate-700 shadow-sm lg:hidden" type="button" @click="sidebarOpen = true">☰</button>
            <div>
              <p class="text-xs font-bold uppercase tracking-[0.25em] text-blue-500">Control Plane</p>
              <h1 class="text-xl font-black text-slate-950 md:text-2xl">{{ selectedModule.label }}</h1>
            </div>
          </div>
          <div class="flex items-center gap-3">
            <button class="hidden rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-bold text-slate-600 shadow-sm md:block" type="button" @click="loadDashboard">{{ loadingDashboard ? 'Atualizando...' : 'Atualizar' }}</button>
            <div class="hidden text-right md:block">
              <p class="text-sm font-black text-slate-950">{{ session?.userEmail }}</p>
              <p class="text-xs text-slate-500">platform_admin</p>
            </div>
            <div class="h-11 w-11 overflow-hidden rounded-full bg-gradient-to-br from-blue-500 to-cyan-400 ring-4 ring-blue-50"></div>
          </div>
        </header>

        <main class="space-y-8 p-5 lg:p-8">
          <section class="overflow-hidden rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
            <div class="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <p class="text-sm font-semibold text-slate-500">{{ selectedModule.description }}</p>
                <h2 class="mt-2 text-3xl font-black tracking-tight text-slate-950">Painel administrativo da plataforma</h2>
              </div>
              <button class="rounded-xl bg-blue-600 px-5 py-3 text-sm font-black text-white shadow-xl shadow-blue-600/20 transition hover:bg-blue-700" type="button">Novo tenant / cliente</button>
            </div>
          </section>

          <p v-if="errorMessage" class="rounded-2xl border border-red-200 bg-red-50 px-5 py-4 text-sm font-semibold text-red-700">{{ errorMessage }}</p>

          <section class="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <article class="metric-card">
              <span>Tenants cadastrados</span>
              <strong>{{ totals?.tenants ?? '—' }}</strong>
              <small>{{ activeTenantsRatio }} ativos</small>
            </article>
            <article class="metric-card metric-violet">
              <span>Provisionamentos</span>
              <strong>{{ totals?.provisioning_jobs ?? '—' }}</strong>
              <small>jobs registrados</small>
            </article>
            <article class="metric-card metric-emerald">
              <span>Domínios pendentes</span>
              <strong>{{ totals?.domains_pending ?? '—' }}</strong>
              <small>validação / SSL</small>
            </article>
            <article class="metric-card metric-orange">
              <span>Builds e artefatos</span>
              <strong>{{ totals ? `${totals.builds}/${totals.build_artifacts}` : '—' }}</strong>
              <small>jobs / arquivos</small>
            </article>
          </section>

          <section class="grid gap-5 xl:grid-cols-[1.2fr_0.8fr]">
            <article class="panel-card">
              <div class="mb-5 flex items-center justify-between">
                <div>
                  <h3>Tenants recentes</h3>
                  <p>Clientes SaaS provisionados na plataforma</p>
                </div>
                <span class="rounded-full bg-blue-50 px-3 py-1 text-xs font-black text-blue-700">{{ dashboard?.recent_tenants?.length ?? 0 }}</span>
              </div>
              <div class="space-y-3">
                <div v-for="tenant in dashboard?.recent_tenants ?? []" :key="tenant.id" class="row-card">
                  <div>
                    <strong>{{ tenant.name }}</strong>
                    <small>{{ tenant.slug }}</small>
                  </div>
                  <span class="status-pill">{{ tenant.status }}</span>
                </div>
                <div v-if="!dashboard?.recent_tenants?.length" class="empty-state">Nenhum tenant encontrado no banco da plataforma.</div>
              </div>
            </article>

            <article class="panel-card">
              <div class="mb-5">
                <h3>Saúde operacional</h3>
                <p>Estado dos componentes principais</p>
              </div>
              <div class="space-y-3">
                <div v-for="(value, key) in dashboard?.health ?? {}" :key="key" class="row-card">
                  <div>
                    <strong>{{ key }}</strong>
                    <small>monitoramento interno</small>
                  </div>
                  <span class="status-pill good">{{ value }}</span>
                </div>
              </div>
            </article>
          </section>

          <section class="grid gap-5 xl:grid-cols-2">
            <article class="panel-card">
              <div class="mb-5">
                <h3>Builds recentes</h3>
                <p>Jobs de aplicativos, PWA e artefatos</p>
              </div>
              <div class="space-y-3">
                <div v-for="build in dashboard?.recent_builds ?? []" :key="build.id" class="row-card">
                  <div>
                    <strong>{{ build.target }}</strong>
                    <small>{{ build.id }}</small>
                  </div>
                  <span class="status-pill">{{ build.status }}</span>
                </div>
                <div v-if="!dashboard?.recent_builds?.length" class="empty-state">Nenhum build registrado ainda.</div>
              </div>
            </article>

            <article class="panel-card">
              <div class="mb-5">
                <h3>Provisionamento recente</h3>
                <p>Execuções de criação de tenant e recursos</p>
              </div>
              <div class="space-y-3">
                <div v-for="job in dashboard?.recent_provisioning ?? []" :key="job.id" class="row-card">
                  <div>
                    <strong>{{ job.correlation_id }}</strong>
                    <small>{{ job.id }}</small>
                  </div>
                  <span class="status-pill">{{ job.status }}</span>
                </div>
                <div v-if="!dashboard?.recent_provisioning?.length" class="empty-state">Nenhum provisionamento registrado ainda.</div>
              </div>
            </article>
          </section>
        </main>
      </section>
    </section>
  </main>
</template>
