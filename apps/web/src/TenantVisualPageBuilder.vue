<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { Code2, ExternalLink, LayoutTemplate, RotateCcw, ShieldCheck, X } from 'lucide-vue-next'
import {
  ARGWS_VISUAL_BUILDER_RELEASES,
  createSchedulerProAdapter,
  resolveVisualBuilderVersionFromContent,
  type VisualBuilderVersion,
} from '@argws/visual-builder'
import HtmlTemplateFrame from './HtmlTemplateFrame.vue'

type HtmlContent={render_mode:'HTML';html_document:string;template_key?:string;content_version?:number}
type EditorState={content:Record<string,any>|HtmlContent;template_key?:string|null;status?:string}
type BuilderState={available:boolean;allowed_versions:VisualBuilderVersion[];selected_version?:VisualBuilderVersion|null;effective_version?:VisualBuilderVersion|null;default_version?:VisualBuilderVersion|null;platform_default_version:VisualBuilderVersion;releases:Array<{version:VisualBuilderVersion;label:string;schema:string;channel:string;recommended:boolean;description:string;allowed:boolean}>}
type Envelope<T>={data?:T;error?:{message?:string}}
type VisualEditorElement=HTMLElement&{adapter:Record<string,any>;load:()=>Promise<void>}

const active=ref(false)
const portalReady=ref(false)
const mountPoint=ref<HTMLDivElement|null>(null)
const loading=ref(false)
const switching=ref(false)
const error=ref('')
const htmlProtected=ref<HtmlContent|null>(null)
const builderState=ref<BuilderState|null>(null)
const requestedVersion=ref<VisualBuilderVersion>('2.0.1')
const currentContent=ref<Record<string,any>|null>(null)
let editor:VisualEditorElement|null=null
let generation=0

const release=computed(()=>ARGWS_VISUAL_BUILDER_RELEASES.find(item=>item.version===requestedVersion.value))
const allowedReleases=computed(()=>ARGWS_VISUAL_BUILDER_RELEASES.filter(item=>builderState.value?.allowed_versions.includes(item.version as VisualBuilderVersion)))

function isHtmlContent(value:unknown):value is HtmlContent{return Boolean(value&&typeof value==='object'&&(value as HtmlContent).render_mode==='HTML'&&typeof (value as HtmlContent).html_document==='string')}
async function api<T>(path:string,init:RequestInit={}):Promise<T>{
  const response=await fetch(`/api/v1${path}`,{...init,cache:'no-store',headers:{accept:'application/json',...(init.body?{'content-type':'application/json'}:{}),...(init.headers||{})}})
  const payload=await response.json().catch(()=>({})) as Envelope<T>
  if(!response.ok||payload.data===undefined)throw new Error(payload.error?.message||`Falha HTTP ${response.status}`)
  return payload.data
}

async function open():Promise<void>{
  window.dispatchEvent(new CustomEvent('scheduler-pro-workspace-open',{detail:'landing-page'}))
  active.value=true;loading.value=true;error.value='';htmlProtected.value=null;currentContent.value=null
  const current=++generation
  await nextTick()
  try{
    const [page,policy]=await Promise.all([
      api<EditorState>('/landing-pages/home'),
      api<BuilderState>('/settings/visual-builder'),
    ])
    if(current!==generation||!active.value)return
    builderState.value=policy
    if(!policy.available||!policy.effective_version){
      throw new Error('Nenhuma versão do ARGWS Visual Builder foi liberada para esta empresa.')
    }
    requestedVersion.value=policy.effective_version
    if(isHtmlContent(page.content)){htmlProtected.value=page.content;return}
    currentContent.value=page.content
    await mountEditor(policy.effective_version)
  }catch(exc){if(current===generation)error.value=exc instanceof Error?exc.message:'Não foi possível abrir o editor.'}
  finally{if(current===generation)loading.value=false}
}

async function mountEditor(version:VisualBuilderVersion):Promise<void>{
  if(!mountPoint.value||editor||htmlProtected.value)return
  const loaded=await createSchedulerProAdapter(version,{baseUrl:'/api/v1',slug:'home'})
  const element=document.createElement('argws-visual-builder') as VisualEditorElement
  element.classList.add('sp-visual-builder-shell')
  element.adapter=loaded.adapter
  element.addEventListener('upb-close',close)
  mountPoint.value.appendChild(element)
  editor=element
  await editor.load()
}

async function switchVersion():Promise<void>{
  const state=builderState.value
  if(!state||switching.value)return
  const current=state.effective_version
  if(current===requestedVersion.value)return
  const contentVersion=currentContent.value?resolveVisualBuilderVersionFromContent(currentContent.value):current
  if(requestedVersion.value==='1.0.0'&&contentVersion!=='1.0.0'){
    const accepted=window.confirm('A versão 1.0.0 usa o schema anterior. Abrir e salvar uma página criada no 2.x pode simplificar estruturas modernas. O histórico continuará disponível. Deseja trocar mesmo assim?')
    if(!accepted){requestedVersion.value=current||state.platform_default_version;return}
  }
  switching.value=true;error.value=''
  try{
    await api<BuilderState>('/settings/visual-builder',{method:'PUT',body:JSON.stringify({version:requestedVersion.value})})
    // Custom Elements não podem ser redefinidos no mesmo documento. O reload é
    // intencional para ativar exatamente uma release do editor por execução.
    window.location.reload()
  }catch(exc){error.value=exc instanceof Error?exc.message:'Não foi possível alterar a versão.';requestedVersion.value=current||state.platform_default_version;switching.value=false}
}

async function resetVersion():Promise<void>{
  if(switching.value)return
  switching.value=true;error.value=''
  try{await api('/settings/visual-builder',{method:'PUT',body:JSON.stringify({version:null})});window.location.reload()}
  catch(exc){error.value=exc instanceof Error?exc.message:'Não foi possível voltar ao padrão.';switching.value=false}
}

function close():void{
  generation+=1
  editor?.removeEventListener('upb-close',close)
  editor?.remove();editor=null
  htmlProtected.value=null;currentContent.value=null;builderState.value=null;error.value='';loading.value=false;switching.value=false;active.value=false
  window.dispatchEvent(new CustomEvent('scheduler-pro-workspace-close',{detail:'landing-page'}))
}
function workspaceOpened(event:Event):void{const detail=(event as CustomEvent<string>).detail;if(active.value&&detail&&detail!=='landing-page')close()}
function openPublic():void{window.open(`${window.location.origin}/pagina`,'_blank','noopener,noreferrer')}

onMounted(async()=>{await nextTick();portalReady.value=Boolean(document.querySelector('.tenant-console .nav-list'));window.addEventListener('scheduler-pro-workspace-open',workspaceOpened)})
onUnmounted(()=>{window.removeEventListener('scheduler-pro-workspace-open',workspaceOpened);close()})
</script>

<template>
  <Teleport v-if="portalReady" to=".tenant-console .nav-list">
    <button class="nav-item sp-page-editor-nav sp-visual-builder-nav" @click="open"><LayoutTemplate :size="19"/><span>Landing Page</span></button>
  </Teleport>
  <Teleport v-if="active" to="body">
    <div ref="mountPoint" class="sp-visual-builder-mount">
      <aside v-if="builderState?.available" class="builder-version-dock">
        <div><span>ARGWS Visual Builder Editor</span><strong>{{release?.label||requestedVersion}}</strong><small>{{release?.schema}} · {{release?.recommended?'recomendada':'teste/compatibilidade'}}</small></div>
        <label>Versão liberada<select v-model="requestedVersion" :disabled="switching" @change="switchVersion"><option v-for="item in allowedReleases" :key="item.version" :value="item.version">{{item.version}}{{item.recommended?' · atual':''}}</option></select></label>
        <button v-if="builderState.selected_version" :disabled="switching" title="Voltar ao padrão definido pelo administrador" @click="resetVersion"><RotateCcw :size="15"/>Padrão</button>
      </aside>
      <section v-if="loading" class="builder-state"><strong>Abrindo ARGWS Visual Builder…</strong><span>Ativando a release liberada para esta empresa.</span></section>
      <section v-else-if="error" class="builder-state error"><strong>Não foi possível abrir o editor.</strong><span>{{error}}</span><button @click="close">Fechar</button></section>
      <section v-else-if="htmlProtected" class="html-protected-editor">
        <header><div><span><ShieldCheck :size="16"/> HTML preservado</span><h1>Landing Page em HTML completo</h1><p>Este layout não será convertido silenciosamente em blocos. O código, CSS, JavaScript inline, SEO e responsividade permanecem intactos.</p></div><div><button @click="openPublic"><ExternalLink :size="16"/>Página pública</button><button class="icon" aria-label="Fechar" @click="close"><X :size="18"/></button></div></header>
        <div class="html-protected-info"><Code2 :size="20"/><div><strong>Modo HTML visual protegido</strong><span>Os modelos HTML continuam íntegros. A versão selecionada do ARGWS Visual Builder será usada quando uma página nativa editável for aplicada.</span></div></div>
        <div class="html-preview"><HtmlTemplateFrame :html="htmlProtected.html_document" mode="preview"/></div>
      </section>
    </div>
  </Teleport>
</template>

<style scoped>
.sp-visual-builder-mount{position:fixed;inset:0;z-index:10000;background:#0b0f17}.builder-version-dock{position:fixed;z-index:10020;left:max(10px,env(safe-area-inset-left));bottom:max(10px,env(safe-area-inset-bottom));display:flex;align-items:center;gap:10px;max-width:calc(100vw - 20px);padding:9px 10px;border:1px solid #34425f;border-radius:13px;background:rgba(15,25,46,.96);box-shadow:0 12px 34px rgba(0,0,0,.3);color:#fff;backdrop-filter:blur(14px)}.builder-version-dock>div{display:grid;min-width:190px}.builder-version-dock span{font-size:8px;font-weight:900;letter-spacing:.08em;text-transform:uppercase;color:#9fb1ff}.builder-version-dock strong{font-size:11px}.builder-version-dock small{font-size:8px;color:#9eabc0}.builder-version-dock label{display:grid;gap:2px;font-size:8px;color:#9eabc0}.builder-version-dock select{min-height:34px;border:1px solid #46536d;border-radius:8px;background:#101a31;color:#fff;padding:0 26px 0 9px;font:inherit;font-size:10px}.builder-version-dock button{min-height:34px;border:1px solid #46536d;border-radius:8px;background:#17243e;color:#fff;padding:0 9px;display:flex;align-items:center;gap:5px;font:inherit;font-size:9px}.builder-state{height:100dvh;display:grid;place-items:center;align-content:center;gap:8px;padding:24px;background:#0b0f17;color:#fff;text-align:center}.builder-state span{color:#9eabc0}.builder-state button{min-height:42px;border:0;border-radius:10px;padding:0 16px}.builder-state.error strong{color:#ff9da6}.html-protected-editor{height:100dvh;display:grid;grid-template-rows:auto auto 1fr;background:#eef2f7;color:#172033;overflow:hidden}.html-protected-editor>header{display:flex;justify-content:space-between;gap:18px;padding:14px 18px;background:#101a31;color:#fff}.html-protected-editor h1{margin:4px 0;font-size:22px}.html-protected-editor p{margin:0;max-width:760px;color:#b7c2d6;font-size:12px}.html-protected-editor header span{display:flex;align-items:center;gap:6px;color:#9fb1ff;font-size:11px;font-weight:800;text-transform:uppercase}.html-protected-editor header>div:last-child{display:flex;gap:7px;align-items:flex-start}.html-protected-editor button{min-height:38px;border:1px solid #34425f;border-radius:9px;background:#17243e;color:#fff;padding:0 11px;display:flex;align-items:center;gap:6px}.html-protected-editor button.icon{width:38px;padding:0;justify-content:center}.html-protected-info{display:flex;gap:10px;align-items:center;padding:10px 16px;border-bottom:1px solid #d7dee8;background:#fff8df}.html-protected-info div{display:grid}.html-protected-info span{font-size:11px;color:#667085}.html-preview{min-height:0;overflow:auto;background:#fff}.html-preview :deep(.scheduler-html-template-frame){min-height:100%}@media(max-width:700px){.builder-version-dock{left:8px;right:8px;bottom:max(8px,env(safe-area-inset-bottom));display:grid;grid-template-columns:minmax(0,1fr) auto}.builder-version-dock>div{grid-column:1/-1;min-width:0}.builder-version-dock label{min-width:0}.builder-version-dock select{width:100%}.html-protected-editor>header{padding:12px;align-items:flex-start}.html-protected-editor h1{font-size:17px}.html-protected-editor header p{display:none}.html-protected-editor header>div:last-child>button:first-child{font-size:0}.html-protected-editor header>div:last-child>button:first-child svg{width:18px}.html-protected-info{padding:9px 12px}.html-protected-info span{font-size:10px}}
</style>
