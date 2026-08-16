<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

type TabKey = 'home' | 'clientes' | 'dominios' | 'builds' | 'logs' | 'perfil'
type ApiEnvelope<T> = { data: T }
type Dashboard = { totals: { tenants: number; active_tenants: number; domains_pending: number; builds: number; build_artifacts: number; provisioning_jobs: number; platform_users?: number } }
type Tenant = { id: string; name: string; slug: string; status: string; primary_hostname?: string | null; created_at?: string | null }
type Domain = { id: string; tenant_id: string; tenant_name?: string; hostname: string; status: string; is_temporary: boolean; is_primary: boolean }
type BuildJob = { id: string; tenant?: string; target: string; status: string; source_ref?: string | null; created_at?: string | null; artifacts?: Array<{name:string;download_url?:string|null}> }
type LogEntry = { id: string; tenant_name?: string | null; tenant_slug?: string | null; source: string; level: string; event: string; message: string; error_code?: string | null; created_at?: string | null }
type LogSummary = { last_24h: { total: number; errors: number; docker: number; integrations: number; tenant_scoped: number } }

type CreatedTenant = { tenant_id: string; tenant_code: string; job_id: string; admin_email: string; initial_admin_password: string; hostname: string; status: string }

const tabs = [
  { key: 'home', label: 'Início', icon: '▦' }, { key: 'clientes', label: 'Clientes', icon: '▤' }, { key: 'dominios', label: 'Domínios', icon: '◎' },
  { key: 'builds', label: 'Builds', icon: '⬢' }, { key: 'logs', label: 'Logs', icon: '◫' }, { key: 'perfil', label: 'Perfil', icon: '⚙' },
] as const

const apiBase = (import.meta.env.VITE_ADMIN_API_BASE_URL || 'https://admin.scheduler.argws.com.br/api/v1').replace(/\/$/, '')
const tab = ref<TabKey>('home')
const email = ref(localStorage.getItem('scheduler_admin_mobile_email') || '')
const password = ref('')
const token = ref(localStorage.getItem('scheduler_admin_mobile_token') || '')
const dashboard = ref<Dashboard | null>(null)
const tenants = ref<Tenant[]>([])
const domains = ref<Domain[]>([])
const builds = ref<BuildJob[]>([])
const logs = ref<LogEntry[]>([])
const logSummary = ref<LogSummary | null>(null)
const loading = ref(false)
const error = ref('')
const toast = ref('')
const createdTenant = ref<CreatedTenant | null>(null)
const showTenantForm = ref(false)
const tenantForm = ref({ name: '', slug: '', admin_email: '', admin_password: '' })
const buildForm = ref({ tenant: '', target: 'android', source_ref: 'main' })
const customDomainForm = ref({ tenant_id: '', hostname: '', make_primary: true })
const logged = computed(() => Boolean(token.value))
const title = computed(() => tabs.find((item) => item.key === tab.value)?.label || 'Início')

async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response
  try { response = await fetch(`${apiBase}${path}`, { ...init, headers: { 'content-type': 'application/json', ...(token.value ? { authorization: `Bearer ${token.value}` } : {}), ...(init.headers || {}) } }) }
  catch { throw new Error('Não foi possível conectar ao Control Plane. Verifique internet e SSL.') }
  const body = await response.json().catch(() => ({})) as Partial<ApiEnvelope<T>> & { error?: { message?: string } }
  if (!response.ok) throw new Error(body.error?.message || `Falha HTTP ${response.status}`)
  return body.data as T
}

function setToast(message: string): void { toast.value = message; window.setTimeout(() => { if (toast.value === message) toast.value = '' }, 3500) }
function formatDate(value?: string | null): string { return value ? new Date(value).toLocaleString('pt-BR') : '—' }

async function login(): Promise<void> {
  loading.value = true; error.value = ''
  try {
    const data = await api<{ access_token: string }>('/auth/platform/login', { method: 'POST', body: JSON.stringify({ email: email.value, password: password.value }) })
    token.value = data.access_token; localStorage.setItem('scheduler_admin_mobile_token', data.access_token); localStorage.setItem('scheduler_admin_mobile_email', email.value); password.value = ''; await refreshAll()
  } catch (err) { error.value = err instanceof Error ? err.message : 'Não foi possível entrar' }
  finally { loading.value = false }
}

async function refreshAll(): Promise<void> {
  loading.value = true; error.value = ''
  try {
    const [d,t,dm,b] = await Promise.all([api<Dashboard>('/platform/dashboard'), api<Tenant[]>('/platform/tenants'), api<Domain[]>('/platform/domains'), api<{jobs:BuildJob[]}>('/platform/builds/jobs?limit=100')])
    dashboard.value=d; tenants.value=t; domains.value=dm; builds.value=b.jobs || []
    if (tab.value==='logs') await loadLogs()
  } catch (err) { error.value = err instanceof Error ? err.message : 'Falha ao atualizar Control Plane.' }
  finally { loading.value=false }
}

async function loadLogs(): Promise<void> { const [rows, summary] = await Promise.all([api<LogEntry[]>('/platform/observability/logs?limit=120'), api<LogSummary>('/platform/observability/logs/summary')]); logs.value = rows; logSummary.value = summary }
async function openTab(value: TabKey): Promise<void> { tab.value=value; error.value=''; if(value==='logs') await loadLogs(); else if(!dashboard.value) await refreshAll() }
function logout(): void { token.value=''; dashboard.value=null; tenants.value=[]; domains.value=[]; builds.value=[]; logs.value=[]; localStorage.removeItem('scheduler_admin_mobile_token') }

async function createTenant(): Promise<void> {
  error.value=''; createdTenant.value=null
  try {
    createdTenant.value = await api('/platform/tenants',{method:'POST',body:JSON.stringify({name:tenantForm.value.name,slug:tenantForm.value.slug||null,admin_email:tenantForm.value.admin_email,admin_password:tenantForm.value.admin_password||null})})
    tenantForm.value={name:'',slug:'',admin_email:'',admin_password:''}; showTenantForm.value=false; setToast('Cliente criado e provisionamento enfileirado.'); await refreshAll()
  } catch(err){error.value=err instanceof Error?err.message:'Falha ao criar cliente.'}
}

async function createTemporaryDomain(tenantId:string):Promise<void>{try{await api(`/platform/tenants/${tenantId}/domains/temporary`,{method:'POST',body:'{}'});setToast('Domínio temporário verificado.');await refreshAll()}catch(err){error.value=err instanceof Error?err.message:'Falha no domínio.'}}
async function checkDomain(id:string):Promise<void>{try{await api(`/platform/domains/${id}/check`,{method:'POST',body:'{}'});setToast('Domínio verificado.');await refreshAll()}catch(err){error.value=err instanceof Error?err.message:'Falha na verificação.'}}
async function purgeDomain(id:string):Promise<void>{try{await api(`/platform/domains/${id}/purge-cache`,{method:'POST',body:'{}'});setToast('Purge solicitado.');await loadLogs()}catch(err){error.value=err instanceof Error?err.message:'Falha no purge.'}}
async function connectDomain():Promise<void>{try{await api(`/platform/tenants/${customDomainForm.value.tenant_id}/domains/custom`,{method:'POST',body:JSON.stringify({hostname:customDomainForm.value.hostname,make_primary:customDomainForm.value.make_primary})});customDomainForm.value.hostname='';setToast('Domínio personalizado enviado.');await refreshAll()}catch(err){error.value=err instanceof Error?err.message:'Falha ao conectar domínio.'}}
async function requestBuild():Promise<void>{try{await api('/platform/builds/requests',{method:'POST',body:JSON.stringify({...buildForm.value,payload:{origin:'admin-mobile'}})});setToast('Build solicitado.');await refreshAll()}catch(err){error.value=err instanceof Error?err.message:'Falha ao solicitar build.'}}

onMounted(()=>{if(token.value) void refreshAll()})
</script>

<template>
  <main v-if="!logged" class="login-screen"><section class="hero"><span>SP</span><p>Control Plane Mobile</p><h1>Administração completa no celular.</h1></section><form class="card" @submit.prevent="login"><label>E-mail<input v-model="email" type="email" autocomplete="username" required /></label><label>Senha<input v-model="password" type="password" autocomplete="current-password" required /></label><p v-if="error" class="error">{{error}}</p><button :disabled="loading">{{loading?'Entrando...':'Entrar'}}</button></form></main>

  <main v-else class="app"><header><div><p>Scheduler Pro Admin</p><h1>{{title}}</h1></div><button @click="refreshAll">↻</button></header><p v-if="toast" class="toast">{{toast}}</p><p v-if="error" class="error floating">{{error}}</p>
    <section class="content">
      <template v-if="tab==='home'"><article class="hero-card"><h2>{{dashboard?.totals.tenants??0}} clientes</h2><p>{{dashboard?.totals.active_tenants??0}} ativos • {{dashboard?.totals.domains_pending??0}} domínios pendentes</p></article><section class="metrics"><article><strong>{{dashboard?.totals.builds??0}}</strong><span>Builds</span></article><article><strong>{{dashboard?.totals.build_artifacts??0}}</strong><span>Artefatos</span></article><article><strong>{{dashboard?.totals.provisioning_jobs??0}}</strong><span>Provisionamentos</span></article><article><strong>{{logSummary?.last_24h.errors??0}}</strong><span>Erros 24h</span></article></section><article class="card"><h2>Operação</h2><div class="action-grid"><button @click="openTab('clientes')">Novo cliente</button><button @click="openTab('dominios')">Domínios</button><button @click="openTab('builds')">Artefatos</button><button @click="openTab('logs')">Observabilidade</button></div></article></template>

      <template v-else-if="tab==='clientes'"><article v-if="createdTenant" class="credential-card"><strong>Credencial inicial criada</strong><small>{{createdTenant.admin_email}}</small><code>{{createdTenant.initial_admin_password}}</code><p>Guarde e entregue ao cliente; a senha não deve ser registrada em texto puro em outro lugar.</p></article><article class="card"><div class="section-title"><h2>Clientes SaaS</h2><button class="small" @click="showTenantForm=!showTenantForm">{{showTenantForm?'Fechar':'Novo'}}</button></div><form v-if="showTenantForm" class="stack" @submit.prevent="createTenant"><input v-model="tenantForm.name" placeholder="Nome da empresa" required/><input v-model="tenantForm.slug" placeholder="Código opcional"/><input v-model="tenantForm.admin_email" type="email" placeholder="E-mail administrador" required/><input v-model="tenantForm.admin_password" type="password" minlength="12" placeholder="Senha opcional (gera automática se vazio)"/><button>Criar e provisionar</button></form><div class="rows"><article v-for="t in tenants" :key="t.id"><div><strong>{{t.name}}</strong><small>{{t.slug}} • {{t.primary_hostname||'domínio pendente'}}</small></div><span>{{t.status}}</span><button class="inline" @click="createTemporaryDomain(t.id)">DNS</button></article></div></article></template>

      <template v-else-if="tab==='dominios'"><article class="card"><h2>Conectar domínio próprio</h2><form class="stack" @submit.prevent="connectDomain"><select v-model="customDomainForm.tenant_id" required><option value="">Cliente</option><option v-for="t in tenants" :key="t.id" :value="t.id">{{t.name}}</option></select><input v-model="customDomainForm.hostname" placeholder="agenda.cliente.com.br" required/><label class="check"><input v-model="customDomainForm.make_primary" type="checkbox"/> Tornar primário</label><button>Conectar</button></form></article><article class="card"><h2>Domínios</h2><div class="rows vertical"><article v-for="d in domains" :key="d.id"><div><strong>{{d.hostname}}</strong><small>{{d.tenant_name||d.tenant_id}} • {{d.status}}</small><div class="row-actions"><button class="inline" @click="checkDomain(d.id)">Verificar</button><button class="inline ghost" @click="purgeDomain(d.id)">Purge</button></div></div></article></div></article></template>

      <template v-else-if="tab==='builds'"><article class="card"><h2>Solicitar build</h2><form class="stack" @submit.prevent="requestBuild"><select v-model="buildForm.tenant" required><option value="">Cliente</option><option v-for="t in tenants" :key="t.id" :value="t.id">{{t.name}}</option></select><select v-model="buildForm.target"><option value="desktop">Desktop cliente</option><option value="android">Android cliente</option><option value="ios">iOS cliente</option><option value="admin-desktop">Desktop admin</option><option value="admin-android">Android admin</option><option value="admin-ios">iOS admin</option></select><input v-model="buildForm.source_ref" placeholder="main"/><button>Gerar artefato</button></form></article><article class="card"><h2>Jobs</h2><div class="rows vertical"><article v-for="b in builds" :key="b.id"><div><strong>{{b.target}} • {{b.status}}</strong><small>{{formatDate(b.created_at)}} • {{b.source_ref||'main'}}</small></div></article><p v-if="!builds.length">Nenhum build.</p></div></article></template>

      <template v-else-if="tab==='logs'"><article class="hero-card"><h2>{{logSummary?.last_24h.total??0}} eventos</h2><p>{{logSummary?.last_24h.errors??0}} erros • {{logSummary?.last_24h.integrations??0}} integrações</p></article><article class="card"><div class="rows vertical"><details v-for="l in logs" :key="l.id"><summary><strong>{{l.level}} • {{l.source}} • {{l.event}}</strong><small>{{formatDate(l.created_at)}} • {{l.tenant_name||l.tenant_slug||'plataforma'}}</small></summary><p>{{l.message}}</p><code v-if="l.error_code">{{l.error_code}}</code></details></div></article></template>

      <template v-else><article class="card"><h2>{{email}}</h2><p>Control Plane conectado ao domínio administrativo.</p><button @click="logout">Sair</button></article></template>
    </section>
    <nav><button v-for="item in tabs" :key="item.key" :class="{active:tab===item.key}" @click="openTab(item.key)"><span>{{item.icon}}</span><small>{{item.label}}</small></button></nav>
  </main>
</template>
