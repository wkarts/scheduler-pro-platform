<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { apiGet, apiPut, type ApiError } from './api/client'

type SessionState={accessToken:string;refreshToken:string;userEmail:string}
type Tenant={id:string;name:string;slug:string;status:string}
type BrandingManifest={app?:{public_name?:string};assets?:{icon_url?:string|null};settings?:Record<string,unknown>}
type ExperienceSnapshot={branding?:BrandingManifest|null}

const storageKey='scheduler-pro-admin-session'
const open=ref(false)
const authenticated=ref(false)
const loading=ref(false)
const saving=ref(false)
const error=ref('')
const success=ref('')
const tenants=ref<Tenant[]>([])
const tenantId=ref('')
const branding=ref<BrandingManifest|null>(null)
const allowNameOverride=ref(false)
const allowIconOverride=ref(false)
let authTimer:number|undefined

const selectedTenant=computed(()=>tenants.value.find(item=>item.id===tenantId.value)??null)

function session():SessionState|null{const raw=localStorage.getItem(storageKey);if(!raw)return null;try{return JSON.parse(raw) as SessionState}catch{return null}}
function token():string{return session()?.accessToken||''}
function syncAuth():void{authenticated.value=Boolean(token());if(!authenticated.value)open.value=false}
function describe(errorValue:unknown):string{const value=errorValue as Partial<ApiError>;return value?.message||'Falha ao atualizar a identidade do PWA.'}
function hydratePermissions(settings:Record<string,unknown>|undefined):void{
  const source=settings||{}
  const legacy=Boolean(source.allow_pwa_identity_override)
  allowNameOverride.value=source.allow_pwa_name_override===undefined?legacy:Boolean(source.allow_pwa_name_override)
  allowIconOverride.value=source.allow_pwa_icon_override===undefined?legacy:Boolean(source.allow_pwa_icon_override)
}

async function loadTenant():Promise<void>{
  branding.value=null;allowNameOverride.value=false;allowIconOverride.value=false;error.value='';success.value=''
  if(!tenantId.value)return
  loading.value=true
  try{
    const snapshot=await apiGet<ExperienceSnapshot>(`/platform/tenant-management/${tenantId.value}/experience`,token())
    branding.value=snapshot.branding||null
    hydratePermissions(snapshot.branding?.settings)
  }catch(exc){error.value=describe(exc)}finally{loading.value=false}
}

async function show():Promise<void>{
  open.value=true;loading.value=true;error.value='';success.value=''
  try{
    tenants.value=await apiGet<Tenant[]>('/platform/tenants',token())
    if(!tenantId.value&&tenants.value.length)tenantId.value=tenants.value[0].id
    await loadTenant()
  }catch(exc){error.value=describe(exc)}finally{loading.value=false}
}

async function save():Promise<void>{
  if(!tenantId.value||!branding.value)return
  saving.value=true;error.value='';success.value=''
  try{
    const settings={
      ...(branding.value.settings||{}),
      allow_pwa_identity_override:false,
      allow_pwa_name_override:allowNameOverride.value,
      allow_pwa_icon_override:allowIconOverride.value,
    }
    branding.value=await apiPut<BrandingManifest>(`/platform/tenant-management/${tenantId.value}/experience/branding`,{settings},token())
    hydratePermissions(branding.value.settings)
    if(allowNameOverride.value&&allowIconOverride.value)success.value='Nome e ícone próprios do PWA liberados para este tenant.'
    else if(allowIconOverride.value)success.value='Somente o ícone próprio do PWA foi liberado para este tenant.'
    else if(allowNameOverride.value)success.value='Somente o nome próprio do PWA foi liberado para este tenant.'
    else success.value='PWA protegido: nome e ícones permanecem Scheduler Pro.'
  }catch(exc){error.value=describe(exc)}finally{saving.value=false}
}

onMounted(()=>{syncAuth();authTimer=window.setInterval(syncAuth,800)})
onUnmounted(()=>{if(authTimer!==undefined)window.clearInterval(authTimer)})
</script>

<template>
  <div v-if="authenticated" class="pwa-identity-root">
    <button class="pwa-identity-trigger" type="button" @click="show">PWA</button>
    <div v-if="open" class="pwa-identity-backdrop" @click.self="open=false">
      <section class="pwa-identity-dialog" role="dialog" aria-modal="true" aria-label="Identidade do PWA">
        <header><div><span>Control Plane</span><h2>Identidade do PWA</h2><p>Defina separadamente o que cada tenant pode personalizar no aplicativo instalado.</p></div><button type="button" class="close" @click="open=false">×</button></header>
        <label>Tenant</label>
        <select v-model="tenantId" :disabled="loading||saving" @change="loadTenant"><option value="">Selecione</option><option v-for="tenant in tenants" :key="tenant.id" :value="tenant.id">{{tenant.name}} — {{tenant.slug}}</option></select>
        <div class="core-card"><strong>Padrão da plataforma</strong><span>Nome do aplicativo: Scheduler Pro</span><span>Ícones: identidade oficial Scheduler Pro</span><small>Cores, favicon, logo do tenant, Login e Tenant Console continuam personalizáveis.</small></div>
        <div class="permission-stack">
          <label class="toggle"><input v-model="allowIconOverride" type="checkbox" :disabled="loading||!branding"><span><strong>Permitir alterar o ícone do PWA</strong><small>Libera somente o ícone configurado no branding do tenant. O nome continua Scheduler Pro se a permissão de nome permanecer desligada.</small></span></label>
          <label class="toggle"><input v-model="allowNameOverride" type="checkbox" :disabled="loading||!branding"><span><strong>Permitir alterar o nome do PWA</strong><small>Libera o nome público do tenant como nome do aplicativo instalado. Esta permissão é independente do ícone.</small></span></label>
        </div>
        <p v-if="selectedTenant" class="current">Tenant: <strong>{{selectedTenant.name}}</strong></p>
        <p v-if="error" class="error">{{error}}</p><p v-if="success" class="success">{{success}}</p>
        <footer><button type="button" class="secondary" @click="open=false">Fechar</button><button type="button" class="primary" :disabled="saving||loading||!branding" @click="save">{{saving?'Salvando...':'Salvar regra'}}</button></footer>
      </section>
    </div>
  </div>
</template>

<style scoped>
.pwa-identity-trigger{position:fixed;right:18px;bottom:146px;z-index:24000;border:1px solid #dbe4f0;border-radius:12px;background:#0f172a;color:#fff;padding:10px 16px;font:700 12px Inter,system-ui,sans-serif;box-shadow:0 16px 34px rgba(15,23,42,.18);cursor:pointer}.pwa-identity-backdrop{position:fixed;inset:0;z-index:50000;display:grid;place-items:center;padding:18px;background:rgba(15,23,42,.42);backdrop-filter:blur(4px)}.pwa-identity-dialog{width:min(600px,100%);max-height:min(780px,92dvh);overflow:auto;border:1px solid #e2e8f0;border-radius:22px;background:#fff;padding:22px;box-shadow:0 32px 90px rgba(15,23,42,.25);color:#0f172a;font-family:Inter,system-ui,sans-serif}.pwa-identity-dialog header{display:flex;justify-content:space-between;gap:18px;margin-bottom:18px}.pwa-identity-dialog header span{font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.08em;color:#2563eb}.pwa-identity-dialog h2{margin:4px 0 6px;font-size:24px}.pwa-identity-dialog p{margin:0;color:#64748b}.close{width:38px;height:38px;border:1px solid #e2e8f0;border-radius:10px;background:#fff;font-size:24px;cursor:pointer}.pwa-identity-dialog>label:not(.toggle){display:block;margin:12px 0 6px;font-size:12px;font-weight:800}.pwa-identity-dialog select{width:100%;min-height:42px;border:1px solid #cbd5e1;border-radius:10px;padding:0 11px;background:#fff}.core-card{display:grid;gap:5px;margin:16px 0;padding:15px;border:1px solid #dbeafe;border-radius:14px;background:#f8fbff}.core-card strong{color:#1d4ed8}.core-card span,.core-card small{font-size:13px;color:#475569}.permission-stack{display:grid;gap:10px}.toggle{display:flex;gap:11px;align-items:flex-start;padding:15px;border:1px solid #e2e8f0;border-radius:14px;background:#fff}.toggle input{margin-top:3px;width:18px;height:18px}.toggle span{display:grid;gap:4px}.toggle small{line-height:1.45;color:#64748b}.current{margin-top:12px!important;font-size:12px}.error,.success{margin-top:12px!important;padding:10px 12px;border-radius:10px;font-size:12px}.error{background:#fef2f2;color:#b91c1c!important}.success{background:#ecfdf5;color:#047857!important}.pwa-identity-dialog footer{display:flex;justify-content:flex-end;gap:9px;margin-top:18px}.pwa-identity-dialog footer button{min-height:40px;border-radius:10px;padding:0 16px;font-weight:800;cursor:pointer}.secondary{border:1px solid #cbd5e1;background:#fff;color:#0f172a}.primary{border:0;background:#2563eb;color:#fff}.primary:disabled{opacity:.55;cursor:default}@media(max-width:720px){.pwa-identity-trigger{right:12px;bottom:138px}.pwa-identity-dialog{border-radius:18px;padding:18px}}
</style>
