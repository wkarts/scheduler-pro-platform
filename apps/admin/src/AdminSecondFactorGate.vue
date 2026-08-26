<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { apiGet, apiPost, type ApiError } from './api/client'

type StoredSession = { accessToken?: string; userEmail?: string }
type TwoFactorState = {
  enabled: boolean
  configured: boolean
  mandatory: boolean
  second_factor_verified: boolean
}
type Enrollment = {
  manual_key: string
  otpauth_uri: string
  qr_code: string
  digits: number
  period: number
}

const storageKey = 'scheduler-pro-admin-session'
const visible = ref(false)
const busy = ref(false)
const setupRequired = ref(false)
const enrollment = ref<Enrollment | null>(null)
const code = ref('')
const errorMessage = ref('')
const userEmail = ref('')

function session(): StoredSession | null {
  const raw = localStorage.getItem(storageKey)
  if (!raw) return null
  try {
    return JSON.parse(raw) as StoredSession
  } catch {
    return null
  }
}

function token(): string {
  return session()?.accessToken || ''
}

function describe(error: unknown): string {
  const apiError = error as Partial<ApiError>
  return apiError.message || 'Não foi possível concluir a verificação.'
}

async function inspect(): Promise<void> {
  const current = session()
  if (!current?.accessToken) {
    visible.value = false
    return
  }
  userEmail.value = current.userEmail || ''
  try {
    const state = await apiGet<TwoFactorState>('/auth/platform/2fa/state', current.accessToken)
    if (state.second_factor_verified) {
      visible.value = false
      return
    }
    setupRequired.value = !state.enabled || !state.configured
    visible.value = true
  } catch (error) {
    const apiError = error as Partial<ApiError>
    if (apiError.status === 401) {
      localStorage.removeItem(storageKey)
      visible.value = false
      return
    }
    errorMessage.value = describe(error)
    visible.value = true
  }
}

async function beginSetup(): Promise<void> {
  if (!token()) return
  busy.value = true
  errorMessage.value = ''
  try {
    enrollment.value = await apiPost<Enrollment>('/auth/platform/2fa/setup', {}, token())
  } catch (error) {
    errorMessage.value = describe(error)
  } finally {
    busy.value = false
  }
}

async function confirmSetup(): Promise<void> {
  if (!token() || code.value.trim().length < 6) return
  busy.value = true
  errorMessage.value = ''
  try {
    await apiPost('/auth/platform/2fa/confirm', { code: code.value.trim() }, token())
    window.location.reload()
  } catch (error) {
    errorMessage.value = describe(error)
  } finally {
    busy.value = false
  }
}

async function verify(): Promise<void> {
  if (!token() || code.value.trim().length < 6) return
  busy.value = true
  errorMessage.value = ''
  try {
    await apiPost('/auth/platform/2fa/verify', { code: code.value.trim() }, token())
    window.location.reload()
  } catch (error) {
    errorMessage.value = describe(error)
  } finally {
    busy.value = false
  }
}

function logout(): void {
  localStorage.removeItem(storageKey)
  window.location.reload()
}

function onRequired(): void {
  void inspect()
}

onMounted(() => {
  window.addEventListener('scheduler-pro-admin-2fa-required', onRequired)
  void inspect()
})

onUnmounted(() => {
  window.removeEventListener('scheduler-pro-admin-2fa-required', onRequired)
})
</script>

<template>
  <div v-if="visible" class="two-factor-gate" role="dialog" aria-modal="true" aria-labelledby="two-factor-title">
    <section class="two-factor-card">
      <header>
        <div class="security-mark" aria-hidden="true">2</div>
        <div>
          <p class="eyebrow">Administração da Plataforma</p>
          <h1 id="two-factor-title">Verificação em duas etapas</h1>
          <p>{{ userEmail }}</p>
        </div>
      </header>

      <p class="intro">
        A Administração da Plataforma exige um aplicativo autenticador para proteger operações administrativas.
      </p>

      <p v-if="errorMessage" class="two-factor-error" role="alert">{{ errorMessage }}</p>

      <template v-if="setupRequired">
        <template v-if="!enrollment">
          <div class="info-box">
            <strong>Primeiro acesso protegido</strong>
            <span>Configure o autenticador para liberar sua sessão administrativa.</span>
          </div>
          <button class="primary" :disabled="busy" @click="beginSetup">
            {{ busy ? 'Preparando…' : 'Configurar aplicativo autenticador' }}
          </button>
        </template>

        <template v-else>
          <div class="setup-grid">
            <div class="qr-wrap">
              <img :src="enrollment.qr_code" alt="QR Code para configurar o aplicativo autenticador" />
            </div>
            <div class="setup-copy">
              <strong>1. Leia o QR Code</strong>
              <p>Abra seu aplicativo autenticador e adicione uma nova conta.</p>
              <strong>2. Ou use a chave manual</strong>
              <code>{{ enrollment.manual_key }}</code>
            </div>
          </div>
          <label>
            <span>3. Informe o código de 6 dígitos</span>
            <input
              v-model="code"
              inputmode="numeric"
              autocomplete="one-time-code"
              maxlength="8"
              placeholder="000000"
              @keyup.enter="confirmSetup"
            />
          </label>
          <button class="primary" :disabled="busy || code.trim().length < 6" @click="confirmSetup">
            {{ busy ? 'Validando…' : 'Ativar e continuar' }}
          </button>
        </template>
      </template>

      <template v-else>
        <label>
          <span>Código do aplicativo autenticador</span>
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
          {{ busy ? 'Validando…' : 'Verificar e entrar' }}
        </button>
      </template>

      <button class="link-button" @click="logout">Sair desta conta</button>
    </section>
  </div>
</template>

<style scoped>
.two-factor-gate {
  position: fixed;
  inset: 0;
  z-index: 2147483000;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(8, 13, 24, 0.86);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  overflow: auto;
}
.two-factor-card {
  width: min(100%, 560px);
  display: grid;
  gap: 20px;
  padding: clamp(22px, 5vw, 36px);
  border-radius: 24px;
  background: #fff;
  color: #172033;
  box-shadow: 0 28px 80px rgba(0, 0, 0, 0.3);
}
header { display: flex; gap: 14px; align-items: center; }
header h1 { margin: 2px 0 0; font-size: clamp(1.45rem, 5vw, 2rem); }
header p { margin: 3px 0 0; color: #687086; }
.eyebrow { margin: 0; font-size: .74rem; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; color: #3859d8; }
.security-mark { width: 52px; height: 52px; flex: 0 0 auto; display: grid; place-items: center; border-radius: 16px; background: #ecf0ff; color: #3151cf; font-weight: 900; font-size: 1.4rem; }
.intro { margin: 0; line-height: 1.55; color: #4e586e; }
.info-box { display: grid; gap: 6px; padding: 16px; border-radius: 16px; background: #f5f7fb; }
.info-box span { color: #606a80; line-height: 1.45; }
.setup-grid { display: grid; grid-template-columns: minmax(148px, 190px) 1fr; gap: 20px; align-items: center; }
.qr-wrap { padding: 12px; border: 1px solid #dfe4ee; border-radius: 18px; background: #fff; }
.qr-wrap img { display: block; width: 100%; height: auto; }
.setup-copy { display: grid; gap: 8px; min-width: 0; }
.setup-copy p { margin: 0 0 6px; color: #657086; line-height: 1.4; }
.setup-copy code { overflow-wrap: anywhere; padding: 10px; border-radius: 10px; background: #f2f4f8; font-size: .8rem; }
label { display: grid; gap: 8px; font-weight: 700; }
input { width: 100%; box-sizing: border-box; padding: 14px 16px; border: 1px solid #ccd3df; border-radius: 12px; font: inherit; font-size: 1.1rem; letter-spacing: .12em; }
input:focus { outline: 3px solid rgba(49, 81, 207, .16); border-color: #3151cf; }
button { min-height: 46px; border: 0; border-radius: 12px; font: inherit; font-weight: 800; cursor: pointer; }
button:disabled { opacity: .6; cursor: progress; }
.primary { padding: 0 18px; background: #3151cf; color: #fff; }
.link-button { background: transparent; color: #5f687c; }
.two-factor-error { margin: 0; padding: 12px 14px; border-radius: 12px; background: #fff1f1; color: #a62424; }
@media (max-width: 620px) {
  .two-factor-gate { align-items: start; padding: 12px; }
  .two-factor-card { margin: 10px 0; border-radius: 20px; }
  .setup-grid { grid-template-columns: 1fr; }
  .qr-wrap { width: min(70vw, 230px); justify-self: center; }
}
</style>
