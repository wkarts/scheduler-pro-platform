<script setup lang="ts">
import { computed, ref } from 'vue'

type TabKey = 'home' | 'clientes' | 'dominios' | 'builds' | 'perfil'
type ApiEnvelope<T> = { data: T }
type Dashboard = { totals: { tenants: number; active_tenants: number; domains_pending: number; builds: number; build_artifacts: number; provisioning_jobs: number } }

const tabs = [
  { key: 'home', label: 'Início', icon: '▦' },
  { key: 'clientes', label: 'Clientes', icon: '▤' },
  { key: 'dominios', label: 'Domínios', icon: '◎' },
  { key: 'builds', label: 'Builds', icon: '⬢' },
  { key: 'perfil', label: 'Perfil', icon: '⚙' },
] as const

const apiBase = import.meta.env.VITE_ADMIN_API_BASE_URL || 'https://admin.scheduler.argws.com.br/api/v1'
const tab = ref<TabKey>('home')
const email = ref('')
const password = ref('')
const token = ref(localStorage.getItem('scheduler_admin_mobile_token') || '')
const dashboard = ref<Dashboard | null>(null)
const loading = ref(false)
const error = ref('')
const logged = computed(() => Boolean(token.value))
const title = computed(() => tabs.find((item) => item.key === tab.value)?.label || 'Início')

async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${apiBase}${path}`, {
    ...init,
    headers: { 'content-type': 'application/json', ...(token.value ? { authorization: `Bearer ${token.value}` } : {}), ...(init.headers || {}) },
  })
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
    localStorage.setItem('scheduler_admin_mobile_token', data.access_token)
    await loadDashboard()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Não foi possível entrar'
  } finally {
    loading.value = false
  }
}

async function loadDashboard(): Promise<void> {
  dashboard.value = await api<Dashboard>('/platform/dashboard')
}

function logout(): void {
  token.value = ''
  dashboard.value = null
  localStorage.removeItem('scheduler_admin_mobile_token')
}
</script>

<template>
  <main v-if="!logged" class="login-screen">
    <section class="hero"><span>SP</span><p>Control Plane Mobile</p><h1>Administração da plataforma no celular.</h1></section>
    <form class="card" @submit.prevent="login">
      <label>E-mail<input v-model="email" type="email" autocomplete="username" required /></label>
      <label>Senha<input v-model="password" type="password" autocomplete="current-password" required /></label>
      <p v-if="error" class="error">{{ error }}</p>
      <button type="submit" :disabled="loading">{{ loading ? 'Entrando...' : 'Entrar' }}</button>
    </form>
  </main>
  <main v-else class="app">
    <header><div><p>Scheduler Pro Admin</p><h1>{{ title }}</h1></div><button @click="loadDashboard">↻</button></header>
    <section class="content">
      <article class="hero-card"><h2>{{ dashboard?.totals.tenants ?? '—' }} clientes</h2><p>{{ dashboard?.totals.active_tenants ?? '—' }} ativos • {{ dashboard?.totals.domains_pending ?? '—' }} domínios pendentes</p></article>
      <section class="metrics"><article><strong>{{ dashboard?.totals.builds ?? '—' }}</strong><span>Builds</span></article><article><strong>{{ dashboard?.totals.build_artifacts ?? '—' }}</strong><span>Artefatos</span></article></section>
      <article class="card"><h2>{{ title }}</h2><p>Operação administrativa conectada ao Control Plane, preparada para distribuição própria.</p><button v-if="tab === 'perfil'" type="button" @click="logout">Sair</button></article>
    </section>
    <nav><button v-for="item in tabs" :key="item.key" :class="{ active: tab === item.key }" @click="tab = item.key"><span>{{ item.icon }}</span><small>{{ item.label }}</small></button></nav>
  </main>
</template>
