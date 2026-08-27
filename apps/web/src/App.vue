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
import TenantPublicPageEditorV2 from './TenantPublicPageEditorV2.vue'
import TenantPwaInstallSurface from './TenantPwaInstallSurface.vue'
import TenantSecondFactorGate from './TenantSecondFactorGate.vue'
import TenantUniversalDownloads from './TenantUniversalDownloads.vue'
import TenantVisualPageBuilder from './TenantVisualPageBuilder.vue'
import TenantWorkspaceCoordinator from './TenantWorkspaceCoordinator.vue'
import './tenantContrast.css'
import './tenantEditorMobileHotfix.css'

const authenticated=ref(Boolean(localStorage.getItem('scheduler_pro_access_token')))
const normalizedPath=window.location.pathname.replace(/\/+$/,'')||'/'
const publicSurface=ref(['/agendar','/pagina'].includes(normalizedPath))
const visualBuilderEnabled=import.meta.env.VITE_VISUAL_PAGE_BUILDER!=='false'
function refreshAuthState():void{authenticated.value=Boolean(localStorage.getItem('scheduler_pro_access_token'))}
function onStorage(event:StorageEvent):void{if(event.key==='scheduler_pro_access_token')refreshAuthState()}
onMounted(()=>{refreshAuthState();window.addEventListener('storage',onStorage);window.addEventListener('scheduler-pro-auth-changed',refreshAuthState)})
onUnmounted(()=>{window.removeEventListener('storage',onStorage);window.removeEventListener('scheduler-pro-auth-changed',refreshAuthState)})
</script>

<template>
  <PublicSitePage v-if="publicSurface"/>
  <template v-else>
    <TenantBrandedLogin v-if="!authenticated" @authenticated="refreshAuthState"/>
    <template v-else>
      <TenantConsole/>
      <TenantWorkspaceCoordinator/>
      <TenantDashboardInsights/>
      <TenantAgendaCenter/>
      <TenantAgendaOperator/>
      <TenantExtensions/>
      <TenantConfigurationCenter/>
      <TenantVisualPageBuilder v-if="visualBuilderEnabled"/>
      <TenantPublicPageEditorV2 v-else/>
      <TenantBookingAndMessages/>
      <TenantMailModeSelector/>
      <TenantBrandAssetUploader/>
      <TenantUniversalDownloads/>
      <TenantSecondFactorGate/>
    </template>
    <TenantPwaInstallSurface/>
  </template>
</template>
