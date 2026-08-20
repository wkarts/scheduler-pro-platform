<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { CalendarPlus2, Check, Copy, ExternalLink, MessageSquareText, RefreshCw, Save, X } from 'lucide-vue-next'

type View = ''|'booking'|'messages'
type Envelope<T> = { data?:T; error?:{message?:string} }
type Capabilities = { enabled:string[] }
type TenantSettings = { hostname:string; preferences:Record<string,unknown> }
type NotificationTemplate = { id:string; key:string; channel:string; body:string; active:boolean; subject?:string|null }

const active=ref<View>('')
const portalReady=ref(false)
const loading=ref(false)
const saving=ref(false)
const error=ref('')
const toast=ref('')
const capabilities=ref(new Set<string>())
const hostname=ref(window.location.hostname)
const templates=ref<NotificationTemplate[]>([])
const booking=ref({
  enabled:false,
  title:'Agende seu atendimento',
  subtitle:'Escolha o serviço, o profissional e um horário disponível.',
  success_message:'Seu horário foi reservado. Confira seu WhatsApp ou e-mail para confirmar o agendamento.',
  custom_html:'',
  slot_minutes:30,
  allow_any_professional:true,
  require_phone:true,
  require_email:false,
})

const token=()=>localStorage.getItem('scheduler_pro_access_token')||''
const canBooking=computed(()=>capabilities.value.has('public_booking'))
const canMessages=computed(()=>capabilities.value.has('notifications'))
const publicUrl=computed(()=>`${window.location.origin}/agendar`)
const whatsappTemplates=computed(()=>templates.value.filter(item=>item.channel==='whatsapp'))
const emailTemplates=computed(()=>templates.value.filter(item=>item.channel==='email'))
const variableHelp='{{customer_name}} · {{service_name}} · {{professional_name}} · {{starts_at_br}} · {{ends_at_br}} · {{confirmation_url}} · {{reason}}'

function friendlyKey(value:string):string {
  return ({
    appointment_created:'Reserva criada',
    appointment_confirmation_request:'Pedido de confirmação',
    appointment_rescheduled:'Reagendamento',
    appointment_confirmed:'Confirmação concluída',
    appointment_cancelled:'Cancelamento',
    appointment_completed:'Atendimento concluído',
    appointment_no_show:'Não comparecimento',
    appointment_reminder_24h:'Lembrete 24 horas',
    appointment_reminder_2h:'Lembrete 2 horas',
    appointment_confirmation_request_email:'Pedido de confirmação',
    appointment_rescheduled_email:'Reagendamento',
    appointment_confirmed_email:'Confirmação concluída',
    appointment_cancelled_email:'Cancelamento',
    appointment_reminder_24h_email:'Lembrete 24 horas',
    appointment_reminder_2h_email:'Lembrete 2 horas',
  } as Record<string,string>)[value] || value.replaceAll('_',' ')
}
function showToast(message:string):void { toast.value=message; window.setTimeout(()=>{if(toast.value===message)toast.value=''},3500) }
async function api<T>(path:string,init:RequestInit={}):Promise<T> {
  const response=await fetch(`${window.location.origin}/api/v1${path}`,{
    ...init,
    headers:{Accept:'application/json',...(init.body?{'content-type':'application/json'}:{}),...(token()?{Authorization:`Bearer ${token()}`}:{}) ,...(init.headers||{})},
  })
  const payload=await response.json().catch(()=>({})) as Envelope<T>
  if(!response.ok || payload.data===undefined) throw new Error(payload.error?.message||`Falha HTTP ${response.status}`)
  return payload.data
}

async function initialLoad():Promise<void> {
  try {
    const caps=await api<Capabilities>('/settings/capabilities')
    capabilities.value=new Set(caps.enabled||[])
  } catch { /* console principal permanece */ }
}
function boolValue(value:unknown,fallback:boolean):boolean { return typeof value==='boolean'?value:fallback }
function numberValue(value:unknown,fallback:number):number { const parsed=Number(value); return Number.isFinite(parsed)?parsed:fallback }
function stringValue(value:unknown,fallback:string):string { return typeof value==='string'?value:fallback }
async function loadBooking():Promise<void> {
  const data=await api<TenantSettings>('/settings/tenant')
  hostname.value=data.hostname||window.location.hostname
  const p=data.preferences||{}
  booking.value={
    enabled:boolValue(p.public_booking_enabled,false),
    title:stringValue(p.public_booking_title,'Agende seu atendimento'),
    subtitle:stringValue(p.public_booking_subtitle,'Escolha o serviço, o profissional e um horário disponível.'),
    success_message:stringValue(p.public_booking_success_message,'Seu horário foi reservado. Confira seu WhatsApp ou e-mail para confirmar o agendamento.'),
    custom_html:stringValue(p.public_booking_custom_html,''),
    slot_minutes:numberValue(p.public_booking_slot_minutes,30),
    allow_any_professional:boolValue(p.public_booking_allow_any_professional,true),
    require_phone:boolValue(p.public_booking_require_phone,true),
    require_email:boolValue(p.public_booking_require_email,false),
  }
}
async function loadMessages():Promise<void> { templates.value=await api<NotificationTemplate[]>('/notifications/templates') }
async function open(view:View):Promise<void> {
  active.value=view;error.value='';loading.value=true
  try { if(view==='booking') await loadBooking(); if(view==='messages') await loadMessages() }
  catch(exc){error.value=exc instanceof Error?exc.message:'Não foi possível carregar esta área.'}
  finally{loading.value=false}
}
function close():void { active.value=''; const fallback='#dashboard'; if(['#agenda-publica','#mensagens'].includes(window.location.hash)) window.location.hash=fallback }
async function putSetting(key:string,value:unknown):Promise<void> { await api(`/settings/tenant/${key}`,{method:'PUT',body:JSON.stringify(value)}) }
async function saveBooking():Promise<void> {
  saving.value=true;error.value=''
  try {
    await Promise.all([
      putSetting('public_booking_enabled',booking.value.enabled),
      putSetting('public_booking_title',booking.value.title),
      putSetting('public_booking_subtitle',booking.value.subtitle),
      putSetting('public_booking_success_message',booking.value.success_message),
      putSetting('public_booking_custom_html',booking.value.custom_html),
      putSetting('public_booking_slot_minutes',Math.max(5,Math.min(240,Number(booking.value.slot_minutes)||30))),
      putSetting('public_booking_allow_any_professional',booking.value.allow_any_professional),
      putSetting('public_booking_require_phone',booking.value.require_phone),
      putSetting('public_booking_require_email',booking.value.require_email),
    ])
    showToast('Agenda pública atualizada.')
  } catch(exc){error.value=exc instanceof Error?exc.message:'Falha ao salvar agenda pública.'}
  finally{saving.value=false}
}
async function saveTemplate(item:NotificationTemplate):Promise<void> {
  saving.value=true;error.value=''
  try {
    const saved=await api<NotificationTemplate>(`/notifications/templates/${encodeURIComponent(item.key)}`,{method:'PUT',body:JSON.stringify({channel:item.channel,body:item.body,active:item.active,subject:item.subject||null})})
    Object.assign(item,saved);showToast(`${friendlyKey(item.key)} salvo.`)
  } catch(exc){error.value=exc instanceof Error?exc.message:'Falha ao salvar mensagem.'}
  finally{saving.value=false}
}
async function copyPublicUrl():Promise<void> { await navigator.clipboard.writeText(publicUrl.value);showToast('Link da agenda pública copiado.') }
function openPublic():void { window.open(publicUrl.value,'_blank','noopener') }

onMounted(async()=>{await nextTick();portalReady.value=Boolean(document.querySelector('.tenant-console .nav-list')&&document.querySelector('.tenant-console .main-content'));await initialLoad()})
onUnmounted(()=>{document.body.classList.remove('sp-booking-message-open')})
</script>

<template>
  <Teleport v-if="portalReady" to=".tenant-console .nav-list">
    <button v-if="canBooking" class="nav-item sp-extension-nav" @click="open('booking')"><CalendarPlus2 :size="19"/><span>Agenda pública</span></button>
    <button v-if="canMessages" class="nav-item sp-extension-nav" @click="open('messages')"><MessageSquareText :size="19"/><span>Mensagens</span></button>
  </Teleport>

  <Teleport v-if="portalReady&&active" to=".tenant-console .main-content">
    <section class="sp-extension-root sp-booking-message-root">
      <header class="sp-extension-header">
        <div><span>Scheduler Pro</span><h1>{{ active==='booking'?'Agenda pública':'Mensagens da agenda' }}</h1><p>{{ active==='booking'?'Permita que o próprio cliente escolha serviço, profissional e horário sem entrar no painel.':'Personalize a comunicação enviada por WhatsApp e e-mail em cada etapa do atendimento.' }}</p></div>
        <button class="sp-icon-button" @click="close"><X :size="20"/></button>
      </header>
      <p v-if="toast" class="sp-success"><Check :size="16"/>{{ toast }}</p><p v-if="error" class="sp-error">{{ error }}</p>
      <div v-if="loading" class="sp-config-loading"><RefreshCw :size="20" class="spin"/>Atualizando...</div>

      <template v-else-if="active==='booking'">
        <div class="sp-booking-config-grid">
          <article class="sp-config-card">
            <div class="sp-config-card-head"><div><span>Publicação</span><h2>Agenda aberta</h2></div><label class="sp-switch"><input v-model="booking.enabled" type="checkbox"/><i></i><b>{{ booking.enabled?'Ativa':'Desativada' }}</b></label></div>
            <p>Quando ativa, clientes acessam uma página pública ligada ao mesmo motor de disponibilidade da agenda.</p>
            <div class="sp-public-url"><code>{{ publicUrl }}</code><button @click="copyPublicUrl"><Copy :size="16"/></button><button @click="openPublic"><ExternalLink :size="16"/></button></div>
            <div class="sp-config-form"><label>Título<input v-model="booking.title"/></label><label>Subtítulo<textarea v-model="booking.subtitle" rows="3"/></label><label>Mensagem após reservar<textarea v-model="booking.success_message" rows="3"/></label></div>
          </article>
          <article class="sp-config-card">
            <span class="sp-card-kicker">Disponibilidade</span><h2>Regras da página</h2>
            <div class="sp-config-form"><label>Intervalo da grade (minutos)<input v-model.number="booking.slot_minutes" type="number" min="5" max="240" step="5"/></label><label class="sp-check"><input v-model="booking.allow_any_professional" type="checkbox"/>Permitir “qualquer profissional disponível”</label><label class="sp-check"><input v-model="booking.require_phone" type="checkbox"/>Telefone/WhatsApp obrigatório</label><label class="sp-check"><input v-model="booking.require_email" type="checkbox"/>E-mail obrigatório</label></div>
          </article>
          <article class="sp-config-card wide">
            <span class="sp-card-kicker">Conteúdo personalizado</span><h2>HTML complementar</h2><p>Use HTML para montar apresentação, orientações, endereço, políticas ou outros blocos. Scripts, estilos perigosos e tags inseguras são removidos antes de exibir ao público.</p>
            <textarea v-model="booking.custom_html" class="sp-html-editor" rows="12" placeholder="<section><h2>Antes de agendar</h2><p>Escolha seu serviço...</p></section>"/>
          </article>
        </div>
        <div class="sp-config-actions"><button class="sp-primary-action" :disabled="saving" @click="saveBooking"><Save :size="17"/>{{ saving?'Salvando...':'Salvar agenda pública' }}</button><button class="sp-secondary-action" @click="openPublic"><ExternalLink :size="17"/>Visualizar página</button></div>
      </template>

      <template v-else-if="active==='messages'">
        <section class="sp-template-help"><strong>Variáveis disponíveis</strong><code>{{ variableHelp }}</code><span>As variáveis são substituídas automaticamente com os dados reais do agendamento.</span></section>
        <div class="sp-template-columns">
          <section><header><MessageSquareText :size="20"/><div><span>Canal</span><h2>WhatsApp</h2></div></header><article v-for="item in whatsappTemplates" :key="item.id" class="sp-template-card"><div class="sp-template-card-head"><div><strong>{{ friendlyKey(item.key) }}</strong><code>{{ item.key }}</code></div><label><input v-model="item.active" type="checkbox"/>Ativo</label></div><textarea v-model="item.body" rows="7"/><button :disabled="saving" @click="saveTemplate(item)"><Save :size="15"/>Salvar mensagem</button></article><p v-if="!whatsappTemplates.length" class="sp-empty-message">Nenhum template WhatsApp disponível.</p></section>
          <section><header><MessageSquareText :size="20"/><div><span>Canal</span><h2>E-mail</h2></div></header><article v-for="item in emailTemplates" :key="item.id" class="sp-template-card"><div class="sp-template-card-head"><div><strong>{{ friendlyKey(item.key) }}</strong><code>{{ item.key }}</code></div><label><input v-model="item.active" type="checkbox"/>Ativo</label></div><input v-if="item.subject!==undefined" v-model="item.subject" class="sp-subject-input" placeholder="Assunto do e-mail"/><textarea v-model="item.body" rows="7"/><button :disabled="saving" @click="saveTemplate(item)"><Save :size="15"/>Salvar e-mail</button></article><p v-if="!emailTemplates.length" class="sp-empty-message">Nenhum template de e-mail disponível.</p></section>
        </div>
      </template>
    </section>
  </Teleport>
</template>

<style>
body:has(.sp-booking-message-root) .tenant-console .main-content>.view-stack{display:none!important}body:has(.sp-booking-message-root) .tenant-console .page-actions{display:none!important}.sp-booking-message-root{padding:4px 0 24px}.sp-config-loading{min-height:220px;display:flex;align-items:center;justify-content:center;gap:8px;color:#64748b}.sp-booking-config-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}.sp-config-card{border:1px solid #e2e8f0;border-radius:18px;background:#fff;padding:20px;box-shadow:0 10px 28px rgba(15,23,42,.045)}.sp-config-card.wide{grid-column:1/-1}.sp-config-card>p{color:#64748b;font-size:12px;line-height:1.6}.sp-config-card-head{display:flex;justify-content:space-between;gap:16px;align-items:flex-start}.sp-config-card-head span,.sp-card-kicker,.sp-template-columns header span{font-size:10px;font-weight:900;letter-spacing:.11em;text-transform:uppercase;color:#2563eb}.sp-config-card h2,.sp-template-columns h2{margin:4px 0 8px;color:#0f172a}.sp-switch{display:flex;align-items:center;gap:8px;font-size:11px;color:#475569}.sp-switch input{position:absolute;opacity:0}.sp-switch i{width:38px;height:22px;border-radius:999px;background:#cbd5e1;position:relative}.sp-switch i:after{content:"";position:absolute;width:16px;height:16px;border-radius:50%;background:#fff;top:3px;left:3px;transition:.18s}.sp-switch input:checked+i{background:#2563eb}.sp-switch input:checked+i:after{transform:translateX(16px)}.sp-public-url{display:grid;grid-template-columns:1fr auto auto;gap:6px;align-items:center;margin:14px 0;padding:8px;border:1px solid #dbe4ef;border-radius:12px;background:#f8fafc}.sp-public-url code{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#334155;font-size:11px}.sp-public-url button{width:34px;height:34px;border:1px solid #dbe4ef;border-radius:9px;background:#fff;color:#2563eb}.sp-config-form{display:grid;gap:11px}.sp-config-form label:not(.sp-check){display:grid;gap:6px;font-size:11px;font-weight:800;color:#334155}.sp-config-form input,.sp-config-form textarea,.sp-html-editor,.sp-template-card textarea,.sp-subject-input{width:100%;box-sizing:border-box;border:1px solid #cbd5e1;border-radius:11px;background:#fff;color:#0f172a;font:inherit;outline:none}.sp-config-form input,.sp-subject-input{height:44px;padding:0 11px}.sp-config-form textarea,.sp-html-editor,.sp-template-card textarea{padding:11px;resize:vertical;line-height:1.5}.sp-check{display:flex;align-items:center;gap:9px;color:#475569;font-size:12px}.sp-check input{width:17px;height:17px}.sp-html-editor{font-family:"SFMono-Regular",Consolas,monospace;font-size:12px}.sp-config-actions{display:flex;gap:9px;margin-top:14px}.sp-primary-action,.sp-secondary-action,.sp-template-card button{min-height:43px;border-radius:11px;padding:0 14px;display:flex;align-items:center;justify-content:center;gap:7px;font-weight:850}.sp-primary-action,.sp-template-card button{border:0;background:#2563eb;color:#fff}.sp-secondary-action{border:1px solid #dbe4ef;background:#fff;color:#334155}.sp-template-help{margin-bottom:14px;padding:14px 16px;border:1px solid #bfdbfe;border-radius:14px;background:#eff6ff;display:grid;gap:5px}.sp-template-help strong{color:#1d4ed8}.sp-template-help code{font-size:11px;color:#334155;overflow-wrap:anywhere}.sp-template-help span{font-size:11px;color:#64748b}.sp-template-columns{display:grid;grid-template-columns:1fr 1fr;gap:14px}.sp-template-columns>section>header{display:flex;align-items:center;gap:9px;margin-bottom:10px;color:#2563eb}.sp-template-card{margin-bottom:10px;border:1px solid #e2e8f0;border-radius:15px;background:#fff;padding:15px}.sp-template-card-head{display:flex;justify-content:space-between;gap:10px;margin-bottom:10px}.sp-template-card-head strong,.sp-template-card-head code{display:block}.sp-template-card-head code{margin-top:3px;color:#94a3b8;font-size:9px}.sp-template-card-head label{display:flex;gap:5px;align-items:center;color:#64748b;font-size:10px}.sp-template-card textarea{font-family:inherit;font-size:12px}.sp-template-card button{margin-top:8px;min-height:38px;font-size:11px}.sp-subject-input{margin-bottom:8px;font-size:12px}.sp-empty-message{padding:24px;border-radius:14px;background:#f8fafc;color:#64748b;text-align:center}.sp-success{display:flex!important;align-items:center;gap:6px}.spin{animation:sp-bm-spin .8s linear infinite}@keyframes sp-bm-spin{to{transform:rotate(360deg)}}@media(max-width:850px){.sp-booking-config-grid,.sp-template-columns{grid-template-columns:1fr}.sp-config-card.wide{grid-column:auto}.sp-config-actions{display:grid}.sp-config-card{padding:16px}.sp-config-card-head{display:grid}.sp-template-card textarea{min-height:160px}}
</style>
