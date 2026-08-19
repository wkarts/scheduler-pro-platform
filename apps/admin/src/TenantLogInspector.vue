<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Download, RefreshCw, Search, ServerCog, X } from 'lucide-vue-next'

type Tenant = { id:string; name:string; slug:string; status:string; primary_hostname?:string|null }
type LogEntry = { id:string; source:string; service:string; level:string; event:string; message:string; integration?:string|null; error_code?:string|null; correlation_id?:string|null; request_id?:string|null; actor?:string|null; details?:Record<string,unknown>; created_at?:string|null }
type ApiEnvelope<T> = { data:T; error?:{message?:string;code?:string} }

const open = ref(false)
const loading = ref(false)
const tenants = ref<Tenant[]>([])
const selected = ref(sessionStorage.getItem('scheduler_pro_log_tenant') || '')
const logs = ref<LogEntry[]>([])
const search = ref('')
const level = ref('')
const error = ref('')
const downloading = ref(false)

const selectedTenant = computed(() => tenants.value.find((item) => item.id === selected.value) || null)
const stats = computed(() => ({
  total: logs.value.length,
  errors: logs.value.filter((item) => ['ERROR','CRITICAL'].includes(String(item.level).toUpperCase())).length,
  warnings: logs.value.filter((item) => String(item.level).toUpperCase() === 'WARNING').length,
}))

function sessionToken(): string {
  try {
    const raw = localStorage.getItem('scheduler-pro-admin-session')
    if (!raw) return ''
    return String((JSON.parse(raw) as {accessToken?:string}).accessToken || '')
  } catch { return '' }
}

async function api<T>(path:string):Promise<T> {
  const token = sessionToken()
  if (!token) throw new Error('Entre novamente no Control Plane para consultar os logs.')
  const response = await fetch(`/api/v1${path}`, { headers:{ accept:'application/json', authorization:`Bearer ${token}` }, cache:'no-store' })
  const payload = await response.json().catch(()=>({})) as Partial<ApiEnvelope<T>>
  if (!response.ok) throw new Error(payload.error?.message || `Falha ao consultar o servidor (${response.status}).`)
  return payload.data as T
}

async function loadTenants():Promise<void> {
  tenants.value = await api<Tenant[]>('/platform/tenants')
  if (selected.value && !tenants.value.some((item)=>item.id===selected.value)) selected.value=''
}

async function loadLogs():Promise<void> {
  if (!selected.value) { logs.value=[]; return }
  loading.value=true; error.value=''
  try {
    sessionStorage.setItem('scheduler_pro_log_tenant', selected.value)
    const params = new URLSearchParams({ limit:'2000' })
    if (search.value.trim()) params.set('search',search.value.trim())
    if (level.value) params.set('level',level.value)
    logs.value = await api<LogEntry[]>(`/platform/observability/tenant/${selected.value}/logs?${params}`)
  } catch (exc) { error.value=exc instanceof Error?exc.message:'Não foi possível carregar o diagnóstico do tenant.' }
  finally { loading.value=false }
}

async function show():Promise<void> {
  open.value=true; error.value=''
  try { await loadTenants(); if (selected.value) await loadLogs() }
  catch(exc){ error.value=exc instanceof Error?exc.message:'Não foi possível abrir os logs por tenant.' }
}

async function downloadBundle():Promise<void> {
  if (!selected.value) return
  downloading.value=true; error.value=''
  try {
    const token=sessionToken()
    const response=await fetch(`/api/v1/platform/observability/logs/export?tenant=${encodeURIComponent(selected.value)}`,{headers:{authorization:`Bearer ${token}`}})
    if(!response.ok){ const payload=await response.json().catch(()=>({})) as Partial<ApiEnvelope<unknown>>; throw new Error(payload.error?.message || 'Não foi possível gerar o pacote de diagnóstico.') }
    const blob=await response.blob()
    const disposition=response.headers.get('content-disposition') || ''
    const match=disposition.match(/filename="?([^";]+)"?/i)
    const filename=match?.[1] || `scheduler-pro-${selectedTenant.value?.slug || 'tenant'}-diagnostico.zip`
    const url=URL.createObjectURL(blob); const anchor=document.createElement('a'); anchor.href=url; anchor.download=filename; anchor.click(); URL.revokeObjectURL(url)
  } catch(exc){ error.value=exc instanceof Error?exc.message:'Falha ao baixar o diagnóstico.' }
  finally{ downloading.value=false }
}

function formatDate(value?:string|null):string { return value?new Date(value).toLocaleString('pt-BR'):'—' }
function levelClass(value:string):string { return String(value||'INFO').toLowerCase() }

onMounted(()=>{
  window.addEventListener('scheduler-pro-open-tenant-logs',()=>{ void show() })
})
</script>

<template>
  <button class="tenant-log-launcher" type="button" title="Abrir diagnóstico individual por tenant" @click="show"><ServerCog :size="19"/><span>Logs por tenant</span></button>
  <div v-if="open" class="tenant-log-backdrop" @click.self="open=false">
    <aside class="tenant-log-drawer">
      <header><div><span>Observabilidade persistente</span><h2>Diagnóstico individual do tenant</h2><p>Eventos gravados no banco isolado do cliente, com correlação e detalhes técnicos.</p></div><button class="icon" @click="open=false"><X :size="21"/></button></header>
      <section class="tenant-log-toolbar">
        <label>Tenant<select v-model="selected" @change="loadLogs"><option value="">Selecione um cliente</option><option v-for="tenant in tenants" :key="tenant.id" :value="tenant.id">{{ tenant.name }} — {{ tenant.slug }}</option></select></label>
        <label>Buscar<div class="search"><Search :size="15"/><input v-model="search" placeholder="mensagem, evento, código..." @keyup.enter="loadLogs"/></div></label>
        <label>Nível<select v-model="level" @change="loadLogs"><option value="">Todos</option><option>INFO</option><option>WARNING</option><option>ERROR</option><option>CRITICAL</option></select></label>
        <button :disabled="!selected || loading" @click="loadLogs"><RefreshCw :size="16"/> Atualizar</button>
        <button class="primary" :disabled="!selected || downloading" @click="downloadBundle"><Download :size="16"/> {{ downloading?'Gerando...':'Baixar diagnóstico completo' }}</button>
      </section>
      <p v-if="error" class="tenant-log-error">{{ error }}</p>
      <section v-if="selectedTenant" class="tenant-log-summary"><article><span>Tenant</span><strong>{{ selectedTenant.name }}</strong><small>{{ selectedTenant.primary_hostname || selectedTenant.slug }}</small></article><article><span>Eventos</span><strong>{{ stats.total }}</strong><small>últimos registros consultados</small></article><article><span>Erros</span><strong>{{ stats.errors }}</strong><small>ERROR / CRITICAL</small></article><article><span>Avisos</span><strong>{{ stats.warnings }}</strong><small>WARNING</small></article></section>
      <section class="tenant-log-list">
        <div v-if="loading" class="tenant-log-empty"><RefreshCw class="spin" :size="22"/> Carregando histórico persistente...</div>
        <article v-for="entry in logs" v-else :key="entry.id" class="tenant-log-entry" :class="levelClass(entry.level)">
          <div class="meta"><time>{{ formatDate(entry.created_at) }}</time><span>{{ entry.level }}</span><strong>{{ entry.service }}</strong><em v-if="entry.integration">{{ entry.integration }}</em></div>
          <div class="body"><h3>{{ entry.event }}</h3><p>{{ entry.message }}</p><div class="ids"><code v-if="entry.error_code">{{ entry.error_code }}</code><code v-if="entry.correlation_id">corr {{ entry.correlation_id }}</code><code v-if="entry.request_id">req {{ entry.request_id }}</code></div><details v-if="entry.details && Object.keys(entry.details).length"><summary>Detalhes técnicos</summary><pre>{{ JSON.stringify(entry.details,null,2) }}</pre></details></div>
        </article>
        <div v-if="!loading && selected && !logs.length" class="tenant-log-empty">Nenhum registro encontrado para este filtro.</div>
        <div v-if="!selected" class="tenant-log-empty">Selecione um tenant para ver exatamente o que aconteceu naquele ambiente.</div>
      </section>
    </aside>
  </div>
</template>

<style>
.tenant-log-launcher{position:fixed;right:22px;bottom:22px;z-index:1200;display:flex;align-items:center;gap:8px;min-height:46px;padding:0 16px;border:0;border-radius:15px;background:#0b1d3a;color:#fff;font:inherit;font-size:12px;font-weight:850;box-shadow:0 16px 40px rgba(15,23,42,.22);cursor:pointer}.tenant-log-backdrop{position:fixed;z-index:1500;inset:0;background:rgba(8,18,35,.5);backdrop-filter:blur(5px);display:flex;justify-content:flex-end}.tenant-log-drawer{width:min(920px,96vw);height:100dvh;background:#f6f8fc;box-shadow:-20px 0 70px rgba(8,18,35,.26);overflow:auto;color:#13233b}.tenant-log-drawer>header{position:sticky;top:0;z-index:5;display:flex;justify-content:space-between;gap:20px;padding:25px 28px 20px;background:rgba(255,255,255,.97);border-bottom:1px solid #e1e7ef;backdrop-filter:blur(12px)}.tenant-log-drawer header span{font-size:10px;font-weight:900;text-transform:uppercase;letter-spacing:.1em;color:#2875e8}.tenant-log-drawer header h2{margin:5px 0;font-size:25px;letter-spacing:-.03em}.tenant-log-drawer header p{margin:0;color:#728197;font-size:12px}.tenant-log-drawer .icon{width:42px;height:42px;display:grid;place-items:center;border:1px solid #dce4ee;border-radius:12px;background:#fff;cursor:pointer}.tenant-log-toolbar{display:grid;grid-template-columns:1.2fr 1.2fr .65fr auto auto;gap:9px;padding:17px 22px;background:#fff;border-bottom:1px solid #e4e9f1}.tenant-log-toolbar label{display:grid;gap:5px;font-size:10px;font-weight:850;color:#69788e;text-transform:uppercase;letter-spacing:.04em}.tenant-log-toolbar select,.tenant-log-toolbar input{width:100%;height:42px;border:1px solid #d8e1ec;border-radius:11px;background:#fff;padding:0 11px;font:inherit;font-size:12px;color:#1a2c46;outline:none}.tenant-log-toolbar .search{position:relative}.tenant-log-toolbar .search svg{position:absolute;left:10px;top:13px;color:#8492a6}.tenant-log-toolbar .search input{padding-left:32px}.tenant-log-toolbar button{align-self:end;height:42px;display:flex;align-items:center;justify-content:center;gap:7px;border:1px solid #d9e2ed;border-radius:11px;background:#fff;font:inherit;font-size:11px;font-weight:850;cursor:pointer}.tenant-log-toolbar button.primary{border-color:#2563eb;background:linear-gradient(135deg,#0b1d3a,#19b9ed);color:#fff}.tenant-log-toolbar button:disabled{opacity:.55;cursor:not-allowed}.tenant-log-error{margin:14px 22px 0;padding:12px 14px;border:1px solid #fecaca;border-radius:12px;background:#fff1f2;color:#9f1239;font-size:12px;font-weight:750}.tenant-log-summary{display:grid;grid-template-columns:1.4fr repeat(3,.7fr);gap:10px;padding:17px 22px 5px}.tenant-log-summary article{min-height:98px;padding:15px;border:1px solid #e0e7f0;border-radius:16px;background:#fff}.tenant-log-summary span,.tenant-log-summary strong,.tenant-log-summary small{display:block}.tenant-log-summary span{font-size:9px;font-weight:900;text-transform:uppercase;color:#79889c;letter-spacing:.06em}.tenant-log-summary strong{margin:9px 0 4px;font-size:20px}.tenant-log-summary small{font-size:10px;color:#8996a8}.tenant-log-list{display:grid;gap:9px;padding:15px 22px 90px}.tenant-log-entry{display:grid;grid-template-columns:185px minmax(0,1fr);border:1px solid #e0e7f0;border-left:4px solid #60a5fa;border-radius:16px;background:#fff;overflow:hidden}.tenant-log-entry.warning{border-left-color:#f59e0b}.tenant-log-entry.error,.tenant-log-entry.critical{border-left-color:#ef4444}.tenant-log-entry .meta{padding:14px;border-right:1px solid #edf1f6;background:#fafbfd}.tenant-log-entry .meta>*{display:block}.tenant-log-entry time{font-size:10px;color:#7c8ba0}.tenant-log-entry .meta span{width:max-content;margin:7px 0;padding:4px 7px;border-radius:999px;background:#eff6ff;color:#1d4ed8;font-size:9px;font-weight:900}.tenant-log-entry.error .meta span,.tenant-log-entry.critical .meta span{background:#fee2e2;color:#b91c1c}.tenant-log-entry .meta strong{font-size:11px}.tenant-log-entry .meta em{margin-top:4px;font-size:10px;color:#64748b;font-style:normal}.tenant-log-entry .body{min-width:0;padding:14px 16px}.tenant-log-entry h3{margin:0 0 5px;font-size:13px}.tenant-log-entry p{margin:0;color:#46566e;font-size:12px;line-height:1.5;overflow-wrap:anywhere}.tenant-log-entry .ids{display:flex;flex-wrap:wrap;gap:5px;margin-top:9px}.tenant-log-entry code{padding:3px 6px;border-radius:6px;background:#f1f5f9;color:#475569;font-size:9px}.tenant-log-entry details{margin-top:9px}.tenant-log-entry summary{cursor:pointer;color:#2563eb;font-size:10px;font-weight:800}.tenant-log-entry pre{max-height:300px;overflow:auto;padding:10px;border-radius:9px;background:#0b1729;color:#dbeafe;font-size:10px}.tenant-log-empty{padding:45px 20px;text-align:center;color:#758399;font-size:12px}.spin{animation:tenant-log-spin 1s linear infinite}@keyframes tenant-log-spin{to{transform:rotate(360deg)}}@media(max-width:800px){.tenant-log-launcher span{display:none}.tenant-log-launcher{right:14px;bottom:14px;width:48px;padding:0;justify-content:center}.tenant-log-drawer{width:100vw}.tenant-log-drawer>header{padding:18px 16px}.tenant-log-toolbar{grid-template-columns:1fr 1fr;padding:12px 14px}.tenant-log-toolbar label:first-child,.tenant-log-toolbar label:nth-child(2){grid-column:1/-1}.tenant-log-toolbar button.primary{grid-column:1/-1}.tenant-log-summary{grid-template-columns:1fr 1fr;padding:12px 14px 0}.tenant-log-summary article:first-child{grid-column:1/-1}.tenant-log-list{padding:12px 14px 80px}.tenant-log-entry{grid-template-columns:1fr}.tenant-log-entry .meta{border-right:0;border-bottom:1px solid #edf1f6}.tenant-log-entry .meta>*{display:inline-block;margin-right:6px}.tenant-log-entry .meta span{margin-top:0}.tenant-log-entry .body{padding:13px 14px}}
</style>
