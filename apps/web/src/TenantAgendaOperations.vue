<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { CalendarPlus, Check, Copy, RefreshCw, Repeat2, Shuffle, Trash2, UserPlus, X } from 'lucide-vue-next'

type Appointment={id:string;customer_id:string;service_id:string;professional_id:string;starts_at:string;ends_at:string;status:string;customer_name:string;customer_phone?:string|null;customer_email?:string|null;service_name:string;duration_minutes?:number;price?:number|null;professional_name:string}
type Customer={id:string;name:string;phone?:string|null;email?:string|null}
type Service={id:string;name:string;duration_minutes:number;price?:number|null;active:boolean}
type Professional={id:string;name:string;email?:string|null;phone?:string|null}
type Envelope<T>={data:T;error?:{message?:string;code?:string}}
type RecurringResult={created:Array<{id:string;starts_at:string;status:string}>;skipped:Array<{starts_at:string;code:string;reason:string}>;summary:{requested:number;created:number;skipped:number}}

type Tab='quick'|'recurring'|'swap'|'manage'

const open=ref(false)
const tab=ref<Tab>('quick')
const portalReady=ref(false)
const currentHash=ref(window.location.hash || '#dashboard')
const calendarExtensionVisible=ref(false)
const loading=ref(false)
const saving=ref(false)
const error=ref('')
const success=ref('')
const appointments=ref<Appointment[]>([])
const customers=ref<Customer[]>([])
const services=ref<Service[]>([])
const professionals=ref<Professional[]>([])
const customerSearch=ref('')
const customerMode=ref<'existing'|'new'>('existing')
const selectedCustomerId=ref('')
const selectedServiceId=ref('')
const selectedProfessionalId=ref('')
const quick=ref({customer_name:'',customer_phone:'',customer_email:'',service_name:'Atendimento',duration_minutes:30,price:null as number|null,professional_name:'Agenda geral',starts_at:''})
const recurrence=ref({repeat_every_weeks:1,weekdays:[] as number[],period:'12' as '1'|'3'|'6'|'12'|'until',until:'',max_occurrences:104,skip_sundays:true,skip_dates:'',conflict_policy:'skip' as 'skip'|'abort'})
const swap=ref({first_id:'',second_id:''})
const reuseTarget=ref<Appointment|null>(null)

const isAgendaPage=computed(()=>currentHash.value==='#agenda')
const isCustomersPage=computed(()=>currentHash.value==='#clientes')
const showPageAction=computed(()=>isAgendaPage.value||isCustomersPage.value)
const activeAppointments=computed(()=>appointments.value.filter((item)=>!['COMPLETED','CANCELLED','NO_SHOW'].includes(item.status)))
const manageableAppointments=computed(()=>[...appointments.value].sort((a,b)=>+new Date(b.starts_at)-+new Date(a.starts_at)).slice(0,100))
const filteredCustomers=computed(()=>{const needle=customerSearch.value.trim().toLocaleLowerCase('pt-BR');return customers.value.filter((item)=>!needle||`${item.name} ${item.phone||''} ${item.email||''}`.toLocaleLowerCase('pt-BR').includes(needle)).slice(0,80)})

function token():string{return localStorage.getItem('scheduler_pro_access_token')||''}
async function api<T>(path:string,init:RequestInit={}):Promise<T>{
  const response=await fetch(`/api/v1${path}`,{...init,headers:{accept:'application/json',...(init.body?{'content-type':'application/json'}:{}),authorization:`Bearer ${token()}`,...(init.headers||{})}})
  const payload=await response.json().catch(()=>({})) as Partial<Envelope<T>>
  if(response.status===401){localStorage.removeItem('scheduler_pro_access_token');localStorage.removeItem('scheduler_pro_refresh_token');window.location.reload();throw new Error('Sua sessão expirou.')}
  if(!response.ok)throw new Error(payload.error?.message||`Não foi possível concluir a operação (${response.status}).`)
  return payload.data as T
}
function humanStatus(value:string):string{return({PENDING:'Pendente',AWAITING_CONFIRMATION:'Aguardando confirmação',CONFIRMED:'Confirmado',CHECKED_IN:'Check-in',IN_PROGRESS:'Em atendimento',COMPLETED:'Concluído',CANCELLED:'Cancelado',RESCHEDULED:'Reagendado',NO_SHOW:'Não compareceu'} as Record<string,string>)[value]||value}
function formatDate(value:string):string{return new Date(value).toLocaleString('pt-BR',{dateStyle:'short',timeStyle:'short'})}
function localInput(value:string):string{const d=new Date(value);d.setMinutes(d.getMinutes()-d.getTimezoneOffset());return d.toISOString().slice(0,16)}

async function loadData():Promise<void>{
  loading.value=true;error.value=''
  try{
    const [a,c,s,p]=await Promise.all([
      api<Appointment[]>('/appointments'),
      api<Customer[]>('/customers').catch(()=>[]),
      api<Service[]>('/services').catch(()=>[]),
      api<Professional[]>('/professionals').catch(()=>[]),
    ])
    appointments.value=a;customers.value=c;services.value=s;professionals.value=p
    if(!selectedServiceId.value&&s.length)selectedServiceId.value=s.find((item)=>item.active)?.id||''
    if(!selectedProfessionalId.value&&p.length)selectedProfessionalId.value=p[0]?.id||''
  }catch(exc){error.value=exc instanceof Error?exc.message:'Falha ao carregar a agenda avançada.'}
  finally{loading.value=false}
}

function chooseCustomer():void{
  const item=customers.value.find((row)=>row.id===selectedCustomerId.value)
  if(!item)return
  quick.value.customer_name=item.name;quick.value.customer_phone=item.phone||'';quick.value.customer_email=item.email||''
}
function chooseService():void{
  const item=services.value.find((row)=>row.id===selectedServiceId.value)
  if(!item)return
  quick.value.service_name=item.name;quick.value.duration_minutes=item.duration_minutes;quick.value.price=item.price??null
}
function chooseProfessional():void{const item=professionals.value.find((row)=>row.id===selectedProfessionalId.value);if(item)quick.value.professional_name=item.name}
function resetMessages():void{error.value='';success.value=''}

async function show(target:Tab='quick'):Promise<void>{open.value=true;tab.value=target;resetMessages();await loadData();if(isCustomersPage.value){customerMode.value='existing'}}
function close():void{open.value=false;reuseTarget.value=null;resetMessages()}

function quickPayload(){
  return{
    starts_at:new Date(quick.value.starts_at).toISOString(),
    customer_id:customerMode.value==='existing'&&selectedCustomerId.value?selectedCustomerId.value:null,
    customer_name:quick.value.customer_name.trim()||'Cliente',
    customer_phone:quick.value.customer_phone.trim()||null,
    customer_email:quick.value.customer_email.trim()||null,
    service_id:selectedServiceId.value||null,
    service_name:quick.value.service_name.trim()||'Atendimento',
    duration_minutes:Number(quick.value.duration_minutes)||30,
    price:quick.value.price,
    professional_id:selectedProfessionalId.value||null,
    professional_name:quick.value.professional_name.trim()||'Agenda geral',
  }
}

async function createQuick():Promise<void>{
  resetMessages();if(!quick.value.starts_at){error.value='Informe a data e o horário do atendimento.';return}
  if(customerMode.value==='existing'&&!selectedCustomerId.value){error.value='Selecione um cliente ou escolha “Novo cliente”.';return}
  saving.value=true
  try{await api('/appointments/quick',{method:'POST',body:JSON.stringify({...quickPayload(),source:'tenant-web-quick-advanced'})});success.value='Agendamento criado e preparado para confirmação.';await loadData();quick.value.starts_at=''}
  catch(exc){error.value=exc instanceof Error?exc.message:'Falha ao criar agendamento.'}finally{saving.value=false}
}

async function createRecurring():Promise<void>{
  resetMessages();if(!quick.value.starts_at){error.value='Informe o primeiro horário da recorrência.';return}
  if(customerMode.value==='existing'&&!selectedCustomerId.value){error.value='Selecione um cliente para a recorrência.';return}
  saving.value=true
  try{
    const skipDates=recurrence.value.skip_dates.split(/[\s,;]+/).map((item)=>item.trim()).filter(Boolean)
    const result=await api<RecurringResult>('/appointments/recurring',{method:'POST',body:JSON.stringify({...quickPayload(),source:'tenant-web-recurring',repeat_every_weeks:Number(recurrence.value.repeat_every_weeks),weekdays:recurrence.value.weekdays,months_ahead:recurrence.value.period==='until'?null:Number(recurrence.value.period),until:recurrence.value.period==='until'&&recurrence.value.until?recurrence.value.until:null,max_occurrences:Number(recurrence.value.max_occurrences)||104,skip_sundays:recurrence.value.skip_sundays,skip_dates:skipDates,conflict_policy:recurrence.value.conflict_policy})})
    success.value=`Recorrência processada: ${result.summary.created} criado(s), ${result.summary.skipped} ignorado(s).`;await loadData()
  }catch(exc){error.value=exc instanceof Error?exc.message:'Falha ao criar recorrência.'}finally{saving.value=false}
}

async function swapSlots():Promise<void>{
  resetMessages();if(!swap.value.first_id||!swap.value.second_id){error.value='Selecione os dois agendamentos que terão os horários permutados.';return}
  saving.value=true
  try{await api('/appointments/swap',{method:'POST',body:JSON.stringify({first_id:swap.value.first_id,second_id:swap.value.second_id})});success.value='Horários permutados. Os dois clientes receberão o novo horário e deverão confirmar novamente.';swap.value={first_id:'',second_id:''};await loadData()}
  catch(exc){error.value=exc instanceof Error?exc.message:'Falha ao permutar os horários.'}finally{saving.value=false}
}

function startReuse(item:Appointment):void{
  reuseTarget.value=item;tab.value='quick';customerMode.value='existing';selectedCustomerId.value='';quick.value.starts_at=localInput(item.starts_at);selectedServiceId.value=item.service_id;selectedProfessionalId.value=item.professional_id;quick.value.service_name=item.service_name;quick.value.professional_name=item.professional_name;quick.value.duration_minutes=item.duration_minutes||30;quick.value.price=item.price??null;quick.value.customer_name='';quick.value.customer_phone='';quick.value.customer_email=''
}
async function reuseSlot():Promise<void>{
  if(!reuseTarget.value)return
  resetMessages();if(customerMode.value==='existing'&&!selectedCustomerId.value){error.value='Selecione o novo cliente para reutilizar o horário.';return}
  saving.value=true
  try{await api(`/appointments/${reuseTarget.value.id}/reuse`,{method:'POST',body:JSON.stringify(quickPayload())});success.value='Horário reutilizado com o novo cliente.';reuseTarget.value=null;await loadData()}
  catch(exc){error.value=exc instanceof Error?exc.message:'Falha ao reutilizar o horário.'}finally{saving.value=false}
}

async function cancelItem(item:Appointment):Promise<void>{
  if(!confirm(`Cancelar o agendamento de ${item.customer_name}?`))return
  resetMessages();saving.value=true
  try{await api(`/appointments/${item.id}/cancel`,{method:'POST',body:JSON.stringify({reason:'Cancelado pelo gestor na agenda avançada'})});success.value='Agendamento cancelado e horário liberado.';await loadData()}
  catch(exc){error.value=exc instanceof Error?exc.message:'Falha ao cancelar o agendamento.'}finally{saving.value=false}
}
async function deleteItem(item:Appointment):Promise<void>{
  if(!confirm(`Excluir definitivamente o registro de ${item.customer_name}? A auditoria da exclusão será preservada.`))return
  resetMessages();saving.value=true
  try{await api(`/appointments/${item.id}/permanent`,{method:'DELETE'});success.value='Agendamento removido. A operação ficou registrada na auditoria.';await loadData()}
  catch(exc){error.value=exc instanceof Error?exc.message:'Falha ao excluir o agendamento.'}finally{saving.value=false}
}
async function copyConfirmation(item:Appointment):Promise<void>{
  resetMessages()
  try{const data=await api<{enabled:boolean;request?:{url?:string}|null}>(`/appointment-confirmations/${item.id}`);const url=data.request?.url;if(!url)throw new Error('Este agendamento não possui link de confirmação ativo.');await navigator.clipboard.writeText(url);success.value='Link de confirmação copiado.'}
  catch(exc){error.value=exc instanceof Error?exc.message:'Falha ao copiar o link.'}
}

function syncHash():void{currentHash.value=window.location.hash||'#dashboard'}
function detectCalendar():void{calendarExtensionVisible.value=[...document.querySelectorAll('.sp-extension-header h1')].some((item)=>item.textContent?.trim()==='Calendário da agenda')}
let observer:MutationObserver|undefined

onMounted(async()=>{window.addEventListener('hashchange',syncHash);await nextTick();portalReady.value=Boolean(document.querySelector('.tenant-console .page-actions'));observer=new MutationObserver(detectCalendar);observer.observe(document.body,{subtree:true,childList:true});detectCalendar()})
onUnmounted(()=>{window.removeEventListener('hashchange',syncHash);observer?.disconnect()})
</script>

<template>
  <Teleport v-if="portalReady && showPageAction" to=".tenant-console .page-actions">
    <button class="btn sp-advanced-action" type="button" @click="show(isCustomersPage?'quick':'manage')"><CalendarPlus :size="16"/>{{ isCustomersPage?'Agendar cliente':'Agenda avançada' }}</button>
  </Teleport>
  <button v-if="calendarExtensionVisible" class="sp-calendar-ops-fab" @click="show('manage')"><CalendarPlus :size="17"/><span>Operar agenda</span></button>

  <div v-if="open" class="sp-agenda-ops-backdrop" @click.self="close">
    <section class="sp-agenda-ops">
      <header><div><span>Scheduler Pro · Agenda</span><h2>Operação avançada</h2><p>Agendamento rápido, recorrência, permuta, reutilização e exclusão auditada.</p></div><button @click="close"><X :size="20"/></button></header>
      <nav><button :class="{active:tab==='quick'}" @click="tab='quick'"><UserPlus :size="15"/>Agendar</button><button :class="{active:tab==='recurring'}" @click="tab='recurring'"><Repeat2 :size="15"/>Recorrência</button><button :class="{active:tab==='swap'}" @click="tab='swap'"><Shuffle :size="15"/>Permutar</button><button :class="{active:tab==='manage'}" @click="tab='manage'"><CalendarPlus :size="15"/>Gerenciar</button></nav>
      <p v-if="success" class="sp-op-success"><Check :size="16"/>{{success}}</p><p v-if="error" class="sp-op-error">{{error}}</p>
      <div v-if="loading" class="sp-op-loading"><RefreshCw class="spin" :size="20"/>Atualizando dados...</div>

      <main v-else>
        <section v-if="tab==='quick'" class="sp-op-form">
          <div v-if="reuseTarget" class="sp-reuse-banner"><strong>Reutilizando {{formatDate(reuseTarget.starts_at)}}</strong><span>O registro cancelado será preservado; um novo agendamento será criado neste horário.</span></div>
          <div class="sp-segment"><button :class="{active:customerMode==='existing'}" @click="customerMode='existing'">Cliente existente</button><button :class="{active:customerMode==='new'}" @click="customerMode='new'">Novo cliente</button></div>
          <template v-if="customerMode==='existing'">
            <label>Localizar cliente<input v-model="customerSearch" placeholder="Nome, telefone ou e-mail"/></label>
            <label>Cliente<select v-model="selectedCustomerId" size="Math.min(6, filteredCustomers.length || 2)" @change="chooseCustomer"><option value="">Selecione</option><option v-for="item in filteredCustomers" :key="item.id" :value="item.id">{{item.name}} · {{item.phone||item.email||'sem contato'}}</option></select></label>
          </template>
          <div v-else class="sp-op-grid"><label>Nome<input v-model="quick.customer_name"/></label><label>Telefone / WhatsApp<input v-model="quick.customer_phone"/></label><label>E-mail<input v-model="quick.customer_email" type="email"/></label></div>
          <div class="sp-op-grid"><label>Serviço<select v-model="selectedServiceId" @change="chooseService"><option value="">Atendimento rápido</option><option v-for="item in services.filter(s=>s.active)" :key="item.id" :value="item.id">{{item.name}} · {{item.duration_minutes}} min</option></select></label><label>Profissional<select v-model="selectedProfessionalId" @change="chooseProfessional"><option value="">Agenda geral</option><option v-for="item in professionals" :key="item.id" :value="item.id">{{item.name}}</option></select></label><label>Data e horário<input v-model="quick.starts_at" type="datetime-local"/></label><label>Duração<input v-model.number="quick.duration_minutes" type="number" min="5" max="720"/></label></div>
          <button class="sp-op-primary" :disabled="saving" @click="reuseTarget?reuseSlot():createQuick()"><CalendarPlus :size="16"/>{{saving?'Salvando...':reuseTarget?'Reutilizar horário':'Criar agendamento'}}</button>
        </section>

        <section v-else-if="tab==='recurring'" class="sp-op-form">
          <div class="sp-op-grid"><label>Cliente<select v-model="selectedCustomerId" @change="chooseCustomer"><option value="">Selecione um cliente</option><option v-for="item in customers" :key="item.id" :value="item.id">{{item.name}}</option></select></label><label>Serviço<select v-model="selectedServiceId" @change="chooseService"><option v-for="item in services.filter(s=>s.active)" :key="item.id" :value="item.id">{{item.name}}</option></select></label><label>Profissional<select v-model="selectedProfessionalId" @change="chooseProfessional"><option v-for="item in professionals" :key="item.id" :value="item.id">{{item.name}}</option></select></label><label>Primeiro horário<input v-model="quick.starts_at" type="datetime-local"/></label></div>
          <fieldset><legend>Dias da semana</legend><div class="sp-weekday-picks"><label v-for="(name,index) in ['Seg','Ter','Qua','Qui','Sex','Sáb','Dom']" :key="name"><input v-model="recurrence.weekdays" type="checkbox" :value="index"/>{{name}}</label></div><small>Se nenhum dia for marcado, será usado o mesmo dia da semana do primeiro horário.</small></fieldset>
          <div class="sp-op-grid"><label>Repetir a cada<select v-model.number="recurrence.repeat_every_weeks"><option :value="1">1 semana</option><option :value="2">2 semanas</option><option :value="3">3 semanas</option><option :value="4">4 semanas</option></select></label><label>Período<select v-model="recurrence.period"><option value="1">Mês atual / próximo mês</option><option value="3">3 meses</option><option value="6">6 meses</option><option value="12">12 meses</option><option value="until">Até uma data</option></select></label><label v-if="recurrence.period==='until'">Até<input v-model="recurrence.until" type="date"/></label><label>Máximo de horários<input v-model.number="recurrence.max_occurrences" type="number" min="1" max="366"/></label></div>
          <label class="sp-check"><input v-model="recurrence.skip_sundays" type="checkbox"/>Descartar domingos automaticamente</label>
          <label>Feriados/datas a ignorar<textarea v-model="recurrence.skip_dates" placeholder="2026-09-07, 2026-10-12, 2026-12-25"></textarea><small>Datas opcionais separadas por vírgula, espaço ou linha. No futuro podem vir de um calendário fiscal/municipal.</small></label>
          <label>Ao encontrar conflito<select v-model="recurrence.conflict_policy"><option value="skip">Ignorar horário ocupado e continuar</option><option value="abort">Parar no primeiro conflito</option></select></label>
          <button class="sp-op-primary" :disabled="saving" @click="createRecurring"><Repeat2 :size="16"/>{{saving?'Processando...':'Criar agenda recorrente'}}</button>
        </section>

        <section v-else-if="tab==='swap'" class="sp-op-form">
          <p class="sp-op-help">Permuta os horários completos de dois agendamentos e solicita nova confirmação aos dois clientes.</p>
          <label>Primeiro agendamento<select v-model="swap.first_id"><option value="">Selecione</option><option v-for="item in activeAppointments" :key="item.id" :value="item.id">{{formatDate(item.starts_at)}} · {{item.customer_name}} · {{item.professional_name}}</option></select></label>
          <label>Segundo agendamento<select v-model="swap.second_id"><option value="">Selecione</option><option v-for="item in activeAppointments.filter(row=>row.id!==swap.first_id)" :key="item.id" :value="item.id">{{formatDate(item.starts_at)}} · {{item.customer_name}} · {{item.professional_name}}</option></select></label>
          <button class="sp-op-primary" :disabled="saving" @click="swapSlots"><Shuffle :size="16"/>{{saving?'Permutando...':'Permutar horários'}}</button>
        </section>

        <section v-else class="sp-manage-list">
          <article v-for="item in manageableAppointments" :key="item.id"><div class="sp-manage-time"><strong>{{new Date(item.starts_at).toLocaleTimeString('pt-BR',{hour:'2-digit',minute:'2-digit'})}}</strong><small>{{new Date(item.starts_at).toLocaleDateString('pt-BR')}}</small></div><div class="sp-manage-info"><strong>{{item.customer_name}}</strong><span>{{item.service_name}} · {{item.professional_name}}</span><em :class="item.status.toLowerCase()">{{humanStatus(item.status)}}</em></div><div class="sp-manage-actions"><button v-if="['PENDING','AWAITING_CONFIRMATION','RESCHEDULED'].includes(item.status)" @click="copyConfirmation(item)"><Copy :size="13"/>Link</button><button v-if="!['COMPLETED','CANCELLED','NO_SHOW'].includes(item.status)" @click="cancelItem(item)">Cancelar</button><button v-if="['CANCELLED','NO_SHOW'].includes(item.status)&&new Date(item.starts_at).getTime()>Date.now()" @click="startReuse(item)">Reutilizar</button><button v-if="['COMPLETED','CANCELLED','NO_SHOW'].includes(item.status)" class="danger" @click="deleteItem(item)"><Trash2 :size="13"/>Excluir</button></div></article>
          <div v-if="!manageableAppointments.length" class="sp-op-empty">Nenhum agendamento disponível.</div>
        </section>
      </main>
    </section>
  </div>
</template>

<style>
.sp-advanced-action{order:3}.sp-calendar-ops-fab{position:fixed;right:22px;bottom:82px;z-index:950;display:flex;align-items:center;gap:7px;min-height:43px;padding:0 14px;border:0;border-radius:13px;background:#0b1d3a;color:#fff;font:inherit;font-size:11px;font-weight:850;box-shadow:0 12px 34px rgba(15,23,42,.2);cursor:pointer}.sp-agenda-ops-backdrop{position:fixed;z-index:1600;inset:0;display:grid;place-items:center;padding:24px;background:rgba(8,18,35,.55);backdrop-filter:blur(5px)}.sp-agenda-ops{width:min(980px,96vw);max-height:92dvh;overflow:auto;border:1px solid #dce4ef;border-radius:24px;background:#f7f9fc;color:#11233c;box-shadow:0 28px 90px rgba(8,18,35,.3)}.sp-agenda-ops>header{display:flex;justify-content:space-between;gap:18px;padding:23px 25px 17px;background:#fff;border-bottom:1px solid #e5eaf1}.sp-agenda-ops header span{font-size:10px;font-weight:900;text-transform:uppercase;letter-spacing:.09em;color:#2563eb}.sp-agenda-ops header h2{margin:5px 0;font-size:25px;letter-spacing:-.035em}.sp-agenda-ops header p{margin:0;color:#748298;font-size:12px}.sp-agenda-ops header button{width:42px;height:42px;display:grid;place-items:center;border:1px solid #dbe3ed;border-radius:12px;background:#fff;cursor:pointer}.sp-agenda-ops>nav{position:sticky;top:0;z-index:4;display:grid;grid-template-columns:repeat(4,1fr);gap:6px;padding:10px 14px;background:rgba(255,255,255,.97);border-bottom:1px solid #e4e9f1;backdrop-filter:blur(12px)}.sp-agenda-ops>nav button{height:42px;display:flex;align-items:center;justify-content:center;gap:6px;border:1px solid transparent;border-radius:11px;background:transparent;color:#5e6e85;font:inherit;font-size:11px;font-weight:850;cursor:pointer}.sp-agenda-ops>nav button.active{border-color:#bfdbfe;background:#eff6ff;color:#1d4ed8}.sp-agenda-ops main{padding:18px 22px 26px}.sp-op-success,.sp-op-error{display:flex;align-items:flex-start;gap:8px;margin:12px 22px 0;padding:11px 13px;border-radius:12px;font-size:12px;font-weight:750}.sp-op-success{background:#ecfdf5;color:#047857}.sp-op-error{background:#fff1f2;color:#be123c}.sp-op-loading,.sp-op-empty{padding:48px 20px;text-align:center;color:#76869a;font-size:12px}.sp-op-form{display:grid;gap:13px}.sp-op-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:11px}.sp-op-form label{display:grid;gap:6px;color:#40516a;font-size:10px;font-weight:850;text-transform:uppercase;letter-spacing:.04em}.sp-op-form input,.sp-op-form select,.sp-op-form textarea{width:100%;min-height:44px;border:1px solid #d7e0eb;border-radius:11px;background:#fff;padding:0 11px;color:#172b46;font:inherit;font-size:12px;text-transform:none;letter-spacing:normal;outline:none}.sp-op-form textarea{min-height:90px;padding:10px}.sp-op-form select[size]{min-height:120px;padding:5px}.sp-op-form small{color:#8290a3;font-size:10px;font-weight:500;text-transform:none;letter-spacing:normal;line-height:1.4}.sp-segment{display:grid;grid-template-columns:1fr 1fr;padding:4px;border:1px solid #dde5ef;border-radius:13px;background:#fff}.sp-segment button{min-height:39px;border:0;border-radius:9px;background:transparent;font:inherit;font-size:11px;font-weight:850;color:#6b7b91;cursor:pointer}.sp-segment button.active{background:#0b1d3a;color:#fff}.sp-op-primary{min-height:47px;display:flex;align-items:center;justify-content:center;gap:7px;border:0;border-radius:12px;background:linear-gradient(135deg,#0b1d3a,#24c2ed);color:#fff;font:inherit;font-size:12px;font-weight:900;box-shadow:0 11px 28px rgba(23,115,185,.18);cursor:pointer}.sp-op-primary:disabled{opacity:.6}.sp-op-form fieldset{margin:0;padding:12px;border:1px solid #dce4ee;border-radius:13px;background:#fff}.sp-op-form legend{padding:0 5px;color:#53647c;font-size:10px;font-weight:900;text-transform:uppercase}.sp-weekday-picks{display:grid;grid-template-columns:repeat(7,1fr);gap:5px}.sp-weekday-picks label{display:flex;align-items:center;justify-content:center;gap:4px;min-height:36px;border:1px solid #e2e8f0;border-radius:9px;background:#fafcff;font-size:10px;text-transform:none}.sp-weekday-picks input,.sp-check input{width:auto;min-height:0}.sp-check{display:flex!important;align-items:center!important;grid-template-columns:auto 1fr!important;gap:8px!important;min-height:40px;padding:0 11px;border:1px solid #dce4ee;border-radius:11px;background:#fff;text-transform:none!important}.sp-reuse-banner{display:grid;gap:3px;padding:12px 14px;border:1px solid #a7f3d0;border-radius:12px;background:#ecfdf5;color:#065f46}.sp-reuse-banner span{font-size:11px}.sp-op-help{margin:0;padding:12px 14px;border-radius:11px;background:#eff6ff;color:#1e40af;font-size:12px}.sp-manage-list{display:grid;gap:9px}.sp-manage-list article{display:grid;grid-template-columns:74px minmax(0,1fr) auto;gap:12px;align-items:center;padding:12px 14px;border:1px solid #e0e7f0;border-radius:15px;background:#fff}.sp-manage-time strong,.sp-manage-time small,.sp-manage-info strong,.sp-manage-info span{display:block}.sp-manage-time strong{font-size:16px;color:#1d4ed8}.sp-manage-time small{margin-top:3px;color:#8a97a8;font-size:9px}.sp-manage-info strong{font-size:12px}.sp-manage-info span{margin:3px 0 6px;color:#6d7c91;font-size:10px}.sp-manage-info em{display:inline-flex;padding:4px 7px;border-radius:999px;background:#f1f5f9;color:#475569;font-size:9px;font-style:normal;font-weight:850}.sp-manage-info em.confirmed,.sp-manage-info em.completed{background:#dcfce7;color:#166534}.sp-manage-info em.cancelled,.sp-manage-info em.no_show{background:#fee2e2;color:#991b1b}.sp-manage-actions{display:flex;flex-wrap:wrap;justify-content:flex-end;gap:5px}.sp-manage-actions button{min-height:32px;display:flex;align-items:center;gap:4px;border:1px solid #dce4ef;border-radius:9px;background:#fff;color:#334155;font:inherit;font-size:9px;font-weight:850;cursor:pointer}.sp-manage-actions button.danger{border-color:#fecaca;color:#b91c1c}.spin{animation:sp-ops-spin 1s linear infinite}@keyframes sp-ops-spin{to{transform:rotate(360deg)}}@media(max-width:700px){.sp-calendar-ops-fab{right:14px;bottom:72px}.sp-calendar-ops-fab span{display:none}.sp-calendar-ops-fab{width:46px;padding:0;justify-content:center}.sp-agenda-ops-backdrop{align-items:end;padding:0}.sp-agenda-ops{width:100vw;max-height:94dvh;border-radius:24px 24px 0 0;border-bottom:0}.sp-agenda-ops>header{padding:18px 16px 14px}.sp-agenda-ops header h2{font-size:22px}.sp-agenda-ops>nav{grid-template-columns:repeat(4,minmax(0,1fr));padding:8px}.sp-agenda-ops>nav button{display:grid;height:52px;gap:2px;font-size:9px}.sp-agenda-ops main{padding:14px 13px 28px}.sp-op-grid{grid-template-columns:1fr}.sp-weekday-picks{grid-template-columns:repeat(4,1fr)}.sp-manage-list article{grid-template-columns:58px minmax(0,1fr);align-items:start}.sp-manage-actions{grid-column:1/-1;display:grid;grid-template-columns:repeat(2,1fr);justify-content:stretch}.sp-manage-actions button{min-height:40px;justify-content:center}.sp-op-success,.sp-op-error{margin:10px 13px 0}.sp-op-form input,.sp-op-form select,.sp-op-form textarea{font-size:16px}}
</style>
