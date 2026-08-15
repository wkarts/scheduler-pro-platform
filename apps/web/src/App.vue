<script setup lang="ts">
import { ref } from 'vue'
import { apiGet } from './api/client'

const tenant = ref<any>(null)
const loading = ref(false)

async function loadTenant() {
  loading.value = true
  try {
    tenant.value = await apiGet('/settings/tenant')
  } finally {
    loading.value = false
  }
}

loadTenant()
</script>

<template>
  <main class="min-h-screen bg-slate-950 text-white">
    <section class="mx-auto grid max-w-7xl gap-8 px-6 py-10 lg:grid-cols-[280px_1fr]">
      <aside class="rounded-3xl border border-white/10 bg-white/5 p-6 shadow-2xl">
        <div class="text-2xl font-black tracking-tight">Scheduler Pro</div>
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
        <div class="rounded-3xl border border-white/10 bg-gradient-to-br from-cyan-500/20 to-fuchsia-500/20 p-8 shadow-2xl">
          <p class="text-sm uppercase tracking-[0.3em] text-cyan-200">Tenant Plane</p>
          <h1 class="mt-3 text-4xl font-black">Agenda, clientes, landing page e WhatsApp em um SaaS multitenant.</h1>
          <p class="mt-4 max-w-3xl text-slate-200">Instalável pelo navegador como PWA e conectado à API FastAPI. O tenant é resolvido pelo hostname.</p>
        </div>
        <div class="grid gap-4 md:grid-cols-3">
          <div class="rounded-2xl border border-white/10 bg-white/5 p-5"><b>Hoje</b><p class="text-3xl font-black">0</p><span class="text-slate-400">agendamentos</span></div>
          <div class="rounded-2xl border border-white/10 bg-white/5 p-5"><b>WhatsApp</b><p class="text-3xl font-black">API</p><span class="text-slate-400">provider abstrato</span></div>
          <div class="rounded-2xl border border-white/10 bg-white/5 p-5"><b>Landing</b><p class="text-3xl font-black">PWA</p><span class="text-slate-400">editor por blocos</span></div>
        </div>
        <pre class="overflow-auto rounded-2xl border border-white/10 bg-black/40 p-4 text-xs">{{ loading ? 'Carregando tenant...' : tenant }}</pre>
      </section>
    </section>
  </main>
</template>
