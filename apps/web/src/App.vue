<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import PublicSitePage from './PublicSitePage.vue'
import TenantAgendaCenter from './TenantAgendaCenter.vue'
import TenantAgendaOperator from './TenantAgendaOperator.vue'
import TenantBookingAndMessages from './TenantBookingAndMessages.vue'
import TenantBrandAssetUploader from './TenantBrandAssetUploader.vue'
import TenantBrandedLogin from './TenantBrandedLogin.vue'
import TenantConfigurationCenter from './TenantConfigurationCenter.vue'
import TenantConsole from './TenantConsole.vue'
import TenantDashboardInsights from './TenantDashboardInsights.vue'
import TenantExtensions from './TenantExtensions.vue'
import TenantMailModeSelector from './TenantMailModeSelector.vue'
import TenantPwaInstallSurface from './TenantPwaInstallSurface.vue'
import TenantSecondFactorGate from './TenantSecondFactorGate.vue'
import TenantUniversalDownloads from './TenantUniversalDownloads.vue'
import TenantVisualPageBuilder from './TenantVisualPageBuilder.vue'
import './tenantContrast.css'

const authenticated=ref(Boolean(localStorage.getItem('scheduler_pro_access_token')))
const activeView=ref((window.location.hash||'#dashboard').replace(/^#/,'')||'dashboard')
const normalizedPath=window.location.pathname.replace(/\/+$/,'')||'/'
const sourcePwa=new URLSearchParams(window.location.search).get('source')==='pwa'
const publicLogin=computed(()=>normalizedPath==='/login'&&!authenticated.value)
const pwaOpenMode=ref('AUTO')
// HOTFIX_TENANT_ROOT_ADMIN: a raiz do domínio pertence sempre ao console/login do tenant.
// Landing e Agenda Pública só existem nas rotas públicas explícitas /pagina e /agendar.
const publicSurface=computed(()=>['/agendar','/pagina'].includes(normalizedPath))
const forcePwaLogin=computed(()=>sourcePwa&&pwaOpenMode.value==='LOGIN'&&!authenticated.value)
function refreshAuthState():void{authenticated.value=Boolean(localStorage.getItem('scheduler_pro_access_token'))}
function refreshRoute():void{activeView.value=(window.location.hash||'#dashboard').replace(/^#/,'')||'dashboard'}
function onStorage(event:StorageEvent):void{if(event.key==='scheduler_pro_access_token')refreshAuthState()}
onMounted(()=>{refreshAuthState();refreshRoute();window.addEventListener('storage',onStorage);window.addEventListener('hashchange',refreshRoute);window.addEventListener('scheduler-pro-auth-changed',refreshAuthState);if(sourcePwa)void fetch('/api/v1/public/context',{cache:'no-store',headers:{Accept:'application/json'}}).then(r=>r.json()).then(body=>{pwaOpenMode.value=String(body?.data?.preferences?.pwa_open_mode||'AUTO').toUpperCase()}).catch(()=>undefined)})
onUnmounted(()=>{window.removeEventListener('storage',onStorage);window.removeEventListener('hashchange',refreshRoute);window.removeEventListener('scheduler-pro-auth-changed',refreshAuthState)})
</script>

<template>
  <TenantBrandedLogin v-if="publicLogin||forcePwaLogin" @authenticated="refreshAuthState"/>
  <PublicSitePage v-else-if="publicSurface"/>
  <template v-else>
    <TenantBrandedLogin v-if="!authenticated" @authenticated="refreshAuthState"/>
    <template v-else>
      <TenantConsole/>
      <TenantDashboardInsights v-if="activeView==='dashboard'"/>
      <TenantAgendaCenter v-if="activeView==='agenda'"/>
      <TenantExtensions v-if="activeView==='personalizacao'||activeView==='smtp'"/>
      <TenantConfigurationCenter v-if="activeView==='configuracoes'"/>
      <!-- PR63_FINAL_RUNTIME_FIX: permanece montado; o componente sincroniza o hash internamente. -->
      <TenantVisualPageBuilder/>
      <TenantBookingAndMessages v-if="activeView==='agenda-publica'||activeView==='mensagens'"/>
      <TenantMailModeSelector v-if="activeView==='smtp'"/>
      <TenantBrandAssetUploader v-if="activeView==='personalizacao'"/>
      <TenantUniversalDownloads v-if="activeView==='builds'"/>
      <!-- Overlays globais: não são páginas de navegação e permanecem disponíveis em qualquer rota. -->
      <TenantAgendaOperator/>
      <TenantSecondFactorGate/>
    </template>
    <TenantPwaInstallSurface/>
  </template>
</template>
