<script setup lang="ts">
import { computed, ref } from 'vue'
import { applyBranding, loadBrandingManifest, type BrandingManifest } from './branding'

const branding = ref<BrandingManifest | null>(null)
const appName = computed(() => branding.value?.app.public_name || branding.value?.app.name || 'Scheduler Pro Desktop')
const slogan = computed(() => branding.value?.app.slogan || 'Aplicativo gerencial para agenda, clientes, serviços, profissionais, WhatsApp, notificações e dashboard.')

async function boot() {
  branding.value = await loadBrandingManifest()
  applyBranding(branding.value)
}

boot()
</script>

<template>
  <main class="min-h-screen p-8 text-white" :style="{ background: 'var(--sp-background)', color: 'var(--sp-text)', fontFamily: 'var(--sp-font)' }">
    <section class="mx-auto max-w-6xl border border-white/10 bg-white/5 p-8 shadow-2xl" :style="{ borderRadius: 'var(--sp-radius)' }">
      <p class="text-sm uppercase tracking-[0.3em]" :style="{ color: 'var(--sp-secondary)' }">Tauri Desktop</p>
      <h1 class="mt-3 text-4xl font-black">{{ appName }}</h1>
      <p class="mt-4 text-slate-300">{{ slogan }}</p>
      <div class="mt-8 grid gap-4 md:grid-cols-3">
        <div class="rounded-2xl bg-black/30 p-5">Agenda</div>
        <div class="rounded-2xl bg-black/30 p-5">Clientes</div>
        <div class="rounded-2xl bg-black/30 p-5">WhatsApp API</div>
      </div>
    </section>
  </main>
</template>
