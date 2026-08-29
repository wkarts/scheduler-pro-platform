<script setup lang="ts">
import { nextTick, onUnmounted, ref } from 'vue'
import { RestAdapter, type ArgwsVisualBuilder } from '@argws/visual-builder'
import '@argws/visual-builder'

const open=ref(false)
const mount=ref<HTMLDivElement|null>(null)
let builder:ArgwsVisualBuilder|null=null

async function show():Promise<void>{
  open.value=true
  await nextTick()
  if(!mount.value)return
  builder=document.createElement('argws-visual-builder') as ArgwsVisualBuilder
  builder.adapter=new RestAdapter({baseUrl:'/api/pages',slug:'home'})
  builder.addEventListener('upb-close',hide)
  mount.value.appendChild(builder)
  await builder.load()
}
function hide():void{builder?.remove();builder=null;open.value=false}
onUnmounted(hide)
</script>

<template>
  <button @click="show">Editar página</button>
  <Teleport v-if="open" to="body"><div ref="mount" /></Teleport>
</template>
