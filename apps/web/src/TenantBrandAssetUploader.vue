<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { ImageUp, Upload } from 'lucide-vue-next'

type AssetKind = 'logo' | 'icon' | 'favicon'

const brandingOpen = ref(false)
const busy = ref<AssetKind | ''>('')
const message = ref('')
const error = ref('')
let observer: MutationObserver | undefined

function syncTarget(): void {
  const root = document.querySelector('.sp-extension-root')
  const heading = root?.querySelector('.sp-extension-header h1')?.textContent || ''
  brandingOpen.value = Boolean(root && heading.includes('Personalização'))
}

async function upload(kind: AssetKind, event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  busy.value = kind
  error.value = ''
  message.value = ''
  try {
    const form = new FormData()
    form.append('file', file)
    const token = localStorage.getItem('scheduler_pro_access_token') || ''
    const response = await fetch(`${window.location.origin}/api/v1/branding/assets/${kind}`, {
      method: 'POST',
      headers: { Accept: 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: form,
    })
    const payload = await response.json().catch(() => ({})) as { data?: { url?: string }; error?: { message?: string } }
    if (!response.ok) throw new Error(payload.error?.message || `Falha HTTP ${response.status}`)
    message.value = `${kind === 'logo' ? 'Logo' : kind === 'icon' ? 'Ícone' : 'Favicon'} enviado. Atualizando a identidade visual…`
    window.setTimeout(() => window.location.reload(), 700)
  } catch (exc) {
    error.value = exc instanceof Error ? exc.message : 'Falha ao enviar arquivo.'
  } finally {
    busy.value = ''
    input.value = ''
  }
}

onMounted(() => {
  syncTarget()
  observer = new MutationObserver(syncTarget)
  observer.observe(document.body, { childList: true, subtree: true, characterData: true })
})
onUnmounted(() => observer?.disconnect())
</script>

<template>
  <Teleport v-if="brandingOpen" to=".sp-extension-root">
    <article class="sp-brand-upload-card">
      <div class="sp-brand-upload-copy"><ImageUp :size="24"/><div><strong>Enviar arquivos da marca</strong><span>PNG, JPEG, WebP, SVG ou ICO · até 4 MB. O arquivo fica no storage isolado deste tenant.</span></div></div>
      <div class="sp-brand-upload-actions">
        <label><Upload :size="15"/> {{ busy==='logo'?'Enviando…':'Enviar logo' }}<input type="file" accept="image/png,image/jpeg,image/webp,image/svg+xml" :disabled="Boolean(busy)" @change="upload('logo',$event)"/></label>
        <label><Upload :size="15"/> {{ busy==='icon'?'Enviando…':'Enviar ícone' }}<input type="file" accept="image/png,image/jpeg,image/webp,image/svg+xml" :disabled="Boolean(busy)" @change="upload('icon',$event)"/></label>
        <label><Upload :size="15"/> {{ busy==='favicon'?'Enviando…':'Enviar favicon' }}<input type="file" accept="image/png,image/x-icon,image/vnd.microsoft.icon,image/svg+xml" :disabled="Boolean(busy)" @change="upload('favicon',$event)"/></label>
      </div>
      <p v-if="message" class="sp-brand-upload-success">{{ message }}</p><p v-if="error" class="sp-brand-upload-error">{{ error }}</p>
    </article>
  </Teleport>
</template>

<style>
.sp-brand-upload-card{order:-1;display:flex;align-items:center;justify-content:space-between;gap:18px;padding:17px 19px;border:1px solid #dbeafe;border-radius:17px;background:linear-gradient(135deg,#eff6ff,#f5f3ff);box-shadow:0 8px 28px rgba(37,99,235,.06)}.sp-brand-upload-copy{display:flex;align-items:center;gap:12px;color:#1d4ed8}.sp-brand-upload-copy div{display:grid;gap:3px}.sp-brand-upload-copy strong{font-size:13px;color:#1e3a8a}.sp-brand-upload-copy span{font-size:10px;color:#64748b}.sp-brand-upload-actions{display:flex;flex-wrap:wrap;justify-content:flex-end;gap:7px}.sp-brand-upload-actions label{min-height:37px;padding:0 11px;border:1px solid #bfdbfe;border-radius:9px;background:#fff;color:#1d4ed8;display:flex;align-items:center;gap:6px;font-size:10px;font-weight:900;cursor:pointer}.sp-brand-upload-actions input{display:none}.sp-brand-upload-success,.sp-brand-upload-error{grid-column:1/-1;margin:0;font-size:10px;font-weight:800}.sp-brand-upload-success{color:#047857}.sp-brand-upload-error{color:#b91c1c}@media(max-width:860px){.sp-brand-upload-card{align-items:flex-start;flex-direction:column}.sp-brand-upload-actions{justify-content:flex-start}}@media(max-width:520px){.sp-brand-upload-actions{width:100%;display:grid;grid-template-columns:1fr}.sp-brand-upload-actions label{justify-content:center}}
</style>
