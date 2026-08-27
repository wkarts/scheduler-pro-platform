<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { Archive, CheckCircle2, FileArchive, Upload, X } from 'lucide-vue-next'
import { apiGet, type ApiError } from './api/client'

type Session={accessToken:string;refreshToken:string;userEmail:string}
type Tenant={id:string;name:string;slug:string;status:string}
type Scope='GLOBAL'|'SELECTED'|'EXCLUSIVE'|'INTERNAL'
type Issue={path:string;code:string;message:string}
type SurfaceInfo={surface:string;entry:string;route:string;bytes:number;version:number}
type PackageMeta={key:string;name:string;description?:string|null;segment?:string|null;scope:Scope;default_for_new_tenants?:boolean}
type Validation={valid:boolean;schema:string;errors:Issue[];warnings:Issue[];package:PackageMeta;surfaces:Record<string,SurfaceInfo>;archive_bytes?:number;file_count?:number}
type ImportResult={template_key:string;name:string;scope:Scope;templates:Array<{surface:string;template_id:string;version_number:number;created:boolean;published:boolean}>;package?:PackageMeta&{surfaces?:Record<string,SurfaceInfo>}}
type Envelope<T>={data?:T;error?:{message?:string}}

const storageKey='scheduler-pro-admin-session'
const session=ref<Session|null>(null)
const open=ref(false),loading=ref(false)
const error=ref(''),message=ref('')
const packageFile=ref<File|null>(null),packageName=ref('')
const scope=ref<Scope>('INTERNAL'),publish=ref(false),updateExisting=ref(true)
const exclusiveTenantId=ref(''),selectedTenantIds=ref<string[]>([]),tenants=ref<Tenant[]>([])
const validation=ref<Validation|null>(null)
const authenticated=computed(()=>Boolean(session.value?.accessToken))
const token=()=>session.value?.accessToken||''
const canImport=computed(()=>Boolean(packageFile.value&&validation.value?.valid&&!loading.value&&(scope.value!=='EXCLUSIVE'||exclusiveTenantId.value)&&(scope.value!=='SELECTED'||selectedTenantIds.value.length)))

function readSession():void{const raw=localStorage.getItem(storageKey);if(!raw){session.value=null;return}try{session.value=JSON.parse(raw) as Session}catch{session.value=null}}
function describe(exc:unknown,fallback:string):string{const value=exc as Partial<ApiError>;return value?.message||fallback}
function flash(value:string):void{message.value=value;window.setTimeout(()=>{if(message.value===value)message.value=''},4200)}
function formatBytes(value?:number):string{let size=Math.max(0,Number(value||0));const units=['B','KB','MB'];let i=0;while(size>=1024&&i<units.length-1){size/=1024;i++}return`${size.toFixed(i?1:0)} ${units[i]}`}
async function loadTenants():Promise<void>{if(!authenticated.value)return;tenants.value=await apiGet<Tenant[]>('/platform/tenants',token())}
async function show():Promise<void>{readSession();if(!authenticated.value)return;open.value=true;error.value='';await loadTenants().catch(exc=>{error.value=describe(exc,'Falha ao carregar clientes.')})}
function close():void{open.value=false}
function selectPackage(file:File|undefined):void{
  if(!file)return
  if(!file.name.toLowerCase().endsWith('.zip')){error.value='Selecione um pacote .zip do Scheduler Pro.';return}
  if(file.size>20*1024*1024){error.value='O pacote ZIP excede o limite de 20 MB.';return}
  packageFile.value=file;packageName.value=file.name;validation.value=null;error.value='';message.value=''
}
async function postForm<T>(path:string,form:FormData):Promise<T>{
  const response=await fetch(`/api/v1${path}`,{method:'POST',body:form,cache:'no-store',headers:{accept:'application/json',authorization:`Bearer ${token()}`}})
  const payload=await response.json().catch(()=>({})) as Envelope<T>
  if(!response.ok||payload.data===undefined)throw new Error(payload.error?.message||`Não foi possível concluir a operação (${response.status}).`)
  return payload.data
}
async function validatePackage():Promise<void>{
  if(!packageFile.value)return
  loading.value=true;error.value='';message.value=''
  try{
    const form=new FormData();form.append('package',packageFile.value)
    validation.value=await postForm<Validation>('/platform/html-templates/validate-package',form)
    if(validation.value.valid){scope.value=validation.value.package.scope||'INTERNAL';flash(`Pacote ${validation.value.package.name} validado. Landing e Agendamento serão preservados em HTML.`)}
    else error.value='O pacote possui pontos que precisam ser corrigidos antes da importação.'
  }catch(exc){error.value=describe(exc,'Não foi possível validar o pacote.')}
  finally{loading.value=false}
}
async function importPackage():Promise<void>{
  if(!canImport.value||!packageFile.value)return
  loading.value=true;error.value='';message.value=''
  try{
    const form=new FormData();form.append('package',packageFile.value);form.append('scope',scope.value);form.append('publish',String(publish.value));form.append('update_existing',String(updateExisting.value));form.append('exclusive_tenant_id',scope.value==='EXCLUSIVE'?exclusiveTenantId.value:'');form.append('selected_tenant_ids',JSON.stringify(scope.value==='SELECTED'?selectedTenantIds.value:[]))
    const result=await postForm<ImportResult>('/platform/html-templates/import-package',form)
    flash(`Modelo ${result.name} (${result.template_key}) importado com ${result.templates.length} superfície(s).`)
    validation.value=null
  }catch(exc){error.value=describe(exc,'Falha ao importar o pacote de template.')}
  finally{loading.value=false}
}
function onAuth():void{readSession()}
onMounted(()=>{readSession();window.addEventListener('storage',onAuth);window.addEventListener('scheduler-pro-admin-auth-changed',onAuth)})
onUnmounted(()=>{window.removeEventListener('storage',onAuth);window.removeEventListener('scheduler-pro-admin-auth-changed',onAuth)})
</script>

<template>
  <button v-if="authenticated" class="html-import-launcher" type="button" @click="show"><FileArchive :size="17"/><span>Importar modelo</span></button>
  <div v-if="open&&authenticated" class="html-import-backdrop" @click.self="close">
    <section class="html-import-dialog" role="dialog" aria-modal="true" aria-label="Importar pacote de modelos">
      <header><div><span>Scheduler Pro · Biblioteca de modelos</span><h2>Importar Template Package V1</h2><p>Envie um único ZIP com <b>template.json</b>, <b>landing.html</b> e/ou <b>agendamento.html</b>. O HTML é preservado integralmente; o manifesto apenas descreve a família, o escopo e as superfícies.</p></div><button class="close" aria-label="Fechar" @click="close"><X :size="20"/></button></header>
      <p v-if="error" class="alert error">{{error}}</p><p v-if="message" class="alert success"><CheckCircle2 :size="16"/>{{message}}</p>
      <main>
        <label class="package-card"><Archive :size="34"/><div><strong>{{packageName||'Pacote Scheduler Pro (.zip)'}}</strong><span>{{packageName?'Pronto para validação.':'Selecione o pacote produzido para a biblioteca de modelos.'}}</span><small>Formato oficial: scheduler-pro-template-package/v1 · até 20 MB</small></div><input type="file" accept=".zip,application/zip" @change="selectPackage(($event.target as HTMLInputElement).files?.[0])"/><em><Upload :size="15"/>Selecionar pacote</em></label>

        <section v-if="validation" class="package-summary">
          <div><span>Modelo</span><strong>{{validation.package.name}}</strong><small>{{validation.package.key}}</small></div><div><span>Segmento</span><strong>{{validation.package.segment||'Genérico'}}</strong><small>{{validation.schema}}</small></div><div><span>Arquivo</span><strong>{{formatBytes(validation.archive_bytes)}}</strong><small>{{validation.file_count||0}} arquivo(s)</small></div>
        </section>
        <section v-if="validation" class="surface-grid"><article v-for="item in validation.surfaces" :key="item.surface"><span>{{item.surface}}</span><strong>{{item.entry}}</strong><small>{{item.route}} · v{{item.version}} · {{formatBytes(item.bytes)}}</small></article></section>

        <section class="form-grid"><label>Disponibilidade<select v-model="scope"><option value="INTERNAL">Interno / não publicado</option><option value="GLOBAL">Todos os clientes</option><option value="SELECTED">Clientes selecionados</option><option value="EXCLUSIVE">Cliente exclusivo</option></select></label><label v-if="scope==='EXCLUSIVE'">Cliente exclusivo<select v-model="exclusiveTenantId"><option value="">Selecione</option><option v-for="tenant in tenants" :key="tenant.id" :value="tenant.id">{{tenant.name}}</option></select></label></section>
        <section v-if="scope==='SELECTED'" class="tenant-picker"><strong>Clientes que poderão usar este modelo</strong><label v-for="tenant in tenants" :key="tenant.id"><input v-model="selectedTenantIds" type="checkbox" :value="tenant.id"/>{{tenant.name}}</label></section>
        <div class="options"><label><input v-model="publish" type="checkbox"/>Publicar esta versão imediatamente</label><label><input v-model="updateExisting" type="checkbox"/>Se a chave já existir, criar uma nova versão</label></div>

        <section v-if="validation" class="validation" :class="{valid:validation.valid}"><header><strong>{{validation.valid?'Pacote compatível':'Correções necessárias'}}</strong><span>O importador valida manifesto, ZIP, superfícies e contrato dos HTMLs antes de versionar.</span></header><div v-if="validation.errors.length"><h3>Erros</h3><p v-for="item in validation.errors" :key="item.path+item.code"><code>{{item.path}}</code>{{item.message}}</p></div><div v-if="validation.warnings.length"><h3>Avisos</h3><p v-for="item in validation.warnings" :key="item.path+item.code"><code>{{item.path}}</code>{{item.message}}</p></div></section>
      </main>
      <footer><button type="button" :disabled="loading||!packageFile" @click="validatePackage">{{loading?'Validando…':'Validar pacote'}}</button><button class="primary" type="button" :disabled="!canImport" @click="importPackage">{{loading?'Processando…':'Importar e versionar'}}</button></footer>
    </section>
  </div>
</template>

<style scoped>
.html-import-launcher{position:fixed;right:22px;bottom:82px;z-index:1500;min-height:44px;border:0;border-radius:13px;padding:0 14px;background:#14213b;color:#fff;display:flex;align-items:center;gap:7px;font:inherit;font-size:12px;font-weight:850;box-shadow:0 12px 32px #0f172a33}.html-import-backdrop{position:fixed;inset:0;z-index:6000;display:grid;place-items:center;padding:22px;background:#07111f99;backdrop-filter:blur(4px)}.html-import-dialog{width:min(940px,96vw);max-height:94dvh;overflow:auto;border-radius:22px;background:#f7f9fc;color:#17233a;box-shadow:0 30px 100px #07111f66}.html-import-dialog>header{position:sticky;top:0;z-index:3;display:flex;justify-content:space-between;gap:16px;padding:22px 24px 17px;background:#fff;border-bottom:1px solid #e1e7ef}.html-import-dialog header span{font-size:10px;font-weight:900;letter-spacing:.09em;text-transform:uppercase;color:#3151cf}.html-import-dialog h2{margin:4px 0 5px;font-size:24px}.html-import-dialog header p{margin:0;max-width:720px;color:#607087;font-size:12px;line-height:1.5}.close{width:40px;height:40px;border:1px solid #dce3ed;border-radius:11px;background:#fff;display:grid;place-items:center}.alert{margin:12px 22px 0;padding:10px 12px;border-radius:10px;font-size:12px;font-weight:750}.alert.error{background:#fff0f0;color:#ad2431}.alert.success{display:flex;gap:7px;align-items:center;background:#eaf8ef;color:#176a3b}.html-import-dialog main{display:grid;gap:15px;padding:18px 22px}.package-card{display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:center;gap:14px;padding:20px;border:1px dashed #8ca0bd;border-radius:17px;background:#fff;cursor:pointer}.package-card>svg{color:#3151cf}.package-card div{display:grid;gap:3px}.package-card span,.package-card small{color:#6e7a8d;font-size:11px}.package-card input{display:none}.package-card em{padding:9px 11px;border-radius:9px;background:#eef3ff;color:#3151cf;display:flex;align-items:center;gap:6px;font-size:11px;font-style:normal;font-weight:850}.package-summary{display:grid;grid-template-columns:repeat(3,1fr);gap:9px}.package-summary>div,.surface-grid article{padding:12px;border:1px solid #dbe3ee;border-radius:12px;background:#fff;display:grid;gap:3px}.package-summary span,.surface-grid span{font-size:9px;font-weight:900;text-transform:uppercase;color:#3151cf}.package-summary small,.surface-grid small{color:#6e7a8d;font-size:10px}.surface-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:9px}.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:11px}.form-grid label{display:grid;gap:5px;font-size:11px;font-weight:800}.form-grid select{width:100%;border:1px solid #cfdae8;border-radius:10px;background:#fff;padding:10px;font:inherit}.tenant-picker{display:flex;flex-wrap:wrap;gap:7px;padding:12px;border:1px solid #dbe3ee;border-radius:12px;background:#fff}.tenant-picker>strong{width:100%;font-size:11px}.tenant-picker label,.options label{display:flex;align-items:center;gap:6px;font-size:11px}.options{display:flex;flex-wrap:wrap;gap:14px}.validation{padding:14px;border:1px solid #f0c9cd;border-radius:14px;background:#fff6f6}.validation.valid{border-color:#b7e3c7;background:#f2fbf5}.validation header{display:grid;gap:3px}.validation header span{color:#67758a;font-size:10px}.validation h3{margin:12px 0 5px;font-size:11px}.validation p{margin:5px 0;font-size:11px;line-height:1.45}.validation code{margin-right:7px;color:#3151cf}.html-import-dialog>footer{position:sticky;bottom:0;display:flex;justify-content:flex-end;gap:8px;padding:13px 22px;border-top:1px solid #e1e7ef;background:#fff}.html-import-dialog>footer button{min-height:42px;border:1px solid #cfdae8;border-radius:10px;background:#fff;padding:0 14px;font:inherit;font-weight:850}.html-import-dialog>footer .primary{border-color:#3151cf;background:#3151cf;color:#fff}.html-import-dialog>footer button:disabled{opacity:.5}@media(max-width:700px){.html-import-launcher{right:13px;bottom:72px;width:48px;height:48px;padding:0;justify-content:center;border-radius:50%}.html-import-launcher span{display:none}.html-import-backdrop{align-items:end;padding:0}.html-import-dialog{width:100vw;max-height:96dvh;border-radius:22px 22px 0 0}.html-import-dialog>header{padding:17px 15px 13px}.html-import-dialog h2{font-size:19px}.html-import-dialog main{padding:14px}.package-card{grid-template-columns:auto 1fr}.package-card em{grid-column:1/-1;justify-content:center}.package-summary,.surface-grid,.form-grid{grid-template-columns:1fr}.html-import-dialog>footer{padding:10px 14px}.html-import-dialog>footer button{flex:1;padding:0 8px}}
</style>
