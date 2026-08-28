<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { CalendarDays, ChevronLeft, ChevronRight, Mail, Palette, RefreshCw, Save, Send, X } from 'lucide-vue-next'
import { applyBranding, loadBrandingManifest, type BrandingManifest } from './branding'

type ExtensionView = '' | 'calendar' | 'branding' | 'smtp'
type Appointment = { id:string; starts_at:string; ends_at:string; status:string; customer_name:string; customer_phone?:string|null; service_name:string; professional_name:string }
type VersionInfo = { name:string; version:string; release_tag?:string|null; build_sha?:string|null; tenant_schema?:string; platform_schema?:string }
type SmtpStatus = { enabled:boolean; configured:boolean; host:string; port:number; username:string; from_email:string; from_name:string; reply_to:string; use_tls:boolean; use_ssl:boolean; timeout_seconds:number; password_configured:boolean; updated_at?:string|null }
type Capabilities = { enabled:string[] }
type ApiEnvelope<T> = { data:T; error?:{message?:string} }

const active = ref<ExtensionView>('')
const portalReady = ref(false)
const token = () => localStorage.getItem('scheduler_pro_access_token') || ''
const capabilities = ref(new Set<string>())
const version = ref<VersionInfo | null>(null)
const manifest = ref<BrandingManifest | null>(null)
const appointments = ref<Appointment[]>([])
const loading = ref(false)
const saving = ref(false)
const toast = ref('')
const error = ref('')
const monthCursor = ref(new Date(new Date().getFullYear(), new Date().getMonth(), 1))
const selectedDay = ref(localDayKey(new Date().toISOString()))
const testRecipient = ref(localStorage.getItem('scheduler_pro_email') || '')
const smtp = ref<SmtpStatus>({ enabled:false, configured:false, host:'', port:587, username:'', from_email:'', from_name:'', reply_to:'', use_tls:true, use_ssl:false, timeout_seconds:15, password_configured:false })
const smtpPassword = ref('')
const brand = ref({
  public_name:'', slogan:'', logo_url:'', icon_url:'', favicon_url:'',
  primary_color:'#2563eb', secondary_color:'#0f172a', accent_color:'#7c3aed', background_color:'#f8fafc', text_color:'#0f172a', theme_mode:'system',
  login_title:'Agenda viva, confirmações automáticas e operação em tempo real.',
  login_message:'Entre no ambiente exclusivo da sua empresa para acompanhar cada mudança do atendimento.',
  login_card_title:'Entrar na plataforma', login_card_message:'Acesse o painel gerencial da sua empresa.',
})

const canCalendar = computed(() => capabilities.value.has('appointments'))
const canBranding = computed(() => capabilities.value.has('branding'))
const canSmtp = computed(() => capabilities.value.has('notifications'))
const versionLabel = computed(() => version.value?.release_tag || (version.value?.version ? `v${version.value.version}` : 'versão indisponível'))
const shortSha = computed(() => version.value?.build_sha ? version.value.build_sha.slice(0, 8) : '')
const selectedAppointments = computed(() => appointments.value.filter((item) => localDayKey(item.starts_at) === selectedDay.value).sort((a,b)=>+new Date(a.starts_at)-+new Date(b.starts_at)))
const monthTitle = computed(() => monthCursor.value.toLocaleDateString('pt-BR',{month:'long',year:'numeric'}))
const calendarDays = computed(() => {
  const first = new Date(monthCursor.value.getFullYear(), monthCursor.value.getMonth(), 1)
  const gridStart = new Date(first)
  gridStart.setDate(first.getDate() - first.getDay())
  return Array.from({length:42},(_,index)=>{
    const date = new Date(gridStart); date.setDate(gridStart.getDate()+index)
    const key = localDayKey(date.toISOString())
    const items = appointments.value.filter((item)=>localDayKey(item.starts_at)===key)
    return { date, key, currentMonth:date.getMonth()===monthCursor.value.getMonth(), today:key===localDayKey(new Date().toISOString()), items }
  })
})

function localDayKey(value:string):string { const d=new Date(value); const offset=d.getTimezoneOffset()*60000; return new Date(d.getTime()-offset).toISOString().slice(0,10) }
function formatTime(value:string):string { return new Date(value).toLocaleTimeString('pt-BR',{hour:'2-digit',minute:'2-digit'}) }
function statusLabel(value:string):string { return ({AWAITING_CONFIRMATION:'Aguardando confirmação',CONFIRMED:'Confirmado',CANCELLED:'Cancelado',RESCHEDULED:'Reagendado',CHECKED_IN:'Check-in',IN_PROGRESS:'Em atendimento',COMPLETED:'Concluído',NO_SHOW:'Não compareceu'} as Record<string,string>)[value] || value }
function showToast(message:string):void { toast.value=message; window.setTimeout(()=>{ if(toast.value===message) toast.value='' },3500) }

async function api<T>(path:string, init:RequestInit={}):Promise<T> {
  const response=await fetch(`${window.location.origin}/api/v1${path}`,{...init,headers:{accept:'application/json',...(init.body?{'content-type':'application/json'}:{}),...(token()?{authorization:`Bearer ${token()}`}:{}) ,...(init.headers||{})}})
  const body=await response.json().catch(()=>({})) as Partial<ApiEnvelope<T>> & {error?:{message?:string}}
  if(!response.ok) throw new Error(body.error?.message || `Falha HTTP ${response.status}`)
  return body.data as T
}

async function initialLoad():Promise<void> {
  try {
    const [caps, ver, branding] = await Promise.all([
      api<Capabilities>('/settings/capabilities'),
      api<VersionInfo>('/version'),
      loadBrandingManifest(),
    ])
    capabilities.value = new Set(caps.enabled || [])
    version.value = ver
    hydrateBranding(branding)
  } catch { /* o console principal continuará operacional */ }
}

function hydrateBranding(data:BrandingManifest):void {
  manifest.value=data
  applyBranding(data)
  const settings=data.settings || {}
  brand.value={
    public_name:data.app.public_name || data.app.name || '', slogan:data.app.slogan || '',
    logo_url:data.assets.logo_url || '', icon_url:data.assets.icon_url || '', favicon_url:data.assets.favicon_url || '',
    primary_color:data.theme.colors.primary, secondary_color:data.theme.colors.secondary, accent_color:data.theme.colors.accent,
    background_color:data.theme.colors.background, text_color:data.theme.colors.text, theme_mode:data.theme.mode,
    login_title:String(settings.login_title || 'Agenda viva, confirmações automáticas e operação em tempo real.'),
    login_message:String(settings.login_message || 'Entre no ambiente exclusivo da sua empresa para acompanhar cada mudança do atendimento.'),
    login_card_title:String(settings.login_card_title || 'Entrar na plataforma'),
    login_card_message:String(settings.login_card_message || 'Acesse o painel gerencial da sua empresa.'),
  }
}

async function open(view:ExtensionView):Promise<void> {
  active.value=view; error.value=''; loading.value=true
  try {
    if(view==='calendar') appointments.value=await api<Appointment[]>('/appointments')
    if(view==='branding') hydrateBranding(await loadBrandingManifest())
    if(view==='smtp') { const data=await api<SmtpStatus>('/notifications/smtp'); smtp.value=data; smtpPassword.value='' }
  } catch(exc) { error.value=exc instanceof Error?exc.message:'Não foi possível carregar esta área.' }
  finally { loading.value=false }
}
function close():void { active.value=''; if(['#personalizacao','#smtp'].includes(window.location.hash)) window.location.hash='dashboard' }
function routeView():ExtensionView {
  const hash=(window.location.hash||'').replace(/^#/,'')
  if(hash==='personalizacao') return 'branding'
  if(hash==='smtp') return 'smtp'
  return ''
}
async function syncRoute():Promise<void> {
  const next=routeView()
  if(next && next!==active.value) await open(next)
  else if(!next && active.value) active.value=''
}
function onRouteChange(){void syncRoute()}

function moveMonth(delta:number):void { monthCursor.value=new Date(monthCursor.value.getFullYear(),monthCursor.value.getMonth()+delta,1) }
function selectCalendarDay(key:string):void { selectedDay.value=key }

async function saveBranding(publish=false):Promise<void> {
  if(!manifest.value) return
  saving.value=true; error.value=''
  try {
    const settings={...(manifest.value.settings || {}),login_title:brand.value.login_title,login_message:brand.value.login_message,login_card_title:brand.value.login_card_title,login_card_message:brand.value.login_card_message}
    await api('/branding/profile',{method:'PUT',body:JSON.stringify({
      public_name:brand.value.public_name,slogan:brand.value.slogan,logo_url:brand.value.logo_url||null,icon_url:brand.value.icon_url||null,favicon_url:brand.value.favicon_url||null,
      primary_color:brand.value.primary_color,secondary_color:brand.value.secondary_color,accent_color:brand.value.accent_color,background_color:brand.value.background_color,text_color:brand.value.text_color,theme_mode:brand.value.theme_mode,settings,
    })})
    if(publish) await api('/branding/publish',{method:'POST',body:'{}'})
    hydrateBranding(await loadBrandingManifest())
    showToast(publish?'Personalização publicada.':'Personalização salva.')
  } catch(exc) { error.value=exc instanceof Error?exc.message:'Falha ao salvar personalização.' }
  finally { saving.value=false }
}

async function saveSmtp():Promise<void> {
  saving.value=true; error.value=''
  try {
    smtp.value=await api<SmtpStatus>('/notifications/smtp',{method:'PUT',body:JSON.stringify({...smtp.value,password:smtpPassword.value||undefined})})
    smtpPassword.value=''; showToast('Conta SMTP salva com segurança.')
  } catch(exc) { error.value=exc instanceof Error?exc.message:'Falha ao salvar SMTP.' }
  finally { saving.value=false }
}
async function testSmtp():Promise<void> {
  saving.value=true; error.value=''
  try { await api('/notifications/smtp/test',{method:'POST',body:JSON.stringify({recipient:testRecipient.value})}); showToast(`E-mail de teste enviado para ${testRecipient.value}.`) }
  catch(exc) { error.value=exc instanceof Error?exc.message:'Falha no teste SMTP.' }
  finally { saving.value=false }
}

watch(active,(value)=>document.body.classList.toggle('sp-extension-open',Boolean(value)))
onMounted(async()=>{ await nextTick(); portalReady.value=Boolean(document.querySelector('.tenant-console .main-content')); await initialLoad(); window.addEventListener('hashchange',onRouteChange); await syncRoute() })
onUnmounted(()=>{document.body.classList.remove('sp-extension-open');window.removeEventListener('hashchange',onRouteChange)})
</script>

<template>
  <Teleport v-if="portalReady && manifest?.assets.logo_url" to=".tenant-console .sidebar .brand">
    <img class="sp-sidebar-logo" :src="manifest.assets.logo_url" :alt="manifest.app.public_name" />
  </Teleport>
  <Teleport v-if="portalReady" to=".tenant-console .sidebar-footer">
    <div class="sp-version"><strong>{{ versionLabel }}</strong><small v-if="shortSha">build {{ shortSha }}</small></div>
  </Teleport>

  <Teleport v-if="portalReady && active" to=".tenant-console .main-content">
    <section class="sp-extension-root">
      <header class="sp-extension-header"><div><span>Scheduler Pro</span><h1>{{ active==='calendar'?'Calendário da agenda':active==='branding'?'Personalização do tenant':'E-mail da agenda' }}</h1><p v-if="active==='calendar'">Clique em qualquer dia para acompanhar todos os atendimentos e seus estados.</p><p v-else-if="active==='branding'">Logo, ícone, favicon, cores e textos próprios da tela de acesso.</p><p v-else>Configure a conta SMTP que envia confirmações, cancelamentos e lembretes aos clientes.</p></div><button class="sp-icon-button" @click="close"><X :size="20"/></button></header>
      <p v-if="toast" class="sp-success">{{ toast }}</p><p v-if="error" class="sp-error">{{ error }}</p>
      <div v-if="loading" class="sp-loading"><RefreshCw :size="22" class="spin"/> Carregando...</div>

      <div v-else-if="active==='calendar'" class="sp-calendar-layout">
        <article class="sp-card sp-calendar-card">
          <div class="sp-calendar-head"><button class="sp-icon-button" @click="moveMonth(-1)"><ChevronLeft :size="19"/></button><strong>{{ monthTitle }}</strong><button class="sp-icon-button" @click="moveMonth(1)"><ChevronRight :size="19"/></button></div>
          <div class="sp-weekdays"><span v-for="day in ['Dom','Seg','Ter','Qua','Qui','Sex','Sáb']" :key="day">{{ day }}</span></div>
          <div class="sp-calendar-grid"><button v-for="cell in calendarDays" :key="cell.key" :class="{outside:!cell.currentMonth,today:cell.today,selected:selectedDay===cell.key,occupied:cell.items.length}" @click="selectCalendarDay(cell.key)"><span>{{ cell.date.getDate() }}</span><small v-if="cell.items.length">{{ cell.items.length }}</small><i v-if="cell.items.length"></i></button></div>
        </article>
        <article class="sp-card sp-day-card"><div class="sp-day-head"><div><span>Dia selecionado</span><h2>{{ new Date(selectedDay+'T12:00:00').toLocaleDateString('pt-BR',{dateStyle:'full'}) }}</h2></div><strong>{{ selectedAppointments.length }} agenda(s)</strong></div><div class="sp-day-list"><div v-for="item in selectedAppointments" :key="item.id" class="sp-appointment"><time>{{ formatTime(item.starts_at) }}</time><div><strong>{{ item.customer_name }}</strong><span>{{ item.service_name }} · {{ item.professional_name }}</span></div><em :class="item.status.toLowerCase()">{{ statusLabel(item.status) }}</em></div><div v-if="!selectedAppointments.length" class="sp-empty"><CalendarDays :size="42"/><strong>Nenhum agendamento neste dia.</strong><span>Escolha outro dia ou use “Novo” na Agenda para criar um atendimento.</span></div></div></article>
      </div>

      <div v-else-if="active==='branding'" class="sp-form-layout">
        <article class="sp-card"><h2>Identidade visual</h2><p>As URLs podem apontar para arquivos já hospedados no seu domínio/CDN. O favicon é aplicado no navegador e PWA.</p><div class="sp-form-grid"><label>Nome público<input v-model="brand.public_name"/></label><label>Slogan<input v-model="brand.slogan"/></label><label class="wide">Logo<input v-model="brand.logo_url" placeholder="https://.../logo.svg"/></label><label>Ícone<input v-model="brand.icon_url" placeholder="https://.../icon.png"/></label><label>Favicon<input v-model="brand.favicon_url" placeholder="https://.../favicon.ico"/></label></div><div class="sp-color-grid"><label>Primária<input v-model="brand.primary_color" type="color"/></label><label>Secundária<input v-model="brand.secondary_color" type="color"/></label><label>Destaque<input v-model="brand.accent_color" type="color"/></label><label>Fundo<input v-model="brand.background_color" type="color"/></label><label>Texto<input v-model="brand.text_color" type="color"/></label></div></article>
        <article class="sp-card"><h2>Tela de login</h2><p>Personalize as frases sem alterar o núcleo da aplicação.</p><div class="sp-form-grid one"><label>Título principal<input v-model="brand.login_title"/></label><label>Texto principal<textarea v-model="brand.login_message"/></label><label>Título do formulário<input v-model="brand.login_card_title"/></label><label>Texto do formulário<textarea v-model="brand.login_card_message"/></label></div><div class="sp-actions"><button class="sp-btn" :disabled="saving" @click="saveBranding(false)"><Save :size="16"/> Salvar</button><button class="sp-btn primary" :disabled="saving" @click="saveBranding(true)">Publicar personalização</button></div></article>
      </div>

      <div v-else-if="active==='smtp'" class="sp-form-layout smtp">
        <article class="sp-card"><div class="sp-smtp-status"><div><span>Envio por e-mail</span><h2>{{ smtp.configured ? (smtp.enabled?'Ativo':'Configurado, porém desativado') : 'Não configurado' }}</h2></div><label class="sp-switch"><input v-model="smtp.enabled" type="checkbox"/><span></span></label></div><div class="sp-form-grid"><label>Servidor SMTP<input v-model="smtp.host" placeholder="smtp.seudominio.com.br"/></label><label>Porta<input v-model.number="smtp.port" type="number" min="1" max="65535"/></label><label>Usuário<input v-model="smtp.username" autocomplete="username"/></label><label>Senha<input v-model="smtpPassword" type="password" autocomplete="new-password" :placeholder="smtp.password_configured?'•••••••• (manter atual)':'Senha SMTP'"/></label><label>E-mail remetente<input v-model="smtp.from_email" type="email"/></label><label>Nome remetente<input v-model="smtp.from_name"/></label><label>Responder para<input v-model="smtp.reply_to" type="email"/></label><label>Timeout (s)<input v-model.number="smtp.timeout_seconds" type="number" min="1" max="120"/></label></div><div class="sp-security"><label><input v-model="smtp.use_tls" type="checkbox" @change="smtp.use_tls && (smtp.use_ssl=false)"/> STARTTLS</label><label><input v-model="smtp.use_ssl" type="checkbox" @change="smtp.use_ssl && (smtp.use_tls=false)"/> SSL/TLS direto</label></div><div class="sp-actions"><button class="sp-btn primary" :disabled="saving" @click="saveSmtp"><Save :size="16"/> Salvar SMTP</button></div></article>
        <article class="sp-card"><h2>Testar configuração</h2><p>Envia uma mensagem real usando exatamente a conta acima já salva.</p><label class="sp-test-recipient">Destinatário<input v-model="testRecipient" type="email"/></label><button class="sp-btn" :disabled="saving||!smtp.configured" @click="testSmtp"><Send :size="16"/> Enviar e-mail de teste</button><div class="sp-email-note"><Mail :size="22"/><div><strong>Agenda multicanal</strong><span>Com SMTP ativo, clientes que possuem e-mail recebem confirmação, reagendamento, cancelamento e lembretes, em paralelo ao WhatsApp quando este estiver disponível.</span></div></div></article>
      </div>
    </section>
  </Teleport>
</template>

<style>
.sp-extension-open .tenant-console .main-content>section:not(.sp-extension-root),.sp-extension-open .tenant-console .main-content>p:not(.sp-success):not(.sp-error){display:none!important}.sp-extension-root{display:grid;gap:18px;animation:sp-enter .16s ease-out}.sp-extension-header{display:flex;justify-content:space-between;gap:20px;align-items:flex-start}.sp-extension-header span{font-size:11px;font-weight:900;color:#2563eb;text-transform:uppercase;letter-spacing:.08em}.sp-extension-header h1{margin:4px 0 6px;font-size:30px;letter-spacing:-.035em}.sp-extension-header p{margin:0;color:#64748b}.sp-icon-button{width:38px;height:38px;border:1px solid #e2e8f0;border-radius:11px;background:#fff;display:grid;place-items:center;cursor:pointer;color:#475569}.sp-version{display:grid;padding:8px 12px 4px;color:#64748b}.sp-version strong{font-size:11px;color:#94a3b8}.sp-version small{font-size:9px;margin-top:2px}.tenant-console .sidebar .brand:has(.sp-sidebar-logo)>.brand-mark{display:none}.sp-sidebar-logo{max-width:150px;max-height:42px;object-fit:contain;order:-1}.sp-extension-nav span{white-space:nowrap}.sp-success,.sp-error{margin:0;padding:11px 13px;border-radius:12px;font-size:12px;font-weight:700}.sp-success{background:#ecfdf5;color:#047857}.sp-error{background:#fef2f2;color:#b91c1c}.sp-loading{min-height:280px;display:grid;place-items:center;align-content:center;gap:10px;color:#64748b}.spin{animation:spin 1s linear infinite}.sp-card{background:#fff;border:1px solid #e2e8f0;border-radius:18px;padding:20px;box-shadow:0 8px 28px rgba(15,23,42,.04)}.sp-card h2{margin:0 0 5px;font-size:19px}.sp-card>p{margin:0 0 18px;color:#64748b;font-size:13px}.sp-calendar-layout{display:grid;grid-template-columns:minmax(460px,1.05fr) minmax(360px,.95fr);gap:18px}.sp-calendar-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:18px;text-transform:capitalize}.sp-weekdays,.sp-calendar-grid{display:grid;grid-template-columns:repeat(7,1fr)}.sp-weekdays span{text-align:center;padding:8px 2px;color:#94a3b8;font-size:10px;font-weight:900;text-transform:uppercase}.sp-calendar-grid{border-left:1px solid #eef2f7;border-top:1px solid #eef2f7}.sp-calendar-grid button{position:relative;min-height:76px;border:0;border-right:1px solid #eef2f7;border-bottom:1px solid #eef2f7;background:#fff;text-align:left;padding:10px;cursor:pointer;color:#334155}.sp-calendar-grid button:hover{background:#f8fafc}.sp-calendar-grid button.outside{color:#cbd5e1;background:#fbfdff}.sp-calendar-grid button.today span{display:inline-grid;place-items:center;width:25px;height:25px;border-radius:50%;background:#eff6ff;color:#2563eb;font-weight:900}.sp-calendar-grid button.selected{box-shadow:inset 0 0 0 2px #2563eb;background:#eff6ff}.sp-calendar-grid button small{position:absolute;right:8px;top:9px;border-radius:999px;padding:2px 6px;background:#e0e7ff;color:#4338ca;font-size:9px;font-weight:900}.sp-calendar-grid button i{position:absolute;left:10px;bottom:9px;width:7px;height:7px;border-radius:50%;background:#10b981}.sp-day-head{display:flex;justify-content:space-between;gap:15px;border-bottom:1px solid #eef2f7;padding-bottom:14px}.sp-day-head span{color:#64748b;font-size:10px;font-weight:900;text-transform:uppercase}.sp-day-head h2{margin-top:5px;text-transform:capitalize}.sp-day-head>strong{font-size:11px;color:#2563eb}.sp-day-list{display:grid;gap:8px;margin-top:14px}.sp-appointment{display:grid;grid-template-columns:54px 1fr auto;gap:12px;align-items:center;padding:12px;border:1px solid #e2e8f0;border-radius:13px}.sp-appointment time{font-weight:900;color:#0f172a}.sp-appointment div{display:grid;gap:2px}.sp-appointment div span{font-size:11px;color:#64748b}.sp-appointment em{font-style:normal;font-size:9px;font-weight:900;padding:5px 7px;border-radius:999px;background:#f1f5f9;color:#475569}.sp-appointment em.confirmed{background:#dcfce7;color:#166534}.sp-appointment em.cancelled{background:#fee2e2;color:#991b1b}.sp-empty{min-height:260px;display:grid;place-items:center;align-content:center;text-align:center;color:#94a3b8;gap:8px}.sp-empty strong{color:#475569}.sp-empty span{max-width:290px;font-size:12px}.sp-form-layout{display:grid;grid-template-columns:1.05fr .95fr;gap:18px}.sp-form-layout.smtp{grid-template-columns:1.2fr .8fr}.sp-form-grid{display:grid;grid-template-columns:1fr 1fr;gap:13px}.sp-form-grid.one{grid-template-columns:1fr}.sp-form-grid label,.sp-test-recipient{display:grid;gap:6px;font-size:11px;font-weight:800;color:#475569}.sp-form-grid .wide{grid-column:1/-1}.sp-form-grid input,.sp-form-grid textarea,.sp-test-recipient input{width:100%;min-height:43px;border:1px solid #cbd5e1;border-radius:10px;padding:9px 11px;font:inherit;outline:none}.sp-form-grid textarea{min-height:82px;resize:vertical}.sp-form-grid input:focus,.sp-form-grid textarea:focus,.sp-test-recipient input:focus{border-color:#2563eb;box-shadow:0 0 0 3px rgba(37,99,235,.09)}.sp-color-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:9px;margin-top:15px}.sp-color-grid label{font-size:9px;font-weight:800;color:#64748b}.sp-color-grid input{width:100%;height:38px;border:0;background:none;padding:0}.sp-actions{display:flex;justify-content:flex-end;gap:9px;margin-top:18px}.sp-btn{min-height:40px;border:1px solid #cbd5e1;border-radius:10px;background:#fff;padding:0 14px;display:inline-flex;align-items:center;justify-content:center;gap:7px;font:inherit;font-size:11px;font-weight:900;cursor:pointer}.sp-btn.primary{border-color:#2563eb;background:#2563eb;color:#fff}.sp-btn:disabled{opacity:.55;cursor:not-allowed}.sp-smtp-status{display:flex;align-items:center;justify-content:space-between;margin-bottom:18px}.sp-smtp-status span{font-size:10px;color:#64748b;text-transform:uppercase;font-weight:900}.sp-smtp-status h2{margin-top:4px}.sp-switch input{display:none}.sp-switch span{display:block;width:48px;height:27px;border-radius:999px;background:#cbd5e1;position:relative;cursor:pointer}.sp-switch span:after{content:"";position:absolute;top:4px;left:4px;width:19px;height:19px;border-radius:50%;background:#fff;transition:.15s}.sp-switch input:checked+span{background:#10b981}.sp-switch input:checked+span:after{transform:translateX(21px)}.sp-security{display:flex;gap:16px;margin-top:14px;font-size:11px;color:#475569}.sp-email-note{display:flex;gap:12px;margin-top:22px;padding:14px;border-radius:13px;background:#eff6ff;color:#1e40af}.sp-email-note div{display:grid;gap:4px}.sp-email-note span{font-size:11px;line-height:1.5}@keyframes sp-enter{from{opacity:0;transform:translateY(5px)}to{opacity:1;transform:none}}@keyframes spin{to{transform:rotate(360deg)}}
@media(max-width:1050px){.sp-calendar-layout,.sp-form-layout,.sp-form-layout.smtp{grid-template-columns:1fr}.sp-calendar-grid button{min-height:66px}}
@media(max-width:760px){.tenant-console.mobileOpen .sidebar{width:min(88vw,320px)!important}.tenant-console.mobileOpen .sidebar .nav-item span,.tenant-console.mobileOpen .sidebar .brand>div:not(.brand-mark),.tenant-console.mobileOpen .sidebar .sidebar-footer .nav-item span,.tenant-console.mobileOpen .sidebar .version-info{display:block!important}.tenant-console.mobileOpen .sidebar .nav-item{justify-content:flex-start!important;padding-left:14px!important;gap:11px!important}.tenant-console.mobileOpen .sp-sidebar-logo{display:block!important;max-width:150px}.sp-extension-header h1{font-size:25px}.sp-calendar-card,.sp-day-card,.sp-card{padding:15px}.sp-calendar-grid button{min-height:54px;padding:7px}.sp-calendar-grid button i{left:7px;bottom:6px}.sp-appointment{grid-template-columns:48px 1fr}.sp-appointment em{grid-column:2}.sp-form-grid{grid-template-columns:1fr}.sp-form-grid .wide{grid-column:auto}.sp-color-grid{grid-template-columns:repeat(3,1fr)}}
@media(max-width:520px){.sp-calendar-grid button{min-height:48px}.sp-calendar-grid button small{display:none}.sp-weekdays span{font-size:8px}.sp-extension-root{gap:12px}.sp-security{display:grid;gap:8px}.sp-actions{flex-direction:column}.sp-btn{width:100%}}
</style>
