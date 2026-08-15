<script setup lang="ts">
import { computed, ref } from 'vue'
import { applyBranding, loadBrandingManifest, type BrandingManifest } from './branding'

const branding = ref<BrandingManifest | null>(null)
const appName = computed(() => branding.value?.app.public_name || branding.value?.app.name || 'Scheduler Pro Mobile')
const slogan = computed(() => branding.value?.app.slogan || 'Agenda, confirmações, clientes, serviços, dashboard e WhatsApp no celular.')

async function boot() {
  branding.value = await loadBrandingManifest()
  applyBranding(branding.value)
}

boot()
</script>

<template>
  <main class="min-h-screen p-5 text-white" :style="{ background: 'var(--sp-background)', color: 'var(--sp-text)', fontFamily: 'var(--sp-font)' }">
    <section class="border border-white/10 bg-white/5 p-6 shadow-2xl" :style="{ borderRadius: 'var(--sp-radius)' }">
      <p class="text-xs uppercase tracking-[0.3em]" :style="{ color: 'var(--sp-secondary)' }">Tauri Mobile</p>
      <h1 class="mt-3 text-3xl font-black">{{ appName }}</h1>
      <p class="mt-4 text-slate-300">{{ slogan }}</p>
      <div class="mt-6 space-y-3">
        <button class="w-full px-4 py-3 font-bold text-slate-950" :style="{ borderRadius: 'var(--sp-radius)', background: 'var(--sp-accent)' }">Ver agenda</button>
        <button class="w-full bg-white/10 px-4 py-3 font-bold" :style="{ borderRadius: 'var(--sp-radius)' }">Clientes</button>
        <button class="w-full bg-white/10 px-4 py-3 font-bold" :style="{ borderRadius: 'var(--sp-radius)' }">Notificações</button>
      </div>
    </section>
  </main>
</template>
