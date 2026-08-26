<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch, type CSSProperties } from 'vue'
import {
  ArrowDown, ArrowUp, Copy, Eye, History, ImageUp, LayoutTemplate, Monitor,
  Plus, RotateCcw, Save, Smartphone, Tablet, Trash2, Upload, X,
} from 'lucide-vue-next'
import PublicLandingRenderer from './PublicLandingRenderer.vue'

type Device='desktop'|'tablet'|'mobile'
type SideTab='structure'|'templates'|'elements'
type InspectorTab='content'|'style'|'responsive'|'global'|'history'
type Envelope<T>={data?:T;error?:{message?:string}}
type Template={key:string;name:string;description:string;segment:string}
type Version={id:string;version_number:number;label?:string|null;created_at?:string;published:boolean;draft:boolean}
type Service={id:string;name:string;duration_minutes:number;price?:number|null}
type Professional={id:string;name:string}
type StorageQuota={quota_bytes:number;used_bytes:number;remaining_bytes:number;usage_percent:number}
type ResponsiveStyles={desktop:CSSProperties;tablet:CSSProperties;mobile:CSSProperties;hidden:Partial<Record<Device,boolean>>}
type Block={id:string;type:string;props:Record<string,unknown>;style:CSSProperties;responsive:ResponsiveStyles}
type PageContent={version:number;title?:string;global_styles:Record<string,unknown>;seo:Record<string,unknown>;blocks:Block[]}
type EditorState={
  id?:string;slug:string;status:string;template_key?:string|null;current_version_id?:string|null;
  draft_version_id?:string|null;version_number?:number|null;content:PageContent;published_content?:PageContent|null;versions:Version[]
}
type UploadResult={key:string;public_url?:string;size_bytes?:number}

const ELEMENTS:[string,string][]=[
  ['hero','Hero'],['text','Texto'],['gallery','Galeria'],['services','Serviços'],['professionals','Profissionais'],
  ['testimonials','Depoimentos'],['social','Redes sociais'],['business_hours','Horários'],['address','Endereço'],
  ['contact','Contato'],['faq','FAQ'],['booking','Calendário / Agenda'],['cta','CTA'],['whatsapp_button','Botão WhatsApp'],['footer','Rodapé'],
]
const pageSlug='home'
const portalReady=ref(false)
const active=ref(false)
const loading=ref(false)
const saving=ref(false)
const publishing=ref(false)
const previewOpen=ref(false)
const errorMessage=ref('')
const successMessage=ref('')
const templates=ref<Template[]>([])
const state=ref<EditorState|null>(null)
const content=ref<PageContent>({version:2,global_styles:{},seo:{},blocks:[]})
const selectedId=ref('')
const device=ref<Device>('desktop')
const sideTab=ref<SideTab>('structure')
const inspectorTab=ref<InspectorTab>('content')
const services=ref<Service[]>([])
const professionals=ref<Professional[]>([])
const storage=ref<StorageQuota|null>(null)
const dirty=ref(false)
const uploadBusy=ref(false)
let autosaveTimer:number|undefined
let saveGeneration=0
let editGeneration=0

const selectedBlock=computed(()=>content.value.blocks.find(item=>item.id===selectedId.value)||null)
const globalStyles=computed(()=>content.value.global_styles||{})
const canvasWidth=computed(()=>device.value==='mobile'?'390px':device.value==='tablet'?'820px':'1180px')
const publicLandingUrl=computed(()=>`${window.location.origin}/pagina`)
const publicBookingUrl=computed(()=>`${window.location.origin}/agendar`)

function uid(type:string):string{return `${type}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2,8)}`}
function clone<T>(value:T):T{return JSON.parse(JSON.stringify(value)) as T}
function emptyResponsive():ResponsiveStyles{return{desktop:{},tablet:{},mobile:{},hidden:{desktop:false,tablet:false,mobile:false}}}
function defaultBlock(type:string):Block{
  const defaults:Record<string,Record<string,unknown>>={
    hero:{eyebrow:'Seu estabelecimento',title:'Agende seu horário',text:'Atendimento profissional, simples e no seu tempo.',cta:'Agendar agora',image:''},
    text:{title:'Sobre nós',text:'Conte em poucas linhas o que torna seu atendimento especial.'},
    gallery:{title:'Trabalhos recentes',layout:'editorial',images:[]},
    services:{title:'Serviços',subtitle:'Escolha o atendimento ideal',show_prices:true},
    professionals:{title:'Profissionais',layout:'cards'},
    testimonials:{title:'Depoimentos',items:[]},social:{title:'Redes sociais',instagram:'',facebook:'',tiktok:''},
    business_hours:{title:'Horários de atendimento'},address:{title:'Onde estamos',address:'',show_map:true},
    contact:{title:'Contato',phone:'',email:''},faq:{title:'Perguntas frequentes',items:[]},
    booking:{title:'Escolha seu horário',subtitle:'Selecione serviço, profissional, data e horário.'},
    cta:{title:'Pronto para agendar?',text:'Escolha um horário disponível.',button:'Ver agenda'},
    whatsapp_button:{label:'Falar pelo WhatsApp',phone:''},footer:{text:'Obrigado pela visita.'},
  }
  return{id:uid(type),type,props:clone(defaults[type]||{title:'Novo bloco'}),style:{},responsive:emptyResponsive()}
}
function normalizeContent(value:PageContent|undefined|null):PageContent{
  const next=clone(value||{version:2,global_styles:{},seo:{},blocks:[]})
  next.version=2;next.global_styles=next.global_styles||{};next.seo=next.seo||{};next.blocks=Array.isArray(next.blocks)?next.blocks:[]
  next.blocks=next.blocks.map(block=>({
    ...block,id:block.id||uid(block.type||'block'),type:block.type||'text',props:block.props||{},style:(block.style||{}) as CSSProperties,
    responsive:{desktop:{...(block.responsive?.desktop||{})},tablet:{...(block.responsive?.tablet||{})},mobile:{...(block.responsive?.mobile||{})},hidden:{desktop:false,tablet:false,mobile:false,...(block.responsive?.hidden||{})}},
  }))
  return next
}
function token():string{return localStorage.getItem('scheduler_pro_access_token')||''}
async function api<T>(path:string,init:RequestInit={}):Promise<T>{
  const response=await fetch(`/api/v1${path}`,{...init,cache:'no-store',headers:{accept:'application/json',...(init.body&&!((init.body) instanceof FormData)?{'content-type':'application/json'}:{}),...(token()?{authorization:`Bearer ${token()}`}:{}) ,...(init.headers||{})}})
  const body=await response.json().catch(()=>({})) as Envelope<T>
  if(!response.ok||body.data===undefined)throw new Error(body.error?.message||`Falha HTTP ${response.status}`)
  return body.data
}
function toast(message:string):void{successMessage.value=message;window.setTimeout(()=>{if(successMessage.value===message)successMessage.value=''},3500)}
function fail(error:unknown,fallback:string):void{errorMessage.value=error instanceof Error?error.message:fallback}
function formatBytes(value:number):string{const units=['B','KB','MB','GB'];let size=Math.max(0,value);let unit=0;while(size>=1024&&unit<units.length-1){size/=1024;unit+=1}return`${size.toFixed(unit?1:0)} ${units[unit]}`}

async function load():Promise<void>{
  loading.value=true;errorMessage.value=''
  try{
    const [available,current,serviceRows,professionalRows]=await Promise.all([
      api<Template[]>('/landing-pages/templates'),api<EditorState>(`/landing-pages/${pageSlug}`),
      api<Service[]>('/services').catch(()=>[]),api<Professional[]>('/professionals').catch(()=>[]),
    ])
    templates.value=available;state.value=current;content.value=normalizeContent(current.content);services.value=serviceRows;professionals.value=professionalRows
    selectedId.value=content.value.blocks[0]?.id||'';dirty.value=false
    storage.value=await api<StorageQuota>('/files/quota').catch(()=>null)
  }catch(error){fail(error,'Não foi possível abrir o editor.')}
  finally{loading.value=false}
}
async function open():Promise<void>{window.dispatchEvent(new CustomEvent('scheduler-pro-workspace-open',{detail:'landing-page'}));active.value=true;await load()}
function close():void{if(dirty.value)void saveNow('Alterações salvas ao fechar.');previewOpen.value=false;active.value=false}
function markDirty():void{dirty.value=true;editGeneration+=1;if(autosaveTimer!==undefined)window.clearTimeout(autosaveTimer);autosaveTimer=window.setTimeout(()=>void autosave(),1200)}
function selectBlock(block:Block):void{selectedId.value=block.id;inspectorTab.value='content'}
function addBlock(type:string):void{const block=defaultBlock(type);content.value.blocks.push(block);selectedId.value=block.id;sideTab.value='structure';markDirty()}
function removeBlock(block:Block):void{const index=content.value.blocks.findIndex(item=>item.id===block.id);if(index<0)return;content.value.blocks.splice(index,1);selectedId.value=content.value.blocks[Math.min(index,content.value.blocks.length-1)]?.id||'';markDirty()}
function duplicateBlock(block:Block):void{const index=content.value.blocks.findIndex(item=>item.id===block.id);const copy=clone(block);copy.id=uid(block.type);content.value.blocks.splice(index+1,0,copy);selectedId.value=copy.id;markDirty()}
function moveBlock(block:Block,delta:number):void{const index=content.value.blocks.findIndex(item=>item.id===block.id);const target=index+delta;if(index<0||target<0||target>=content.value.blocks.length)return;const[item]=content.value.blocks.splice(index,1);if(!item)return;content.value.blocks.splice(target,0,item);markDirty()}
function updateProp(key:string,value:unknown):void{if(!selectedBlock.value)return;selectedBlock.value.props[key]=value;markDirty()}
function updateStyle(key:string,value:string|number):void{if(!selectedBlock.value)return;Object.assign(selectedBlock.value.style,{[key]:value});markDirty()}
function updateResponsive(key:string,value:string|number):void{if(!selectedBlock.value)return;Object.assign(selectedBlock.value.responsive[device.value],{[key]:value});markDirty()}
function updateGlobal(key:string,value:unknown):void{content.value.global_styles[key]=value;markDirty()}
function updateSeo(key:string,value:unknown):void{content.value.seo[key]=value;markDirty()}
function toggleHidden(target:Device):void{if(!selectedBlock.value)return;selectedBlock.value.responsive.hidden[target]=!selectedBlock.value.responsive.hidden[target];markDirty()}

async function persistDraft(path:'draft'|'autosave',label?:string):Promise<void>{
  if(saving.value)return
  const generation=editGeneration;const request=++saveGeneration;saving.value=true
  try{
    const result=await api<{version_id:string;version_number:number}>(`/landing-pages/${pageSlug}/${path}`,{method:'POST',body:JSON.stringify(content.value)})
    if(request===saveGeneration&&generation===editGeneration){dirty.value=false;if(state.value){state.value.draft_version_id=result.version_id;state.value.version_number=result.version_number}if(label)toast(label)}
  }catch(error){if(request===saveGeneration)fail(error,path==='autosave'?'Autosave falhou; suas alterações continuam nesta tela.':'Não foi possível salvar o rascunho.')}
  finally{if(request===saveGeneration)saving.value=false}
}
async function saveNow(label='Rascunho salvo.'):Promise<void>{await persistDraft('draft',label)}
async function autosave():Promise<void>{if(!dirty.value||saving.value||publishing.value)return;await persistDraft('autosave')}
async function publish():Promise<void>{
  publishing.value=true;errorMessage.value=''
  try{if(dirty.value)await saveNow();await api(`/landing-pages/${pageSlug}/publish`,{method:'POST',body:JSON.stringify({version_id:state.value?.draft_version_id||null})});await load();toast('Landing Page publicada.')}
  catch(error){fail(error,'Não foi possível publicar.')}
  finally{publishing.value=false}
}
async function applyTemplate(template:Template):Promise<void>{
  if(!window.confirm(`Aplicar o modelo “${template.name}” ao rascunho? A versão publicada não será alterada.`))return
  loading.value=true
  try{await api(`/landing-pages/${pageSlug}/templates/${template.key}`,{method:'POST',body:'{}'});await load();sideTab.value='structure';toast(`Modelo ${template.name} aplicado.`)}
  catch(error){fail(error,'Não foi possível aplicar o modelo.')}
  finally{loading.value=false}
}
async function refreshHistory():Promise<void>{if(state.value)state.value.versions=await api<Version[]>(`/landing-pages/${pageSlug}/versions`)}
async function restoreVersion(version:Version):Promise<void>{if(!window.confirm(`Restaurar a versão ${version.version_number} como novo rascunho?`))return;loading.value=true;try{await api(`/landing-pages/${pageSlug}/versions/${version.id}/restore`,{method:'POST',body:'{}'});await load();toast(`Versão ${version.version_number} restaurada.`)}catch(error){fail(error,'Não foi possível restaurar a versão.')}finally{loading.value=false}}

function safeFileName(value:string):string{return value.normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^A-Za-z0-9._-]+/g,'-').replace(/^-+|-+$/g,'').slice(0,120)||'arquivo'}
async function uploadFile(file:File):Promise<string>{
  uploadBusy.value=true;errorMessage.value=''
  try{
    const key=`landing/${Date.now()}-${safeFileName(file.name)}`
    const form=new FormData();form.append('key',key);form.append('file',file)
    const result=await api<UploadResult>('/files/upload',{method:'POST',body:form})
    storage.value=await api<StorageQuota>('/files/quota').catch(()=>storage.value)
    return result.public_url||`/api/v1/public/assets/${encodeURI(result.key)}`
  }finally{uploadBusy.value=false}
}
async function uploadHeroImage(event:Event):Promise<void>{const input=event.target as HTMLInputElement;const file=input.files?.[0];if(!file||!selectedBlock.value)return;try{updateProp('image',await uploadFile(file));toast('Imagem enviada ao storage do tenant.')}catch(error){fail(error,'Falha ao enviar imagem.')}finally{input.value=''}}
async function uploadGallery(event:Event):Promise<void>{const input=event.target as HTMLInputElement;const files=Array.from(input.files||[]);if(!files.length||!selectedBlock.value)return;try{const current=Array.isArray(selectedBlock.value.props.images)?[...selectedBlock.value.props.images] as string[]:[];for(const file of files)current.push(await uploadFile(file));updateProp('images',current);toast(`${files.length} imagem(ns) enviada(s).`)}catch(error){fail(error,'Falha ao enviar galeria.')}finally{input.value=''}}
async function uploadShareImage(event:Event):Promise<void>{const input=event.target as HTMLInputElement;const file=input.files?.[0];if(!file)return;try{updateSeo('share_image',await uploadFile(file));toast('Imagem de compartilhamento enviada.')}catch(error){fail(error,'Falha ao enviar imagem.')}finally{input.value=''}}

function openPublic(url:string):void{window.open(url,'_blank','noopener,noreferrer')}
function beforeUnload(event:BeforeUnloadEvent):void{if(!dirty.value)return;event.preventDefault();event.returnValue=''}
watch(inspectorTab,value=>{if(value==='history')void refreshHistory()})
watch(active,value=>document.body.classList.toggle('sp-public-editor-open',value))
onMounted(async()=>{await nextTick();portalReady.value=Boolean(document.querySelector('.tenant-console .nav-list'));window.addEventListener('beforeunload',beforeUnload)})
onUnmounted(()=>{document.body.classList.remove('sp-public-editor-open');window.removeEventListener('beforeunload',beforeUnload);if(autosaveTimer!==undefined)window.clearTimeout(autosaveTimer)})
</script>

<template>
  <Teleport v-if="portalReady" to=".tenant-console .nav-list"><button class="nav-item sp-page-editor-nav" @click="open"><LayoutTemplate :size="19"/><span>Landing Page</span></button></Teleport>

  <Teleport v-if="active" to="body">
    <section class="page-editor-v2" role="dialog" aria-modal="true" aria-label="Editor da Landing Page">
      <header class="editor-topbar">
        <div class="editor-brand"><LayoutTemplate :size="20"/><div><strong>Landing Page</strong><small>{{ dirty?'Alterações pendentes':saving?'Salvando…':'Rascunho sincronizado' }}</small></div></div>
        <div class="device-switcher"><button :class="{active:device==='desktop'}" @click="device='desktop'"><Monitor :size="18"/><span>Desktop</span></button><button :class="{active:device==='tablet'}" @click="device='tablet'"><Tablet :size="18"/><span>Tablet</span></button><button :class="{active:device==='mobile'}" @click="device='mobile'"><Smartphone :size="18"/><span>Mobile</span></button></div>
        <div class="top-actions"><button class="soft" :disabled="saving" @click="saveNow()"><Save :size="17"/>Salvar</button><button class="soft" @click="previewOpen=true"><Eye :size="17"/>Preview</button><button class="publish" :disabled="publishing||saving" @click="publish"><Upload :size="17"/>{{ publishing?'Publicando…':'Publicar' }}</button><button class="icon" aria-label="Fechar" @click="close"><X :size="19"/></button></div>
      </header>

      <div class="editor-urlbar"><div><span>Landing pública</span><button @click="openPublic(publicLandingUrl)">{{ publicLandingUrl }}</button></div><div><span>Agenda direta</span><button @click="openPublic(publicBookingUrl)">{{ publicBookingUrl }}</button></div><div v-if="storage" class="storage-meter"><span>Storage {{ formatBytes(storage.used_bytes) }} / {{ formatBytes(storage.quota_bytes) }}</span><i><b :style="{width:`${Math.min(100,storage.usage_percent)}%`}"></b></i></div></div>
      <p v-if="errorMessage" class="editor-alert error">{{ errorMessage }}</p><p v-if="successMessage" class="editor-alert success">{{ successMessage }}</p>

      <div class="editor-body">
        <aside class="editor-left">
          <div class="side-tabs"><button :class="{active:sideTab==='structure'}" @click="sideTab='structure'">Estrutura</button><button :class="{active:sideTab==='templates'}" @click="sideTab='templates'">Modelos</button><button :class="{active:sideTab==='elements'}" @click="sideTab='elements'">+ Blocos</button></div>
          <div v-if="sideTab==='structure'" class="structure-list"><button v-for="(block,index) in content.blocks" :key="block.id" :class="{selected:selectedId===block.id}" @click="selectBlock(block)"><div><strong>{{ block.type }}</strong><small>{{ String(block.props.title||block.props.text||block.props.label||'Bloco') }}</small></div><span><i @click.stop="moveBlock(block,-1)"><ArrowUp :size="13"/></i><i @click.stop="moveBlock(block,1)"><ArrowDown :size="13"/></i></span></button><div v-if="!content.blocks.length" class="empty-side">Escolha um modelo pronto.</div></div>
          <div v-else-if="sideTab==='templates'" class="template-list"><button v-for="template in templates" :key="template.key" :class="{current:state?.template_key===template.key}" @click="applyTemplate(template)"><LayoutTemplate :size="20"/><div><strong>{{ template.name }}</strong><span>{{ template.description }}</span><small>{{ template.segment }}</small></div></button></div>
          <div v-else class="element-list"><button v-for="element in ELEMENTS" :key="element[0]" @click="addBlock(element[0])"><Plus :size="15"/>{{ element[1] }}</button></div>
        </aside>

        <main class="editor-stage">
          <div v-if="loading" class="editor-loading">Carregando editor…</div>
          <div v-else class="canvas-frame" :style="{width:canvasWidth}"><div class="canvas-label">Prévia {{ device==='desktop'?'desktop':device==='tablet'?'tablet':'mobile' }} · mesma renderização da página publicada</div><PublicLandingRenderer :content="content" :services="services" :professionals="professionals" :template-key="state?.template_key" :viewport-override="device"><template #booking><div class="booking-preview-real"><strong>Agenda integrada</strong><span>Serviço → Profissional → Data → Horário → Confirmação</span><button>Escolher horário</button></div></template></PublicLandingRenderer></div>
        </main>

        <aside class="editor-right">
          <div class="inspector-tabs"><button :class="{active:inspectorTab==='content'}" @click="inspectorTab='content'">Conteúdo</button><button :class="{active:inspectorTab==='style'}" @click="inspectorTab='style'">Estilo</button><button :class="{active:inspectorTab==='responsive'}" @click="inspectorTab='responsive'">Responsivo</button><button :class="{active:inspectorTab==='global'}" @click="inspectorTab='global'">Global</button><button :class="{active:inspectorTab==='history'}" @click="inspectorTab='history'">Histórico</button></div>
          <div class="inspector-scroll">
            <template v-if="inspectorTab==='history'"><div class="inspector-title"><History :size="18"/><strong>Histórico</strong></div><div class="history-list"><button v-for="version in state?.versions||[]" :key="version.id" @click="restoreVersion(version)"><div><strong>Versão {{ version.version_number }}</strong><small>{{ version.created_at?new Date(version.created_at).toLocaleString('pt-BR'):'' }}</small></div><em v-if="version.published">Publicada</em><em v-else-if="version.draft">Rascunho</em><RotateCcw v-else :size="15"/></button></div></template>
            <template v-else-if="inspectorTab==='global'"><div class="inspector-title"><strong>Identidade e SEO</strong></div><label>Cor principal<input type="color" :value="String(globalStyles.primary||'#3151cf')" @input="updateGlobal('primary',($event.target as HTMLInputElement).value)"/></label><label>Cor secundária<input type="color" :value="String(globalStyles.secondary||'#151c31')" @input="updateGlobal('secondary',($event.target as HTMLInputElement).value)"/></label><label>Cor de destaque<input type="color" :value="String(globalStyles.accent||'#6d72ef')" @input="updateGlobal('accent',($event.target as HTMLInputElement).value)"/></label><label>Fundo<input type="color" :value="String(globalStyles.background||'#ffffff')" @input="updateGlobal('background',($event.target as HTMLInputElement).value)"/></label><label>Texto<input type="color" :value="String(globalStyles.text||'#1d273a')" @input="updateGlobal('text',($event.target as HTMLInputElement).value)"/></label><label>Fonte de títulos<input :value="String(globalStyles.heading_font||'Inter')" @input="updateGlobal('heading_font',($event.target as HTMLInputElement).value)"/></label><label>Fonte de textos<input :value="String(globalStyles.body_font||'Inter')" @input="updateGlobal('body_font',($event.target as HTMLInputElement).value)"/></label><label>Título social<input :value="String(content.seo.title||'')" @input="updateSeo('title',($event.target as HTMLInputElement).value)"/></label><label>Descrição social<textarea :value="String(content.seo.description||'')" @input="updateSeo('description',($event.target as HTMLTextAreaElement).value)"></textarea></label><label class="file-label"><ImageUp :size="16"/>Imagem de compartilhamento<input type="file" accept="image/png,image/jpeg,image/webp" :disabled="uploadBusy" @change="uploadShareImage"/></label><small v-if="content.seo.share_image" class="asset-path">{{ content.seo.share_image }}</small></template>
            <template v-else-if="selectedBlock"><div class="inspector-title"><strong>{{ selectedBlock.type }}</strong><small>{{ selectedBlock.id }}</small></div>
              <template v-if="inspectorTab==='content'"><label v-if="'eyebrow' in selectedBlock.props">Chamada<input :value="String(selectedBlock.props.eyebrow||'')" @input="updateProp('eyebrow',($event.target as HTMLInputElement).value)"/></label><label v-if="'title' in selectedBlock.props">Título<input :value="String(selectedBlock.props.title||'')" @input="updateProp('title',($event.target as HTMLInputElement).value)"/></label><label v-if="'text' in selectedBlock.props">Texto<textarea :value="String(selectedBlock.props.text||'')" @input="updateProp('text',($event.target as HTMLTextAreaElement).value)"></textarea></label><label v-if="'subtitle' in selectedBlock.props">Subtítulo<textarea :value="String(selectedBlock.props.subtitle||'')" @input="updateProp('subtitle',($event.target as HTMLTextAreaElement).value)"></textarea></label><label v-if="'label' in selectedBlock.props">Rótulo<input :value="String(selectedBlock.props.label||'')" @input="updateProp('label',($event.target as HTMLInputElement).value)"/></label><label v-if="'cta' in selectedBlock.props">Botão<input :value="String(selectedBlock.props.cta||'')" @input="updateProp('cta',($event.target as HTMLInputElement).value)"/></label><label v-if="'button' in selectedBlock.props">Botão<input :value="String(selectedBlock.props.button||'')" @input="updateProp('button',($event.target as HTMLInputElement).value)"/></label><label v-if="'phone' in selectedBlock.props">Telefone<input :value="String(selectedBlock.props.phone||'')" @input="updateProp('phone',($event.target as HTMLInputElement).value)"/></label><label v-if="'email' in selectedBlock.props">E-mail<input :value="String(selectedBlock.props.email||'')" @input="updateProp('email',($event.target as HTMLInputElement).value)"/></label><label v-if="'address' in selectedBlock.props">Endereço<textarea :value="String(selectedBlock.props.address||'')" @input="updateProp('address',($event.target as HTMLTextAreaElement).value)"></textarea></label><label v-if="'image' in selectedBlock.props" class="file-label"><ImageUp :size="16"/>Enviar imagem<input type="file" accept="image/png,image/jpeg,image/webp,image/svg+xml" :disabled="uploadBusy" @change="uploadHeroImage"/></label><label v-if="selectedBlock.type==='gallery'" class="file-label"><ImageUp :size="16"/>Adicionar fotos<input type="file" multiple accept="image/png,image/jpeg,image/webp" :disabled="uploadBusy" @change="uploadGallery"/></label><div class="inspector-actions"><button @click="duplicateBlock(selectedBlock)"><Copy :size="15"/>Duplicar</button><button class="danger" @click="removeBlock(selectedBlock)"><Trash2 :size="15"/>Excluir</button></div></template>
              <template v-else-if="inspectorTab==='style'"><label>Fonte<input :value="String(selectedBlock.style.fontFamily||'')" placeholder="Herdar global" @input="updateStyle('fontFamily',($event.target as HTMLInputElement).value)"/></label><label>Tamanho<input type="number" :value="Number(String(selectedBlock.style.fontSize||'0').replace('px',''))" @input="updateStyle('fontSize',`${($event.target as HTMLInputElement).value}px`)"/></label><label>Alinhamento<select :value="String(selectedBlock.style.textAlign||'')" @change="updateStyle('textAlign',($event.target as HTMLSelectElement).value)"><option value="">Padrão</option><option value="left">Esquerda</option><option value="center">Centro</option><option value="right">Direita</option></select></label><label>Padding<input :value="String(selectedBlock.style.padding||'')" placeholder="24px" @input="updateStyle('padding',($event.target as HTMLInputElement).value)"/></label><label>Gap<input :value="String(selectedBlock.style.gap||'')" placeholder="16px" @input="updateStyle('gap',($event.target as HTMLInputElement).value)"/></label><label>Largura máxima<input :value="String(selectedBlock.style.maxWidth||'')" placeholder="1180px" @input="updateStyle('maxWidth',($event.target as HTMLInputElement).value)"/></label></template>
              <template v-else><div class="responsive-summary"><strong>{{ device==='desktop'?'Desktop':device==='tablet'?'Tablet':'Mobile' }}</strong><span>Aqui você altera somente este breakpoint.</span></div><label>Tamanho<input type="number" min="8" max="120" :value="Number(String(selectedBlock.responsive[device].fontSize||'0').replace('px',''))" @input="updateResponsive('fontSize',`${($event.target as HTMLInputElement).value}px`)"/></label><label>Padding<input :value="String(selectedBlock.responsive[device].padding||'')" placeholder="20px" @input="updateResponsive('padding',($event.target as HTMLInputElement).value)"/></label><label>Gap<input :value="String(selectedBlock.responsive[device].gap||'')" placeholder="12px" @input="updateResponsive('gap',($event.target as HTMLInputElement).value)"/></label><div class="hide-grid"><button :class="{active:selectedBlock.responsive.hidden.desktop}" @click="toggleHidden('desktop')"><Monitor :size="15"/>Desktop</button><button :class="{active:selectedBlock.responsive.hidden.tablet}" @click="toggleHidden('tablet')"><Tablet :size="15"/>Tablet</button><button :class="{active:selectedBlock.responsive.hidden.mobile}" @click="toggleHidden('mobile')"><Smartphone :size="15"/>Mobile</button></div></template>
            </template>
            <div v-else class="empty-side">Selecione um bloco na estrutura.</div>
          </div>
        </aside>
      </div>

      <div v-if="previewOpen" class="preview-dialog"><header><strong>Preview real</strong><div class="device-switcher"><button :class="{active:device==='desktop'}" @click="device='desktop'"><Monitor :size="17"/></button><button :class="{active:device==='tablet'}" @click="device='tablet'"><Tablet :size="17"/></button><button :class="{active:device==='mobile'}" @click="device='mobile'"><Smartphone :size="17"/></button></div><button class="icon" aria-label="Fechar preview" @click="previewOpen=false"><X :size="19"/></button></header><main><div class="preview-frame" :style="{width:canvasWidth}"><PublicLandingRenderer :content="content" :services="services" :professionals="professionals" :template-key="state?.template_key" :viewport-override="device"><template #booking><div class="booking-preview-real"><strong>Agenda integrada</strong><span>Fluxo real disponível em /agendar</span><button>Escolher horário</button></div></template></PublicLandingRenderer></div></main></div>
    </section>
  </Teleport>
</template>

<style scoped>
.page-editor-v2{position:fixed;inset:0;z-index:10000;display:grid;grid-template-rows:auto auto auto 1fr;background:#eef2f7;color:#172033;font-family:Inter,system-ui,sans-serif}.editor-topbar{display:grid;grid-template-columns:minmax(180px,1fr) auto minmax(300px,1fr);align-items:center;gap:12px;padding:10px 14px;background:#101a31;color:#fff}.editor-brand{display:flex;gap:9px;align-items:center}.editor-brand div{display:grid}.editor-brand small{color:#aab6ce}.device-switcher,.top-actions{display:flex;gap:6px;align-items:center}.device-switcher button,.top-actions button,.icon{min-height:38px;border:1px solid rgba(255,255,255,.16);border-radius:9px;background:rgba(255,255,255,.06);color:inherit;padding:0 10px;display:inline-flex;align-items:center;justify-content:center;gap:6px;font:inherit;cursor:pointer}.device-switcher button.active{background:#fff;color:#172033}.top-actions{justify-content:flex-end}.top-actions .publish{background:#4164e8;border-color:#4164e8}.editor-urlbar{display:grid;grid-template-columns:1fr 1fr minmax(220px,.8fr);gap:10px;align-items:center;padding:8px 14px;border-bottom:1px solid #dbe2ec;background:#fff}.editor-urlbar>div{min-width:0;display:grid;gap:2px}.editor-urlbar span{font-size:.7rem;font-weight:800;color:#64748b}.editor-urlbar button{overflow:hidden;border:0;background:none;padding:0;color:#3151cf;text-align:left;text-overflow:ellipsis;white-space:nowrap;cursor:pointer}.storage-meter i{height:5px;overflow:hidden;border-radius:999px;background:#e5e7eb}.storage-meter b{display:block;height:100%;background:#3151cf}.editor-alert{margin:0;padding:8px 14px}.editor-alert.error{background:#fff0f0;color:#a62323}.editor-alert.success{background:#eaf8ef;color:#176a3b}.editor-body{min-height:0;display:grid;grid-template-columns:280px minmax(0,1fr) 330px}.editor-left,.editor-right{min-height:0;overflow:hidden;background:#fff}.editor-left{border-right:1px solid #dce2eb}.editor-right{border-left:1px solid #dce2eb}.side-tabs,.inspector-tabs{display:flex;gap:4px;padding:8px;border-bottom:1px solid #e4e8ef;overflow:auto}.side-tabs button,.inspector-tabs button{border:0;border-radius:8px;background:transparent;padding:8px;font:inherit;font-size:.76rem;font-weight:750;white-space:nowrap;cursor:pointer}.side-tabs button.active,.inspector-tabs button.active{background:#eaf0ff;color:#2946ae}.structure-list,.template-list,.element-list{height:calc(100dvh - 145px);box-sizing:border-box;overflow:auto;padding:10px;display:grid;align-content:start;gap:7px}.structure-list>button{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;gap:6px;border:1px solid #e0e5ee;border-radius:10px;background:#fff;padding:9px;text-align:left}.structure-list>button.selected{border-color:#4164e8;background:#f3f6ff}.structure-list button div{min-width:0;display:grid}.structure-list small{overflow:hidden;color:#7b8699;text-overflow:ellipsis;white-space:nowrap}.structure-list button>span{display:flex}.structure-list button i{display:grid;place-items:center;padding:4px;border-radius:6px;background:#eef1f6}.template-list button{display:grid;grid-template-columns:auto 1fr;gap:10px;border:1px solid #dfe5ee;border-radius:12px;background:#fff;padding:12px;text-align:left}.template-list button.current{border-color:#4164e8;background:#f3f6ff}.template-list button div{display:grid;gap:4px}.template-list span,.template-list small{color:#6f7b8f;font-size:.76rem}.element-list{grid-template-columns:1fr 1fr}.element-list button{min-height:48px;border:1px solid #dfe5ee;border-radius:9px;background:#fff;display:flex;align-items:center;gap:6px;padding:8px;text-align:left}.editor-stage{min-width:0;min-height:0;overflow:auto;padding:24px;background:radial-gradient(circle at 1px 1px,#ccd3df 1px,transparent 0);background-size:18px 18px}.canvas-frame{max-width:100%;margin:auto;transition:width .18s;background:#fff;box-shadow:0 14px 50px rgba(20,31,54,.16)}.canvas-label{position:sticky;top:0;z-index:2;padding:7px 10px;background:#0f172adf;color:#fff;font-size:.72rem;text-align:center}.canvas-frame :deep(.sp-public-renderer){min-height:680px}.booking-preview-real{display:grid;gap:8px;padding:20px;border:1px solid #dbe3ee;border-radius:16px;background:#fff}.booking-preview-real span{color:#64748b}.booking-preview-real button{width:max-content;min-height:42px;border:0;border-radius:10px;background:#3151cf;color:#fff;padding:0 14px;font-weight:800}.editor-loading{display:grid;place-items:center;min-height:400px}.inspector-scroll{height:calc(100dvh - 145px);overflow:auto;padding:14px;box-sizing:border-box}.inspector-title{display:grid;gap:2px;margin-bottom:14px}.inspector-title small{color:#7b8699}.inspector-scroll label{display:grid;gap:6px;margin-bottom:12px;font-size:.8rem;font-weight:750}.inspector-scroll input,.inspector-scroll textarea,.inspector-scroll select{box-sizing:border-box;width:100%;border:1px solid #d3dae5;border-radius:8px;padding:9px;font:inherit}.inspector-scroll textarea{min-height:78px;resize:vertical}.file-label{min-height:42px;border:1px dashed #aebbd0;border-radius:9px;padding:9px;color:#3151cf;display:flex!important;align-items:center;justify-content:center;gap:7px!important;cursor:pointer}.file-label input{display:none}.asset-path{display:block;margin:-6px 0 12px;overflow-wrap:anywhere;color:#758095}.inspector-actions{display:grid;grid-template-columns:1fr 1fr;gap:6px}.inspector-actions button,.hide-grid button{min-height:38px;border:1px solid #d7dee9;border-radius:8px;background:#fff;display:flex;align-items:center;justify-content:center;gap:5px}.inspector-actions .danger{color:#aa2525}.hide-grid{display:grid;grid-template-columns:1fr;gap:6px;margin-top:12px}.hide-grid button.active{background:#fff0f0;color:#a62323;border-color:#efcaca}.responsive-summary{display:grid;gap:3px;margin-bottom:13px;padding:10px;border-radius:9px;background:#f2f5fb}.responsive-summary span{font-size:.76rem;color:#758095}.history-list{display:grid;gap:7px}.history-list button{display:flex;justify-content:space-between;align-items:center;gap:8px;border:1px solid #e0e5ee;border-radius:9px;background:#fff;padding:10px;text-align:left}.history-list button div{display:grid}.history-list small{color:#7b8699}.history-list em{font-size:.7rem;color:#3151cf;font-style:normal}.empty-side{padding:22px;text-align:center;color:#7d8798}.preview-dialog{position:fixed;inset:0;z-index:10020;display:grid;grid-template-rows:auto 1fr;background:#dfe5ee}.preview-dialog>header{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;padding:9px 14px;background:#101a31;color:#fff}.preview-dialog>header>.icon{justify-self:end}.preview-dialog>main{overflow:auto;padding:24px}.preview-frame{max-width:100%;margin:auto;background:#fff;box-shadow:0 16px 60px rgba(15,23,42,.2)}.preview-frame :deep(.sp-public-renderer){min-height:100dvh}.sp-public-editor-open{overflow:hidden}
@media(max-width:1000px){.editor-topbar{grid-template-columns:1fr auto}.editor-brand{display:none}.device-switcher button span{display:none}.editor-body{grid-template-columns:220px minmax(0,1fr)}.editor-right{position:fixed;z-index:10010;right:0;top:104px;bottom:0;width:min(86vw,330px);box-shadow:-18px 0 50px rgba(15,23,42,.16)}.editor-stage{padding:14px}.editor-urlbar{grid-template-columns:1fr 1fr}.storage-meter{grid-column:1/-1}.inspector-tabs{position:sticky;top:0;background:#fff}.top-actions{justify-content:flex-end}}
@media(max-width:700px){.page-editor-v2{grid-template-rows:auto auto auto 1fr}.editor-topbar{display:flex;flex-wrap:wrap}.device-switcher{order:3;width:100%;justify-content:center}.top-actions{margin-left:auto}.top-actions button{padding:0 8px}.top-actions button:not(.icon) svg+*{display:none}.editor-urlbar{display:none}.editor-body{grid-template-columns:1fr}.editor-left{position:fixed;z-index:10009;left:0;bottom:0;top:96px;width:74px}.side-tabs{display:grid}.side-tabs button{font-size:.65rem;padding:7px 3px}.structure-list,.template-list,.element-list{height:calc(100dvh - 190px);padding:5px}.structure-list>button{display:block;padding:6px}.structure-list small,.structure-list button>span,.template-list svg,.template-list span,.template-list small{display:none}.template-list button{display:block;padding:7px;font-size:.7rem}.element-list{grid-template-columns:1fr}.element-list button{min-height:40px;font-size:0;justify-content:center}.element-list button svg{width:18px}.editor-stage{padding:8px 8px 8px 82px}.editor-right{top:96px}.preview-dialog>main{padding:8px}.preview-dialog>header{grid-template-columns:1fr auto auto}}
</style>
