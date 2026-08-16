<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { apiGet, apiPost, apiPut, type ApiError } from './api/client'

type LoginResponse = { access_token: string; refresh_token: string; user: { email: string } }
type SessionState = { accessToken: string; refreshToken: string; userEmail: string }
type ModuleKey = 'overview'|'tenants'|'provisioning'|'domains'|'builds'|'logs'|'branding'|'integrations'|'audit'|'settings'
type Tenant = { id:string;name:string;slug:string;status:string;created_at?:string|null;primary_hostname?:string|null;branding_name?:string|null }
type Domain = { id:string;tenant_id:string;tenant_name?:string;hostname:string;is_primary:boolean;is_temporary:boolean;status:string;validation?:Record<string,unknown> }
type BuildJob = { id:string;tenant?:string;target:string;status:string;created_at?:string|null;source_ref?:string|null;workflow_run_id?:string|null;error?:string|null;artifacts?:Array<{id:string;name:string;download_url?:string|null}> }
type BuildProfile = { id:string;tenant:string;name:string;target:string;api_url:string;bundle_identifier?:string|null;package_name?:string|null;config?:Record<string,unknown> }
type ProvisioningJob = { id:string;tenant_id:string;tenant_name:string;slug:string;status:string;correlation_id:string;created_at?:string|null;steps:Array<{id:string;name:string;status:string;error?:string|null}> }
type Dashboard = { totals:{tenants:number;active_tenants:number;provisioning_jobs:number;domains_pending:number;builds:number;build_artifacts:number;platform_users:number};health:Record<string,string> }
type LogEntry = { id:string;tenant_id?:string|null;tenant_name?:string|null;tenant_slug?:string|null;source:string;service:string;level:string;event:string;message:string;integration?:string|null;error_code?:string|null;details?:Record<string,unknown>;created_at?:string|null }
type LogSummary = { last_24h:{total:number;errors:number;docker:number;integrations:number;tenant_scoped:number};tenant_boundaries:Array<{tenant_id:string;tenant_name:string;slug:string;database_name:string;database_user:string;storage_bucket:string;storage_prefix:string;artifact_prefix:string;isolation_status:string}> }
type AuditEntry = { id:string;user_id?:string|null;email?:string|null;action:string;result:string;ip_address?:string|null;correlation_id?:string|null;metadata:Record<string,unknown>;created_at:string }
type FeatureFlag = { key:string;enabled:boolean;rules:Record<string,unknown> }
type CreatedTenant = { tenant_id:string;tenant_code:string;job_id:string;admin_email:string;initial_admin_password:string;hostname:string;status:string }
type PwaInstaller = { canInstall:boolean;isInstalled:boolean;install:()=>Promise<unknown> }

type NavItem = { key:ModuleKey; label:string; icon:string; description:string }

const storageKey = 'scheduler-pro-admin-session'
const modules: NavItem[] = [
  {key:'overview',label:'Visão geral',icon:'▦',description:'Indicadores operacionais da plataforma'},
  {key:'tenants',label:'Tenants / Clientes',icon:'▤',description:'Clientes, credenciais e isolamento'},
  {key:'provisioning',label:'Provisionamento',icon:'◉',description:'Banco, migrations, storage, DNS e seed'},
  {key:'domains',label:'Domínios',icon:'◎',description:'DNS, domínio próprio, SSL e cache'},
  {key:'builds',label:'Builds e distribuições',icon:'⬢',description:'PWA, desktop, Android e iOS'},
  {key:'logs',label:'Logs e observabilidade',icon:'◫',description:'Aplicação, infraestrutura e tenants'},
  {key:'branding',label:'Marca e aplicativos',icon:'◇',description:'Perfis e identidade por cliente'},
  {key:'integrations',label:'Integrações',icon:'⌁',description:'Cloudflare, Evolution, storage e filas'},
  {key:'audit',label:'Auditoria',icon:'☷',description:'Sessões, segurança e ações sensíveis'},
  {key:'settings',label:'Configurações',icon:'⚙',description:'Feature flags e parâmetros globais'},
]

const email=ref('')
const password=ref('')
const session=ref<SessionState|null>(null)
const errorMessage=ref('')
const toastMessage=ref('')
const loading=ref(false)
const activeModule=ref<ModuleKey>('overview')
const sidebarOpen=ref(false)
const search=ref('')
const tenantContext=ref('')
const installState=ref({canInstall:false,isInstalled:false})

const dashboard=ref<Dashboard|null>(null)
const tenants=ref<Tenant[]>([])
const domains=ref<Domain[]>([])
const builds=ref<BuildJob[]>([])
const profiles=ref<BuildProfile[]>([])
const provisioning=ref<ProvisioningJob[]>([])
const logs=ref<LogEntry[]>([])
const logSummary=ref<LogSummary|null>(null)
const integrations=ref<Record<string,unknown>>({})
const audit=ref<AuditEntry[]>([])
const flags=ref<FeatureFlag[]>([])
const createdTenant=ref<CreatedTenant|null>(null)

const tenantForm=ref({name:'',slug:'',admin_email:'',admin_password:''})
const domainForm=ref({tenant_id:'',hostname:'',make_primary:true})
const buildForm=ref({tenant:'',target:'desktop',source_ref:'main'})
const flagForm=ref({key:'',enabled:true,rules:'{}'})

const isAuthenticated=computed(()=>Boolean(session.value?.accessToken))
const selectedModule=computed(()=>modules.find(item=>item.key===activeModule.value)??modules[0])
const selectedTenant=computed(()=>tenants.value.find(item=>item.id===tenantContext.value)??null)
const query=computed(()=>search.value.trim().toLowerCase())
const profileInitial=computed(()=>(session.value?.userEmail||'A').trim().charAt(0).toUpperCase())

function textMatches(value:string):boolean{return !query.value||value.toLowerCase().includes(query.value)}
function tenantReferenceMatches(value?:string|null):boolean{
  if(!selectedTenant.value)return true
  const raw=String(value||'').toLowerCase()
  return [selectedTenant.value.id,selectedTenant.value.name,selectedTenant.value.slug].some(item=>raw.includes(item.toLowerCase()))
}

const filteredTenants=computed(()=>tenants.value.filter(item=>(!tenantContext.value||item.id===tenantContext.value)&&textMatches(`${item.name} ${item.slug} ${item.primary_hostname||''} ${item.status}`)))
const filteredDomains=computed(()=>domains.value.filter(item=>(!tenantContext.value||item.tenant_id===tenantContext.value)&&textMatches(`${item.hostname} ${item.tenant_name||''} ${item.status}`)))
const filteredBuilds=computed(()=>builds.value.filter(item=>tenantReferenceMatches(item.tenant)&&textMatches(`${item.target} ${item.status} ${item.source_ref||''} ${item.tenant||''}`)))
const filteredProvisioning=computed(()=>provisioning.value.filter(item=>(!tenantContext.value||item.tenant_id===tenantContext.value)&&textMatches(`${item.tenant_name} ${item.slug} ${item.status}`)))
const filteredProfiles=computed(()=>profiles.value.filter(item=>tenantReferenceMatches(item.tenant)&&textMatches(`${item.tenant} ${item.name} ${item.target} ${item.api_url}`)))
const filteredLogs=computed(()=>logs.value.filter(item=>(!tenantContext.value||item.tenant_id===tenantContext.value||tenantReferenceMatches(item.tenant_name)||tenantReferenceMatches(item.tenant_slug))&&textMatches(`${item.level} ${item.source} ${item.service} ${item.event} ${item.message} ${item.tenant_name||''}`)))

const metricClients=computed(()=>selectedTenant.value?1:(dashboard.value?.totals.tenants??tenants.value.length))
const metricActiveClients=computed(()=>selectedTenant.value?(selectedTenant.value.status.toLowerCase()==='active'?1:0):(dashboard.value?.totals.active_tenants??tenants.value.filter(t=>t.status.toLowerCase()==='active').length))
const metricProvisioning=computed(()=>selectedTenant.value?filteredProvisioning.value.length:(dashboard.value?.totals.provisioning_jobs??provisioning.value.length))
const metricPendingDomains=computed(()=>selectedTenant.value?filteredDomains.value.filter(item=>!['active','ready','verified'].includes(item.status.toLowerCase())).length:(dashboard.value?.totals.domains_pending??0))
const metricArtifacts=computed(()=>selectedTenant.value?filteredBuilds.value.reduce((sum,item)=>sum+(item.artifacts?.length||0),0):(dashboard.value?.totals.build_artifacts??0))
const metricBuilds=computed(()=>selectedTenant.value?filteredBuilds.value.length:(dashboard.value?.totals.builds??builds.value.length))

function token():string{return session.value?.accessToken||''}
function formatDate(value?:string|null):string{return value?new Date(value).toLocaleString('pt-BR'):'—'}
function statusClass(value?:string|null):string{return String(value||'').toLowerCase().replace(/[^a-z0-9]+/g,'-')}
function showToast(message:string):void{toastMessage.value=message;window.setTimeout(()=>{if(toastMessage.value===message)toastMessage.value=''},3500)}
function describeError(error:unknown,fallback:string):string{
  const value=error as Partial<ApiError>
  if(value?.message&&value?.code)return `${value.message} (${value.code})`
  return value?.message||fallback
}
function restoreSession():void{const raw=localStorage.getItem(storageKey);if(!raw)return;try{session.value=JSON.parse(raw) as SessionState}catch{localStorage.removeItem(storageKey)}}
function clearSession():void{session.value=null;localStorage.removeItem(storageKey)}

async function login():Promise<void>{
  loading.value=true
  errorMessage.value=''
  try{
    const payload=await apiPost<LoginResponse>('/auth/platform/login',{email:email.value,password:password.value})
    session.value={accessToken:payload.access_token,refreshToken:payload.refresh_token,userEmail:payload.user?.email||email.value}
    localStorage.setItem(storageKey,JSON.stringify(session.value))
    password.value=''
    await refreshAll()
  }catch(error){errorMessage.value=describeError(error,'Não foi possível entrar na plataforma.')}
  finally{loading.value=false}
}

async function refreshAll():Promise<void>{
  if(!token())return
  loading.value=true
  errorMessage.value=''
  let expired=false
  const failures:string[]=[]
  try{
    const results=await Promise.allSettled([
      apiGet<Dashboard>('/platform/dashboard',token()),
      apiGet<Tenant[]>('/platform/tenants',token()),
      apiGet<Domain[]>('/platform/domains',token()),
      apiGet<{jobs:BuildJob[]}>('/platform/builds/jobs?limit=100',token()),
      apiGet<{profiles:BuildProfile[]}>('/platform/builds/profiles',token()),
      apiGet<ProvisioningJob[]>('/platform/provisioning',token()),
    ] as const)

    function applyResult<T>(result:PromiseSettledResult<T>,apply:(value:T)=>void,label:string):void{
      if(result.status==='fulfilled'){apply(result.value);return}
      const apiError=result.reason as Partial<ApiError>
      if(apiError?.status===401||apiError?.status===403){expired=true;return}
      failures.push(`${label}: ${describeError(result.reason,'indisponível')}`)
    }

    applyResult(results[0],value=>{dashboard.value=value},'Dashboard')
    applyResult(results[1],value=>{tenants.value=value},'Tenants')
    applyResult(results[2],value=>{domains.value=value},'Domínios')
    applyResult(results[3],value=>{builds.value=value.jobs||[]},'Builds')
    applyResult(results[4],value=>{profiles.value=value.profiles||[]},'Perfis')
    applyResult(results[5],value=>{provisioning.value=value},'Provisionamento')

    if(expired){clearSession();return}

    try{
      if(activeModule.value==='logs')await loadLogs()
      if(activeModule.value==='integrations')integrations.value=await apiGet('/platform/integrations/status',token())
      if(activeModule.value==='audit')audit.value=await apiGet('/platform/audit?limit=300',token())
      if(activeModule.value==='settings')flags.value=await apiGet('/platform/feature-flags',token())
    }catch(error){
      const apiError=error as Partial<ApiError>
      if(apiError?.status===401||apiError?.status===403){clearSession();return}
      failures.push(describeError(error,`Falha ao carregar ${selectedModule.value.label}.`))
    }

    if(failures.length)errorMessage.value=`Alguns dados não puderam ser atualizados. ${failures[0]}`
  }finally{loading.value=false}
}

async function loadLogs():Promise<void>{
  const results=await Promise.allSettled([
    apiGet<LogEntry[]>('/platform/observability/logs?limit=300',token()),
    apiGet<LogSummary>('/platform/observability/logs/summary',token()),
  ] as const)
  if(results[0].status==='fulfilled')logs.value=results[0].value
  else throw results[0].reason
  if(results[1].status==='fulfilled')logSummary.value=results[1].value
  else throw results[1].reason
}

async function selectModule(key:ModuleKey):Promise<void>{activeModule.value=key;sidebarOpen.value=false;await refreshAll()}
function chooseTenant():void{search.value=''}
async function createTenant():Promise<void>{try{createdTenant.value=await apiPost('/platform/tenants',{name:tenantForm.value.name,slug:tenantForm.value.slug||null,admin_email:tenantForm.value.admin_email,admin_password:tenantForm.value.admin_password||null},token());tenantForm.value={name:'',slug:'',admin_email:'',admin_password:''};showToast('Cliente criado e provisionamento iniciado.');await refreshAll();activeModule.value='provisioning'}catch(error){errorMessage.value=describeError(error,'Falha ao criar cliente.')}}
async function retryProvision(jobId:string):Promise<void>{try{await apiPost(`/platform/provisioning/${jobId}/retry`,{},token());showToast('Provisionamento reenfileirado.');await refreshAll()}catch(error){errorMessage.value=describeError(error,'Falha ao reenfileirar provisionamento.')}}
async function temporaryDomain(id:string):Promise<void>{try{await apiPost(`/platform/tenants/${id}/domains/temporary`,{},token());showToast('DNS temporário solicitado.');await refreshAll()}catch(error){errorMessage.value=describeError(error,'Falha no DNS temporário.')}}
async function customDomain():Promise<void>{try{await apiPost(`/platform/tenants/${domainForm.value.tenant_id}/domains/custom`,{hostname:domainForm.value.hostname,make_primary:domainForm.value.make_primary},token());domainForm.value.hostname='';showToast('Domínio enviado para validação.');await refreshAll()}catch(error){errorMessage.value=describeError(error,'Falha ao conectar domínio.')}}
async function checkDomain(id:string):Promise<void>{try{await apiPost(`/platform/domains/${id}/check`,{},token());showToast('Verificação concluída.');await refreshAll()}catch(error){errorMessage.value=describeError(error,'Falha na verificação do domínio.')}}
async function purgeDomain(id:string):Promise<void>{try{await apiPost(`/platform/domains/${id}/purge-cache`,{},token());showToast('Cache invalidado.');if(activeModule.value==='logs')await loadLogs()}catch(error){errorMessage.value=describeError(error,'Falha ao invalidar cache.')}}
async function createBuild():Promise<void>{try{await apiPost('/platform/builds/requests',{...buildForm.value,requested_by:session.value?.userEmail,payload:{origin:'admin-pwa'}},token());showToast('Build solicitado.');await refreshAll()}catch(error){errorMessage.value=describeError(error,'Falha ao solicitar build.')}}
async function refreshBuild(id:string):Promise<void>{try{await apiPost(`/platform/builds/jobs/${id}/refresh`,{},token());showToast('Build sincronizado.');await refreshAll()}catch(error){errorMessage.value=describeError(error,'Falha ao sincronizar build.')}}
async function saveFlag():Promise<void>{try{let rules:Record<string,unknown>;try{rules=JSON.parse(flagForm.value.rules) as Record<string,unknown>}catch{throw new Error('As regras devem ser um JSON válido.')}await apiPut(`/platform/feature-flags/${encodeURIComponent(flagForm.value.key)}`,{enabled:flagForm.value.enabled,rules},token());flagForm.value={key:'',enabled:true,rules:'{}'};flags.value=await apiGet('/platform/feature-flags',token());showToast('Configuração salva.')}catch(error){errorMessage.value=error instanceof Error?error.message:'Falha ao salvar configuração.'}}
function updateInstallState():void{const installer=(window as unknown as{schedulerProAdminPwa?:PwaInstaller}).schedulerProAdminPwa;installState.value={canInstall:Boolean(installer?.canInstall),isInstalled:Boolean(installer?.isInstalled)}}
async function installPwa():Promise<void>{const installer=(window as unknown as{schedulerProAdminPwa?:PwaInstaller}).schedulerProAdminPwa;if(installer?.isInstalled){showToast('Aplicativo administrativo já instalado.');return}if(installer?.canInstall){await installer.install();updateInstallState()}}
function logout():void{clearSession();dashboard.value=null;tenantContext.value=''}

onMounted(()=>{restoreSession();updateInstallState();if(token())void refreshAll();window.addEventListener('scheduler-pro-admin-install-state',updateInstallState)})
onUnmounted(()=>window.removeEventListener('scheduler-pro-admin-install-state',updateInstallState))
</script>

<template>
  <main class="admin-root">
    <section v-if="!isAuthenticated" class="auth-page">
      <aside class="auth-visual auth-visual-minimal" aria-label="Scheduler Pro">
        <div class="auth-brand auth-brand-only">
          <div class="brand-mark">SP</div>
          <div><strong>Scheduler Pro</strong><span>Control Plane</span></div>
        </div>
      </aside>
      <form class="auth-card" @submit.prevent="login">
        <div class="mobile-brand"><div class="brand-mark">SP</div><div><strong>Scheduler Pro</strong><span>Control Plane</span></div></div>
        <h2>Entrar na plataforma</h2>
        <p class="auth-helper">Utilize suas credenciais administrativas.</p>
        <label>E-mail<input v-model="email" type="email" autocomplete="username" required/></label>
        <label>Senha<input v-model="password" type="password" autocomplete="current-password" required/></label>
        <p v-if="errorMessage" class="form-error">{{errorMessage}}</p>
        <button class="btn primary full" :disabled="loading">{{loading?'Validando...':'Entrar'}}</button>
      </form>
    </section>

    <div v-else class="admin-shell" :class="{mobileOpen:sidebarOpen}">
      <aside class="sidebar">
        <div class="brand"><div class="brand-mark">SP</div><div><strong>Scheduler Pro</strong><small>Control Plane</small></div></div>
        <nav class="nav-list">
          <button v-for="item in modules" :key="item.key" class="nav-item" :class="{active:activeModule===item.key}" @click="selectModule(item.key)">
            <span class="nav-icon">{{item.icon}}</span><span>{{item.label}}</span>
          </button>
        </nav>
        <div class="sidebar-footer">
          <button class="nav-item sidebar-logout" @click="logout"><span class="nav-icon">⇥</span><span>Sair</span></button>
          <div class="sidebar-account"><strong>{{session?.userEmail}}</strong><small>Administrador da plataforma</small></div>
        </div>
      </aside>
      <button v-if="sidebarOpen" class="mobile-backdrop" aria-label="Fechar menu" @click="sidebarOpen=false"></button>

      <section class="content-shell">
        <header class="topbar">
          <button class="icon-button" aria-label="Menu" @click="sidebarOpen=!sidebarOpen">☰</button>
          <label class="company-switcher">
            <span>Tenant</span>
            <select v-model="tenantContext" @change="chooseTenant">
              <option value="">Todos os clientes</option>
              <option v-for="tenant in tenants" :key="tenant.id" :value="tenant.id">{{tenant.name}}</option>
            </select>
          </label>
          <label class="topbar-search"><span>⌕</span><input v-model="search" placeholder="Buscar tenant, domínio, build ou evento"/></label>
          <div class="topbar-spacer"></div>
          <button v-if="installState.canInstall&&!installState.isInstalled" class="btn" @click="installPwa">Instalar</button>
          <button class="icon-button refresh-button" :disabled="loading" title="Atualizar" @click="refreshAll">↻</button>
          <div class="profile"><div><strong>{{session?.userEmail}}</strong><small>platform_admin</small></div><div class="avatar">{{profileInitial}}</div></div>
        </header>

        <main class="main-content">
          <section class="page-header">
            <div>
              <p class="eyebrow">{{selectedTenant?'Tenant selecionado':'Plataforma'}}</p>
              <h1>{{selectedModule.label}}</h1>
              <p>{{selectedModule.description}}</p>
            </div>
            <div class="page-actions">
              <span v-if="selectedTenant" class="tenant-context-badge"><b>{{selectedTenant.name}}</b><small>{{selectedTenant.primary_hostname||selectedTenant.slug}}</small></span>
            </div>
          </section>

          <p v-if="toastMessage" class="toast-message">{{toastMessage}}</p>
          <p v-if="errorMessage" class="form-error wide">{{errorMessage}}</p>

          <section class="metric-grid">
            <article class="metric-card blue"><div><span>Tenants / Clientes</span><strong>{{metricClients}}</strong><small>{{metricActiveClients}} ativos</small></div><b>▤</b></article>
            <article class="metric-card violet"><div><span>Provisionamentos</span><strong>{{metricProvisioning}}</strong><small>jobs registrados</small></div><b>◉</b></article>
            <article class="metric-card green"><div><span>Domínios pendentes</span><strong>{{metricPendingDomains}}</strong><small>DNS / SSL</small></div><b>◎</b></article>
            <article class="metric-card orange"><div><span>Artefatos</span><strong>{{metricArtifacts}}</strong><small>{{metricBuilds}} builds</small></div><b>⬢</b></article>
          </section>

          <section v-if="activeModule==='overview'" class="dashboard-grid">
            <article class="panel">
              <div class="panel-title"><div><h3>Tenants recentes</h3><p>Clientes e ambientes provisionados</p></div><button class="btn small" @click="selectModule('tenants')">Ver clientes</button></div>
              <div class="responsive-table"><table><thead><tr><th>Cliente</th><th>Domínio</th><th>Status</th></tr></thead><tbody><tr v-for="tenant in filteredTenants.slice(0,8)" :key="tenant.id"><td><strong>{{tenant.name}}</strong><small>{{tenant.slug}}</small></td><td>{{tenant.primary_hostname||'Domínio pendente'}}</td><td><span :class="['status-pill',statusClass(tenant.status)]">{{tenant.status}}</span></td></tr><tr v-if="!filteredTenants.length"><td colspan="3"><div class="empty-state">Nenhum tenant encontrado.</div></td></tr></tbody></table></div>
            </article>
            <article class="panel">
              <div class="panel-title"><div><h3>Saúde da plataforma</h3><p>Serviços essenciais</p></div></div>
              <div class="health-list"><div v-for="(value,key) in dashboard?.health||{}" :key="key"><span><i class="ok"></i>{{key}}</span><strong>{{value}}</strong></div><div v-if="!Object.keys(dashboard?.health||{}).length"><span>Sem telemetria</span><strong>—</strong></div></div>
            </article>
          </section>

          <section v-else-if="activeModule==='tenants'" class="view-stack">
            <article class="panel form-panel"><div><h2>Novo tenant / cliente</h2><p>Crie o cliente e inicie o provisionamento isolado.</p></div><form class="inline-form" @submit.prevent="createTenant"><input v-model="tenantForm.name" placeholder="Nome da empresa" required/><input v-model="tenantForm.slug" placeholder="Código opcional"/><input v-model="tenantForm.admin_email" type="email" placeholder="E-mail do administrador" required/><input v-model="tenantForm.admin_password" type="password" minlength="12" placeholder="Senha opcional"/><button class="btn primary">Criar e provisionar</button></form></article>
            <article v-if="createdTenant" class="credential-card"><strong>Credencial inicial gerada</strong><span>{{createdTenant.admin_email}}</span><code>{{createdTenant.initial_admin_password}}</code><small>Esta senha deve ser entregue ao cliente e armazenada com segurança.</small></article>
            <article class="panel table-panel"><div class="panel-title"><div><h3>Tenants / Clientes</h3><p>{{filteredTenants.length}} registro(s)</p></div></div><div class="responsive-table"><table><thead><tr><th>Cliente</th><th>Domínio principal</th><th>Código</th><th>Status</th><th>Ações</th></tr></thead><tbody><tr v-for="tenant in filteredTenants" :key="tenant.id"><td><strong>{{tenant.name}}</strong><small>{{tenant.branding_name||'Scheduler Pro'}}</small></td><td>{{tenant.primary_hostname||'—'}}</td><td>{{tenant.slug}}</td><td><span :class="['status-pill',statusClass(tenant.status)]">{{tenant.status}}</span></td><td><div class="actions-cell"><button class="btn small" @click="tenantContext=tenant.id">Selecionar</button><button class="btn small" @click="temporaryDomain(tenant.id)">DNS temporário</button></div></td></tr></tbody></table></div></article>
          </section>

          <section v-else-if="activeModule==='provisioning'" class="view-stack">
            <article v-for="job in filteredProvisioning" :key="job.id" class="panel provisioning-card"><div class="panel-title"><div><h3>{{job.tenant_name}}</h3><p>{{job.slug}} • {{formatDate(job.created_at)}} • {{job.correlation_id}}</p></div><div class="actions"><span :class="['status-pill',statusClass(job.status)]">{{job.status}}</span><button v-if="job.status.toLowerCase()==='failed'" class="btn small" @click="retryProvision(job.id)">Tentar novamente</button></div></div><div class="step-grid"><article v-for="step in job.steps" :key="step.id" :class="['step',statusClass(step.status)]"><strong>{{step.name}}</strong><span>{{step.status}}</span><small v-if="step.error">{{step.error}}</small></article></div></article>
            <div v-if="!filteredProvisioning.length" class="empty-state">Nenhum provisionamento para o contexto atual.</div>
          </section>

          <section v-else-if="activeModule==='domains'" class="view-stack">
            <article class="panel form-panel"><div><h2>Conectar domínio</h2><p>Associe um domínio próprio ao tenant selecionado.</p></div><form class="inline-form" @submit.prevent="customDomain"><select v-model="domainForm.tenant_id" required><option value="">Selecione o tenant</option><option v-for="tenant in tenants" :key="tenant.id" :value="tenant.id">{{tenant.name}}</option></select><input v-model="domainForm.hostname" placeholder="agenda.cliente.com.br" required/><label class="checkbox-line"><input v-model="domainForm.make_primary" type="checkbox"/> Tornar primário</label><button class="btn primary">Conectar domínio</button></form></article>
            <article class="panel table-panel"><div class="panel-title"><div><h3>Domínios</h3><p>DNS, SSL e cache por tenant</p></div></div><div class="responsive-table"><table><thead><tr><th>Hostname</th><th>Tenant</th><th>Tipo</th><th>Status</th><th>Ações</th></tr></thead><tbody><tr v-for="domain in filteredDomains" :key="domain.id"><td><strong>{{domain.hostname}}</strong><small>{{domain.is_primary?'Primário':'Secundário'}}</small></td><td>{{domain.tenant_name||domain.tenant_id}}</td><td>{{domain.is_temporary?'Temporário':'Personalizado'}}</td><td><span :class="['status-pill',statusClass(domain.status)]">{{domain.status}}</span></td><td><div class="actions-cell"><button class="btn small" @click="checkDomain(domain.id)">Verificar</button><button class="btn small" @click="purgeDomain(domain.id)">Limpar cache</button></div></td></tr></tbody></table></div></article>
          </section>

          <section v-else-if="activeModule==='builds'" class="view-stack">
            <article class="panel form-panel"><div><h2>Nova distribuição</h2><p>Dispare a geração de artefatos para o cliente.</p></div><form class="inline-form" @submit.prevent="createBuild"><select v-model="buildForm.tenant" required><option value="">Selecione o tenant</option><option v-for="tenant in tenants" :key="tenant.id" :value="tenant.id">{{tenant.name}}</option></select><select v-model="buildForm.target"><option value="web">Web / PWA</option><option value="desktop">Desktop cliente</option><option value="android">Android cliente</option><option value="ios">iOS cliente</option><option value="admin-desktop">Desktop admin</option><option value="admin-android">Android admin</option><option value="admin-ios">iOS admin</option></select><input v-model="buildForm.source_ref" placeholder="main"/><button class="btn primary">Gerar artefato</button></form></article>
            <article class="panel table-panel"><div class="panel-title"><div><h3>Builds e distribuições</h3><p>Execuções e artefatos gerados</p></div></div><div class="responsive-table"><table><thead><tr><th>Alvo</th><th>Tenant</th><th>Origem</th><th>Data</th><th>Status</th><th>Ação</th></tr></thead><tbody><tr v-for="build in filteredBuilds" :key="build.id"><td><strong>{{build.target}}</strong><small>run {{build.workflow_run_id||'aguardando'}}</small></td><td>{{build.tenant||'—'}}</td><td>{{build.source_ref||'main'}}</td><td>{{formatDate(build.created_at)}}</td><td><span :class="['status-pill',statusClass(build.status)]">{{build.status}}</span><small v-if="build.error" class="error-text">{{build.error}}</small></td><td><button class="btn small" @click="refreshBuild(build.id)">Sincronizar</button></td></tr></tbody></table></div></article>
          </section>

          <section v-else-if="activeModule==='logs'" class="view-stack">
            <section class="metric-grid compact"><article class="metric-card"><div><span>Eventos 24h</span><strong>{{logSummary?.last_24h.total??0}}</strong></div></article><article class="metric-card"><div><span>Erros</span><strong>{{logSummary?.last_24h.errors??0}}</strong></div></article><article class="metric-card"><div><span>Integrações</span><strong>{{logSummary?.last_24h.integrations??0}}</strong></div></article></section>
            <article class="panel"><div class="panel-title"><div><h3>Logs e observabilidade</h3><p>Eventos da plataforma e dos tenants</p></div></div><div class="log-list"><details v-for="log in filteredLogs" :key="log.id"><summary><strong>{{log.level}} • {{log.source}} • {{log.event}}</strong><small>{{formatDate(log.created_at)}} • {{log.tenant_name||log.tenant_slug||'plataforma'}} • {{log.message}}</small></summary><pre>{{JSON.stringify(log.details||{error_code:log.error_code,integration:log.integration},null,2)}}</pre></details></div></article>
            <article class="panel table-panel"><div class="panel-title"><div><h3>Isolamento por tenant</h3><p>Banco, storage e artefatos</p></div></div><div class="responsive-table"><table><thead><tr><th>Tenant</th><th>Banco</th><th>Storage</th><th>Artefatos</th><th>Status</th></tr></thead><tbody><tr v-for="boundary in logSummary?.tenant_boundaries||[]" :key="boundary.tenant_id"><td>{{boundary.tenant_name}}</td><td><strong>{{boundary.database_name}}</strong><small>{{boundary.database_user}}</small></td><td><strong>{{boundary.storage_bucket}}</strong><small>{{boundary.storage_prefix}}</small></td><td>{{boundary.artifact_prefix}}</td><td><span :class="['status-pill',statusClass(boundary.isolation_status)]">{{boundary.isolation_status}}</span></td></tr></tbody></table></div></article>
          </section>

          <section v-else-if="activeModule==='branding'" class="view-stack">
            <article class="panel table-panel"><div class="panel-title"><div><h3>Marca e aplicativos</h3><p>Perfis de distribuição configurados por cliente</p></div></div><div class="responsive-table"><table><thead><tr><th>Tenant</th><th>Aplicativo</th><th>Nome</th><th>Endpoint</th><th>Identificador</th></tr></thead><tbody><tr v-for="profile in filteredProfiles" :key="profile.id"><td>{{profile.tenant}}</td><td>{{profile.target}}</td><td><strong>{{profile.name}}</strong></td><td>{{profile.api_url}}</td><td>{{profile.bundle_identifier||profile.package_name||'—'}}</td></tr></tbody></table></div></article>
          </section>

          <section v-else-if="activeModule==='integrations'" class="cards-grid">
            <article v-for="(value,key) in integrations" :key="key" class="panel card integration-card"><h3>{{key}}</h3><pre>{{JSON.stringify(value,null,2)}}</pre></article>
            <div v-if="!Object.keys(integrations).length" class="empty-state">Nenhum estado de integração retornado.</div>
          </section>

          <section v-else-if="activeModule==='audit'" class="view-stack">
            <article class="panel table-panel"><div class="panel-title"><div><h3>Auditoria da plataforma</h3><p>Usuários, ações e resultados</p></div></div><div class="responsive-table"><table><thead><tr><th>Data</th><th>Usuário</th><th>Ação</th><th>IP</th><th>Resultado</th></tr></thead><tbody><tr v-for="entry in audit" :key="entry.id"><td>{{formatDate(entry.created_at)}}</td><td>{{entry.email||entry.user_id||'sistema'}}</td><td>{{entry.action}}</td><td>{{entry.ip_address||'—'}}</td><td><span :class="['status-pill',statusClass(entry.result)]">{{entry.result}}</span></td></tr></tbody></table></div></article>
          </section>

          <section v-else class="view-stack">
            <article class="panel form-panel"><div><h2>Feature flag</h2><p>Controle recursos globais sem alterar o código publicado.</p></div><form class="inline-form" @submit.prevent="saveFlag"><input v-model="flagForm.key" placeholder="chave" required/><label class="checkbox-line"><input v-model="flagForm.enabled" type="checkbox"/> Habilitada</label><input v-model="flagForm.rules" placeholder="{}"/><button class="btn primary">Salvar</button></form></article>
            <article class="panel table-panel"><div class="panel-title"><div><h3>Configurações</h3><p>Flags e regras cadastradas</p></div></div><div class="responsive-table"><table><thead><tr><th>Chave</th><th>Regras</th><th>Status</th></tr></thead><tbody><tr v-for="flag in flags" :key="flag.key"><td><strong>{{flag.key}}</strong></td><td><code>{{JSON.stringify(flag.rules)}}</code></td><td><span :class="['status-pill',flag.enabled?'active':'inactive']">{{flag.enabled?'Ativa':'Inativa'}}</span></td></tr></tbody></table></div></article>
          </section>
        </main>
      </section>
    </div>
  </main>
</template>
