<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'

type VersionPayload={data?:{version?:string;release_tag?:string|null;build_sha?:string|null}}

const targetReady=ref(false)
const releaseLabel=ref('versão…')
const buildSha=ref('')

const versionLabel=computed(()=>`${releaseLabel.value}${buildSha.value?` · ${buildSha.value.slice(0,8)}`:''}`)

async function loadVersion():Promise<void>{
  try{
    const response=await fetch('/api/v1/version',{cache:'no-store',headers:{Accept:'application/json'}})
    if(!response.ok)throw new Error('version unavailable')
    const payload=await response.json() as VersionPayload
    const value=payload.data
    releaseLabel.value=value?.release_tag||(value?.version?`v${value.version}`:'versão indisponível')
    buildSha.value=value?.build_sha||''
  }catch{
    releaseLabel.value='versão indisponível'
    buildSha.value=''
  }
}

onMounted(async()=>{
  await nextTick()
  targetReady.value=Boolean(document.querySelector('.tenant-console .sidebar-footer'))
  void loadVersion()
})
</script>

<template>
  <Teleport v-if="targetReady" to=".tenant-console .sidebar-footer">
    <div class="tenant-runtime-version" aria-label="Versão do Scheduler Pro">
      <strong>{{versionLabel}}</strong>
      <small>Tenant Console</small>
    </div>
  </Teleport>
</template>

<style scoped>
:global(.tenant-console .sidebar-footer>.version-info){display:none!important}
.tenant-runtime-version{margin:8px 10px 4px;padding:8px 10px;border-top:1px solid rgba(148,163,184,.16);color:#94a3b8;font-size:10px;line-height:1.35;display:grid;gap:2px}.tenant-runtime-version strong{color:#cbd5e1;font-size:10px}.tenant-runtime-version small{color:#94a3b8;font-size:9px}
</style>
