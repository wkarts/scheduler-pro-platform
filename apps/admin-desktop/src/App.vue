<script setup lang="ts">
import { onMounted, ref } from 'vue'

const STORAGE_KEY = 'scheduler_pro_admin_desktop_instance_url'
const instanceUrl = ref(localStorage.getItem(STORAGE_KEY) || 'https://admin.scheduler.argws.com.br')
const error = ref('')
const opening = ref(false)

function normalizeInstanceUrl(value: string): string {
  const trimmed = value.trim()
  if (!trimmed) throw new Error('Informe a URL do Control Plane.')
  const parsed = new URL(trimmed.includes('://') ? trimmed : `https://${trimmed}`)
  if (parsed.protocol !== 'https:' && !['localhost', '127.0.0.1'].includes(parsed.hostname)) {
    throw new Error('O Control Plane deve utilizar HTTPS.')
  }
  parsed.search = ''
  parsed.hash = ''
  parsed.pathname = parsed.pathname.replace(/\/+$/, '') || '/'
  return parsed.toString().replace(/\/$/, '')
}

function openWebApp(url: string): void {
  opening.value = true
  window.location.replace(url)
}

function configureAndOpen(): void {
  error.value = ''
  try {
    const normalized = normalizeInstanceUrl(instanceUrl.value)
    localStorage.setItem(STORAGE_KEY, normalized)
    openWebApp(normalized)
  } catch (exc) {
    error.value = exc instanceof Error ? exc.message : 'Não foi possível configurar o Control Plane.'
  }
}

onMounted(() => {
  const saved = localStorage.getItem(STORAGE_KEY)
  if (!saved) return
  try {
    openWebApp(normalizeInstanceUrl(saved))
  } catch {
    localStorage.removeItem(STORAGE_KEY)
  }
})
</script>

<template>
  <main class="instance-setup">
    <section class="setup-card">
      <div class="brand-mark">SP</div>
      <p class="eyebrow">Scheduler Pro Admin Desktop</p>
      <h1>Conectar ao Control Plane</h1>
      <p class="lead">O aplicativo administrativo usa exatamente a aplicação web do Control Plane. Configure o endereço uma vez; os próximos acessos abrirão diretamente a interface web atual.</p>
      <form @submit.prevent="configureAndOpen">
        <label>
          URL administrativa
          <input v-model="instanceUrl" type="url" inputmode="url" autocomplete="url" placeholder="https://admin.scheduler.argws.com.br" required />
        </label>
        <p v-if="error" class="error">{{ error }}</p>
        <button type="submit" :disabled="opening">{{ opening ? 'Abrindo...' : 'Salvar e continuar' }}</button>
      </form>
    </section>
  </main>
</template>

<style scoped>
.instance-setup{min-height:100vh;display:grid;place-items:center;padding:32px;background:radial-gradient(circle at 18% 12%,rgba(124,58,237,.2),transparent 34%),linear-gradient(135deg,#07182f,#17153d);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.setup-card{width:min(620px,100%);padding:42px;border-radius:28px;background:#fff;box-shadow:0 30px 80px rgba(3,15,35,.32);color:#10213b}.brand-mark{width:64px;height:64px;display:grid;place-items:center;border-radius:20px;background:linear-gradient(135deg,#2563eb,#7c3aed);color:#fff;font-weight:900;font-size:22px}.eyebrow{margin:24px 0 8px;color:#5b4bd8;font-weight:900;font-size:12px;letter-spacing:.18em;text-transform:uppercase}.setup-card h1{margin:0;font-size:34px;letter-spacing:-.04em}.lead{margin:14px 0 28px;color:#61718a;line-height:1.65}.setup-card form{display:grid;gap:14px}.setup-card label{display:grid;gap:8px;font-size:13px;font-weight:800}.setup-card input{height:52px;border:1px solid #d9e4f0;border-radius:14px;padding:0 15px;font:inherit;outline:0}.setup-card input:focus{border-color:#5b4bd8;box-shadow:0 0 0 4px rgba(91,75,216,.09)}.setup-card button{height:52px;border:0;border-radius:14px;background:linear-gradient(135deg,#2563eb,#7c3aed);color:#fff;font:inherit;font-weight:900;cursor:pointer}.setup-card button:disabled{opacity:.6}.error{margin:0;color:#b91c1c;background:#fef2f2;border:1px solid #fecaca;border-radius:12px;padding:11px 13px;font-size:13px}@media(max-width:640px){.instance-setup{padding:16px}.setup-card{padding:28px 22px;border-radius:22px}.setup-card h1{font-size:29px}}
</style>
