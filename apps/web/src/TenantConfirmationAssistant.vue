<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { Clock3, MessageCircle, RefreshCw, Send, X } from 'lucide-vue-next'
import { confirmDialog } from './appDialog'

type Appointment={
  id:string
  starts_at:string
  status:string
  customer_name:string
  customer_phone?:string|null
  customer_email?:string|null
  service_name?:string|null
  professional_name:string
}
type ConfirmationStatus={
  appointment_id:string
  appointment_status:string
  request_state?:string|null
  has_request:boolean
  confirmation_deadline?:string|null
  expires_at?:string|null
  deadline_expired:boolean
  link_expired:boolean
  can_send:boolean
  can_resend:boolean
  can_renew:boolean
  action?:'send'|'resend'|'renew'|null
  label:string
  source?:string|null
  customer_confirmed:boolean
  manual_confirmed:boolean
  auto_expired_cancel:boolean
}
type SendResult={action:string;queued_channels:string[];status:ConfirmationStatus}
type Envelope<T>={data?:T;error?:{message?:string}}

const open=ref(false)
const loading=ref(false)
const busy=ref('')
const error=ref('')
const message=ref('')
const appointments=ref<Appointment[]>([])
const statuses=ref<Record<string,ConfirmationStatus>>({})
let refreshTimer:number|undefined

function token():string{return localStorage.getItem('scheduler_pro_access_token')||''}
function todayKey():string{const now=new Date();const offset=now.getTimezoneOffset()*60000;return new Date(now.getTime()-offset).toISOString().slice(0,10)}
function time(value:string):string{return new Date(value).toLocaleTimeString('pt-BR',{hour:'2-digit',minute:'2-digit'})}
function deadline(value?:string|null):string{if(!value)return 'sem prazo definido';return new Date(value).toLocaleString('pt-BR',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'})}
function flash(value:string):void{message.value=value;window.setTimeout(()=>{if(message.value===value)message.value=''},5000)}
async function api<T>(path:string,init:RequestInit={}):Promise<T>{const response=await fetch(`/api/v1${path}`,{...init,cache:'no-store',headers:{Accept:'application/json',...(init.body?{'content-type':'application/json'}:{}),Authorization:`Bearer ${token()}`,...(init.headers||{})}});const payload=await response.json().catch(()=>({})) as Envelope<T>;if(!response.ok)throw new Error(payload.error?.message||`Falha HTTP ${response.status}`);return payload.data as T}

const rows=computed(()=>appointments.value
  .filter(item=>Boolean(statuses.value[item.id]))
  .filter(item=>['PENDING','AWAITING_CONFIRMATION','RESCHEDULED','CONFIRMED','CANCELLED'].includes(item.status))
  .sort((a,b)=>{
    const sa=statuses.value[a.id],sb=statuses.value[b.id]
    const aa=sa?.action?0:1,ab=sb?.action?0:1
    return aa-ab||(+new Date(a.starts_at)-+new Date(b.starts_at))
  })
  .slice(0,60))
const actionableCount=computed(()=>rows.value.filter(item=>Boolean(statuses.value[item.id]?.action)).length)

function stateClass(state?:ConfirmationStatus):string{
  if(!state)return''
  if(state.can_renew)return'expired'
  if(state.can_send||state.can_resend)return'waiting'
  if(state.customer_confirmed)return'confirmed-client'
  if(state.manual_confirmed)return'confirmed-manual'
  if(state.appointment_status==='CANCELLED')return'cancelled'
  return''
}
function actionLabel(state:ConfirmationStatus):string{
  if(state.can_renew)return'Renovar e enviar'
  if(state.can_resend)return'Reenviar link'
  return'Enviar confirmação'
}

async function load():Promise<void>{
  if(!open.value)return
  loading.value=true;error.value=''
  try{
    const list=await api<Appointment[]>(`/appointments?day=${encodeURIComponent(todayKey())}`)
    appointments.value=list
    const appointmentIds=list.map(item=>item.id)
    statuses.value=appointmentIds.length
      ? await api<Record<string,ConfirmationStatus>>('/appointment-confirmations/statuses',{method:'POST',body:JSON.stringify({appointment_ids:appointmentIds})})
      : {}
  }catch(exc){error.value=exc instanceof Error?exc.message:'Não foi possível carregar as confirmações.'}
  finally{loading.value=false}
}

async function show():Promise<void>{open.value=true;await load()}
function hide():void{open.value=false}

async function sendConfirmation(item:Appointment):Promise<void>{
  const state=statuses.value[item.id]
  if(!state?.action)return
  const renewing=state.action==='renew'
  const title=renewing?'Renovar confirmação':state.action==='resend'?'Reenviar confirmação':'Enviar confirmação'
  const messageText=renewing
    ? state.auto_expired_cancel
      ? `O prazo de ${item.customer_name} venceu e o horário foi liberado automaticamente. O Scheduler Pro verificará novamente a disponibilidade antes de reabrir o atendimento, gerar um novo prazo e enviar um novo link. Deseja continuar?`
      : `Gerar um novo link e um novo prazo de confirmação para ${item.customer_name}, substituindo o link vencido?`
    : `${state.action==='resend'?'Reenviar':'Enviar'} o link de confirmação para ${item.customer_name}? O envio utilizará os canais configurados no tenant.`
  const ok=await confirmDialog({title,message:messageText,danger:false,confirmLabel:renewing?'Renovar e enviar':state.action==='resend'?'Reenviar link':'Enviar link'})
  if(!ok)return
  busy.value=item.id;error.value=''
  try{
    const result=await api<SendResult>(`/appointment-confirmations/${item.id}/send`,{method:'POST'})
    const channels=result.queued_channels.map(value=>value==='whatsapp'?'WhatsApp':value==='email'?'e-mail':value).join(' + ')
    flash(`${renewing?'Confirmação renovada':'Confirmação enviada'}${channels?` por ${channels}`:''}.`)
    window.dispatchEvent(new CustomEvent('scheduler-pro-appointments-changed'))
    await load()
  }catch(exc){error.value=exc instanceof Error?exc.message:'Não foi possível enviar a confirmação.'}
  finally{busy.value=''}
}

function onAppointmentsChanged():void{if(open.value)void load()}
onMounted(()=>{window.addEventListener('scheduler-pro-appointments-changed',onAppointmentsChanged);refreshTimer=window.setInterval(()=>{if(open.value)void load()},60000)})
onUnmounted(()=>{window.removeEventListener('scheduler-pro-appointments-changed',onAppointmentsChanged);if(refreshTimer!==undefined)window.clearInterval(refreshTimer)})
</script>

<template>
  <Teleport to="body">
    <button v-if="!open" class="confirmation-assistant-launcher" type="button" title="Confirmações de clientes" @click="show">
      <MessageCircle :size="18"/>
      <span>Confirmações</span>
      <b v-if="actionableCount">{{actionableCount}}</b>
    </button>
    <section v-else class="confirmation-assistant" aria-label="Assistente de confirmações">
      <header>
        <div><MessageCircle :size="20"/><div><strong>Confirmações</strong><span>Envio, reenvio e renovação segura</span></div></div>
        <button type="button" title="Fechar" @click="hide"><X :size="19"/></button>
      </header>
      <div class="assistant-toolbar"><span>{{actionableCount}} pendência(s) de confirmação hoje</span><button type="button" title="Atualizar" @click="load"><RefreshCw :size="16" :class="{spin:loading}"/></button></div>
      <p v-if="message" class="assistant-notice success">{{message}}</p>
      <p v-if="error" class="assistant-notice error">{{error}}</p>
      <div v-if="loading&&!rows.length" class="assistant-empty"><RefreshCw class="spin" :size="24"/><span>Atualizando...</span></div>
      <div v-else-if="!rows.length" class="assistant-empty"><MessageCircle :size="28"/><strong>Nenhum atendimento para acompanhar hoje.</strong></div>
      <div v-else class="assistant-list">
        <article v-for="item in rows" :key="item.id" :class="['assistant-card',stateClass(statuses[item.id])]">
          <div class="assistant-time"><strong>{{time(item.starts_at)}}</strong><span>{{item.professional_name}}</span></div>
          <div class="assistant-client"><strong>{{item.customer_name}}</strong><span>{{item.service_name||'Atendimento'}}</span><small>{{statuses[item.id]?.label}}</small><small v-if="statuses[item.id]?.confirmation_deadline"><Clock3 :size="12"/> prazo {{deadline(statuses[item.id]?.confirmation_deadline)}}</small></div>
          <button v-if="statuses[item.id]?.action" type="button" class="assistant-action" :disabled="busy===item.id" @click="sendConfirmation(item)"><Send :size="14"/><span>{{actionLabel(statuses[item.id])}}</span></button>
        </article>
      </div>
      <footer>Links e tokens de confirmação não são exibidos nem gravados nos logs deste painel.</footer>
    </section>
  </Teleport>
</template>

<style scoped>
.confirmation-assistant-launcher{position:fixed;right:22px;bottom:132px;z-index:2147481250;display:flex;align-items:center;gap:7px;min-height:40px;padding:0 13px;border:1px solid #bfdbfe;border-radius:13px;background:#fff;color:#1d4ed8;font:inherit;font-size:11px;font-weight:850;box-shadow:0 10px 28px rgba(15,23,42,.14);cursor:pointer}.confirmation-assistant-launcher b{display:grid;place-items:center;min-width:20px;height:20px;padding:0 5px;border-radius:999px;background:#dc2626;color:#fff;font-size:9px}.confirmation-assistant{position:fixed;right:22px;bottom:22px;z-index:2147481250;width:min(430px,calc(100vw - 44px));max-height:min(760px,calc(100dvh - 44px));display:flex;flex-direction:column;border:1px solid #dbe3ef;border-radius:18px;background:#f8fafc;color:#0f172a;box-shadow:0 24px 70px rgba(15,23,42,.24);overflow:hidden;font-family:Inter,Sora,system-ui,sans-serif}.confirmation-assistant>header{display:flex;align-items:center;justify-content:space-between;padding:13px 14px;border-bottom:1px solid #dbe3ef;background:#fff}.confirmation-assistant>header>div{display:flex;align-items:center;gap:9px}.confirmation-assistant>header>div>svg{color:#2563eb}.confirmation-assistant>header div div{display:grid}.confirmation-assistant>header strong{font-size:14px}.confirmation-assistant>header span{font-size:9px;color:#64748b}.confirmation-assistant>header button,.assistant-toolbar button{width:34px;height:34px;display:grid;place-items:center;border:1px solid #dbe3ef;border-radius:9px;background:#fff;color:#475569;cursor:pointer}.assistant-toolbar{display:flex;align-items:center;justify-content:space-between;padding:8px 12px;border-bottom:1px solid #e2e8f0;background:#f8fafc}.assistant-toolbar span{font-size:10px;font-weight:800;color:#475569}.assistant-notice{margin:8px 10px 0;padding:8px 10px;border-radius:9px;font-size:10px;font-weight:700}.assistant-notice.success{background:#dcfce7;color:#166534}.assistant-notice.error{background:#fee2e2;color:#991b1b}.assistant-list{min-height:0;overflow:auto;padding:10px;display:grid;gap:8px}.assistant-card{display:grid;grid-template-columns:58px minmax(0,1fr) auto;align-items:center;gap:9px;padding:10px;border:1px solid #dbe3ef;border-left:4px solid #cbd5e1;border-radius:12px;background:#fff}.assistant-card.waiting{border-left-color:#f59e0b}.assistant-card.expired{border-left-color:#dc2626;background:#fff7f7}.assistant-card.confirmed-client{border-left-color:#16a34a}.assistant-card.confirmed-manual{border-left-color:#2563eb}.assistant-card.cancelled{opacity:.78}.assistant-time{display:grid}.assistant-time strong{font-size:16px}.assistant-time span{font-size:8px;color:#64748b;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.assistant-client{display:grid;gap:2px;min-width:0}.assistant-client>strong{font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.assistant-client>span{font-size:9px;color:#64748b}.assistant-client small{display:flex;align-items:center;gap:4px;font-size:9px;color:#475569}.assistant-action{display:flex;align-items:center;gap:5px;min-height:32px;padding:0 9px;border:1px solid #bfdbfe;border-radius:9px;background:#eff6ff;color:#1d4ed8;font:inherit;font-size:9px;font-weight:850;cursor:pointer}.assistant-action:disabled{opacity:.55;cursor:wait}.assistant-empty{min-height:150px;display:grid;place-content:center;justify-items:center;gap:7px;padding:20px;color:#64748b;font-size:10px}.confirmation-assistant>footer{padding:8px 12px;border-top:1px solid #e2e8f0;background:#fff;color:#94a3b8;font-size:8px}.spin{animation:assistant-spin 1s linear infinite}@keyframes assistant-spin{to{transform:rotate(360deg)}}
@media(max-width:700px){.confirmation-assistant-launcher{right:15px;bottom:126px;width:46px;height:46px;min-height:46px;padding:0;justify-content:center;border-radius:50%}.confirmation-assistant-launcher>span{display:none}.confirmation-assistant-launcher b{position:absolute;right:-3px;top:-4px}.confirmation-assistant{right:10px;bottom:10px;width:calc(100vw - 20px);max-height:calc(100dvh - 20px);border-radius:16px}.assistant-card{grid-template-columns:52px minmax(0,1fr)}.assistant-action{grid-column:1/-1;justify-content:center;min-height:38px}.confirmation-assistant>footer{font-size:8px}}
</style>
