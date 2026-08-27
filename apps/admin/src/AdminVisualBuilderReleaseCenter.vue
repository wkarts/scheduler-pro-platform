<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { apiGet, apiPut, type ApiError } from './api/client'

type Session={accessToken:string;refreshToken:string;userEmail:string}
type Tenant={id:string;name:string;slug:string;status:string}
type Release={version:string;label:string;schema:string;channel:string;recommended:boolean;description:string;allowed?:boolean}
type PlatformPolicy={product:string;default_version:string;supported_versions:string[];releases:Release[];policy_configured:boolean}
type TenantPolicy={tenant_id:string;explicit:boolean;allowed_versions:string[];default_version?:string|null;platform_default_version:string;supported_versions:string[];releases:Release[]}

const storageKey='scheduler-pro-admin-session'
const open=ref(false),loading=ref(false),saving=ref(false),error=ref(''),toast=ref('')
const session=ref<Session|null>(null),tenants=ref<Tenant[]>([]),tenantId=ref('')
const platform=ref<PlatformPolicy|null>(null),tenant=ref<TenantPolicy|null>(null)
const globalDefault=ref('2.0.1'),tenantDefault=ref<string>(''),allowed=ref<string[]>([])

const authenticated=computed(()=>Boolean(session.value?.accessToken))
const selectedTenant=computed(()=>tenants.value.find(item=>item.id===tenantId.value)||null)
const releases=computed(()=>platform.value?.releases||[])
const token=()=>session.value?.accessToken||''

function readSession(){const raw=localStorage.getItem(storageKey);if(!raw){session.value=null;return}try{session.value=JSON.parse(raw) as Session}catch{session.value=null}}
function describe(exc:unknown,fallback:string){const value=exc as Partial<ApiError>;return value?.message||fallback}
function flash(value:string){toast.value=value;window.setTimeout(()=>{if(toast.value===value)toast.value=''},3500)}

async function loadPlatform(){platform.value=await apiGet<PlatformPolicy>('/platform/visual-builder',token());globalDefault.value=platform.value.default_version}
async function loadTenants(){tenants.value=await apiGet<Tenant[]>('/platform/tenants',token());if(!tenantId.value&&tenants.value.length)tenantId.value=tenants.value[0]!.id}
async function loadTenant(){if(!tenantId.value){tenant.value=null;allowed.value=[];tenantDefault.value='';return}tenant.value=await apiGet<TenantPolicy>(`/platform/visual-builder/tenants/${tenantId.value}`,token());allowed.value=[...tenant.value.allowed_versions];tenantDefault.value=tenant.value.default_version||''}
async function openCenter(){readSession();if(!authenticated.value)return;open.value=true;loading.value=true;error.value='';try{await Promise.all([loadPlatform(),loadTenants()]);await loadTenant()}catch(exc){error.value=describe(exc,'Não foi possível carregar as versões do editor.')}finally{loading.value=false}}
function close(){open.value=false;error.value=''}
async function selectTenant(){loading.value=true;error.value='';try{await loadTenant()}catch(exc){error.value=describe(exc,'Falha ao carregar a política do cliente.')}finally{loading.value=false}}
function toggle(version:string,checked:boolean){const set=new Set(allowed.value);checked?set.add(version):set.delete(version);allowed.value=releases.value.map(item=>item.version).filter(version=>set.has(version));if(tenantDefault.value&&!set.has(tenantDefault.value))tenantDefault.value=''}
async function saveGlobal(){saving.value=true;error.value='';try{platform.value=await apiPut<PlatformPolicy>('/platform/visual-builder/default',{version:globalDefault.value},token());globalDefault.value=platform.value.default_version;flash('Versão padrão global atualizada.');await loadTenant()}catch(exc){error.value=describe(exc,'Falha ao salvar a versão padrão global.')}finally{saving.value=false}}
async function saveTenant(){if(!tenantId.value)return;saving.value=true;error.value='';try{tenant.value=await apiPut<TenantPolicy>(`/platform/visual-builder/tenants/${tenantId.value}`,{allowed_versions:allowed.value,default_version:tenantDefault.value||null},token());allowed.value=[...tenant.value.allowed_versions];tenantDefault.value=tenant.value.default_version||'';flash('Versões liberadas para o cliente foram atualizadas.')}catch(exc){error.value=describe(exc,'Falha ao salvar as versões do cliente.')}finally{saving.value=false}}
function refreshSession(){const was=authenticated.value;readSession();if(!was&&authenticated.value&&open.value)void openCenter()}
onMounted(()=>{readSession();window.addEventListener('storage',refreshSession);window.addEventListener('scheduler-pro-admin-auth-changed',refreshSession)})
onUnmounted(()=>{window.removeEventListener('storage',refreshSession);window.removeEventListener('scheduler-pro-admin-auth-changed',refreshSession)})
</script>

<template>
  <button v-if="authenticated" class="vb-launcher" type="button" @click="openCenter"><span>VB</span><strong>Visual Builder</strong></button>
  <div v-if="open&&authenticated" class="vb-backdrop" @click.self="close">
    <section class="vb-center">
      <header><div><span>Scheduler Pro · Control Plane</span><h2>ARGWS Visual Builder Editor</h2><p>Defina a release padrão da plataforma e quais versões cada cliente pode testar.</p></div><button class="close" type="button" @click="close">×</button></header>
      <p v-if="toast" class="ok">{{toast}}</p><p v-if="error" class="err">{{error}}</p>
      <div v-if="loading" class="state">Carregando políticas do editor…</div>
      <template v-else>
        <section class="vb-panel">
          <div class="panel-title"><div><span>Política global</span><h3>Versão padrão para novos clientes</h3></div><button :disabled="saving" @click="saveGlobal">Salvar padrão</button></div>
          <label class="field">Release padrão<select v-model="globalDefault"><option v-for="item in releases" :key="item.version" :value="item.version">{{item.label}}{{item.recommended?' · recomendada':''}}</option></select></label>
          <div class="release-grid"><article v-for="item in releases" :key="item.version" :class="{current:item.version===globalDefault}"><div><strong>{{item.version}}</strong><span>{{item.channel}}</span></div><p>{{item.description}}</p><small>{{item.schema}}</small></article></div>
        </section>

        <section class="vb-panel">
          <div class="panel-title"><div><span>Liberação por cliente</span><h3>{{selectedTenant?.name||'Selecione uma empresa'}}</h3></div><button :disabled="saving||!tenantId" @click="saveTenant">Salvar liberações</button></div>
          <label class="field">Cliente<select v-model="tenantId" @change="selectTenant"><option value="">Selecione…</option><option v-for="item in tenants" :key="item.id" :value="item.id">{{item.name}} · {{item.slug}}</option></select></label>
          <template v-if="tenantId&&tenant">
            <div class="release-list"><label v-for="item in releases" :key="item.version" :class="{allowed:allowed.includes(item.version)}"><input type="checkbox" :checked="allowed.includes(item.version)" @change="toggle(item.version,($event.target as HTMLInputElement).checked)"/><div><strong>{{item.label}}</strong><span>{{item.description}}</span><small>{{item.schema}}</small></div></label></div>
            <label class="field">Padrão deste cliente<select v-model="tenantDefault"><option value="">Herdar política permitida</option><option v-for="version in allowed" :key="version" :value="version">ARGWS Visual Builder {{version}}</option></select></label>
            <p class="note">O cliente só enxerga as releases marcadas. A troca feita por ele vale apenas para a conta dele e pode ser revertida para este padrão.</p>
          </template>
        </section>
      </template>
    </section>
  </div>
</template>

<style scoped>
.vb-launcher{position:fixed;right:18px;bottom:78px;z-index:8700;display:flex;align-items:center;gap:9px;min-height:42px;padding:0 14px;border:1px solid #cfd7e6;border-radius:999px;background:#111a31;color:#fff;box-shadow:0 12px 32px #0f172a33;font:inherit}.vb-launcher span{display:grid;place-items:center;width:27px;height:27px;border-radius:9px;background:#6d5dfc;font-size:10px;font-weight:900}.vb-backdrop{position:fixed;inset:0;z-index:12000;background:#07111ed9;display:grid;place-items:center;padding:18px}.vb-center{width:min(1120px,100%);max-height:calc(100dvh - 36px);overflow:auto;border-radius:22px;background:#f5f7fb;color:#172033;box-shadow:0 34px 100px #0007}.vb-center>header{position:sticky;top:0;z-index:2;display:flex;justify-content:space-between;gap:16px;padding:20px 22px;background:#101a31;color:#fff}.vb-center>header span,.panel-title span{font-size:10px;font-weight:900;letter-spacing:.08em;text-transform:uppercase;color:#9fb1ff}.vb-center h2,.vb-center h3,.vb-center p{margin:0}.vb-center h2{margin-top:4px}.vb-center>header p{margin-top:5px;color:#b8c4d8;font-size:12px}.close{width:40px;height:40px;border:1px solid #40506e;border-radius:11px;background:#182641;color:#fff;font-size:24px}.vb-panel{margin:18px;padding:18px;border:1px solid #dbe2ed;border-radius:18px;background:#fff}.panel-title{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;margin-bottom:14px}.panel-title h3{margin-top:4px}.panel-title button{min-height:40px;border:0;border-radius:10px;padding:0 14px;background:#3151cf;color:#fff;font-weight:800}.field{display:grid;gap:6px;margin:12px 0;font-size:12px;font-weight:800}.field select{min-height:43px;border:1px solid #cfd7e6;border-radius:10px;background:#fff;padding:0 12px;color:#172033}.release-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.release-grid article{padding:14px;border:1px solid #dbe2ed;border-radius:14px;background:#f8fafc}.release-grid article.current{border-color:#6d5dfc;box-shadow:inset 0 0 0 1px #6d5dfc}.release-grid article>div{display:flex;justify-content:space-between;gap:8px}.release-grid article span,.release-grid small,.release-list small{color:#738097;font-size:10px}.release-grid p{margin:8px 0;color:#536176;font-size:11px;line-height:1.45}.release-list{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.release-list>label{display:flex;gap:10px;padding:14px;border:1px solid #dbe2ed;border-radius:14px;background:#fafbfc}.release-list>label.allowed{border-color:#6d5dfc;background:#f7f5ff}.release-list input{margin-top:3px}.release-list div{display:grid;gap:4px}.release-list span{font-size:11px;color:#536176;line-height:1.4}.note{padding:11px 12px;border-radius:11px;background:#eef2ff;color:#44506b;font-size:11px}.state{padding:50px;text-align:center}.ok,.err{margin:14px 18px 0!important;padding:11px 13px;border-radius:10px}.ok{background:#eafaf0;color:#13723d}.err{background:#fff0f2;color:#b4233f}@media(max-width:760px){.vb-backdrop{padding:0}.vb-center{height:100dvh;max-height:none;border-radius:0}.vb-center>header{padding:14px}.vb-center>header p{display:none}.vb-panel{margin:10px;padding:13px}.panel-title{display:grid}.panel-title button{width:100%}.release-grid,.release-list{grid-template-columns:1fr}.vb-launcher{right:10px;bottom:72px}.vb-launcher strong{display:none}}
</style>
