<script setup lang="ts">
import { computed, ref } from 'vue'
import { apiGet } from './api/client'
import { applyBranding, loadBrandingManifest, type BrandingManifest } from './branding'

const tenant = ref<any>(null)
const branding = ref<BrandingManifest | null>(null)
const loading = ref(false)

const appName = computed(() => branding.value?.app.public_name || branding.value?.app.name || 'Scheduler Pro')
const slogan = computed(() => branding.value?.app.slogan || 'Agenda, clientes, landing page e WhatsApp em um SaaS multitenant.')
const logoUrl = computed(() => branding.value?.assets.logo_url)

async function loadTenant() {
  loading.value = true
  try {
    branding.value = await loadBrandingManifest()
    applyBranding(branding.value)
    tenant.value = await apiGet('/settings/tenant')
  } finally {
    loading.value = false
  }
}

loadTenant()
</script>

<template>
  <main class="min-h-screen text-white" :style="{ background: 'var(--sp-background)', color: 'var(--sp-text)', fontFamily: 'var(--sp-font)' }">
    <section class="mx-auto grid max-w-7xl gap-8 px-6 py-10 lg:grid-cols-[280px_1fr]">
      <aside class="border border-white/10 bg-white/5 p-6 shadow-2xl" :style="{ borderRadius: 'var(--sp-radius)' }">
        <img v-if="logoUrl" :src="logoUrl" :alt="appName" class="mb-4 h-12 max-w-48 object-contain" />
        <div class="text-2xl font-black tracking-tight">{{ appName }}</div>
        <p class="mt-2 text-sm text-slate-300">Webapp tenant instalável</p>
        <nav class="mt-8 space-y-2 text-sm">
          <a class="block rounded-xl bg-white/10 px-4 py-3" href="#agenda">Agenda</a>
          <a class="block rounded-xl px-4 py-3 hover:bg-white/10" href="#clientes">Clientes</a>
          <a class="block rounded-xl px-4 py-3 hover:bg-white/10" href="#servicos">Serviços</a>
          <a class="block rounded-xl px-4 py-3 hover:bg-white/10" href="#landing">Landing Page</a>
          <a class="block rounded-xl px-4 py-3 hover:bg-white/10" href="#whatsapp">WhatsApp API</a>
        </nav>
      </aside>
      <section class="space-y-6">
        <div class="border border-white/10 p-8 shadow-2xl" :style="{ borderRadius: 'var(--sp-radius)', background: `linear-gradient(135deg, ${branding?.theme.colors.primary || '#0f172a'}55, ${branding?.theme.colors.accent || '#38bdf8'}44)` }">
          <p class="text-sm uppercase tracking-[0.3em]" :style="{ color: 'var(--sp-secondary)' }">Tenant Plane</p>
          <h1 class="mt-3 text-4xl font-black">{{ slogan }}</h1>
          <p class="mt-4 max-w-3xl text-slate-200">Instalável pelo navegador como PWA, conectado à API FastAPI e personalizado por hostname, sem aceitar tenant_id arbitrário do frontend.</p>
        </div>
        <div class="grid gap-4 md:grid-cols-3">
          <div class="border border-white/10 bg-white/5 p-5" :style="{ borderRadius: 'var(--sp-radius)' }"><b>Hoje</b><p class="text-3xl font-black">0</p><span class="text-slate-400">agendamentos</span></div>
          <div class="border border-white/10 bg-white/5 p-5" :style="{ borderRadius: 'var(--sp-radius)' }"><b>WhatsApp</b><p class="text-3xl font-black">API</p><span class="text-slate-400">provider abstrato</span></div>
          <div class="border border-white/10 bg-white/5 p-5" :style="{ borderRadius: 'var(--sp-radius)' }"><b>Landing</b><p class="text-3xl font-black">PWA</p><span class="text-slate-400">editor por blocos</span></div>
        </div>
        <pre class="overflow-auto border border-white/10 bg-black/40 p-4 text-xs" :style="{ borderRadius: 'var(--sp-radius)' }">{{ loading ? 'Carregando tenant...' : { tenant, branding } }}</pre>
      </section>
    </section>
  </main>
</template>
