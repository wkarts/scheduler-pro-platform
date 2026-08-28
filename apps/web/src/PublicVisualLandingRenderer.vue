<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import type { PageDocument, ArgwsPageRenderer } from '@argws/visual-builder'
import '@argws/visual-builder'

type Service={id:string;name:string;duration_minutes:number;price?:number|null}
type Professional={id:string;name:string}
const props=defineProps<{content:PageDocument|Record<string,unknown>;services?:Service[];professionals?:Professional[]}>()
const host=ref<HTMLDivElement|null>(null)
const bookingTarget=ref<Element|null>(null)
let renderer:ArgwsPageRenderer|null=null

function escapeHtml(value:unknown):string{return String(value??'').replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]||char))}
function money(value?:number|null):string{return value==null?'':new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL'}).format(Number(value))}
function servicesHtml():string{
  if(!props.services?.length)return '<div class="upb-empty">Nenhum serviço cadastrado.</div>'
  return `<div class="upb-cards">${props.services.map(service=>`<article class="upb-card"><strong>${escapeHtml(service.name)}</strong><p>${Number(service.duration_minutes)||0} min${service.price!=null?` · ${escapeHtml(money(service.price))}`:''}</p></article>`).join('')}</div>`
}
function professionalsHtml():string{
  if(!props.professionals?.length)return '<div class="upb-empty">Nenhum profissional cadastrado.</div>'
  return `<div class="upb-cards">${props.professionals.map(item=>`<article class="upb-card"><strong>${escapeHtml(item.name)}</strong></article>`).join('')}</div>`
}
async function render():Promise<void>{
  if(!renderer)return
  renderer.context={servicesHtml:servicesHtml(),professionalsHtml:professionalsHtml(),ensureBooking:true}
  renderer.document=props.content as PageDocument
  await nextTick()
}
function onRendered():void{
  const target=renderer?.shadowRoot?.querySelector('[data-upb-dynamic="booking"]')||null
  if(target){target.textContent='';bookingTarget.value=target}else bookingTarget.value=null
}
onMounted(()=>{
  if(!host.value)return
  renderer=document.createElement('argws-page-renderer') as ArgwsPageRenderer
  renderer.addEventListener('upb-rendered',onRendered)
  host.value.appendChild(renderer)
  void render()
})
onUnmounted(()=>{renderer?.removeEventListener('upb-rendered',onRendered);renderer?.remove();renderer=null;bookingTarget.value=null})
watch(()=>[props.content,props.services,props.professionals],()=>void render(),{deep:true})
</script>

<template>
  <div ref="host" class="sp-visual-public-renderer" />
  <Teleport v-if="bookingTarget" :to="bookingTarget"><slot name="booking" /></Teleport>
</template>

<style scoped>
.sp-visual-public-renderer{min-height:100dvh}
.sp-visual-public-renderer :deep(argws-page-renderer){display:block}
</style>
