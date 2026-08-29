<script setup lang="ts">
import { computed, onMounted, ref, type CSSProperties } from 'vue'
import { CalendarClock, LogIn } from 'lucide-vue-next'
import { applyBranding, loadBrandingManifest, type BrandingManifest } from './branding'

const emit = defineEmits<{ authenticated: [] }>()

const manifest = ref<BrandingManifest | null>(null)
const email = ref(localStorage.getItem('scheduler_pro_email') || '')
const password = ref('')
const loading = ref(false)
const error = ref('')

const defaults = {
  login_title: 'Agenda viva, confirmações automáticas e operação em tempo real.',
  login_message: 'Entre no ambiente exclusivo da sua empresa para acompanhar cada mudança do atendimento.',
  login_card_title: 'Entrar na plataforma',
  login_card_message: 'Acesse o painel gerencial da sua empresa.',
}

const loginStyle=computed<CSSProperties>(()=>{
  const colors=manifest.value?.theme.colors
  const background=typeof manifest.value?.settings?.login_background_url==='string'?manifest.value.settings.login_background_url:''
  return {
    '--login-primary':colors?.primary||'#2563EB',
    '--login-secondary':colors?.secondary||'#0B0F1A',
    '--login-accent':colors?.accent||'#0AE1C0',
    '--login-background':colors?.background||'#FFFFFF',
    '--login-text':colors?.text||'#0B0F1A',
    '--login-font':manifest.value?.theme.font_family||'Sora, Inter, system-ui, sans-serif',
    '--login-background-image':background?`url("${background.replace(/"/g,'')}" )`:'none',
  } as CSSProperties
})
const platformLogo=/^\/branding\/scheduler-pro-logo-(?:light|dark)\.png(?:\?.*)?$/i
const loginLogo=computed(()=>{
  const regular=String(manifest.value?.assets.logo_url||'')
  const dark=String(manifest.value?.assets.logo_dark_url||'')
  if(!regular||platformLogo.test(regular))return '/branding/scheduler-pro-symbol.png'
  return dark&&!platformLogo.test(dark)?dark:regular
})

function setting(key: keyof typeof defaults): string {
  const value = manifest.value?.settings?.[key]
  return typeof value === 'string' && value.trim() ? value.trim() : defaults[key]
}

async function login(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    const response = await fetch(`${window.location.origin}/api/v1/auth/login`, {
      method: 'POST',
      headers: { 'content-type': 'application/json', accept: 'application/json' },
      body: JSON.stringify({ email: email.value, password: password.value }),
    })
    const body = await response.json().catch(() => ({})) as { data?: { access_token?: string; refresh_token?: string; user?: { email?: string; display_name?: string } }; error?: { message?: string } }
    if (!response.ok || !body.data?.access_token) throw new Error(body.error?.message || 'Login inválido.')
    localStorage.setItem('scheduler_pro_access_token', body.data.access_token)
    if (body.data.refresh_token) localStorage.setItem('scheduler_pro_refresh_token', body.data.refresh_token)
    localStorage.setItem('scheduler_pro_email', body.data.user?.email || email.value)
    localStorage.setItem('scheduler_pro_display_name', body.data.user?.display_name || '')
    window.dispatchEvent(new Event('scheduler-pro-auth-changed'))
    emit('authenticated')
    window.location.assign('/#dashboard')
  } catch (exc) {
    error.value = exc instanceof Error ? exc.message : 'Não foi possível entrar.'
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  try {
    manifest.value = await loadBrandingManifest()
    applyBranding(manifest.value)
  } catch { /* fallback visual Scheduler Pro */ }
})
</script>

<template>
  <main class="tenant-login-page" :style="loginStyle">
    <section class="tenant-login-visual">
      <div class="tenant-login-brand">
        <img v-if="loginLogo" :src="loginLogo" :alt="manifest?.app.public_name || 'Scheduler Pro'" />
        <div v-else class="tenant-login-mark"><CalendarClock :size="30" /></div>
        <div><strong>{{ manifest?.app.public_name || 'Scheduler Pro' }}</strong><span>{{ manifest?.app.slogan || 'Plataforma inteligente de agendamentos' }}</span></div>
      </div>
      <div class="tenant-login-copy"><span class="tenant-login-kicker">Agenda profissional</span><h1>{{ setting('login_title') }}</h1><p>{{ setting('login_message') }}</p></div>
      <div class="tenant-login-foot">Scheduler Pro · ambiente exclusivo da empresa</div>
    </section>
    <form class="tenant-login-card" @submit.prevent="login">
      <div class="tenant-login-card-head"><span>Acesso seguro</span><h2>{{ setting('login_card_title') }}</h2><p>{{ setting('login_card_message') }}</p></div>
      <label>E-mail<input v-model="email" type="email" autocomplete="username" placeholder="voce@empresa.com.br" required /></label>
      <label>Senha<input v-model="password" type="password" autocomplete="current-password" required /></label>
      <p v-if="error" class="tenant-login-error">{{ error }}</p>
      <button class="tenant-login-button" :disabled="loading"><LogIn :size="18" />{{ loading ? 'Entrando...' : 'Entrar' }}</button>
    </form>
  </main>
</template>

<style>
.tenant-login-page{min-height:100vh;display:grid;grid-template-columns:minmax(0,1.15fr) minmax(390px,.85fr);background:var(--login-background,#f8fafc);color:var(--login-text,#0f172a);font-family:var(--login-font,inherit)}.tenant-login-visual{position:relative;overflow:hidden;display:flex;flex-direction:column;padding:clamp(34px,6vw,82px);background-image:var(--login-background-image,none),radial-gradient(circle at 12% 18%,color-mix(in srgb,var(--login-primary,#2563eb) 35%,transparent),transparent 34%),radial-gradient(circle at 86% 76%,color-mix(in srgb,var(--login-accent,#7c3aed) 30%,transparent),transparent 36%),linear-gradient(145deg,var(--login-secondary,#071426),#0d1b2a 46%,#172554);background-size:cover,auto,auto,auto;background-position:center;color:#fff}.tenant-login-visual:after{content:"";position:absolute;inset:0;background-image:linear-gradient(rgba(255,255,255,.035) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.035) 1px,transparent 1px);background-size:42px 42px;mask-image:linear-gradient(to bottom,rgba(0,0,0,.7),transparent)}.tenant-login-brand,.tenant-login-copy,.tenant-login-foot{position:relative;z-index:1}.tenant-login-brand{display:flex;align-items:center;gap:15px}.tenant-login-brand img{width:auto;max-width:190px;max-height:58px;object-fit:contain}.tenant-login-mark{width:54px;height:54px;border-radius:17px;display:grid;place-items:center;background:var(--login-primary,#2563eb);box-shadow:0 15px 38px rgba(37,99,235,.28)}.tenant-login-brand strong,.tenant-login-brand span{display:block}.tenant-login-brand strong{font-size:18px}.tenant-login-brand span{margin-top:3px;color:#a5b4fc;font-size:12px}.tenant-login-copy{margin:auto 0;max-width:760px}.tenant-login-kicker{display:inline-flex;padding:7px 11px;border:1px solid rgba(255,255,255,.16);border-radius:999px;background:rgba(255,255,255,.06);font-size:11px;font-weight:800;letter-spacing:.08em;text-transform:uppercase}.tenant-login-copy h1{max-width:720px;margin:22px 0 15px;font-size:clamp(38px,5.3vw,72px);line-height:.98;letter-spacing:-.055em}.tenant-login-copy p{max-width:620px;margin:0;color:#cbd5e1;font-size:clamp(15px,1.6vw,19px);line-height:1.7}.tenant-login-foot{color:#64748b;font-size:11px}.tenant-login-card{align-self:center;width:min(470px,calc(100% - 48px));margin:auto;padding:38px;border:1px solid #e2e8f0;border-radius:25px;background:#fff;box-shadow:0 24px 70px rgba(15,23,42,.09)}.tenant-login-card-head span{font-size:11px;font-weight:900;color:var(--login-primary,#2563eb);text-transform:uppercase;letter-spacing:.08em}.tenant-login-card-head h2{margin:8px 0 7px;font-size:30px;letter-spacing:-.035em}.tenant-login-card-head p{margin:0 0 27px;color:#64748b;line-height:1.5}.tenant-login-card label{display:grid;gap:7px;margin:15px 0;font-size:12px;font-weight:800;color:#334155}.tenant-login-card input{height:48px;border:1px solid #cbd5e1;border-radius:12px;padding:0 14px;font:inherit;outline:none}.tenant-login-card input:focus{border-color:var(--login-primary,#2563eb);box-shadow:0 0 0 3px color-mix(in srgb,var(--login-primary,#2563eb) 14%,transparent)}.tenant-login-button{width:100%;height:50px;margin-top:12px;border:0;border-radius:13px;display:flex;align-items:center;justify-content:center;gap:8px;background:var(--login-primary,#2563eb);color:#fff;font:inherit;font-weight:900;cursor:pointer}.tenant-login-button:disabled{opacity:.65;cursor:wait}.tenant-login-error{padding:10px 12px;border-radius:10px;background:#fef2f2;color:#b91c1c;font-size:12px}@media(max-width:840px){.tenant-login-page{display:block;background:#0d1b2a;padding:16px}.tenant-login-visual{min-height:300px;border-radius:24px;padding:28px}.tenant-login-copy{margin:64px 0 30px}.tenant-login-copy h1{font-size:38px}.tenant-login-foot{display:none}.tenant-login-card{position:relative;width:calc(100% - 24px);margin:-34px auto 20px;padding:28px;border-radius:21px;z-index:3}}@media(max-width:520px){.tenant-login-page{padding:0}.tenant-login-visual{border-radius:0;min-height:330px;padding:24px 20px 64px}.tenant-login-brand img{max-width:150px;max-height:48px}.tenant-login-copy{margin:54px 0 12px}.tenant-login-copy h1{font-size:34px}.tenant-login-card{width:calc(100% - 24px);margin:-42px 12px 20px;padding:24px}}
</style>
