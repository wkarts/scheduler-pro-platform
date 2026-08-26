<script setup lang="ts">
import { nextTick, onMounted, ref } from 'vue'
import { CalendarClock, MapPin, MessageCircle, Save, Settings, ShieldCheck, X } from 'lucide-vue-next'

type Tab = 'agenda' | 'phone' | 'security' | 'whatsapp'
type Envelope<T> = { data?: T; error?: { message?: string } }
type BookingParameters = {
  service_mode: 'DISABLED' | 'OPTIONAL' | 'REQUIRED'
  email_mode: 'DISABLED' | 'OPTIONAL' | 'REQUIRED'
  default_duration_minutes: number
  simultaneous: { public: boolean; internal: boolean; capacity: number }
  minimum_notice_minutes: number
  phone: { country: string; country_code: string; area_code: string; add_ninth_digit: boolean }
}
type TwoFactorState = { enabled:boolean; configured:boolean; mandatory:boolean; second_factor_verified:boolean }
type Enrollment = { manual_key:string; qr_code:string; otpauth_uri:string }
type WhatsStatus = {
  product?:string
  instance_name?:string
  status:string
  connection_method?:string|null
  phone?:string|null
  qr?:{base64?:string|null;pairing_code?:string|null;code?:string|null;count?:number|null}|null
  pairing_code?:string|null
  provider?:Record<string,unknown>
}
type Capabilities = { enabled:string[] }

const active = ref(false)
const tab = ref<Tab>('agenda')
const portalReady = ref(false)
const loading = ref(false)
const saving = ref(false)
const errorMessage = ref('')
const successMessage = ref('')
const params = ref<BookingParameters>({
  service_mode:'REQUIRED', email_mode:'OPTIONAL', default_duration_minutes:60,
  simultaneous:{public:false,internal:false,capacity:1}, minimum_notice_minutes:1440,
  phone:{country:'BR',country_code:'55',area_code:'',add_ninth_digit:true},
})
const twoFactor = ref<TwoFactorState | null>(null)
const enrollment = ref<Enrollment | null>(null)
const twoFactorCode = ref('')
const disableCode = ref('')
const whatsEnabled = ref(false)
const whats = ref<WhatsStatus | null>(null)
const pairingPhone = ref('')
const pairingCode = ref('')
const testPhone = ref('')
const testMessage = ref('Teste de comunicação do Scheduler Pro.')

async function api<T>(path:string, init:RequestInit={}):Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    ...init,
    cache:'no-store',
    headers:{
      accept:'application/json',
      ...(init.body ? {'content-type':'application/json'} : {}),
      ...(init.headers || {}),
    },
  })
  const body = await response.json().catch(()=>({})) as Envelope<T>
  if(!response.ok) throw new Error(body.error?.message || `Falha HTTP ${response.status}`)
  return body.data as T
}

function toast(message:string):void {
  successMessage.value=message
  window.setTimeout(()=>{ if(successMessage.value===message) successMessage.value='' },3500)
}
function failure(error:unknown, fallback:string):void {
  errorMessage.value=error instanceof Error ? error.message : fallback
}
function whatsStatusLabel(status?:string|null):string {
  const labels:Record<string,string>={
    DISCONNECTED:'Desconectado',
    CONNECTING:'Conectando',
    CONNECTED:'Conectado',
    RECONNECTING:'Reconectando',
    FAILED:'Falha',
  }
  return labels[String(status || '').toUpperCase()] || 'Desconhecido'
}

async function loadBase():Promise<void> {
  loading.value=true; errorMessage.value=''
  try {
    const [booking, security, capabilities] = await Promise.all([
      api<BookingParameters>('/settings/booking'),
      api<TwoFactorState>('/auth/2fa/state'),
      api<Capabilities>('/settings/capabilities'),
    ])
    params.value=booking
    twoFactor.value=security
    whatsEnabled.value=(capabilities.enabled || []).includes('whatsapp')
    if(whatsEnabled.value) await loadWhatsStatus(false)
  } catch(error) { failure(error,'Não foi possível carregar as configurações.') }
  finally { loading.value=false }
}

async function open():Promise<void> { active.value=true; await loadBase() }
function close():void { active.value=false; enrollment.value=null; pairingCode.value=''; errorMessage.value='' }

async function saveBooking():Promise<void> {
  saving.value=true; errorMessage.value=''
  try {
    params.value=await api<BookingParameters>('/settings/booking',{method:'PUT',body:JSON.stringify(params.value)})
    toast('Parâmetros salvos.')
    window.dispatchEvent(new CustomEvent('scheduler-pro-revalidate-current-view'))
  } catch(error) { failure(error,'Falha ao salvar parâmetros.') }
  finally { saving.value=false }
}

async function beginTwoFactor():Promise<void> {
  saving.value=true; errorMessage.value=''
  try { enrollment.value=await api<Enrollment>('/auth/2fa/setup',{method:'POST',body:'{}'}) }
  catch(error) { failure(error,'Não foi possível iniciar a configuração de segurança.') }
  finally { saving.value=false }
}
async function confirmTwoFactor():Promise<void> {
  saving.value=true; errorMessage.value=''
  try {
    await api('/auth/2fa/confirm',{method:'POST',body:JSON.stringify({code:twoFactorCode.value})})
    twoFactor.value=await api<TwoFactorState>('/auth/2fa/state')
    enrollment.value=null; twoFactorCode.value=''; toast('Verificação em duas etapas ativada.')
  } catch(error) { failure(error,'Código inválido.') }
  finally { saving.value=false }
}
async function disableTwoFactor():Promise<void> {
  saving.value=true; errorMessage.value=''
  try {
    await api('/auth/2fa/disable',{method:'POST',body:JSON.stringify({code:disableCode.value})})
    twoFactor.value=await api<TwoFactorState>('/auth/2fa/state')
    disableCode.value=''; toast('Verificação em duas etapas desativada.')
  } catch(error) { failure(error,'Não foi possível desativar a verificação.') }
  finally { saving.value=false }
}

async function loadWhatsStatus(showError=true):Promise<void> {
  if(!whatsEnabled.value) return
  try { whats.value=await api<WhatsStatus>('/integrations/whatsapp/status') }
  catch(error) { if(showError) failure(error,'Não foi possível verificar a conexão.') }
}
async function connectQr():Promise<void> {
  saving.value=true; errorMessage.value=''; pairingCode.value=''
  try { whats.value=await api<WhatsStatus>('/integrations/whatsapp/connect/qr',{method:'POST',body:'{}'}) }
  catch(error) { failure(error,'Não foi possível iniciar a conexão.') }
  finally { saving.value=false }
}
async function connectPairing():Promise<void> {
  saving.value=true; errorMessage.value=''
  try {
    const data=await api<WhatsStatus>('/integrations/whatsapp/connect/pairing',{method:'POST',body:JSON.stringify({phone:pairingPhone.value})})
    whats.value=data; pairingCode.value=String(data.pairing_code || data.qr?.pairing_code || '')
  } catch(error) { failure(error,'Não foi possível gerar o código de pareamento.') }
  finally { saving.value=false }
}
async function reconnectWhats():Promise<void> {
  saving.value=true; errorMessage.value=''
  try { whats.value=await api<WhatsStatus>('/integrations/whatsapp/reconnect',{method:'POST',body:'{}'}) }
  catch(error) { failure(error,'Não foi possível reconectar.') }
  finally { saving.value=false }
}
async function disconnectWhats():Promise<void> {
  saving.value=true; errorMessage.value=''
  try { whats.value=await api<WhatsStatus>('/integrations/whatsapp/disconnect',{method:'POST',body:'{}'}); pairingCode.value=''; toast('WhatsApp desconectado.') }
  catch(error) { failure(error,'Não foi possível desconectar.') }
  finally { saving.value=false }
}
async function testWhats():Promise<void> {
  saving.value=true; errorMessage.value=''
  try { await api('/integrations/whatsapp/test',{method:'POST',body:JSON.stringify({phone:testPhone.value,message:testMessage.value})}); toast('Mensagem de teste aceita para envio.') }
  catch(error) { failure(error,'Não foi possível enviar o teste.') }
  finally { saving.value=false }
}

onMounted(async()=>{
  await nextTick()
  window.requestAnimationFrame(()=>{ portalReady.value=Boolean(document.querySelector('.tenant-console .nav-list')&&document.querySelector('.tenant-console .main-content')) })
})
</script>

<template>
  <Teleport v-if="portalReady" to=".tenant-console .nav-list">
    <button class="nav-item sp-config-nav" @click="open"><Settings :size="19"/><span>Configurações</span></button>
  </Teleport>

  <Teleport v-if="portalReady && active" to=".tenant-console .main-content">
    <section class="sp-config-root">
      <header class="sp-config-header">
        <div><span>Scheduler Pro</span><h1>Configurações</h1><p>Parâmetros da empresa, agenda, segurança e comunicação.</p></div>
        <button class="icon" aria-label="Fechar" @click="close"><X :size="20"/></button>
      </header>
      <nav class="sp-config-tabs" aria-label="Seções de configuração">
        <button :class="{active:tab==='agenda'}" @click="tab='agenda'"><CalendarClock :size="17"/> Agenda</button>
        <button :class="{active:tab==='phone'}" @click="tab='phone'"><MapPin :size="17"/> Telefones e Localização</button>
        <button :class="{active:tab==='security'}" @click="tab='security'"><ShieldCheck :size="17"/> Segurança</button>
        <button v-if="whatsEnabled" :class="{active:tab==='whatsapp'}" @click="tab='whatsapp'"><MessageCircle :size="17"/> ARGWS Whatsapp API</button>
      </nav>

      <p v-if="errorMessage" class="sp-config-error" role="alert">{{ errorMessage }}</p>
      <p v-if="successMessage" class="sp-config-success">{{ successMessage }}</p>
      <div v-if="loading" class="sp-config-loading">Carregando configurações…</div>

      <template v-else>
        <div v-if="tab==='agenda'" class="sp-config-grid">
          <article class="card">
            <h2>Dados do agendamento</h2>
            <p>Nome e telefone/WhatsApp são sempre obrigatórios.</p>
            <label>Serviço
              <select v-model="params.service_mode">
                <option value="DISABLED">Desativado</option><option value="OPTIONAL">Opcional</option><option value="REQUIRED">Obrigatório</option>
              </select>
            </label>
            <label>E-mail
              <select v-model="params.email_mode">
                <option value="DISABLED">Não solicitar</option><option value="OPTIONAL">Opcional</option><option value="REQUIRED">Obrigatório</option>
              </select>
            </label>
            <label>Duração padrão sem serviço <span>minutos</span><input v-model.number="params.default_duration_minutes" type="number" min="5" max="720"/></label>
          </article>
          <article class="card">
            <h2>Capacidade e antecedência</h2>
            <label class="check"><input v-model="params.simultaneous.public" type="checkbox"/> Permitir agendamentos simultâneos na agenda pública</label>
            <label class="check"><input v-model="params.simultaneous.internal" type="checkbox"/> Permitir agendamentos simultâneos na agenda interna</label>
            <label>Capacidade máxima simultânea<input v-model.number="params.simultaneous.capacity" type="number" min="1" max="100"/></label>
            <label>Antecedência mínima <span>minutos — 1440 = 24 horas</span><input v-model.number="params.minimum_notice_minutes" type="number" min="0"/></label>
          </article>
          <div class="actions"><button class="primary" :disabled="saving" @click="saveBooking"><Save :size="17"/> Salvar parâmetros da agenda</button></div>
        </div>

        <div v-else-if="tab==='phone'" class="sp-config-grid one">
          <article class="card">
            <h2>Telefones e Localização</h2><p>Todos os números são convertidos para um formato operacional único antes de pesquisar, gravar ou enviar mensagens.</p>
            <div class="fields">
              <label>País padrão<input v-model.trim="params.phone.country" maxlength="3" placeholder="BR"/></label>
              <label>Código internacional<input v-model.trim="params.phone.country_code" inputmode="numeric" placeholder="55"/></label>
              <label>DDD padrão<input v-model.trim="params.phone.area_code" inputmode="numeric" placeholder="75"/></label>
              <label class="check"><input v-model="params.phone.add_ninth_digit" type="checkbox"/> Adicionar nono dígito automaticamente quando aplicável</label>
            </div>
            <div class="example"><strong>Exemplo</strong><span>Com Brasil +55, DDD 75 e nono dígito ativo:</span><code>88881111 → 5575988881111</code></div>
          </article>
          <div class="actions"><button class="primary" :disabled="saving" @click="saveBooking"><Save :size="17"/> Salvar telefones e localização</button></div>
        </div>

        <div v-else-if="tab==='security'" class="sp-config-grid one">
          <article class="card">
            <h2>Verificação em duas etapas</h2><p>Opcional para a empresa. Novas e atuais empresas permanecem com o recurso desativado até ativação explícita.</p>
            <div v-if="twoFactor?.enabled" class="status good"><ShieldCheck :size="20"/><div><strong>Ativada</strong><span>O código do aplicativo autenticador será solicitado nos próximos acessos.</span></div></div>
            <template v-if="!twoFactor?.enabled && !enrollment">
              <button class="primary" :disabled="saving" @click="beginTwoFactor">Configurar aplicativo autenticador</button>
            </template>
            <template v-else-if="enrollment">
              <div class="setup"><img :src="enrollment.qr_code" alt="QR Code do aplicativo autenticador"/><div><strong>Leia o QR Code</strong><p>Ou informe manualmente esta chave:</p><code>{{ enrollment.manual_key }}</code></div></div>
              <label>Código de 6 dígitos<input v-model="twoFactorCode" inputmode="numeric" autocomplete="one-time-code" maxlength="8" placeholder="000000"/></label>
              <button class="primary" :disabled="saving || twoFactorCode.length < 6" @click="confirmTwoFactor">Ativar verificação</button>
            </template>
            <template v-else>
              <hr/><h3>Desativar</h3><p>Para desativar, confirme com um código atual do autenticador.</p>
              <label>Código atual<input v-model="disableCode" inputmode="numeric" autocomplete="one-time-code" maxlength="8" placeholder="000000"/></label>
              <button class="danger" :disabled="saving || disableCode.length < 6" @click="disableTwoFactor">Desativar verificação</button>
            </template>
          </article>
        </div>

        <div v-else-if="tab==='whatsapp'" class="sp-config-grid one">
          <article class="card">
            <div class="whats-head"><div><h2>ARGWS Whatsapp API</h2><p>Conecte por QR Code ou por código de pareamento.</p></div><span class="status-pill">{{ whatsStatusLabel(whats?.status) }}</span></div>
            <div class="connection-options">
              <section><h3>QR Code</h3><p>Abra WhatsApp → Dispositivos conectados → Vincular dispositivo.</p><button class="secondary" :disabled="saving" @click="connectQr">Gerar / atualizar QR Code</button><div v-if="whats?.qr?.base64" class="whats-qr"><img :src="whats.qr.base64" alt="QR Code para conexão do WhatsApp"/></div></section>
              <section><h3>Código de pareamento</h3><p>Informe o telefone. A plataforma normaliza o número antes de solicitar o código.</p><label>Telefone<input v-model="pairingPhone" inputmode="tel" placeholder="(75) 98888-1111"/></label><button class="secondary" :disabled="saving || pairingPhone.length < 8" @click="connectPairing">Gerar código</button><div v-if="pairingCode" class="pairing"><span>Código de pareamento</span><strong>{{ pairingCode }}</strong></div></section>
            </div>
            <div class="actions wrap"><button class="secondary" :disabled="saving" @click="loadWhatsStatus()">Verificar conexão</button><button class="secondary" :disabled="saving" @click="reconnectWhats">Reconectar</button><button class="danger" :disabled="saving" @click="disconnectWhats">Desconectar</button></div>
            <hr/><h3>Testar envio</h3><div class="fields"><label>Telefone<input v-model="testPhone" inputmode="tel" placeholder="(75) 98888-1111"/></label><label class="wide">Mensagem<input v-model="testMessage"/></label></div><button class="secondary" :disabled="saving || testPhone.length < 8" @click="testWhats">Enviar teste</button>
          </article>
        </div>
      </template>
    </section>
  </Teleport>
</template>

<style scoped>
.sp-config-root{display:grid;gap:18px;padding:clamp(16px,3vw,30px);min-height:100%;background:var(--sp-bg,#f6f8fc);color:var(--sp-text,#172033)}
.sp-config-header{display:flex;justify-content:space-between;gap:20px;align-items:flex-start}.sp-config-header span{color:#526fd7;font-size:.72rem;font-weight:800;text-transform:uppercase;letter-spacing:.08em}.sp-config-header h1{margin:4px 0;font-size:clamp(1.7rem,4vw,2.35rem)}.sp-config-header p,.card p{margin:0;color:#697287;line-height:1.5}.icon{width:42px;height:42px;border:0;border-radius:12px;background:#fff;display:grid;place-items:center;cursor:pointer}
.sp-config-tabs{display:flex;gap:8px;overflow:auto;padding-bottom:4px}.sp-config-tabs button{display:flex;gap:7px;align-items:center;white-space:nowrap;border:1px solid #dfe4ee;background:#fff;padding:10px 13px;border-radius:12px;font:inherit;font-weight:700;cursor:pointer}.sp-config-tabs button.active{background:#263f9c;color:#fff;border-color:#263f9c}
.sp-config-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.sp-config-grid.one{grid-template-columns:1fr}.card{display:grid;gap:16px;padding:20px;border:1px solid #e2e6ef;border-radius:18px;background:#fff;box-shadow:0 7px 28px rgba(22,34,65,.05)}.card h2,.card h3{margin:0}.card hr{width:100%;border:0;border-top:1px solid #e7eaf0}
label{display:grid;gap:7px;font-weight:700;color:#3b4558}label>span{font-size:.78rem;font-weight:500;color:#7a8497}input,select{box-sizing:border-box;width:100%;min-height:44px;border:1px solid #cfd6e2;border-radius:10px;padding:9px 11px;background:#fff;font:inherit;color:inherit}.check{display:flex;align-items:center;gap:9px}.check input{width:18px;min-height:18px;flex:0 0 auto}.fields{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.fields .wide{grid-column:span 2}.actions{grid-column:1/-1;display:flex;justify-content:flex-end;gap:8px}.actions.wrap{justify-content:flex-start;flex-wrap:wrap}
button.primary,button.secondary,button.danger{display:inline-flex;align-items:center;justify-content:center;gap:7px;min-height:44px;border-radius:11px;padding:0 15px;font:inherit;font-weight:800;cursor:pointer}.primary{border:0;background:#3151cf;color:#fff}.secondary{border:1px solid #ccd4e2;background:#fff;color:#28334a}.danger{border:1px solid #efcaca;background:#fff7f7;color:#aa2525}button:disabled{opacity:.55;cursor:progress}
.example{display:grid;gap:5px;padding:14px;border-radius:13px;background:#f4f6fb}.example code{font-size:1rem;font-weight:800;color:#263f9c}.status{display:flex;align-items:center;gap:10px;padding:14px;border-radius:13px}.status.good{background:#eefaf3;color:#197144}.status div{display:grid;gap:3px}.status span{font-size:.85rem;color:#52705e}.setup{display:grid;grid-template-columns:180px 1fr;gap:18px;align-items:center}.setup img,.whats-qr img{display:block;width:100%;height:auto}.setup img{padding:8px;box-sizing:border-box;border:1px solid #e0e4ec;border-radius:14px}.setup code{display:block;overflow-wrap:anywhere;padding:10px;border-radius:9px;background:#f3f5f8}.whats-head{display:flex;justify-content:space-between;gap:16px}.status-pill{height:max-content;padding:7px 10px;border-radius:999px;background:#edf1ff;color:#2945ad;font-weight:800;font-size:.82rem}.connection-options{display:grid;grid-template-columns:1fr 1fr;gap:14px}.connection-options>section{display:grid;gap:11px;padding:16px;border:1px solid #e3e7ee;border-radius:15px}.connection-options p{font-size:.9rem}.whats-qr{width:min(100%,240px);justify-self:center;padding:10px;border:1px solid #e1e5ed;border-radius:15px}.pairing{display:grid;gap:4px;padding:13px;border-radius:12px;background:#f2f5ff;text-align:center}.pairing span{font-size:.8rem}.pairing strong{font-size:1.45rem;letter-spacing:.08em}.sp-config-error,.sp-config-success,.sp-config-loading{margin:0;padding:12px 14px;border-radius:12px}.sp-config-error{background:#fff0f0;color:#a62323}.sp-config-success{background:#eefaf3;color:#197144}.sp-config-loading{background:#fff;color:#657086}
@media(max-width:800px){.sp-config-grid,.connection-options{grid-template-columns:1fr}.fields{grid-template-columns:1fr}.fields .wide{grid-column:auto}.setup{grid-template-columns:1fr}.setup img{width:min(65vw,220px);justify-self:center}.actions{justify-content:stretch}.actions button{flex:1}.sp-config-root{padding:14px}.sp-config-tabs{margin-inline:-14px;padding-inline:14px}.whats-head{align-items:flex-start;flex-direction:column}}
</style>