<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import TenantAgendaOperations from './TenantAgendaOperations.vue'
import TenantBrandAssetUploader from './TenantBrandAssetUploader.vue'
import TenantBrandedLogin from './TenantBrandedLogin.vue'
import TenantConsole from './TenantConsole.vue'
import TenantExtensions from './TenantExtensions.vue'

const authenticated = ref(Boolean(localStorage.getItem('scheduler_pro_access_token')))
let authPoll: number | undefined

function refreshAuthState(): void {
  authenticated.value = Boolean(localStorage.getItem('scheduler_pro_access_token'))
}

onMounted(() => {
  refreshAuthState()
  authPoll = window.setInterval(refreshAuthState, 500)
})

onUnmounted(() => {
  if (authPoll !== undefined) window.clearInterval(authPoll)
})
</script>

<template>
  <TenantBrandedLogin v-if="!authenticated" @authenticated="refreshAuthState" />
  <template v-else>
    <TenantConsole />
    <TenantExtensions />
    <TenantAgendaOperations />
    <TenantBrandAssetUploader />
  </template>
</template>
