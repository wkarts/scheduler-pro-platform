<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { loadVisualBuilderRuntime, type PageDocument } from '@argws/visual-builder'

type Service={id:string;name:string;duration_minutes:number;price?:number|null}
type Professional={id:string;name:string}
type RendererElement=HTMLElement&{document:PageDocument;context:Record<string,unknown>;shadowRoot:ShadowRoot|null}
const props=defineProps<{content:PageDocument|Record<string,unknown>;services?:Service[];professionals?:Professional[]}>()
const host=ref<HTMLDivElement|null>(null)
const bookingTarget=ref<Element|null>(null)
const error=ref('')
let renderer:RendererElement|null=null
let renderRaf=0
let generation=0

function escapeHtml(value:unknown):string{return String(value??'').replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]||char))}
function money(value?:number|null):string{return value==null?'':new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL'}).format(Number(value))}
function servicesHtml():string{if(!props.services?.length)return '<div class="upb-empty">Nenhum serviço cadastrado.</div>';return `<div class="upb-cards">${props.services.map(service=>`<article class="upb-card"><strong>${escapeHtml(service.name)}</strong><p>${Number(service.duration_minutes)||0} min${service.price!=null?` · ${escapeHtml(money(service.price))}`:''}</p></article>`).join('')}</div>`}
function professionalsHtml():string{if(!props.professionals?.length)return '<div class="upb-empty">Nenhum profissional cadastrado.</div>';return `<div class="upb-cards">${props.professionals.map(item=>`<article class="upb-card"><strong>${escapeHtml(item.name)}</strong></article>`).join('')}</div>`}

async function ensureRenderer():Promise<void>{
  if(renderer||!host.value)return
  const current=++generation
  try{
    await loadVisualBuilderRuntime()
    if(current!==generation||renderer||!host.value)return
    const element=document.createElement('argws-page-renderer') as RendererElement
    element.addEventListener('upb-rendered',onRendered)
    host.value.appendChild(element)
    renderer=element
  }catch(exc){error.value=exc instanceof Error?exc.message:'Não foi possível carregar o renderizador da página.'}
}
async function render():Promise<void>{
  await ensureRenderer()
  if(!renderer)return
  renderer.context={servicesHtml:servicesHtml(),professionalsHtml:professionalsHtml(),ensureBooking:true}
  renderer.document=props.content as PageDocument
  await nextTick()
}
function scheduleRender():void{cancelAnimationFrame(renderRaf);renderRaf=requestAnimationFrame(()=>void render())}
function onRendered():void{const target=renderer?.shadowRoot?.querySelector('[data-upb-dynamic="booking"]')||null;if(target){target.textContent='';bookingTarget.value=target}else bookingTarget.value=null}
onMounted(scheduleRender)
onUnmounted(()=>{generation+=1;cancelAnimationFrame(renderRaf);renderer?.removeEventListener('upb-rendered',onRendered);renderer?.remove();renderer=null;bookingTarget.value=null})
watch(()=>props.content,scheduleRender,{deep:false})
watch(()=>props.services,scheduleRender,{deep:false})
watch(()=>props.professionals,scheduleRender,{deep:false})
</script>

<template><div ref="host" class="sp-visual-public-renderer"/><p v-if="error" class="sp-render-error">{{error}}</p><Teleport v-if="bookingTarget" :to="bookingTarget"><slot name="booking"/></Teleport></template>
<style scoped>.sp-visual-public-renderer{min-height:100dvh}.sp-visual-public-renderer :deep(argws-page-renderer){display:block}.sp-render-error{margin:24px auto;max-width:760px;padding:14px;border-radius:12px;background:#fff1f2;color:#be123c;text-align:center}</style>
