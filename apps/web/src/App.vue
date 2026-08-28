<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
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
const publicSurface=ref(['/agendar','/pagina'].includes(normalizedPath))
function refreshAuthState():void{authenticated.value=Boolean(localStorage.getItem('scheduler_pro_access_token'))}
function refreshRoute():void{activeView.value=(window.location.hash||'#dashboard').replace(/^#/,'')||'dashboard'}
function onStorage(event:StorageEvent):void{if(event.key==='scheduler_pro_access_token')refreshAuthState()}
onMounted(()=>{refreshAuthState();refreshRoute();window.addEventListener('storage',onStorage);window.addEventListener('hashchange',refreshRoute);window.addEventListener('scheduler-pro-auth-changed',refreshAuthState)})
onUnmounted(()=>{window.removeEventListener('storage',onStorage);window.removeEventListener('hashchange',refreshRoute);window.removeEventListener('scheduler-pro-auth-changed',refreshAuthState)})
</script>

<template>
  <PublicSitePage v-if="publicSurface"/>
  <template v-else>
    <TenantBrandedLogin v-if="!authenticated" @authenticated="refreshAuthState"/>
    <template v-else>
      <TenantConsole/>
      <TenantDashboardInsights v-if="activeView==='dashboard'"/>
      <TenantAgendaCenter v-if="activeView==='agenda'"/>
      <TenantExtensions v-if="activeView==='personalizacao'||activeView==='smtp'"/>
      <TenantConfigurationCenter v-if="activeView==='configuracoes'"/>
      <TenantVisualPageBuilder v-if="activeView==='visual-builder'"/>
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
