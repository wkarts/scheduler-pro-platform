<script setup lang="ts">
import { canAccess } from './tenantAccess'
import { computed, onMounted, onUnmounted, ref } from 'vue'
import PublicSitePage from './PublicSitePage.vue'
import TenantAgendaCenter from './TenantAgendaCenter.vue'
import TenantAgendaOperator from './TenantAgendaOperator.vue'
import TenantBookingAndMessages from './TenantBookingAndMessages.vue'
import TenantBrandAssetUploader from './TenantBrandAssetUploader.vue'
import TenantBrandedLogin from './TenantBrandedLogin.vue'
import TenantCheckInCenter from './TenantCheckInCenter.vue'
import TenantConfirmationAssistant from './TenantConfirmationAssistant.vue'
import TenantConfigurationCenter from './TenantConfigurationCenter.vue'
import TenantConsole from './TenantConsole.vue'
import TenantDashboardInsights from './TenantDashboardInsights.vue'
import TenantExtensions from './TenantExtensions.vue'
import TenantMailModeSelector from './TenantMailModeSelector.vue'
import TenantPwaInstallSurface from './TenantPwaInstallSurface.vue'
import TenantRuntimeVersion from './TenantRuntimeVersion.vue'
import TenantSecondFactorGate from './TenantSecondFactorGate.vue'
import TenantUniversalDownloads from './TenantUniversalDownloads.vue'
import TenantVisualPageBuilder from './TenantVisualPageBuilder.vue'
import { installTenantStaticVersionGuard } from './tenantStaticVersionGuard'
import './tenantContrast.css'
import './tenant-shell-desktop-branding-fix.css'
import './tenant-global-operators.css'
import './tenant-checkin-mobile-operator.css'
import './tenant-version-dedup.css'

const authenticated=ref(Boolean(localStorage.getItem('scheduler_pro_access_token')))
const activeView=ref((window.location.hash||'#dashboard').replace(/^#/,'')||'dashboard')
const normalizedPath=window.location.pathname.replace(/\/+$/,'')||'/'
const sourcePwa=new URLSearchParams(window.location.search).get('source')==='pwa'
const publicLogin=computed(()=>normalizedPath==='/login'&&!authenticated.value)
const pwaOpenMode=ref('AUTO')
const publicSurface=computed(()=>['/agendar','/pagina'].includes(normalizedPath))
const forcePwaLogin=computed(()=>sourcePwa&&pwaOpenMode.value==='LOGIN'&&!authenticated.value)
let stopStaticVersionGuard:(()=>void)|undefined

function refreshAuthState():void{authenticated.value=Boolean(localStorage.getItem('scheduler_pro_access_token'))}
function refreshRoute():void{activeView.value=(window.location.hash||'#dashboard').replace(/^#/,'')||'dashboard'}
function onStorage(event:StorageEvent):void{if(event.key==='scheduler_pro_access_token')refreshAuthState()}
function isPublicPagesButton(target:EventTarget|null):boolean{if(!(target instanceof Element))return false;const button=target.closest('button.nav-item');return Boolean(button&&button.textContent?.replace(/\s+/g,' ').trim().includes('Páginas públicas'))}
function onPublicPagesNavCapture(event:Event):void{if(window.location.hash!=='#visual-builder'||!isPublicPagesButton(event.target))return;if(document.querySelector('.experience-center'))return;queueMicrotask(()=>window.dispatchEvent(new HashChangeEvent('hashchange')))}
onMounted(()=>{stopStaticVersionGuard=installTenantStaticVersionGuard();refreshAuthState();refreshRoute();window.addEventListener('storage',onStorage);window.addEventListener('hashchange',refreshRoute);window.addEventListener('scheduler-pro-auth-changed',refreshAuthState);document.addEventListener('click',onPublicPagesNavCapture,true);if(sourcePwa)void fetch('/api/v1/public/context',{cache:'no-store',headers:{Accept:'application/json'}}).then(r=>r.json()).then(body=>{pwaOpenMode.value=String(body?.data?.preferences?.pwa_open_mode||'AUTO').toUpperCase()}).catch(()=>undefined)})
onUnmounted(()=>{stopStaticVersionGuard?.();window.removeEventListener('storage',onStorage);window.removeEventListener('hashchange',refreshRoute);window.removeEventListener('scheduler-pro-auth-changed',refreshAuthState);document.removeEventListener('click',onPublicPagesNavCapture,true)})
</script>

<template>
  <TenantBrandedLogin v-if="publicLogin||forcePwaLogin" @authenticated="refreshAuthState"/>
  <PublicSitePage v-else-if="publicSurface"/>
  <template v-else>
    <TenantBrandedLogin v-if="!authenticated" @authenticated="refreshAuthState"/>
    <template v-else>
      <TenantConsole/>
      <TenantRuntimeVersion/>
      <TenantDashboardInsights v-if="canAccess('appointments.create') && (activeView==='dashboard')"/>
      <TenantAgendaCenter v-if="canAccess('appointments.create') && (activeView==='agenda')"/>
      <TenantExtensions v-if="canAccess('tenant.manage') && (activeView==='personalizacao'||activeView==='smtp')"/>
      <TenantConfigurationCenter v-if="canAccess('tenant.manage') && (activeView==='configuracoes')"/>
      <TenantVisualPageBuilder v-if="canAccess('tenant.manage')"/>
      <TenantBookingAndMessages v-if="canAccess('tenant.manage') && (activeView==='agenda-publica'||activeView==='mensagens')"/>
      <TenantMailModeSelector v-if="canAccess('tenant.manage') && (activeView==='smtp')"/>
      <TenantBrandAssetUploader v-if="canAccess('tenant.manage') && (activeView==='personalizacao')"/>
      <TenantUniversalDownloads v-if="canAccess('tenant.manage') && (activeView==='builds')"/>
      <!-- Operadores globais permanecem disponíveis em qualquer view autenticada. -->
      <TenantCheckInCenter v-if="canAccess('appointments.create')"/>
      <TenantConfirmationAssistant v-if="canAccess('appointments.create')"/>
      <TenantAgendaOperator v-if="canAccess('appointments.create')"/>
      <TenantSecondFactorGate/>
    </template>
    <TenantPwaInstallSurface/>
  </template>
</template>
