<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { Boxes, Check, RotateCcw, Settings2, ShieldCheck, X } from 'lucide-vue-next'
import { apiDelete, apiGet, apiPut, type ApiError } from './api/client'

type Version='1.0.0'|'2.0.0'|'2.0.1'
type Session={accessToken:string;refreshToken:string;userEmail:string}
type Tenant={id:string;name:string;slug:string;status:string}
type Release={version:Version;label:string;schema:string;channel:string;recommended:boolean;description:string;allowed?:boolean}
type PlatformPolicy={product:string;default_version:Version;supported_versions:Version[];releases:Release[];policy_configured:boolean}
type TenantPolicy={tenant_id:string;explicit:boolean;allowed_versions:Version[];default_version?:Version|null;platform_default_version:Version;supported_versions:Version[];releases:Release[]}

const storageKey='scheduler-pro-admin-session'
const open=ref(false)
const loading=ref(false)
const saving=ref(false)
const error=ref('')
const toast=ref('')
const session=ref<Session|null>(null)
const platform=ref<PlatformPolicy|null>(null)
const tenants=ref<Tenant[]>([])
const tenantId=ref('')
const tenantPolicy=ref<TenantPolicy|null>(null)
const globalDefault=ref<Version>('2.0.1')
const allowed=ref<Version[]>([])
const tenantDefault=ref<Version|''>('')

const authenticated=computed(()=>Boolean(session.value?.accessToken))
const selectedTenant=computed(()=>tenants.value.find(item=>item.id===tenantId.value)||null)
const releases=computed(()=>platform.value?.releases||[])
const token=()=>session.value?.accessToken||''

function readSession():void{
  const raw=localStorage.getItem(storageKey)
  if(!raw){session.value=null;return}
  try{session.value=JSON.parse(raw) as Session}catch{session.value=null}
}
function describe(exc:unknown,fallback:string):string{
  const value=exc as Partial<ApiError>
  return value?.message||fallback
}
function message(value:string):void{
  toast.value=value
  window.setTimeout(()=>{if(toast.value===value)toast.value=''},3500)
}
function selected(version:Version):boolean{return allowed.value.includes(version)}
function toggle(version:Version):void{
  allowed.value=selected(version)
    ? allowed.value.filter(item=>item!==version)
    : [...allowed.value,version]
  if(tenantDefault.value&&!allowed.value.includes(tenantDefault.value))tenantDefault.value=''
}
function releaseAll():void{
  allowed.value=(platform.value?.supported_versions||[]).slice()
  if(!tenantDefault.value)tenantDefault.value=globalDefault.value
}
function releaseOnlyDefault():void{
  allowed.value=[globalDefault.value]
  tenantDefault.value=globalDefault.value
}
function blockBuilder():void{allowed.value=[];tenantDefault.value=''}

async function loadPlatform():Promise<void>{
  const [policy,rows]=await Promise.all([
    apiGet<PlatformPolicy>('/platform/visual-builder',token()),
    apiGet<Tenant[]>('/platform/tenants',token()),
  ])
  platform.value=policy
  globalDefault.value=policy.default_version
  tenants.value=rows
  if(!tenantId.value&&rows.length)tenantId.value=rows[0]!.id
}
async function loadTenant():Promise<void>{
  if(!tenantId.value){tenantPolicy.value=null;allowed.value=[];tenantDefault.value='';return}
  const policy=await apiGet<TenantPolicy>(`/platform/visual-builder/tenants/${tenantId.value}`,token())
  tenantPolicy.value=policy
  allowed.value=policy.allowed_versions.slice()
  tenantDefault.value=policy.default_version||''
}
async function openManager():Promise<void>{
  readSession()
  if(!authenticated.value)return
  open.value=true;loading.value=true;error.value=''
  try{await loadPlatform();await loadTenant()}
  catch(exc){error.value=describe(exc,'Não foi possível carregar as releases do editor.')}
  finally{loading.value=false}
}
function close():void{open.value=false;error.value=''}
async function changeTenant():Promise<void>{
  loading.value=true;error.value=''
  try{await loadTenant()}catch(exc){error.value=describe(exc,'Falha ao carregar a política da empresa.')}
  finally{loading.value=false}
}
async function saveGlobalDefault():Promise<void>{
  saving.value=true;error.value=''
  try{
    platform.value=await apiPut<PlatformPolicy>('/platform/visual-builder/default',{version:globalDefault.value},token())
    globalDefault.value=platform.value.default_version
    message(`ARGWS Visual Builder ${globalDefault.value} definido como padrão global.`)
    if(tenantPolicy.value&&!tenantPolicy.value.explicit)await loadTenant()
  }catch(exc){error.value=describe(exc,'Falha ao salvar a versão padrão.')}
  finally{saving.value=false}
}
async function saveTenant():Promise<void>{
  if(!tenantId.value)return
  saving.value=true;error.value=''
  try{
    tenantPolicy.value=await apiPut<TenantPolicy>(
      `/platform/visual-builder/tenants/${tenantId.value}`,
      {allowed_versions:allowed.value,default_version:tenantDefault.value||null},
      token(),
    )
    allowed.value=tenantPolicy.value.allowed_versions.slice()
    tenantDefault.value=tenantPolicy.value.default_version||''
    message('Releases liberadas para a empresa atualizadas.')
  }catch(exc){error.value=describe(exc,'Falha ao salvar as releases da empresa.')}
  finally{saving.value=false}
}
async function inheritGlobal():Promise<void>{
  if(!tenantId.value)return
  saving.value=true;error.value=''
  try{
    tenantPolicy.value=await apiDelete<TenantPolicy>(`/platform/visual-builder/tenants/${tenantId.value}`,token())
    allowed.value=tenantPolicy.value.allowed_versions.slice()
    tenantDefault.value=tenantPolicy.value.default_version||''
    message('Empresa voltou a herdar a versão padrão global.')
  }catch(exc){error.value=describe(exc,'Falha ao restaurar a política herdada.')}
  finally{saving.value=false}
}
function authChanged():void{
  const before=authenticated.value
  readSession()
  if(before&&!authenticated.value)close()
}

onMounted(()=>{
  readSession()
  window.addEventListener('storage',authChanged)
  window.addEventListener('scheduler-pro-admin-auth-changed',authChanged)
})
onUnmounted(()=>{
  window.removeEventListener('storage',authChanged)
  window.removeEventListener('scheduler-pro-admin-auth-changed',authChanged)
})
</script>

<template>
  <button v-if="authenticated" class="vb-launcher" type="button" @click="openManager">
    <Boxes :size="17"/><strong>ARGWS Visual Builder</strong>
  </button>
  <div v-if="open&&authenticated" class="vb-backdrop" @click.self="close">
    <section class="vb-manager">
      <header class="vb-topbar">
        <div><span>Scheduler Pro · Control Plane</span><h2>ARGWS Visual Builder Editor</h2><p>Gerencie versões instaladas, padrão global e liberação por empresa.</p></div>
        <button class="vb-icon" aria-label="Fechar" @click="close"><X :size="19"/></button>
      </header>

      <div v-if="loading" class="vb-state">Carregando política de releases…</div>
      <template v-else>
        <p v-if="toast" class="vb-success">{{toast}}</p>
        <p v-if="error" class="vb-error">{{error}}</p>

        <section class="vb-section">
          <div class="vb-section-title"><div><span>Política global</span><h3>Release padrão da plataforma</h3></div><ShieldCheck :size="22"/></div>
          <div class="vb-global-row">
            <label>Versão padrão
              <select v-model="globalDefault" :disabled="saving">
                <option v-for="item in releases" :key="item.version" :value="item.version">{{item.version}}{{item.recommended?' · recomendada':''}}</option>
              </select>
            </label>
            <button class="vb-primary" :disabled="saving" @click="saveGlobalDefault"><Check :size="16"/>Salvar padrão</button>
          </div>
          <div class="vb-release-grid">
            <article v-for="item in releases" :key="item.version" :class="{current:item.version===globalDefault}">
              <div><strong>{{item.label}}</strong><span>{{item.channel}}</span></div>
              <p>{{item.description}}</p><small>{{item.schema}}</small>
            </article>
          </div>
        </section>

        <section class="vb-section">
          <div class="vb-section-title"><div><span>Liberação por empresa</span><h3>{{selectedTenant?.name||'Selecione uma empresa'}}</h3></div><Settings2 :size="22"/></div>
          <label class="vb-tenant-select">Empresa
            <select v-model="tenantId" :disabled="saving" @change="changeTenant">
              <option v-for="tenant in tenants" :key="tenant.id" :value="tenant.id">{{tenant.name}} · {{tenant.slug}}</option>
            </select>
          </label>

          <template v-if="tenantPolicy">
            <div class="vb-policy-note" :class="{inherited:!tenantPolicy.explicit}">
              <strong>{{tenantPolicy.explicit?'Política própria':'Herdando o padrão global'}}</strong>
              <span v-if="!tenantPolicy.explicit">Enquanto não houver política própria, a empresa recebe apenas {{tenantPolicy.platform_default_version}}.</span>
              <span v-else>O tenant poderá escolher somente entre as versões marcadas abaixo.</span>
            </div>

            <div class="vb-actions-inline">
              <button @click="releaseAll">Liberar todas</button>
              <button @click="releaseOnlyDefault">Somente padrão</button>
              <button @click="blockBuilder">Bloquear editor</button>
              <button v-if="tenantPolicy.explicit" @click="inheritGlobal"><RotateCcw :size="14"/>Herdar global</button>
            </div>

            <div class="vb-release-grid tenant">
              <button v-for="item in releases" :key="item.version" type="button" :class="{allowed:selected(item.version)}" @click="toggle(item.version)">
                <div><strong>{{item.version}}</strong><span>{{selected(item.version)?'Liberada':'Bloqueada'}}</span></div>
                <p>{{item.description}}</p><small>{{item.schema}}</small>
              </button>
            </div>

            <div class="vb-save-row">
              <label>Padrão desta empresa
                <select v-model="tenantDefault" :disabled="!allowed.length||saving">
                  <option value="">Sem padrão próprio</option>
                  <option v-for="version in allowed" :key="version" :value="version">{{version}}</option>
                </select>
              </label>
              <div><span>{{allowed.length}} release(s) liberada(s)</span><button class="vb-primary" :disabled="saving" @click="saveTenant"><Check :size="16"/>Salvar liberação</button></div>
            </div>
          </template>
        </section>
      </template>
    </section>
  </div>
</template>

<style scoped>
.vb-launcher{position:fixed;right:18px;bottom:76px;z-index:8100;display:flex;align-items:center;gap:7px;min-height:42px;padding:0 13px;border:1px solid #334155;border-radius:12px;background:#101a31;color:#fff;box-shadow:0 14px 35px rgba(15,23,42,.24);font:inherit;font-size:12px}.vb-backdrop{position:fixed;inset:0;z-index:12000;display:grid;place-items:center;padding:18px;background:rgba(2,6,23,.72);backdrop-filter:blur(7px)}.vb-manager{width:min(1080px,100%);max-height:calc(100dvh - 36px);overflow:auto;border:1px solid #d8e0eb;border-radius:20px;background:#f6f8fc;color:#172033;box-shadow:0 30px 90px rgba(2,6,23,.35)}.vb-topbar{position:sticky;top:0;z-index:2;display:flex;justify-content:space-between;gap:18px;padding:18px 20px;background:#101a31;color:#fff}.vb-topbar span,.vb-section-title span{font-size:10px;font-weight:900;letter-spacing:.08em;text-transform:uppercase;color:#8fa3ff}.vb-topbar h2{margin:3px 0;font-size:23px}.vb-topbar p{margin:0;color:#b6c0d4;font-size:12px}.vb-icon{width:40px;height:40px;display:grid;place-items:center;border:1px solid #34425f;border-radius:10px;background:#17243e;color:#fff}.vb-state{padding:54px;text-align:center;color:#64748b}.vb-success,.vb-error{margin:14px 18px 0;padding:10px 12px;border-radius:10px;font-size:12px}.vb-success{background:#ecfdf3;color:#067647}.vb-error{background:#fff1f2;color:#be123c}.vb-section{margin:16px 18px;padding:18px;border:1px solid #dce3ed;border-radius:16px;background:#fff}.vb-section-title{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:15px}.vb-section-title h3{margin:2px 0 0;font-size:18px}.vb-global-row,.vb-save-row{display:flex;justify-content:space-between;align-items:end;gap:12px}.vb-manager label{display:grid;gap:6px;font-size:11px;font-weight:800;color:#475467}.vb-manager select{min-height:42px;min-width:230px;border:1px solid #cbd5e1;border-radius:10px;background:#fff;padding:0 34px 0 10px;color:#172033}.vb-primary{min-height:42px;display:flex;align-items:center;justify-content:center;gap:7px;border:0;border-radius:10px;background:#3151cf;color:#fff;padding:0 14px;font:inherit;font-weight:800}.vb-release-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-top:14px}.vb-release-grid article,.vb-release-grid button{display:grid;gap:7px;padding:13px;border:1px solid #dce3ed;border-radius:13px;background:#f9fbfe;text-align:left;color:inherit}.vb-release-grid article.current,.vb-release-grid button.allowed{border-color:#6b80e8;background:#f1f4ff}.vb-release-grid div{display:flex;justify-content:space-between;gap:7px}.vb-release-grid strong{font-size:13px}.vb-release-grid span{font-size:9px;font-weight:900;text-transform:uppercase;color:#64748b}.vb-release-grid p{margin:0;color:#667085;font-size:10px;line-height:1.45}.vb-release-grid small{font-size:9px;color:#98a2b3}.vb-release-grid button{cursor:pointer;font:inherit}.vb-tenant-select{margin-bottom:13px}.vb-tenant-select select{width:min(100%,520px)}.vb-policy-note{display:grid;gap:3px;padding:10px 12px;border:1px solid #d5def0;border-radius:11px;background:#f4f7ff}.vb-policy-note.inherited{background:#f0fdf4;border-color:#bbf7d0}.vb-policy-note strong{font-size:12px}.vb-policy-note span{font-size:10px;color:#667085}.vb-actions-inline{display:flex;flex-wrap:wrap;gap:7px;margin-top:10px}.vb-actions-inline button{min-height:34px;display:flex;align-items:center;gap:5px;border:1px solid #d0d7e2;border-radius:9px;background:#fff;padding:0 10px;color:#344054;font:inherit;font-size:10px;font-weight:800}.vb-save-row{margin-top:14px;padding-top:14px;border-top:1px solid #e5e9f0}.vb-save-row>div{display:flex;align-items:center;gap:10px}.vb-save-row>div>span{font-size:10px;color:#667085}@media(max-width:760px){.vb-launcher{right:10px;bottom:max(70px,calc(env(safe-area-inset-bottom) + 58px));font-size:0;width:44px;padding:0;justify-content:center}.vb-backdrop{padding:0}.vb-manager{width:100%;height:100dvh;max-height:none;border:0;border-radius:0}.vb-topbar{padding:14px}.vb-topbar h2{font-size:18px}.vb-topbar p{display:none}.vb-section{margin:10px;padding:13px}.vb-release-grid{grid-template-columns:1fr}.vb-global-row,.vb-save-row{display:grid;align-items:stretch}.vb-manager select{width:100%;min-width:0}.vb-save-row>div{justify-content:space-between;flex-wrap:wrap}}
</style>
