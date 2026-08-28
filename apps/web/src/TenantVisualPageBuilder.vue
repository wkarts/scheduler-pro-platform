<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref } from 'vue'
import { LayoutTemplate } from 'lucide-vue-next'
import { ARGWS_VISUAL_BUILDER_VERSION, createSchedulerProAdapter } from '@argws/visual-builder'

type VisualEditorElement=HTMLElement&{adapter:Record<string,any>;load:()=>Promise<void>}

const active=ref(false)
const portalReady=ref(false)
const mountPoint=ref<HTMLDivElement|null>(null)
const loading=ref(false)
const error=ref('')
let editor:VisualEditorElement|null=null
let generation=0

async function open():Promise<void>{
  window.dispatchEvent(new CustomEvent('scheduler-pro-workspace-open',{detail:'landing-page'}))
  active.value=true;loading.value=true;error.value=''
  const current=++generation
  await nextTick()
  try{
    await mountEditor()
  }catch(exc){if(current===generation)error.value=exc instanceof Error?exc.message:'Não foi possível abrir o editor.'}
  finally{if(current===generation)loading.value=false}
}

async function mountEditor():Promise<void>{
  if(!mountPoint.value||editor)return
  const loaded=await createSchedulerProAdapter({baseUrl:'/api/v1',slug:'home'})
  const element=document.createElement('argws-visual-builder') as VisualEditorElement
  element.classList.add('sp-visual-builder-shell')
  element.adapter=loaded.adapter
  element.addEventListener('upb-close',close)
  mountPoint.value.appendChild(element)
  editor=element
  await editor.load()
}

function close():void{
  generation+=1
  editor?.removeEventListener('upb-close',close)
  editor?.remove();editor=null
  error.value='';loading.value=false;active.value=false
  window.dispatchEvent(new CustomEvent('scheduler-pro-workspace-close',{detail:'landing-page'}))
}
function workspaceOpened(event:Event):void{const detail=(event as CustomEvent<string>).detail;if(active.value&&detail&&detail!=='landing-page')close()}

onMounted(async()=>{await nextTick();portalReady.value=Boolean(document.querySelector('.tenant-console .nav-list'));window.addEventListener('scheduler-pro-workspace-open',workspaceOpened)})
onUnmounted(()=>{window.removeEventListener('scheduler-pro-workspace-open',workspaceOpened);close()})
</script>

<template>
  <Teleport v-if="portalReady" to=".tenant-console .nav-list">
    <button class="nav-item sp-page-editor-nav sp-visual-builder-nav" @click="open"><LayoutTemplate :size="19"/><span>Landing Page</span></button>
  </Teleport>
  <Teleport v-if="active" to="body">
    <div ref="mountPoint" class="sp-visual-builder-mount">
      <aside class="builder-release-badge"><span>ARGWS Visual Builder Editor</span><strong>{{ARGWS_VISUAL_BUILDER_VERSION}}</strong></aside>
      <section v-if="loading" class="builder-state"><strong>Abrindo ARGWS Visual Builder 2.1.0…</strong><span>Carregando o editor visual responsivo canônico.</span></section>
      <section v-else-if="error" class="builder-state error"><strong>Não foi possível abrir o editor.</strong><span>{{error}}</span><button @click="close">Fechar</button></section>
    </div>
  </Teleport>
</template>

<style scoped>
.sp-visual-builder-mount{position:fixed;inset:0;z-index:10000;background:#0b0f17}.builder-release-badge{position:fixed;z-index:10020;left:max(10px,env(safe-area-inset-left));bottom:max(10px,env(safe-area-inset-bottom));display:flex;align-items:center;gap:8px;padding:8px 10px;border:1px solid #34425f;border-radius:11px;background:rgba(15,25,46,.94);box-shadow:0 12px 34px rgba(0,0,0,.25);color:#fff;backdrop-filter:blur(14px);pointer-events:none}.builder-release-badge span{font-size:8px;font-weight:900;letter-spacing:.06em;text-transform:uppercase;color:#9fb1ff}.builder-release-badge strong{font-size:10px}.builder-state{height:100dvh;display:grid;place-items:center;align-content:center;gap:8px;padding:24px;background:#0b0f17;color:#fff;text-align:center}.builder-state span{color:#9eabc0}.builder-state button{min-height:42px;border:0;border-radius:10px;padding:0 16px}.builder-state.error strong{color:#ff9da6}@media(max-width:700px){.builder-release-badge{left:8px;bottom:max(8px,env(safe-area-inset-bottom));padding:7px 9px}}
</style>
