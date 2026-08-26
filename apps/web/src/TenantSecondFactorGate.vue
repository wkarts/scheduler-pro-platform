<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'

type Envelope<T> = { data?: T; error?: { message?: string } }
type TwoFactorState = {
  enabled: boolean
  configured: boolean
  mandatory: boolean
  second_factor_verified: boolean
}

const visible = ref(false)
const busy = ref(false)
const code = ref('')
const errorMessage = ref('')

async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    ...init,
    headers: {
      accept: 'application/json',
      ...(init.body ? { 'content-type': 'application/json' } : {}),
      ...(init.headers || {}),
    },
    cache: 'no-store',
  })
  const body = await response.json().catch(() => ({})) as Envelope<T>
  if (!response.ok) throw new Error(body.error?.message || 'Falha ao validar a sessão.')
  return body.data as T
}

async function inspect(): Promise<void> {
  if (!localStorage.getItem('scheduler_pro_access_token')) {
    visible.value = false
    return
  }
  try {
    const state = await api<TwoFactorState>('/auth/2fa/state')
    visible.value = Boolean(state.enabled && !state.second_factor_verified)
  } catch {
    // O console existente continua responsável por sessões inválidas. O gate não
    // derruba a experiência por falha transitória de rede.
  }
}

async function verify(): Promise<void> {
  if (code.value.trim().length < 6) return
  busy.value = true
  errorMessage.value = ''
  try {
    await api('/auth/2fa/verify', {
      method: 'POST',
      body: JSON.stringify({ code: code.value.trim() }),
    })
    visible.value = false
    window.dispatchEvent(new CustomEvent('scheduler-pro-tenant-2fa-verified'))
    window.dispatchEvent(new CustomEvent('scheduler-pro-revalidate-current-view'))
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Código inválido.'
  } finally {
    busy.value = false
  }
}

function logout(): void {
  localStorage.removeItem('scheduler_pro_access_token')
  localStorage.removeItem('scheduler_pro_refresh_token')
  window.location.reload()
}

function recheck(): void { void inspect() }

onMounted(() => {
  void inspect()
  window.addEventListener('scheduler-pro-session-refreshed', recheck)
  window.addEventListener('scheduler-pro-revalidate-current-view', recheck)
  window.addEventListener('pageshow', recheck)
})

onUnmounted(() => {
  window.removeEventListener('scheduler-pro-session-refreshed', recheck)
  window.removeEventListener('scheduler-pro-revalidate-current-view', recheck)
  window.removeEventListener('pageshow', recheck)
})
</script>

<template>
  <div v-if="visible" class="tenant-2fa-backdrop" role="dialog" aria-modal="true">
    <section class="tenant-2fa-card">
      <span class="tenant-2fa-kicker">Painel da Empresa</span>
      <h1>Verificação em duas etapas</h1>
      <p>Informe o código atual do seu aplicativo autenticador para continuar.</p>
      <p v-if="errorMessage" class="error" role="alert">{{ errorMessage }}</p>
      <label>
        <span>Código de 6 dígitos</span>
        <input
          v-model="code"
          inputmode="numeric"
          autocomplete="one-time-code"
          maxlength="8"
          autofocus
          placeholder="000000"
          @keyup.enter="verify"
        />
      </label>
      <button class="primary" :disabled="busy || code.trim().length < 6" @click="verify">
        {{ busy ? 'Validando…' : 'Verificar e continuar' }}
      </button>
      <button class="link" @click="logout">Sair desta conta</button>
    </section>
  </div>
</template>

<style scoped>
.tenant-2fa-backdrop { position:fixed; inset:0; z-index:2147482000; display:grid; place-items:center; padding:18px; overflow:auto; background:rgba(8,15,28,.84); -webkit-backdrop-filter:blur(12px); backdrop-filter:blur(12px); }
.tenant-2fa-card { width:min(100%,460px); display:grid; gap:16px; padding:clamp(22px,5vw,34px); border-radius:22px; background:white; color:#172033; box-shadow:0 24px 70px rgba(0,0,0,.3); }
.tenant-2fa-kicker { color:#3151cf; font-size:.75rem; font-weight:800; text-transform:uppercase; letter-spacing:.08em; }
h1,p { margin:0; } p { color:#5f687c; line-height:1.5; } label { display:grid; gap:8px; font-weight:700; }
input { box-sizing:border-box; width:100%; padding:14px; border:1px solid #ccd3df; border-radius:12px; font:inherit; font-size:1.1rem; letter-spacing:.12em; }
button { min-height:46px; border:0; border-radius:12px; font:inherit; font-weight:800; cursor:pointer; }.primary{background:#3151cf;color:#fff}.link{background:transparent;color:#5f687c}.error{padding:12px;border-radius:12px;background:#fff1f1;color:#a62424}
</style>
