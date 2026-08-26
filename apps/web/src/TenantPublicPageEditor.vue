<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import {
  ArrowDown, ArrowUp, Check, ChevronLeft, Clipboard, Copy, Eye, GripVertical,
  History, Laptop, Layers3, LayoutTemplate, Menu, Monitor, Palette, Plus,
  RotateCcw, Save, Settings2, Smartphone, Tablet, Trash2, Upload, X,
} from 'lucide-vue-next'

type Device = 'desktop' | 'tablet' | 'mobile'
type SideTab = 'elements' | 'structure' | 'templates'
type InspectorTab = 'content' | 'style' | 'responsive' | 'global' | 'history'
type Envelope<T> = { data?:T; error?:{message?:string} }
type Template = { key:string; name:string; description:string; segment:string }
type Version = { id:string; version_number:number; label?:string|null; created_at?:string; published:boolean; draft:boolean }
type Block = {
  id:string
  type:string
  props:Record<string, unknown>
  style:Record<string, unknown>
  responsive:{desktop:Record<string,unknown>;tablet:Record<string,unknown>;mobile:Record<string,unknown>;hidden:{desktop:boolean;tablet:boolean;mobile:boolean}}
}
type PageContent = {
  version:number
  title?:string
  global_styles:Record<string,unknown>
  seo:Record<string,unknown>
  blocks:Block[]
}
type EditorState = {
  id?:string
  slug:string
  status:string
  template_key?:string|null
  current_version_id?:string|null
  draft_version_id?:string|null
  version_number?:number|null
  content:PageContent
  published_content?:PageContent|null
  versions:Version[]
}

const ELEMENTS = [
  ['section','Seção'],['container','Container'],['columns','Colunas'],['grid','Grid'],
  ['hero','Hero'],['title','Título'],['subtitle','Subtítulo'],['text','Texto'],['logo','Logo'],
  ['image','Imagem'],['gallery','Galeria'],['video','Vídeo seguro'],['button','Botão'],
  ['whatsapp_button','Botão WhatsApp'],['social','Redes sociais'],['divider','Divisor'],['spacer','Espaço'],
  ['card','Card'],['services','Serviços'],['professionals','Profissionais'],['booking','Calendário / Agenda'],
  ['form','Formulário'],['business_hours','Horário de funcionamento'],['address','Endereço'],['map','Mapa'],
  ['contact','Contato'],['faq','FAQ'],['testimonials','Depoimentos'],['cta','CTA'],['notices','Avisos'],
  ['policies','Políticas'],['footer','Rodapé'],
] as const

const pageSlug = 'home'
const portalReady = ref(false)
const active = ref(false)
const loading = ref(false)
const saving = ref(false)
const publishing = ref(false)
const errorMessage = ref('')
const successMessage = ref('')
const templates = ref<Template[]>([])
const state = ref<EditorState|null>(null)
const content = ref<PageContent>({version:2,global_styles:{},seo:{},blocks:[]})
const selectedId = ref<string>('')
const device = ref<Device>('desktop')
const sideTab = ref<SideTab>('elements')
const inspectorTab = ref<InspectorTab>('content')
const leftOpen = ref(true)
const rightOpen = ref(true)
const draggingId = ref('')
const clipboard = ref<Block|null>(null)
const dirty = ref(false)
let autosaveTimer:number|undefined
let editGeneration = 0
let saveGeneration = 0

const selectedBlock = computed(()=>content.value.blocks.find(item=>item.id===selectedId.value)||null)
const canvasWidth = computed(()=>device.value==='mobile'?'390px':device.value==='tablet'?'820px':'1180px')
const globalStyles = computed(()=>content.value.global_styles || {})

function id(type:string):string { return `${type}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2,8)}` }
function deepClone<T>(value:T):T { return JSON.parse(JSON.stringify(value)) as T }
function emptyResponsive():Block['responsive'] { return {desktop:{},tablet:{},mobile:{},hidden:{desktop:false,tablet:false,mobile:false}} }
function defaultBlock(type:string):Block {
  const defaults:Record<string,Record<string,unknown>>={
    section:{title:'Nova seção'},container:{title:'Container'},columns:{columns:2},grid:{columns:3},
    hero:{eyebrow:'Seu estabelecimento',title:'Agende seu horário',text:'Apresente aqui sua proposta de valor.',cta:'Agendar agora',image:''},
    title:{text:'Novo título'},subtitle:{text:'Novo subtítulo'},text:{text:'Escreva seu conteúdo aqui.'},logo:{image:'',alt:'Logomarca'},
    image:{image:'',alt:'Imagem'},gallery:{title:'Galeria',layout:'grid',images:[]},video:{title:'Vídeo',url:''},
    button:{label:'Saiba mais',url:'#'},whatsapp_button:{label:'Falar pelo WhatsApp',phone:''},social:{title:'Redes sociais',instagram:'',facebook:''},
    divider:{},spacer:{height:32},card:{title:'Card',text:'Conteúdo do card'},services:{title:'Serviços',subtitle:'Conheça as opções',show_prices:true},
    professionals:{title:'Profissionais',layout:'cards'},booking:{title:'Agende seu horário',subtitle:'Escolha a melhor data e horário.'},
    form:{title:'Formulário'},business_hours:{title:'Horário de funcionamento'},address:{title:'Onde estamos',address:'',show_map:true},
    map:{title:'Localização',address:''},contact:{title:'Contato',phone:'',email:''},faq:{title:'Perguntas frequentes',items:[]},
    testimonials:{title:'Depoimentos',items:[]},cta:{title:'Pronto para agendar?',text:'Escolha um horário disponível.',button:'Agendar'},
    notices:{title:'Avisos',text:''},policies:{title:'Políticas',text:''},footer:{text:'Obrigado pela visita.'},
  }
  return {id:id(type),type,props:deepClone(defaults[type]||{title:'Novo bloco'}),style:{},responsive:emptyResponsive()}
}

async function api<T>(path:string,init:RequestInit={}):Promise<T>{
  const response=await fetch(`/api/v1${path}`,{...init,cache:'no-store',headers:{accept:'application/json',...(init.body?{'content-type':'application/json'}:{}),...(init.headers||{})}})
  const body=await response.json().catch(()=>({})) as Envelope<T>
  if(!response.ok) throw new Error(body.error?.message||`Falha HTTP ${response.status}`)
  return body.data as T
}
function toast(message:string):void{successMessage.value=message;window.setTimeout(()=>{if(successMessage.value===message)successMessage.value=''},3500)}
function fail(error:unknown,fallback:string):void{errorMessage.value=error instanceof Error?error.message:fallback}

function normalizeContent(value:PageContent|undefined|null):PageContent{
  const candidate=deepClone(value||({version:2,global_styles:{},seo:{},blocks:[]} as PageContent))
  candidate.version=Number(candidate.version||2)
  candidate.global_styles=candidate.global_styles||{}
  candidate.seo=candidate.seo||{}
  candidate.blocks=Array.isArray(candidate.blocks)?candidate.blocks:[]
  candidate.blocks=candidate.blocks.map(item=>({
    ...item,id:item.id||id(item.type||'block'),type:item.type||'text',props:item.props||{},style:item.style||{},
    responsive:item.responsive||emptyResponsive(),
  }))
  return candidate
}

async function load():Promise<void>{
  loading.value=true;errorMessage.value=''
  try{
    const [available,current]=await Promise.all([api<Template[]>('/landing-pages/templates'),api<EditorState>(`/landing-pages/${pageSlug}`)])
    templates.value=available;state.value=current;content.value=normalizeContent(current.content);selectedId.value=content.value.blocks[0]?.id||'';dirty.value=false
  }catch(error){fail(error,'Não foi possível abrir o editor.')}
  finally{loading.value=false}
}
async function open():Promise<void>{active.value=true;await load()}
function close():void{if(dirty.value)void saveNow('Autosave ao fechar');active.value=false}

function markDirty():void{
  dirty.value=true;editGeneration+=1
  if(autosaveTimer!==undefined)window.clearTimeout(autosaveTimer)
  autosaveTimer=window.setTimeout(()=>void autosave(),900)
}
function selectBlock(block:Block):void{selectedId.value=block.id;if(window.innerWidth<760)rightOpen.value=true}
function addBlock(type:string,index?:number):void{
  const block=defaultBlock(type);const at=index===undefined?content.value.blocks.length:index
  content.value.blocks.splice(at,0,block);selectedId.value=block.id;markDirty()
}
function removeBlock(block:Block):void{
  const index=content.value.blocks.findIndex(item=>item.id===block.id);if(index<0)return
  content.value.blocks.splice(index,1);selectedId.value=content.value.blocks[Math.min(index,content.value.blocks.length-1)]?.id||'';markDirty()
}
function duplicateBlock(block:Block):void{
  const index=content.value.blocks.findIndex(item=>item.id===block.id);const copy=deepClone(block);copy.id=id(block.type)
  content.value.blocks.splice(index+1,0,copy);selectedId.value=copy.id;markDirty()
}
function copyBlock(block:Block):void{clipboard.value=deepClone(block);toast('Bloco copiado.')}
function pasteBlock():void{if(!clipboard.value)return;const copy=deepClone(clipboard.value);copy.id=id(copy.type);const index=Math.max(0,content.value.blocks.findIndex(item=>item.id===selectedId.value)+1);content.value.blocks.splice(index,0,copy);selectedId.value=copy.id;markDirty()}
function moveBlock(block:Block,delta:number):void{const index=content.value.blocks.findIndex(item=>item.id===block.id);const target=index+delta;if(index<0||target<0||target>=content.value.blocks.length)return;const [item]=content.value.blocks.splice(index,1);content.value.blocks.splice(target,0,item);markDirty()}
function dragStart(block:Block,event:DragEvent):void{draggingId.value=block.id;event.dataTransfer?.setData('text/plain',block.id);if(event.dataTransfer)event.dataTransfer.effectAllowed='move'}
function dropOn(target:Block,event:DragEvent):void{event.preventDefault();const sourceId=event.dataTransfer?.getData('text/plain')||draggingId.value;if(!sourceId||sourceId===target.id)return;const from=content.value.blocks.findIndex(item=>item.id===sourceId);const to=content.value.blocks.findIndex(item=>item.id===target.id);if(from<0||to<0)return;const [item]=content.value.blocks.splice(from,1);content.value.blocks.splice(to,0,item);draggingId.value='';markDirty()}

function updateProp(key:string,value:unknown):void{if(!selectedBlock.value)return;selectedBlock.value.props[key]=value;markDirty()}
function updateStyle(key:string,value:unknown):void{if(!selectedBlock.value)return;selectedBlock.value.style[key]=value;markDirty()}
function updateResponsive(key:string,value:unknown):void{if(!selectedBlock.value)return;selectedBlock.value.responsive[device.value][key]=value;markDirty()}
function toggleHidden(target:Device):void{if(!selectedBlock.value)return;selectedBlock.value.responsive.hidden[target]=!selectedBlock.value.responsive.hidden[target];markDirty()}
function updateGlobal(key:string,value:unknown):void{content.value.global_styles[key]=value;markDirty()}
function updateSeo(key:string,value:unknown):void{content.value.seo[key]=value;markDirty()}

async function saveNow(label='Rascunho manual'):Promise<void>{
  const generation=editGeneration;const requestGeneration=++saveGeneration;saving.value=true;errorMessage.value=''
  try{
    const result=await api<{version_id:string;version_number:number}>(`/landing-pages/${pageSlug}/draft`,{method:'POST',body:JSON.stringify(content.value)})
    if(requestGeneration===saveGeneration&&generation===editGeneration){dirty.value=false;if(state.value){state.value.draft_version_id=result.version_id;state.value.version_number=result.version_number}toast(label==='Rascunho manual'?'Rascunho salvo.':'Alterações salvas.')}
  }catch(error){if(requestGeneration===saveGeneration)fail(error,'Não foi possível salvar o rascunho.')}
  finally{if(requestGeneration===saveGeneration)saving.value=false}
}
async function autosave():Promise<void>{
  if(!dirty.value||saving.value||publishing.value)return
  const generation=editGeneration;const requestGeneration=++saveGeneration;saving.value=true
  try{
    const result=await api<{version_id:string;version_number:number}>(`/landing-pages/${pageSlug}/autosave`,{method:'POST',body:JSON.stringify(content.value)})
    // Uma resposta antiga nunca marca como salvo um conteúdo editado depois dela.
    if(requestGeneration===saveGeneration&&generation===editGeneration){dirty.value=false;if(state.value){state.value.draft_version_id=result.version_id;state.value.version_number=result.version_number}}
  }catch(error){if(requestGeneration===saveGeneration)fail(error,'Autosave falhou; suas alterações continuam nesta tela.')}
  finally{if(requestGeneration===saveGeneration)saving.value=false}
}
async function publish():Promise<void>{
  publishing.value=true;errorMessage.value=''
  try{if(dirty.value)await saveNow('Preparação da publicação');await api(`/landing-pages/${pageSlug}/publish`,{method:'POST',body:JSON.stringify({version_id:state.value?.draft_version_id||null})});state.value=await api<EditorState>(`/landing-pages/${pageSlug}`);content.value=normalizeContent(state.value.content);toast('Nova versão publicada.')}
  catch(error){fail(error,'Não foi possível publicar.')}
  finally{publishing.value=false}
}
async function applyTemplate(template:Template):Promise<void>{
  if(!window.confirm(`Criar um novo rascunho usando o modelo “${template.name}”? A versão publicada não será alterada.`))return
  loading.value=true;errorMessage.value=''
  try{await api(`/landing-pages/${pageSlug}/templates/${template.key}`,{method:'POST',body:'{}'});await load();sideTab.value='structure';toast(`Modelo ${template.name} aplicado ao rascunho.`)}
  catch(error){fail(error,'Não foi possível aplicar o modelo.')}
  finally{loading.value=false}
}
async function restoreVersion(version:Version):Promise<void>{
  if(!window.confirm(`Restaurar a versão ${version.version_number} como um novo rascunho?`))return
  loading.value=true
  try{await api(`/landing-pages/${pageSlug}/versions/${version.id}/restore`,{method:'POST',body:'{}'});await load();toast(`Versão ${version.version_number} restaurada em novo rascunho.`)}
  catch(error){fail(error,'Não foi possível restaurar a versão.')}
  finally{loading.value=false}
}
async function refreshHistory():Promise<void>{if(!state.value)return;state.value.versions=await api<Version[]>(`/landing-pages/${pageSlug}/versions`)}

const cardTitle=(block:Block)=>String(block.props.title||block.props.text||block.props.label||block.type)
const displayType=(type:string)=>ELEMENTS.find(item=>item[0]===type)?.[1]||type
const previewStyle=(block:Block)=>{
  const responsive=block.responsive?.[device.value]||{}
  return {...block.style,...responsive}
}

watch(inspectorTab,value=>{if(value==='history')void refreshHistory()})
watch(active,value=>document.body.classList.toggle('sp-public-editor-open',value))
onMounted(async()=>{await nextTick();window.requestAnimationFrame(()=>{portalReady.value=Boolean(document.querySelector('.tenant-console .nav-list')&&document.querySelector('.tenant-console .main-content'))});window.addEventListener('beforeunload',beforeUnload)})
onUnmounted(()=>{document.body.classList.remove('sp-public-editor-open');window.removeEventListener('beforeunload',beforeUnload);if(autosaveTimer!==undefined)window.clearTimeout(autosaveTimer)})
function beforeUnload(event:BeforeUnloadEvent):void{if(!dirty.value)return;event.preventDefault();event.returnValue=''}
</script>

<template>
  <Teleport v-if="portalReady" to=".tenant-console .nav-list">
    <button class="nav-item sp-page-editor-nav" @click="open"><LayoutTemplate :size="19"/><span>Página Pública</span></button>
  </Teleport>

  <Teleport v-if="portalReady && active" to="body">
    <section class="page-editor" role="dialog" aria-modal="true" aria-label="Editor da página pública">
      <header class="editor-topbar">
        <div class="top-left"><button class="icon" aria-label="Fechar editor" @click="close"><ChevronLeft :size="20"/></button><div><strong>Página Pública</strong><small>{{ dirty?'Alterações não publicadas':saving?'Salvando…':'Rascunho salvo' }}</small></div></div>
        <div class="device-switcher" aria-label="Visualização responsiva">
          <button :class="{active:device==='desktop'}" title="Desktop" @click="device='desktop'"><Monitor :size="18"/></button>
          <button :class="{active:device==='tablet'}" title="Tablet" @click="device='tablet'"><Tablet :size="18"/></button>
          <button :class="{active:device==='mobile'}" title="Mobile" @click="device='mobile'"><Smartphone :size="18"/></button>
        </div>
        <div class="top-actions"><button class="soft mobile-panel" @click="leftOpen=!leftOpen"><Menu :size="17"/> Elementos</button><button class="soft" :disabled="saving" @click="saveNow()"><Save :size="17"/> Salvar</button><button class="soft" title="Preview responsivo" @click="device=device==='desktop'?'mobile':'desktop'"><Eye :size="17"/><span class="desktop-label">Preview</span></button><button class="publish" :disabled="publishing||saving" @click="publish"><Upload :size="17"/> {{ publishing?'Publicando…':'Publicar' }}</button><button class="icon" aria-label="Fechar" @click="close"><X :size="19"/></button></div>
      </header>

      <p v-if="errorMessage" class="editor-alert error">{{ errorMessage }}</p><p v-if="successMessage" class="editor-alert success">{{ successMessage }}</p>

      <div class="editor-body">
        <aside class="editor-left" :class="{open:leftOpen}">
          <div class="side-tabs"><button :class="{active:sideTab==='elements'}" @click="sideTab='elements'"><Plus :size="16"/> Elementos</button><button :class="{active:sideTab==='structure'}" @click="sideTab='structure'"><Layers3 :size="16"/> Estrutura</button><button :class="{active:sideTab==='templates'}" @click="sideTab='templates'"><LayoutTemplate :size="16"/> Modelos</button></div>
          <div v-if="sideTab==='elements'" class="element-list"><button v-for="item in ELEMENTS" :key="item[0]" @click="addBlock(item[0])"><Plus :size="15"/><span>{{ item[1] }}</span></button></div>
          <div v-else-if="sideTab==='structure'" class="structure-list">
            <div v-for="(block,index) in content.blocks" :key="block.id" class="structure-item" :class="{selected:selectedId===block.id}" draggable="true" @dragstart="dragStart(block,$event)" @dragover.prevent @drop="dropOn(block,$event)" @click="selectBlock(block)">
              <GripVertical :size="15"/><div><strong>{{ displayType(block.type) }}</strong><small>{{ cardTitle(block) }}</small></div><div class="mini-actions"><button :disabled="index===0" title="Subir" @click.stop="moveBlock(block,-1)"><ArrowUp :size="13"/></button><button :disabled="index===content.blocks.length-1" title="Descer" @click.stop="moveBlock(block,1)"><ArrowDown :size="13"/></button></div>
            </div><div v-if="!content.blocks.length" class="empty-side">Adicione elementos ou escolha um modelo.</div>
          </div>
          <div v-else class="template-list"><button v-for="template in templates" :key="template.key" @click="applyTemplate(template)"><strong>{{ template.name }}</strong><span>{{ template.description }}</span><small>{{ template.segment }}</small></button></div>
        </aside>

        <main class="editor-stage" @click="leftOpen=false;rightOpen=false">
          <div v-if="loading" class="editor-loading">Carregando editor…</div>
          <div v-else class="canvas-frame" :style="{width:canvasWidth}">
            <div class="canvas-page" :style="{'--preview-primary':String(globalStyles.primary||'#3151cf'),'--preview-bg':String(globalStyles.background||'#ffffff'),'--preview-text':String(globalStyles.text||'#1d273a')}" @click.stop>
              <div v-if="!content.blocks.length" class="canvas-empty"><LayoutTemplate :size="46"/><strong>Comece com um modelo profissional</strong><span>Ou adicione elementos pela lateral.</span><button @click="sideTab='templates';leftOpen=true">Escolher modelo</button></div>
              <article v-for="block in content.blocks" v-show="!block.responsive.hidden[device]" :key="block.id" class="canvas-block" :class="[block.type,{selected:selectedId===block.id}]" :style="previewStyle(block)" draggable="true" @dragstart="dragStart(block,$event)" @dragover.prevent @drop="dropOn(block,$event)" @click.stop="selectBlock(block)">
                <div class="block-toolbar" v-if="selectedId===block.id"><span>{{ displayType(block.type) }}</span><button title="Copiar" @click.stop="copyBlock(block)"><Copy :size="13"/></button><button title="Duplicar" @click.stop="duplicateBlock(block)"><Clipboard :size="13"/></button><button title="Excluir" @click.stop="removeBlock(block)"><Trash2 :size="13"/></button></div>
                <template v-if="block.type==='hero'"><small>{{ block.props.eyebrow }}</small><h1>{{ block.props.title }}</h1><p>{{ block.props.text }}</p><button>{{ block.props.cta }}</button></template>
                <template v-else-if="['title','subtitle','text'].includes(block.type)"><h2 v-if="block.type==='title'">{{ block.props.text }}</h2><h3 v-else-if="block.type==='subtitle'">{{ block.props.text }}</h3><p v-else>{{ block.props.text }}</p></template>
                <template v-else-if="block.type==='image'||block.type==='logo'"><div class="image-placeholder">{{ block.props.image?'Imagem configurada':'Adicionar imagem' }}</div></template>
                <template v-else-if="block.type==='gallery'"><h2>{{ block.props.title }}</h2><div class="fake-grid"><i v-for="n in 6" :key="n"></i></div></template>
                <template v-else-if="block.type==='services'"><h2>{{ block.props.title }}</h2><p>{{ block.props.subtitle }}</p><div class="fake-cards"><i v-for="n in 3" :key="n">Serviço {{ n }}</i></div></template>
                <template v-else-if="block.type==='professionals'"><h2>{{ block.props.title }}</h2><div class="fake-cards"><i v-for="n in 3" :key="n">Profissional {{ n }}</i></div></template>
                <template v-else-if="block.type==='booking'"><h2>{{ block.props.title }}</h2><p>{{ block.props.subtitle }}</p><div class="booking-preview"><span>Data</span><span>Horário</span><button>Agendar</button></div></template>
                <template v-else-if="block.type==='button'||block.type==='whatsapp_button'"><button>{{ block.props.label }}</button></template>
                <template v-else-if="block.type==='spacer'"><div :style="{height:`${block.props.height||32}px`}"></div></template>
                <template v-else-if="block.type==='divider'"><hr/></template>
                <template v-else><h2>{{ block.props.title||displayType(block.type) }}</h2><p v-if="block.props.text">{{ block.props.text }}</p><span class="block-hint">{{ displayType(block.type) }}</span></template>
              </article>
            </div>
          </div>
        </main>

        <aside class="editor-right" :class="{open:rightOpen}">
          <div class="inspector-tabs"><button :class="{active:inspectorTab==='content'}" @click="inspectorTab='content'">Conteúdo</button><button :class="{active:inspectorTab==='style'}" @click="inspectorTab='style'">Estilo</button><button :class="{active:inspectorTab==='responsive'}" @click="inspectorTab='responsive'">Responsivo</button><button :class="{active:inspectorTab==='global'}" @click="inspectorTab='global'">Global</button><button :class="{active:inspectorTab==='history'}" @click="inspectorTab='history'">Histórico</button></div>
          <div class="inspector-scroll">
            <template v-if="inspectorTab==='history'">
              <div class="inspector-title"><History :size="18"/><div><strong>Histórico de versões</strong><small>Restaurar cria novo rascunho</small></div></div>
              <div class="history-list"><button v-for="version in state?.versions||[]" :key="version.id" @click="restoreVersion(version)"><div><strong>Versão {{ version.version_number }}</strong><span>{{ version.label||'Rascunho' }}</span><small>{{ version.created_at?new Date(version.created_at).toLocaleString('pt-BR'):'' }}</small></div><em v-if="version.published">Publicada</em><em v-else-if="version.draft">Rascunho atual</em><RotateCcw v-else :size="15"/></button></div>
            </template>
            <template v-else-if="inspectorTab==='global'">
              <div class="inspector-title"><Palette :size="18"/><div><strong>Identidade visual</strong><small>Configurações globais da página</small></div></div>
              <label>Cor principal<input type="color" :value="String(globalStyles.primary||'#3151cf')" @input="updateGlobal('primary',($event.target as HTMLInputElement).value)"/></label><label>Cor secundária<input type="color" :value="String(globalStyles.secondary||'#151c31')" @input="updateGlobal('secondary',($event.target as HTMLInputElement).value)"/></label><label>Cor de destaque<input type="color" :value="String(globalStyles.accent||'#6d72ef')" @input="updateGlobal('accent',($event.target as HTMLInputElement).value)"/></label><label>Cor do texto<input type="color" :value="String(globalStyles.text||'#1d273a')" @input="updateGlobal('text',($event.target as HTMLInputElement).value)"/></label><label>Cor de fundo<input type="color" :value="String(globalStyles.background||'#ffffff')" @input="updateGlobal('background',($event.target as HTMLInputElement).value)"/></label><label>Fonte dos títulos<input :value="String(globalStyles.heading_font||'Inter')" @input="updateGlobal('heading_font',($event.target as HTMLInputElement).value)"/></label><label>Fonte dos textos<input :value="String(globalStyles.body_font||'Inter')" @input="updateGlobal('body_font',($event.target as HTMLInputElement).value)"/></label><label>Arredondamento<input type="number" min="0" max="60" :value="Number(globalStyles.radius||16)" @input="updateGlobal('radius',Number(($event.target as HTMLInputElement).value))"/></label><hr/><strong>Compartilhamento</strong><label>Título social<input :value="String(content.seo.title||'')" @input="updateSeo('title',($event.target as HTMLInputElement).value)"/></label><label>Descrição<textarea :value="String(content.seo.description||'')" @input="updateSeo('description',($event.target as HTMLTextAreaElement).value)"></textarea></label><label>Imagem de compartilhamento<input :value="String(content.seo.share_image||'')" placeholder="https://…" @input="updateSeo('share_image',($event.target as HTMLInputElement).value)"/></label>
            </template>
            <template v-else-if="selectedBlock">
              <div class="inspector-title"><Settings2 :size="18"/><div><strong>{{ displayType(selectedBlock.type) }}</strong><small>{{ selectedBlock.id }}</small></div></div>
              <template v-if="inspectorTab==='content'">
                <label v-if="'eyebrow' in selectedBlock.props">Chamada pequena<input :value="String(selectedBlock.props.eyebrow||'')" @input="updateProp('eyebrow',($event.target as HTMLInputElement).value)"/></label><label v-if="'title' in selectedBlock.props">Título<input :value="String(selectedBlock.props.title||'')" @input="updateProp('title',($event.target as HTMLInputElement).value)"/></label><label v-if="'text' in selectedBlock.props">Texto<textarea :value="String(selectedBlock.props.text||'')" @input="updateProp('text',($event.target as HTMLTextAreaElement).value)"></textarea></label><label v-if="'subtitle' in selectedBlock.props">Subtítulo<textarea :value="String(selectedBlock.props.subtitle||'')" @input="updateProp('subtitle',($event.target as HTMLTextAreaElement).value)"></textarea></label><label v-if="'label' in selectedBlock.props">Rótulo<input :value="String(selectedBlock.props.label||'')" @input="updateProp('label',($event.target as HTMLInputElement).value)"/></label><label v-if="'cta' in selectedBlock.props">Texto do botão<input :value="String(selectedBlock.props.cta||'')" @input="updateProp('cta',($event.target as HTMLInputElement).value)"/></label><label v-if="'button' in selectedBlock.props">Texto do botão<input :value="String(selectedBlock.props.button||'')" @input="updateProp('button',($event.target as HTMLInputElement).value)"/></label><label v-if="'image' in selectedBlock.props">Imagem<input :value="String(selectedBlock.props.image||'')" placeholder="https://…" @input="updateProp('image',($event.target as HTMLInputElement).value)"/></label><label v-if="'url' in selectedBlock.props">Link<input :value="String(selectedBlock.props.url||'')" placeholder="https://…" @input="updateProp('url',($event.target as HTMLInputElement).value)"/></label><label v-if="'phone' in selectedBlock.props">Telefone<input :value="String(selectedBlock.props.phone||'')" @input="updateProp('phone',($event.target as HTMLInputElement).value)"/></label><label v-if="'email' in selectedBlock.props">E-mail<input :value="String(selectedBlock.props.email||'')" @input="updateProp('email',($event.target as HTMLInputElement).value)"/></label><label v-if="'address' in selectedBlock.props">Endereço<textarea :value="String(selectedBlock.props.address||'')" @input="updateProp('address',($event.target as HTMLTextAreaElement).value)"></textarea></label><div class="inspector-actions"><button @click="copyBlock(selectedBlock)"><Copy :size="15"/> Copiar</button><button @click="duplicateBlock(selectedBlock)"><Clipboard :size="15"/> Duplicar</button><button v-if="clipboard" @click="pasteBlock"><Plus :size="15"/> Colar</button><button class="danger" @click="removeBlock(selectedBlock)"><Trash2 :size="15"/> Excluir</button></div>
              </template>
              <template v-else-if="inspectorTab==='style'">
                <label>Fonte<input :value="String(selectedBlock.style.fontFamily||'')" placeholder="Herdar global" @input="updateStyle('fontFamily',($event.target as HTMLInputElement).value)"/></label><label>Tamanho<input type="number" :value="Number(selectedBlock.style.fontSize||0)" @input="updateStyle('fontSize',`${($event.target as HTMLInputElement).value}px`)"/></label><label>Peso<select :value="String(selectedBlock.style.fontWeight||'')" @change="updateStyle('fontWeight',($event.target as HTMLSelectElement).value)"><option value="">Herdar</option><option value="400">Regular</option><option value="500">Médio</option><option value="600">Semibold</option><option value="700">Bold</option><option value="800">Extra bold</option></select></label><label>Alinhamento<select :value="String(selectedBlock.style.textAlign||'')" @change="updateStyle('textAlign',($event.target as HTMLSelectElement).value)"><option value="">Padrão</option><option value="left">Esquerda</option><option value="center">Centro</option><option value="right">Direita</option></select></label><label>Cor do texto<input type="color" :value="String(selectedBlock.style.color||globalStyles.text||'#1d273a')" @input="updateStyle('color',($event.target as HTMLInputElement).value)"/></label><label>Fundo<input type="color" :value="String(selectedBlock.style.backgroundColor||'#ffffff')" @input="updateStyle('backgroundColor',($event.target as HTMLInputElement).value)"/></label><label>Raio<input type="number" min="0" max="80" :value="Number(String(selectedBlock.style.borderRadius||'0').replace('px',''))" @input="updateStyle('borderRadius',`${($event.target as HTMLInputElement).value}px`)"/></label><label>Padding<input :value="String(selectedBlock.style.padding||'')" placeholder="24px" @input="updateStyle('padding',($event.target as HTMLInputElement).value)"/></label><label>Margin<input :value="String(selectedBlock.style.margin||'')" placeholder="0 auto" @input="updateStyle('margin',($event.target as HTMLInputElement).value)"/></label><label>Gap<input :value="String(selectedBlock.style.gap||'')" placeholder="16px" @input="updateStyle('gap',($event.target as HTMLInputElement).value)"/></label><label>Largura máxima<input :value="String(selectedBlock.style.maxWidth||'')" placeholder="1200px" @input="updateStyle('maxWidth',($event.target as HTMLInputElement).value)"/></label><label>Opacidade<input type="range" min="0" max="1" step="0.05" :value="Number(selectedBlock.style.opacity??1)" @input="updateStyle('opacity',Number(($event.target as HTMLInputElement).value))"/></label>
              </template>
              <template v-else-if="inspectorTab==='responsive'">
                <div class="device-caption"><Laptop v-if="device==='desktop'" :size="17"/><Tablet v-else-if="device==='tablet'" :size="17"/><Smartphone v-else :size="17"/><strong>Editando {{ device }}</strong></div><label>Tamanho do título/texto<input type="number" :value="Number(String(selectedBlock.responsive[device].fontSize||'').replace('px',''))" placeholder="Ex.: 30" @input="updateResponsive('fontSize',`${($event.target as HTMLInputElement).value}px`)"/></label><label>Padding<input :value="String(selectedBlock.responsive[device].padding||'')" placeholder="Ex.: 16px" @input="updateResponsive('padding',($event.target as HTMLInputElement).value)"/></label><label>Margem<input :value="String(selectedBlock.responsive[device].margin||'')" placeholder="Ex.: 0" @input="updateResponsive('margin',($event.target as HTMLInputElement).value)"/></label><button class="visibility-toggle" :class="{hidden:selectedBlock.responsive.hidden[device]}" @click="toggleHidden(device)"><Eye :size="16"/> {{ selectedBlock.responsive.hidden[device]?'Oculto neste dispositivo':'Visível neste dispositivo' }}</button>
              </template>
            </template>
            <div v-else class="empty-inspector">Selecione um elemento no canvas.</div>
          </div>
        </aside>
      </div>
    </section>
  </Teleport>
</template>

<style scoped>
.page-editor{position:fixed;inset:0;z-index:2147481000;display:grid;grid-template-rows:auto auto 1fr;background:#eef1f6;color:#182033;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.editor-topbar{min-height:62px;display:grid;grid-template-columns:1fr auto 1fr;align-items:center;gap:12px;padding:8px 12px;border-bottom:1px solid #dce2ea;background:#fff;box-shadow:0 2px 12px rgba(22,35,63,.05)}.top-left,.top-actions,.device-switcher{display:flex;align-items:center;gap:8px}.top-left>div{display:grid}.top-left small{color:#7b8496;font-size:.74rem}.top-actions{justify-content:flex-end}.icon,.soft,.publish,.device-switcher button{min-height:39px;border-radius:10px;border:1px solid #d8dee8;background:#fff;color:#354058;font:inherit;font-weight:750;display:inline-flex;align-items:center;justify-content:center;gap:6px;cursor:pointer}.icon{width:39px;padding:0}.soft{padding:0 12px}.publish{padding:0 15px;background:#3151cf;border-color:#3151cf;color:#fff}.device-switcher{padding:4px;border-radius:12px;background:#f1f3f7}.device-switcher button{width:38px;min-height:34px;border:0;background:transparent}.device-switcher button.active{background:#fff;color:#3151cf;box-shadow:0 2px 8px rgba(20,30,60,.1)}button:disabled{opacity:.5;cursor:progress}.mobile-panel{display:none}.editor-alert{position:fixed;z-index:3;top:72px;left:50%;transform:translateX(-50%);margin:0;padding:10px 14px;border-radius:11px;box-shadow:0 9px 30px rgba(0,0,0,.13)}.editor-alert.error{background:#fff0f0;color:#9b2222}.editor-alert.success{background:#edf9f1;color:#197144}
.editor-body{min-height:0;display:grid;grid-template-columns:260px minmax(0,1fr) 315px}.editor-left,.editor-right{min-width:0;overflow:hidden;background:#fff}.editor-left{border-right:1px solid #dce2ea}.editor-right{border-left:1px solid #dce2ea}.side-tabs{display:grid;grid-template-columns:1fr 1fr 1fr;border-bottom:1px solid #e2e6ed}.side-tabs button,.inspector-tabs button{border:0;background:#fff;padding:11px 4px;font:inherit;font-size:.72rem;font-weight:800;color:#687287;cursor:pointer}.side-tabs button{display:grid;gap:4px;place-items:center}.side-tabs button.active,.inspector-tabs button.active{color:#3151cf;background:#f5f7ff}.element-list,.structure-list,.template-list{height:calc(100vh - 112px);overflow:auto;padding:10px}.element-list{display:grid;grid-template-columns:1fr 1fr;align-content:start;gap:7px}.element-list button{min-height:64px;display:grid;place-items:center;gap:3px;border:1px solid #e0e5ed;border-radius:11px;background:#fff;color:#435067;font:inherit;font-size:.76rem;font-weight:750;cursor:pointer}.element-list button:hover{border-color:#9eade1;background:#f8f9ff}.structure-list{display:grid;align-content:start;gap:6px}.structure-item{display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:center;gap:7px;padding:9px;border:1px solid #e1e5ec;border-radius:10px;cursor:pointer}.structure-item.selected{border-color:#8194df;background:#f5f7ff}.structure-item div:nth-child(2){display:grid;min-width:0}.structure-item small{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#7b8495}.mini-actions{display:flex}.mini-actions button{width:24px;height:24px;border:0;background:transparent;cursor:pointer}.template-list{display:grid;align-content:start;gap:9px}.template-list>button{display:grid;gap:6px;text-align:left;padding:13px;border:1px solid #e0e5ed;border-radius:12px;background:#fff;font:inherit;cursor:pointer}.template-list>button span{font-size:.77rem;color:#6d7688;line-height:1.4}.template-list>button small{width:max-content;padding:4px 7px;border-radius:999px;background:#f0f3f8;color:#58637a}.empty-side,.empty-inspector{padding:28px 12px;color:#778196;text-align:center;line-height:1.45}
.editor-stage{min-width:0;overflow:auto;padding:28px;background-color:#e8ebf1;background-image:linear-gradient(#dce0e8 1px,transparent 1px),linear-gradient(90deg,#dce0e8 1px,transparent 1px);background-size:20px 20px}.canvas-frame{max-width:100%;min-height:calc(100vh - 125px);margin:0 auto;transition:width .2s ease}.canvas-page{min-height:100%;overflow:hidden;border-radius:4px;background:var(--preview-bg);color:var(--preview-text);box-shadow:0 12px 40px rgba(27,36,58,.18);font-family:Inter,system-ui}.canvas-empty{min-height:520px;display:grid;place-items:center;align-content:center;gap:10px;color:#727d91;text-align:center}.canvas-empty strong{color:#29344a;font-size:1.2rem}.canvas-empty button{border:0;border-radius:10px;padding:10px 14px;background:#3151cf;color:#fff;font-weight:800}.canvas-block{position:relative;max-width:100%;box-sizing:border-box;padding:32px;outline:1px solid transparent;transition:outline-color .12s,box-shadow .12s}.canvas-block.selected{outline:2px solid #4770e8;outline-offset:-2px;box-shadow:inset 0 0 0 1px rgba(255,255,255,.8)}.canvas-block.hero{padding:clamp(42px,8vw,90px) 8%;background:linear-gradient(145deg,#111b35,#213763);color:#fff}.canvas-block.hero h1{max-width:820px;font-size:clamp(32px,6vw,64px);line-height:1;margin:8px 0 16px}.canvas-block.hero p{max-width:650px;line-height:1.6}.canvas-block button{border:0;border-radius:10px;padding:10px 15px;background:var(--preview-primary);color:#fff;font-weight:800}.block-toolbar{position:absolute;z-index:2;top:4px;right:4px;display:flex;align-items:center;gap:3px;padding:3px;border-radius:8px;background:#3151cf;color:#fff;box-shadow:0 3px 10px rgba(0,0,0,.2)}.block-toolbar span{padding:0 5px;font-size:.67rem;font-weight:800}.block-toolbar button{width:26px;height:26px;padding:0;background:rgba(255,255,255,.12);display:grid;place-items:center}.image-placeholder{height:220px;display:grid;place-items:center;border:1px dashed #9ba7b9;border-radius:12px;background:#f2f4f7;color:#7a8495}.fake-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.fake-grid i{aspect-ratio:1;border-radius:10px;background:#e9edf3}.fake-cards{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.fake-cards i{padding:24px 12px;border-radius:12px;background:#f3f5f8;font-style:normal}.booking-preview{display:grid;grid-template-columns:1fr 1fr auto;gap:9px}.booking-preview span{padding:12px;border-radius:9px;background:#f1f4f8}.block-hint{display:inline-block;margin-top:8px;padding:4px 7px;border-radius:999px;background:#eef1f6;color:#667087;font-size:.7rem}
.inspector-tabs{display:flex;overflow:auto;border-bottom:1px solid #e2e6ed}.inspector-tabs button{white-space:nowrap;flex:1;min-width:max-content;padding-inline:8px}.inspector-scroll{height:calc(100vh - 112px);overflow:auto;padding:15px}.inspector-title{display:flex;align-items:center;gap:9px;margin-bottom:16px}.inspector-title div{display:grid}.inspector-title small{color:#828b9c;font-size:.7rem;word-break:break-all}.inspector-scroll label{display:grid;gap:6px;margin:12px 0;color:#475269;font-size:.76rem;font-weight:800}.inspector-scroll input,.inspector-scroll select,.inspector-scroll textarea{box-sizing:border-box;width:100%;min-height:40px;padding:8px 10px;border:1px solid #d1d8e2;border-radius:9px;background:#fff;color:#263149;font:inherit;font-size:.82rem}.inspector-scroll textarea{min-height:82px;resize:vertical}.inspector-scroll input[type=color]{padding:3px}.inspector-scroll hr{border:0;border-top:1px solid #e1e5ec;margin:18px 0}.inspector-actions{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:15px}.inspector-actions button,.visibility-toggle{min-height:38px;border:1px solid #d6dce6;border-radius:9px;background:#fff;color:#465269;font:inherit;font-size:.75rem;font-weight:800;display:flex;align-items:center;justify-content:center;gap:5px;cursor:pointer}.inspector-actions .danger{border-color:#efcccc;color:#a22626}.device-caption{display:flex;align-items:center;gap:7px;padding:10px;border-radius:10px;background:#f2f4f8}.visibility-toggle.hidden{background:#fff0f0;border-color:#efcccc;color:#a22626}.history-list{display:grid;gap:7px}.history-list button{display:grid;grid-template-columns:1fr auto;align-items:center;gap:8px;padding:10px;border:1px solid #e0e5ed;border-radius:10px;background:#fff;text-align:left;font:inherit;cursor:pointer}.history-list button div{display:grid;gap:2px}.history-list span,.history-list small{color:#7b8495;font-size:.7rem}.history-list em{font-style:normal;font-size:.68rem;font-weight:800;color:#3151cf}.editor-loading{display:grid;place-items:center;min-height:60vh;color:#697487}
@media(max-width:1050px){.editor-body{grid-template-columns:220px minmax(0,1fr) 290px}.desktop-label{display:none}}
@media(max-width:760px){.editor-topbar{grid-template-columns:1fr auto}.device-switcher{grid-row:2;grid-column:1/-1;justify-self:center}.top-actions .soft:not(.mobile-panel){display:none}.mobile-panel{display:inline-flex}.editor-body{display:block;position:relative}.editor-stage{height:calc(100vh - 110px);padding:12px}.editor-left,.editor-right{position:fixed;z-index:5;top:110px;bottom:0;width:min(88vw,330px);box-shadow:0 12px 45px rgba(0,0,0,.2);transition:transform .2s}.editor-left{left:0;transform:translateX(-105%)}.editor-right{right:0;transform:translateX(105%)}.editor-left.open,.editor-right.open{transform:translateX(0)}.element-list,.structure-list,.template-list,.inspector-scroll{height:calc(100vh - 160px)}.canvas-frame{min-height:calc(100vh - 145px)}.canvas-block{padding:22px 16px}.fake-cards,.fake-grid{grid-template-columns:1fr 1fr}.booking-preview{grid-template-columns:1fr}.editor-alert{top:116px;max-width:calc(100vw - 30px)}.top-left small{display:none}}
</style>
