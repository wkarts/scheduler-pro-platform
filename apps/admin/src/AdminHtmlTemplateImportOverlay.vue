<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { CheckCircle2, FileCode2, Upload, X } from 'lucide-vue-next'
import { apiGet, apiPost, type ApiError } from './api/client'

type Session={accessToken:string;refreshToken:string;userEmail:string}
type Tenant={id:string;name:string;slug:string;status:string}
type Scope='GLOBAL'|'SELECTED'|'EXCLUSIVE'|'INTERNAL'
type Issue={path:string;code:string;message:string}
type Validation={valid:boolean;schema:string;template_key:string;errors:Issue[];warnings:Issue[];surfaces:Record<string,unknown>}
type ImportResult={template_key:string;name:string;scope:Scope;templates:Array<{surface:string;template_id:string;version_number:number;created:boolean;published:boolean}>}

const storageKey='scheduler-pro-admin-session'
const session=ref<Session|null>(null)
const open=ref(false)
const loading=ref(false)
const error=ref('')
const message=ref('')
const landingHtml=ref('')
const bookingHtml=ref('')
const landingName=ref('')
const bookingName=ref('')
const name=ref('')
const description=ref('')
const segment=ref('')
const scope=ref<Scope>('INTERNAL')
const publish=ref(false)
const updateExisting=ref(true)
const exclusiveTenantId=ref('')
const selectedTenantIds=ref<string[]>([])
const tenants=ref<Tenant[]>([])
const validation=ref<Validation|null>(null)

const authenticated=computed(()=>Boolean(session.value?.accessToken))
const token=()=>session.value?.accessToken||''
const canImport=computed(()=>Boolean(name.value.trim()&&(landingHtml.value||bookingHtml.value)&&validation.value?.valid&&!loading.value))

function readSession():void{const raw=localStorage.getItem(storageKey);if(!raw){session.value=null;return}try{session.value=JSON.parse(raw) as Session}catch{session.value=null}}
function describe(exc:unknown,fallback:string):string{const value=exc as Partial<ApiError>;return value?.message||fallback}
function flash(value:string):void{message.value=value;window.setTimeout(()=>{if(message.value===value)message.value=''},4000)}
async function readHtml(file:File|undefined,target:'landing'|'booking'):Promise<void>{
  if(!file)return
  if(!file.name.toLowerCase().endsWith('.html')&&!file.type.includes('html')){error.value='Selecione um arquivo .html.';return}
  const text=await file.text()
  if(target==='landing'){landingHtml.value=text;landingName.value=file.name}else{bookingHtml.value=text;bookingName.value=file.name}
  validation.value=null;error.value=''
}
async function loadTenants():Promise<void>{if(!authenticated.value)return;tenants.value=await apiGet<Tenant[]>('/platform/tenants',token())}
async function show():Promise<void>{readSession();if(!authenticated.value)return;open.value=true;error.value='';await loadTenants().catch(exc=>{error.value=describe(exc,'Falha ao carregar clientes.')})}
function close():void{open.value=false}
async function validate():Promise<void>{
  loading.value=true;error.value='';message.value=''
  try{
    validation.value=await apiPost<Validation>('/platform/html-templates/validate',{landing_html:landingHtml.value||null,booking_html:bookingHtml.value||null},token())
    if(validation.value.valid){if(!name.value.trim()&&validation.value.template_key)name.value=validation.value.template_key.replace(/-/g,' ');flash('HTML validado. O layout será preservado sem conversão para blocos JSON.')}else error.value='O HTML possui pontos que precisam ser corrigidos antes da importação.'
  }catch(exc){error.value=describe(exc,'Não foi possível validar os arquivos HTML.')}finally{loading.value=false}
}
async function importPair():Promise<void>{
  if(!canImport.value)return
  loading.value=true;error.value='';message.value=''
  try{
    const result=await apiPost<ImportResult>('/platform/html-templates/import',{
      landing_html:landingHtml.value||null,
      booking_html:bookingHtml.value||null,
      name:name.value.trim(),description:description.value.trim()||null,segment:segment.value.trim()||null,
      scope:scope.value,publish:publish.value,update_existing:updateExisting.value,
      exclusive_tenant_id:scope.value==='EXCLUSIVE'?exclusiveTenantId.value||null:null,
      selected_tenant_ids:scope.value==='SELECTED'?selectedTenantIds.value:[],
      default_for_new_tenants:false,
    },token())
    flash(`Modelo ${result.template_key} importado com ${result.templates.length} superfície(s).`)
    validation.value=null
  }catch(exc){error.value=describe(exc,'Falha ao importar a família HTML.')}finally{loading.value=false}
}
function onAuth():void{readSession()}
onMounted(()=>{readSession();window.addEventListener('storage',onAuth);window.addEventListener('scheduler-pro-admin-auth-changed',onAuth)})
onUnmounted(()=>{window.removeEventListener('storage',onAuth);window.removeEventListener('scheduler-pro-admin-auth-changed',onAuth)})
</script>

<template>
  <button v-if="authenticated" class="html-import-launcher" type="button" @click="show"><FileCode2 :size="17"/><span>Importar HTML</span></button>
  <div v-if="open&&authenticated" class="html-import-backdrop" @click.self="close">
    <section class="html-import-dialog" role="dialog" aria-modal="true" aria-label="Importar modelos HTML">
      <header><div><span>Scheduler Pro · Modelos</span><h2>Importar Landing + Agendamento em HTML</h2><p>O HTML é o layout autoral. A plataforma valida, versiona e publica sem converter sua identidade visual em JSON.</p></div><button class="close" aria-label="Fechar" @click="close"><X :size="20"/></button></header>

      <p v-if="error" class="alert error">{{error}}</p><p v-if="message" class="alert success"><CheckCircle2 :size="16"/>{{message}}</p>

      <main>
        <section class="file-grid">
          <label class="file-card"><strong>Landing Page</strong><span>{{landingName||'Escolha o HTML da página institucional/marketing'}}</span><input type="file" accept=".html,text/html" @change="readHtml(($event.target as HTMLInputElement).files?.[0],'landing')"/><em><Upload :size="15"/>Selecionar landing.html</em></label>
          <label class="file-card"><strong>Página de Agendamento</strong><span>{{bookingName||'Escolha o HTML da experiência pública de agendamento'}}</span><input type="file" accept=".html,text/html" @change="readHtml(($event.target as HTMLInputElement).files?.[0],'booking')"/><em><Upload :size="15"/>Selecionar agendamento.html</em></label>
        </section>

        <section class="form-grid"><label>Nome do modelo<input v-model="name" placeholder="Ex.: Martelinho de Ouro"/></label><label>Segmento<input v-model="segment" placeholder="Ex.: automotivo"/></label><label class="wide">Descrição<textarea v-model="description" placeholder="Descrição interna do modelo"></textarea></label><label>Disponibilidade<select v-model="scope"><option value="INTERNAL">Interno / não publicado</option><option value="GLOBAL">Todos os clientes</option><option value="SELECTED">Clientes selecionados</option><option value="EXCLUSIVE">Cliente exclusivo</option></select></label><label v-if="scope==='EXCLUSIVE'">Cliente exclusivo<select v-model="exclusiveTenantId"><option value="">Selecione</option><option v-for="tenant in tenants" :key="tenant.id" :value="tenant.id">{{tenant.name}}</option></select></label></section>

        <section v-if="scope==='SELECTED'" class="tenant-picker"><strong>Clientes selecionados</strong><label v-for="tenant in tenants" :key="tenant.id"><input v-model="selectedTenantIds" type="checkbox" :value="tenant.id"/>{{tenant.name}}</label></section>

        <div class="options"><label><input v-model="publish" type="checkbox"/>Publicar esta versão imediatamente</label><label><input v-model="updateExisting" type="checkbox"/>Se a chave já existir, criar nova versão</label></div>

        <section v-if="validation" class="validation" :class="{valid:validation.valid}"><header><strong>{{validation.valid?'Arquivos compatíveis':'Correções necessárias'}}</strong><span>{{validation.template_key||'chave não identificada'}} · {{validation.schema}}</span></header><div v-if="validation.errors.length"><h3>Erros</h3><p v-for="item in validation.errors" :key="item.path+item.code"><code>{{item.path}}</code>{{item.message}}</p></div><div v-if="validation.warnings.length"><h3>Avisos</h3><p v-for="item in validation.warnings" :key="item.path+item.code"><code>{{item.path}}</code>{{item.message}}</p></div></section>
      </main>

      <footer><button type="button" :disabled="loading||(!landingHtml&&!bookingHtml)" @click="validate">{{loading?'Validando…':'Validar HTML'}}</button><button class="primary" type="button" :disabled="!canImport" @click="importPair">{{loading?'Processando…':'Importar e versionar'}}</button></footer>
    </section>
  </div>
</template>

<style scoped>
.html-import-launcher{position:fixed;right:22px;bottom:82px;z-index:1500;min-height:44px;border:0;border-radius:13px;padding:0 14px;background:#14213b;color:#fff;display:flex;align-items:center;gap:7px;font:inherit;font-size:12px;font-weight:850;box-shadow:0 12px 32px #0f172a33}.html-import-backdrop{position:fixed;inset:0;z-index:6000;display:grid;place-items:center;padding:22px;background:#07111f99;backdrop-filter:blur(4px)}.html-import-dialog{width:min(980px,96vw);max-height:94dvh;overflow:auto;border-radius:22px;background:#f7f9fc;color:#17233a;box-shadow:0 30px 100px #07111f66}.html-import-dialog>header{position:sticky;top:0;z-index:3;display:flex;justify-content:space-between;gap:16px;padding:22px 24px 17px;background:#fff;border-bottom:1px solid #e1e7ef}.html-import-dialog header span{font-size:10px;font-weight:900;letter-spacing:.09em;text-transform:uppercase;color:#3151cf}.html-import-dialog h2{margin:4px 0 5px;font-size:24px}.html-import-dialog header p{margin:0;max-width:720px;color:#607087;font-size:12px;line-height:1.5}.close{width:40px;height:40px;border:1px solid #dce3ed;border-radius:11px;background:#fff;display:grid;place-items:center}.alert{margin:12px 22px 0;padding:10px 12px;border-radius:10px;font-size:12px;font-weight:750}.alert.error{background:#fff0f0;color:#ad2431}.alert.success{display:flex;gap:7px;align-items:center;background:#eaf8ef;color:#176a3b}.html-import-dialog main{display:grid;gap:16px;padding:18px 22px}.file-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.file-card{display:grid;gap:7px;padding:18px;border:1px dashed #aab7c9;border-radius:16px;background:#fff;cursor:pointer}.file-card span{color:#6e7a8d;font-size:11px}.file-card input{display:none}.file-card em{width:max-content;padding:8px 10px;border-radius:9px;background:#eef3ff;color:#3151cf;display:flex;align-items:center;gap:6px;font-size:11px;font-style:normal;font-weight:800}.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:11px}.form-grid label{display:grid;gap:5px;font-size:11px;font-weight:800}.form-grid .wide{grid-column:1/-1}.form-grid input,.form-grid select,.form-grid textarea{width:100%;box-sizing:border-box;border:1px solid #cfdae8;border-radius:10px;background:#fff;padding:10px;font:inherit}.form-grid textarea{min-height:70px;resize:vertical}.tenant-picker{display:flex;flex-wrap:wrap;gap:7px;padding:12px;border:1px solid #dbe3ee;border-radius:12px;background:#fff}.tenant-picker>strong{width:100%;font-size:11px}.tenant-picker label,.options label{display:flex;align-items:center;gap:6px;font-size:11px}.options{display:flex;flex-wrap:wrap;gap:14px}.validation{padding:14px;border:1px solid #f0c9cd;border-radius:14px;background:#fff6f6}.validation.valid{border-color:#b7e3c7;background:#f2fbf5}.validation header{display:grid;gap:3px}.validation header span{color:#67758a;font-size:10px}.validation h3{margin:12px 0 5px;font-size:11px}.validation p{margin:5px 0;font-size:11px;line-height:1.45}.validation code{margin-right:7px;color:#3151cf}.html-import-dialog>footer{position:sticky;bottom:0;display:flex;justify-content:flex-end;gap:8px;padding:13px 22px;border-top:1px solid #e1e7ef;background:#fff}.html-import-dialog>footer button{min-height:42px;border:1px solid #cfdae8;border-radius:10px;background:#fff;padding:0 14px;font:inherit;font-weight:850}.html-import-dialog>footer .primary{border-color:#3151cf;background:#3151cf;color:#fff}.html-import-dialog>footer button:disabled{opacity:.5}@media(max-width:700px){.html-import-launcher{right:13px;bottom:72px;width:48px;height:48px;padding:0;justify-content:center;border-radius:50%}.html-import-launcher span{display:none}.html-import-backdrop{align-items:end;padding:0}.html-import-dialog{width:100vw;max-height:96dvh;border-radius:22px 22px 0 0}.html-import-dialog>header{padding:17px 15px 13px}.html-import-dialog h2{font-size:19px}.html-import-dialog main{padding:14px}.file-grid,.form-grid{grid-template-columns:1fr}.form-grid .wide{grid-column:auto}.html-import-dialog>footer{padding:10px 14px}.html-import-dialog>footer button{flex:1;padding:0 8px}}
</style>
