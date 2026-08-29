<script setup lang="ts">
import { confirmDialog } from './appDialog'
import { computed, onMounted, onUnmounted, ref } from 'vue'
import {
  CalendarPlus,
  Check,
  Copy,
  RefreshCw,
  Repeat2,
  Shuffle,
  Trash2,
  UserPlus,
  X,
} from 'lucide-vue-next'
import {
  AGENDA_OPERATOR_EVENT,
  type AgendaOperatorDetail,
  type AgendaOperatorTab,
} from './tenantNavigation'

type FieldMode = 'DISABLED' | 'OPTIONAL' | 'REQUIRED'
type Appointment = {
  id:string;customer_id:string;service_id?:string|null;professional_id:string;
  starts_at:string;ends_at:string;status:string;customer_name:string;
  customer_phone?:string|null;customer_email?:string|null;service_name?:string|null;
  duration_minutes?:number;price?:number|null;professional_name:string
}
type Customer={id:string;name:string;phone?:string|null;email?:string|null}
type Service={id:string;name:string;duration_minutes:number;price?:number|null;active:boolean}
type Professional={id:string;name:string;email?:string|null;phone?:string|null}
type Lookup={customers:Customer[];services:Service[];professionals:Professional[]}
type Parameters={
  service_mode:FieldMode;email_mode:FieldMode;phone_mode:FieldMode;duration_mode:FieldMode;
  professional_mode:FieldMode;default_duration_minutes:number;default_professional_name:string;
  default_customer_mode:'NEW'|'EXISTING';
  simultaneous:{public:boolean;internal:boolean;capacity:number;enforce_public:boolean;enforce_internal:boolean};
  rules:{enforce_business_hours:boolean;enforce_blocked_periods:boolean};
  phone:{country:string;country_code:string;area_code:string;add_ninth_digit:boolean}
}
type Envelope<T>={data?:T;error?:{message?:string;code?:string;details?:Record<string,unknown>}}
type RecurringResult={created:Array<{id:string;starts_at:string;status:string}>;skipped:Array<{starts_at:string;code:string;reason:string}>;summary:{requested:number;created:number;skipped:number}}

type ApiProblem={message:string;code:string;details:Record<string,unknown>}
class AgendaApiError extends Error { code:string; details:Record<string,unknown>; constructor(problem:ApiProblem){super(problem.message);this.code=problem.code;this.details=problem.details} }

const open=ref(false)
const tab=ref<AgendaOperatorTab>('quick')
const loading=ref(false)
const saving=ref(false)
const error=ref('')
const success=ref('')
const params=ref<Parameters|null>(null)
const appointments=ref<Appointment[]>([])
const customers=ref<Customer[]>([])
const services=ref<Service[]>([])
const professionals=ref<Professional[]>([])
const customerSearch=ref('')
const customerMode=ref<'existing'|'new'>('new')
const selectedCustomerId=ref('')
const selectedServiceId=ref('')
const selectedProfessionalId=ref('')
const freeService=ref('')
const quick=ref({customer_name:'',customer_phone:'',customer_email:'',duration_minutes:60,price:null as number|null,professional_name:'',starts_at:''})
const recurrence=ref({repeat_every_weeks:1,weekdays:[] as number[],period:'12' as '1'|'3'|'6'|'12'|'until',until:'',max_occurrences:104,skip_sundays:true,skip_dates:'',conflict_policy:'skip' as 'skip'|'abort'})
const swap=ref({first_id:'',second_id:''})
const reuseTarget=ref<Appointment|null>(null)

const activeAppointments=computed(()=>appointments.value.filter((item)=>!['COMPLETED','CANCELLED','NO_SHOW'].includes(item.status)))
const manageableAppointments=computed(()=>[...appointments.value].sort((a,b)=>+new Date(b.starts_at)-+new Date(a.starts_at)).slice(0,120))
const filteredCustomers=computed(()=>{const needle=customerSearch.value.trim().toLocaleLowerCase('pt-BR');return customers.value.filter((item)=>!needle||`${item.name} ${item.phone||''} ${item.email||''}`.toLocaleLowerCase('pt-BR').includes(needle)).slice(0,80)})
const showPhone=computed(()=>params.value?.phone_mode!=='DISABLED')
const showEmail=computed(()=>params.value?.email_mode!=='DISABLED')
const showService=computed(()=>params.value?.service_mode!=='DISABLED')
const showDuration=computed(()=>params.value?.duration_mode!=='DISABLED')
const showProfessional=computed(()=>params.value?.professional_mode!=='DISABLED')
const serviceRequired=computed(()=>params.value?.service_mode==='REQUIRED')
const phoneRequired=computed(()=>params.value?.phone_mode==='REQUIRED')
const emailRequired=computed(()=>params.value?.email_mode==='REQUIRED')

function token():string{return localStorage.getItem('scheduler_pro_access_token')||''}
async function api<T>(path:string,init:RequestInit={}):Promise<T>{
  const response=await fetch(`/api/v1${path}`,{...init,cache:'no-store',headers:{accept:'application/json',...(init.body?{'content-type':'application/json'}:{}),authorization:`Bearer ${token()}`,...(init.headers||{})}})
  const payload=await response.json().catch(()=>({})) as Envelope<T>
  if(response.status===401){localStorage.removeItem('scheduler_pro_access_token');localStorage.removeItem('scheduler_pro_refresh_token');window.location.reload();throw new Error('Sua sessão expirou.')}
  if(!response.ok)throw new AgendaApiError({message:payload.error?.message||`Não foi possível concluir a operação (${response.status}).`,code:payload.error?.code||`HTTP_${response.status}`,details:payload.error?.details||{}})
  return payload.data as T
}
function humanStatus(value:string):string{return({PENDING:'Pendente',AWAITING_CONFIRMATION:'Aguardando confirmação',CONFIRMED:'Confirmado',CHECKED_IN:'Check-in',IN_PROGRESS:'Em atendimento',COMPLETED:'Concluído',CANCELLED:'Cancelado',RESCHEDULED:'Reagendado',NO_SHOW:'Não compareceu'} as Record<string,string>)[value]||value}
function formatDate(value:string):string{return new Date(value).toLocaleString('pt-BR',{dateStyle:'short',timeStyle:'short'})}
function localInput(value:string):string{const d=new Date(value);d.setMinutes(d.getMinutes()-d.getTimezoneOffset());return d.toISOString().slice(0,16)}
function resetMessages():void{error.value='';success.value=''}
function notifyAppointmentsChanged():void{window.dispatchEvent(new CustomEvent('scheduler-pro-appointments-changed'))}
function applyDefaults():void{
  const p=params.value
  customerMode.value=p?.default_customer_mode==='EXISTING'?'existing':'new'
  quick.value.duration_minutes=p?.default_duration_minutes||60
  quick.value.professional_name=p?.default_professional_name||'Agenda geral'
  if(!selectedServiceId.value)selectedServiceId.value=services.value.find((item)=>item.active)?.id||''
  if(!selectedProfessionalId.value)selectedProfessionalId.value=professionals.value.find((item)=>item.name===quick.value.professional_name)?.id||professionals.value[0]?.id||''
}
async function loadData():Promise<void>{
  loading.value=true;error.value=''
  try{
    const [parameters,items,lookups]=await Promise.all([
      api<Parameters>('/agenda/parameters'),api<Appointment[]>('/appointments'),api<Lookup>('/appointments/smart/lookups'),
    ])
    params.value=parameters;appointments.value=items;customers.value=lookups.customers||[];services.value=lookups.services||[];professionals.value=lookups.professionals||[];applyDefaults()
  }catch(exc){error.value=exc instanceof Error?exc.message:'Falha ao carregar o Operador da Agenda.'}finally{loading.value=false}
}
function chooseCustomer():void{const item=customers.value.find((row)=>row.id===selectedCustomerId.value);if(!item)return;quick.value.customer_name=item.name;quick.value.customer_phone=item.phone||'';quick.value.customer_email=item.email||''}
function selectCustomer(id:string):void{selectedCustomerId.value=id;chooseCustomer()}
function chooseService():void{const item=services.value.find((row)=>row.id===selectedServiceId.value);if(!item)return;freeService.value='';quick.value.duration_minutes=item.duration_minutes>0?item.duration_minutes:(params.value?.default_duration_minutes||60);quick.value.price=item.price??null}
function chooseProfessional():void{const item=professionals.value.find((row)=>row.id===selectedProfessionalId.value);if(item)quick.value.professional_name=item.name}
function resetQuick(keepDate=false):void{const date=keepDate?quick.value.starts_at:'';selectedCustomerId.value='';customerSearch.value='';freeService.value='';quick.value={customer_name:'',customer_phone:'',customer_email:'',duration_minutes:params.value?.default_duration_minutes||60,price:null,professional_name:params.value?.default_professional_name||'Agenda geral',starts_at:date};applyDefaults()}
async function show(target:AgendaOperatorTab='quick',detail:AgendaOperatorDetail={}):Promise<void>{open.value=true;tab.value=target;resetMessages();await loadData();customerMode.value=params.value?.default_customer_mode==='EXISTING'?'existing':'new';if(detail.startsAt)quick.value.starts_at=detail.startsAt;if(detail.customerId){customerMode.value='existing';selectCustomer(detail.customerId)}}
function close():void{open.value=false;reuseTarget.value=null;resetMessages()}

function quickPayload(confirmCustomerUpdate=false){
  const service=services.value.find((item)=>item.id===selectedServiceId.value)
  const professional=professionals.value.find((item)=>item.id===selectedProfessionalId.value)
  return{
    starts_at:new Date(quick.value.starts_at).toISOString(),
    customer_id:customerMode.value==='existing'&&selectedCustomerId.value?selectedCustomerId.value:null,
    customer_name:quick.value.customer_name.trim()||'Cliente',
    customer_phone:showPhone.value?(quick.value.customer_phone.trim()||null):null,
    customer_email:showEmail.value?(quick.value.customer_email.trim()||null):null,
    confirm_customer_update:confirmCustomerUpdate,
    service_id:showService.value&&selectedServiceId.value?selectedServiceId.value:null,
    service_name:showService.value?(freeService.value.trim()||service?.name||null):null,
    duration_minutes:showDuration.value?(Number(quick.value.duration_minutes)||params.value?.default_duration_minutes||60):null,
    price:showService.value?quick.value.price:null,
    professional_id:showProfessional.value&&selectedProfessionalId.value?selectedProfessionalId.value:null,
    professional_name:showProfessional.value?(professional?.name||quick.value.professional_name.trim()||null):(params.value?.default_professional_name||'Agenda geral'),
  }
}
function validateQuick():string{
  if(!quick.value.starts_at)return'Informe a data e o horário do atendimento.'
  if(customerMode.value==='existing'&&!selectedCustomerId.value)return'Selecione um cliente ou escolha “Novo cliente”.'
  if(customerMode.value==='new'&&!quick.value.customer_name.trim())return'Informe o nome do cliente.'
  if(customerMode.value==='new'&&phoneRequired.value&&!quick.value.customer_phone.trim())return'Informe o telefone/WhatsApp do cliente.'
  if(customerMode.value==='new'&&emailRequired.value&&!quick.value.customer_email.trim())return'Informe o e-mail do cliente.'
  if(serviceRequired.value&&!selectedServiceId.value&&!freeService.value.trim())return'Selecione ou informe o serviço.'
  return''
}
async function createQuick(confirmCustomerUpdate=false):Promise<void>{
  resetMessages();const validation=validateQuick();if(validation){error.value=validation;return} saving.value=true
  try{
    await api('/agenda/quick',{method:'POST',body:JSON.stringify({...quickPayload(confirmCustomerUpdate),source:'tenant-web-global-operator'})})
    success.value='Agendamento criado. O cliente existente foi reutilizado quando o telefone já estava cadastrado.';await loadData();notifyAppointmentsChanged();resetQuick(true)
  }catch(exc){
    if(exc instanceof AgendaApiError&&exc.code==='CUSTOMER_PHONE_MATCH_NAME_DIFFERS'){
      const oldName=String(exc.details.existing_name||'cliente cadastrado');const newName=String(exc.details.received_name||quick.value.customer_name)
      if(await confirmDialog({title:'Cliente já cadastrado',message:`Este telefone já está cadastrado para “${oldName}”. Deseja atualizar o nome para “${newName}” e usar o mesmo cliente?`,confirmLabel:'Atualizar e usar'})){saving.value=false;await createQuick(true);return}
    }
    error.value=exc instanceof Error?exc.message:'Falha ao criar agendamento.'
  }finally{saving.value=false}
}

function legacyRecurringPayload(){const service=services.value.find((item)=>item.id===selectedServiceId.value);const professional=professionals.value.find((item)=>item.id===selectedProfessionalId.value);return{starts_at:new Date(quick.value.starts_at).toISOString(),customer_id:selectedCustomerId.value||null,customer_name:quick.value.customer_name.trim()||'Cliente',customer_phone:quick.value.customer_phone.trim(),customer_email:quick.value.customer_email.trim()||null,service_id:selectedServiceId.value||null,service_name:service?.name||freeService.value.trim()||null,duration_minutes:Number(quick.value.duration_minutes)||params.value?.default_duration_minutes||60,price:quick.value.price,professional_id:selectedProfessionalId.value||null,professional_name:professional?.name||params.value?.default_professional_name||'Agenda geral'} }
async function createRecurring():Promise<void>{resetMessages();if(!quick.value.starts_at){error.value='Informe o primeiro horário da recorrência.';return}if(!selectedCustomerId.value){error.value='Selecione um cliente existente para a recorrência.';return}if(!quick.value.customer_phone.trim()){error.value='O fluxo recorrente atual exige que o cliente possua telefone cadastrado.';return}saving.value=true;try{const skipDates=recurrence.value.skip_dates.split(/[\s,;]+/).map((item)=>item.trim()).filter(Boolean);const result=await api<RecurringResult>('/appointments/recurring',{method:'POST',body:JSON.stringify({...legacyRecurringPayload(),source:'tenant-web-recurring',repeat_every_weeks:Number(recurrence.value.repeat_every_weeks),weekdays:recurrence.value.weekdays,months_ahead:recurrence.value.period==='until'?null:Number(recurrence.value.period),until:recurrence.value.period==='until'&&recurrence.value.until?recurrence.value.until:null,max_occurrences:Number(recurrence.value.max_occurrences)||104,skip_sundays:recurrence.value.skip_sundays,skip_dates:skipDates,conflict_policy:recurrence.value.conflict_policy})});success.value=`Recorrência processada: ${result.summary.created} criado(s), ${result.summary.skipped} ignorado(s).`;await loadData();notifyAppointmentsChanged()}catch(exc){error.value=exc instanceof Error?exc.message:'Falha ao criar recorrência.'}finally{saving.value=false}}
async function swapSlots():Promise<void>{resetMessages();if(!swap.value.first_id||!swap.value.second_id){error.value='Selecione os dois agendamentos que terão os horários permutados.';return}saving.value=true;try{await api('/appointments/swap',{method:'POST',body:JSON.stringify({first_id:swap.value.first_id,second_id:swap.value.second_id})});success.value='Horários permutados.';swap.value={first_id:'',second_id:''};await loadData();notifyAppointmentsChanged()}catch(exc){error.value=exc instanceof Error?exc.message:'Falha ao permutar os horários.'}finally{saving.value=false}}
function startReuse(item:Appointment):void{reuseTarget.value=item;tab.value='quick';customerMode.value='new';quick.value.starts_at=localInput(item.starts_at);selectedServiceId.value=item.service_id||'';selectedProfessionalId.value=item.professional_id;quick.value.duration_minutes=item.duration_minutes||params.value?.default_duration_minutes||60;quick.value.price=item.price??null;quick.value.customer_name='';quick.value.customer_phone='';quick.value.customer_email=''}
async function cancelItem(item:Appointment):Promise<void>{if(!await confirmDialog({title:'Cancelar agendamento',message:`Cancelar o agendamento de ${item.customer_name}?`,danger:true,confirmLabel:'Cancelar agendamento'}))return;resetMessages();saving.value=true;try{await api(`/appointments/${item.id}/cancel`,{method:'POST',body:JSON.stringify({reason:'Cancelado pelo gestor no Operador da Agenda'})});success.value='Agendamento cancelado e horário liberado.';await loadData();notifyAppointmentsChanged()}catch(exc){error.value=exc instanceof Error?exc.message:'Falha ao cancelar o agendamento.'}finally{saving.value=false}}
async function deleteItem(item:Appointment):Promise<void>{if(!await confirmDialog({title:'Excluir registro',message:`Excluir definitivamente o registro de ${item.customer_name}? A auditoria será preservada.`,danger:true,confirmLabel:'Excluir'}))return;resetMessages();saving.value=true;try{await api(`/appointments/${item.id}/permanent`,{method:'DELETE'});success.value='Agendamento removido com auditoria preservada.';await loadData();notifyAppointmentsChanged()}catch(exc){error.value=exc instanceof Error?exc.message:'Falha ao excluir o agendamento.'}finally{saving.value=false}}
async function copyConfirmation(item:Appointment):Promise<void>{resetMessages();try{const data=await api<{enabled:boolean;request?:{url?:string}|null}>(`/appointment-confirmations/${item.id}`);const url=data.request?.url;if(!url)throw new Error('Este agendamento não possui link de confirmação ativo.');await navigator.clipboard.writeText(url);success.value='Link de confirmação copiado.'}catch(exc){error.value=exc instanceof Error?exc.message:'Falha ao copiar o link.'}}
function onOperatorEvent(event:Event):void{const detail=(event as CustomEvent<AgendaOperatorDetail>).detail||{};void show(detail.tab||'quick',detail)}

onMounted(()=>window.addEventListener(AGENDA_OPERATOR_EVENT,onOperatorEvent))
onUnmounted(()=>window.removeEventListener(AGENDA_OPERATOR_EVENT,onOperatorEvent))
</script>

<template>
  <button class="sp-global-agenda-operator" type="button" title="Criar ou operar agendamento" @click="show('quick')"><CalendarPlus :size="18"/><span>Novo agendamento</span></button>
  <div v-if="open" class="sp-agenda-operator-backdrop" @click.self="close">
    <section class="sp-agenda-operator" role="dialog" aria-modal="true" aria-label="Operador da Agenda">
      <header><div><span>Scheduler Pro · Agenda</span><h2>Operador da Agenda</h2><p>Crie e gerencie atendimentos de qualquer área da aplicação.</p></div><button aria-label="Fechar" @click="close"><X :size="20"/></button></header>
      <nav><button :class="{active:tab==='quick'}" @click="tab='quick'"><UserPlus :size="15"/>Agendar</button><button :class="{active:tab==='recurring'}" @click="tab='recurring'"><Repeat2 :size="15"/>Recorrência</button><button :class="{active:tab==='swap'}" @click="tab='swap'"><Shuffle :size="15"/>Permutar</button><button :class="{active:tab==='manage'}" @click="tab='manage'"><CalendarPlus :size="15"/>Gerenciar</button></nav>
      <p v-if="success" class="sp-operator-success"><Check :size="16"/>{{success}}</p><p v-if="error" class="sp-operator-error">{{error}}</p>
      <div v-if="loading" class="sp-operator-loading"><RefreshCw class="spin" :size="20"/>Atualizando dados...</div>
      <main v-else>
        <section v-if="tab==='quick'" class="sp-operator-form">
          <div v-if="reuseTarget" class="sp-reuse-banner"><strong>Reutilizando {{formatDate(reuseTarget.starts_at)}}</strong><span>O registro anterior continua preservado na auditoria.</span></div>
          <div class="sp-segment"><button :class="{active:customerMode==='new'}" @click="customerMode='new'">Novo cliente</button><button :class="{active:customerMode==='existing'}" @click="customerMode='existing'">Cliente existente</button></div>
          <template v-if="customerMode==='new'">
            <div class="sp-operator-grid"><label>Nome<input v-model="quick.customer_name" autocomplete="name"/></label><label v-if="showPhone">Telefone / WhatsApp <small v-if="!phoneRequired">opcional</small><input v-model="quick.customer_phone" inputmode="tel"/></label><label v-if="showEmail">E-mail <small v-if="!emailRequired">opcional</small><input v-model="quick.customer_email" type="email"/></label></div>
            <p v-if="showPhone" class="sp-field-help">Se o telefone já estiver cadastrado, o Scheduler Pro reutiliza o cliente. Se o nome for diferente, pede sua confirmação antes de atualizar.</p>
          </template>
          <template v-else>
            <label>Localizar cliente<input v-model="customerSearch" placeholder="Nome, telefone ou e-mail"/></label>
            <label class="sp-customer-select-desktop">Cliente<select v-model="selectedCustomerId" @change="chooseCustomer"><option value="">Selecione um cliente</option><option v-for="item in filteredCustomers" :key="item.id" :value="item.id">{{item.name}} · {{item.phone||item.email||'sem contato'}}</option></select></label>
            <div class="sp-customer-picker-mobile"><button v-for="item in filteredCustomers" :key="item.id" type="button" :class="{selected:selectedCustomerId===item.id}" @click="selectCustomer(item.id)"><strong>{{item.name}}</strong><small>{{item.phone||item.email||'Sem contato informado'}}</small></button></div>
          </template>

          <div class="sp-operator-grid">
            <label v-if="showService">Serviço <small v-if="!serviceRequired">opcional/livre</small><select v-model="selectedServiceId" @change="chooseService"><option value="">Serviço livre / não informado</option><option v-for="item in services.filter(s=>s.active)" :key="item.id" :value="item.id">{{item.name}} · {{item.duration_minutes>0?item.duration_minutes+' min':'duração variável'}}</option></select></label>
            <label v-if="showService&&!selectedServiceId">Descrição do serviço<input v-model="freeService" placeholder="Ex.: Avaliação, retoque, orçamento"/></label>
            <label v-if="showService">Valor<input v-model.number="quick.price" type="number" min="0" step="0.01" placeholder="Opcional"/></label>
            <label v-if="showProfessional">Profissional / responsável<select v-model="selectedProfessionalId" @change="chooseProfessional"><option value="">{{params?.default_professional_name||'Agenda geral'}}</option><option v-for="item in professionals" :key="item.id" :value="item.id">{{item.name}}</option></select></label>
            <label>Data e horário<input v-model="quick.starts_at" type="datetime-local"/></label>
            <label v-if="showDuration">Tempo / duração<input v-model.number="quick.duration_minutes" type="number" min="5" max="720"/><small>Desative este campo nas configurações quando o negócio não trabalha com duração individual.</small></label>
          </div>
          <div v-if="params" class="sp-rule-summary"><span v-if="!params.simultaneous.enforce_internal">Sem limite de atendimentos simultâneos</span><span v-else>Capacidade simultânea: {{params.simultaneous.internal?params.simultaneous.capacity:1}}</span><span v-if="!params.rules.enforce_business_hours">Expediente não restringe o operador</span><span v-if="!params.rules.enforce_blocked_periods">Bloqueios de horário desativados</span></div>
          <button class="sp-operator-primary" :disabled="saving" @click="createQuick(false)"><CalendarPlus :size="16"/>{{saving?'Salvando...':'Criar agendamento'}}</button>
        </section>

        <section v-else-if="tab==='recurring'" class="sp-operator-form">
          <p class="sp-operator-help">Para recorrências, selecione um cliente existente. O fluxo mantém as regras históricas de confirmação e auditoria.</p>
          <label>Cliente<select v-model="selectedCustomerId" @change="chooseCustomer"><option value="">Selecione um cliente</option><option v-for="item in customers" :key="item.id" :value="item.id">{{item.name}} · {{item.phone||'sem telefone'}}</option></select></label>
          <div class="sp-operator-grid"><label v-if="showService">Serviço<select v-model="selectedServiceId" @change="chooseService"><option value="">Sem serviço</option><option v-for="item in services.filter(s=>s.active)" :key="item.id" :value="item.id">{{item.name}}</option></select></label><label v-if="showProfessional">Profissional<select v-model="selectedProfessionalId" @change="chooseProfessional"><option v-for="item in professionals" :key="item.id" :value="item.id">{{item.name}}</option></select></label><label>Primeiro horário<input v-model="quick.starts_at" type="datetime-local"/></label></div>
          <fieldset><legend>Dias da semana</legend><div class="sp-weekday-picks"><label v-for="(name,index) in ['Seg','Ter','Qua','Qui','Sex','Sáb','Dom']" :key="name"><input v-model="recurrence.weekdays" type="checkbox" :value="index"/>{{name}}</label></div></fieldset>
          <div class="sp-operator-grid"><label>Repetir a cada<select v-model.number="recurrence.repeat_every_weeks"><option :value="1">1 semana</option><option :value="2">2 semanas</option><option :value="3">3 semanas</option><option :value="4">4 semanas</option></select></label><label>Período<select v-model="recurrence.period"><option value="1">1 mês</option><option value="3">3 meses</option><option value="6">6 meses</option><option value="12">12 meses</option><option value="until">Até uma data</option></select></label><label v-if="recurrence.period==='until'">Até<input v-model="recurrence.until" type="date"/></label><label>Máximo<input v-model.number="recurrence.max_occurrences" type="number" min="1" max="366"/></label></div>
          <label class="sp-check"><input v-model="recurrence.skip_sundays" type="checkbox"/>Ignorar domingos</label><label>Datas a ignorar<textarea v-model="recurrence.skip_dates" placeholder="2026-09-07, 2026-10-12"></textarea></label><label>Conflito<select v-model="recurrence.conflict_policy"><option value="skip">Ignorar e continuar</option><option value="abort">Parar no primeiro conflito</option></select></label>
          <button class="sp-operator-primary" :disabled="saving" @click="createRecurring"><Repeat2 :size="16"/>{{saving?'Processando...':'Criar recorrência'}}</button>
        </section>

        <section v-else-if="tab==='swap'" class="sp-operator-form"><p class="sp-operator-help">Permuta os horários completos de dois agendamentos e solicita nova confirmação.</p><label>Primeiro agendamento<select v-model="swap.first_id"><option value="">Selecione</option><option v-for="item in activeAppointments" :key="item.id" :value="item.id">{{formatDate(item.starts_at)}} · {{item.customer_name}} · {{item.professional_name}}</option></select></label><label>Segundo agendamento<select v-model="swap.second_id"><option value="">Selecione</option><option v-for="item in activeAppointments.filter(row=>row.id!==swap.first_id)" :key="item.id" :value="item.id">{{formatDate(item.starts_at)}} · {{item.customer_name}} · {{item.professional_name}}</option></select></label><button class="sp-operator-primary" :disabled="saving" @click="swapSlots"><Shuffle :size="16"/>Permutar horários</button></section>

        <section v-else class="sp-manage-list"><article v-for="item in manageableAppointments" :key="item.id"><div class="sp-manage-time"><strong>{{new Date(item.starts_at).toLocaleTimeString('pt-BR',{hour:'2-digit',minute:'2-digit'})}}</strong><small>{{new Date(item.starts_at).toLocaleDateString('pt-BR')}}</small></div><div class="sp-manage-info"><strong>{{item.customer_name}}</strong><span>{{item.service_name||'Sem serviço'}} · {{item.professional_name}}</span><em :class="item.status.toLowerCase()">{{humanStatus(item.status)}}</em></div><div class="sp-manage-actions"><button v-if="['PENDING','AWAITING_CONFIRMATION','RESCHEDULED'].includes(item.status)" @click="copyConfirmation(item)"><Copy :size="13"/>Link</button><button v-if="!['COMPLETED','CANCELLED','NO_SHOW'].includes(item.status)" @click="cancelItem(item)">Cancelar</button><button v-if="['CANCELLED','NO_SHOW'].includes(item.status)&&new Date(item.starts_at).getTime()>Date.now()" @click="startReuse(item)">Reutilizar</button><button v-if="['COMPLETED','CANCELLED','NO_SHOW'].includes(item.status)" class="danger" @click="deleteItem(item)"><Trash2 :size="13"/>Excluir</button></div></article><div v-if="!manageableAppointments.length" class="sp-operator-loading">Nenhum agendamento disponível.</div></section>
      </main>
    </section>
  </div>
</template>

<style>
.sp-global-agenda-operator{position:fixed;right:22px;bottom:22px;z-index:1200;min-height:48px;padding:0 17px;border:0;border-radius:15px;background:linear-gradient(135deg,#0b1d3a,#159ec5);color:#fff;display:flex;align-items:center;gap:8px;font:inherit;font-size:12px;font-weight:900;box-shadow:0 16px 42px rgba(15,43,76,.28);cursor:pointer}.sp-global-agenda-operator:hover{transform:translateY(-1px)}.sp-agenda-operator-backdrop{position:fixed;z-index:1600;inset:0;display:grid;place-items:center;padding:24px;background:rgba(8,18,35,.58);backdrop-filter:blur(5px)}.sp-agenda-operator{width:min(980px,96vw);max-height:92dvh;overflow:auto;border:1px solid #dce4ef;border-radius:24px;background:#f7f9fc;color:#11233c;box-shadow:0 28px 90px rgba(8,18,35,.32)}.sp-agenda-operator>header{display:flex;justify-content:space-between;gap:18px;padding:23px 25px 17px;background:#fff;border-bottom:1px solid #e5eaf1}.sp-agenda-operator header span{font-size:10px;font-weight:900;text-transform:uppercase;letter-spacing:.09em;color:#2563eb}.sp-agenda-operator header h2{margin:5px 0;font-size:25px;letter-spacing:-.035em}.sp-agenda-operator header p{margin:0;color:#52647d;font-size:12px}.sp-agenda-operator header button{width:42px;height:42px;display:grid;place-items:center;border:1px solid #dbe3ed;border-radius:12px;background:#fff;cursor:pointer}.sp-agenda-operator>nav{position:sticky;top:0;z-index:4;display:grid;grid-template-columns:repeat(4,1fr);gap:6px;padding:10px 14px;background:rgba(255,255,255,.98);border-bottom:1px solid #e4e9f1}.sp-agenda-operator>nav button{height:42px;display:flex;align-items:center;justify-content:center;gap:6px;border:1px solid transparent;border-radius:11px;background:transparent;color:#50627b;font:inherit;font-size:11px;font-weight:850;cursor:pointer}.sp-agenda-operator>nav button.active{border-color:#bfdbfe;background:#eff6ff;color:#1d4ed8}.sp-agenda-operator main{padding:18px 22px 26px}.sp-operator-success,.sp-operator-error{display:flex;align-items:flex-start;gap:8px;margin:12px 22px 0;padding:11px 13px;border-radius:12px;font-size:12px;font-weight:750}.sp-operator-success{background:#ecfdf5;color:#047857}.sp-operator-error{background:#fff1f2;color:#be123c}.sp-operator-loading{padding:48px 20px;text-align:center;color:#53657d;font-size:12px}.sp-operator-form{display:grid;gap:13px}.sp-operator-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:11px}.sp-operator-form label{display:grid;gap:6px;color:#334761;font-size:10px;font-weight:850;text-transform:uppercase;letter-spacing:.04em}.sp-operator-form label>small{display:inline;color:#6c7d92;font-size:9px;text-transform:none}.sp-operator-form input,.sp-operator-form select,.sp-operator-form textarea{width:100%;min-height:44px;border:1px solid #cbd7e6;border-radius:11px;background:#fff;padding:0 11px;color:#142943;font:inherit;font-size:12px;text-transform:none;letter-spacing:normal;outline:none}.sp-operator-form textarea{min-height:90px;padding:10px}.sp-field-help,.sp-operator-help{margin:0;padding:11px 13px;border-radius:11px;background:#eff6ff;color:#33527c;font-size:11px;line-height:1.5}.sp-segment{display:grid;grid-template-columns:1fr 1fr;padding:4px;border:1px solid #d5e0ec;border-radius:13px;background:#fff}.sp-segment button{min-height:39px;border:0;border-radius:9px;background:transparent;font:inherit;font-size:11px;font-weight:850;color:#5d6f87;cursor:pointer}.sp-segment button.active{background:#0b1d3a;color:#fff}.sp-customer-picker-mobile{display:none}.sp-rule-summary{display:flex;flex-wrap:wrap;gap:7px}.sp-rule-summary span{padding:7px 9px;border-radius:999px;background:#f1f5f9;color:#41546d;font-size:10px;font-weight:750}.sp-operator-primary{min-height:48px;display:flex;align-items:center;justify-content:center;gap:7px;border:0;border-radius:12px;background:linear-gradient(135deg,#0b1d3a,#24c2ed);color:#fff;font:inherit;font-size:12px;font-weight:900;box-shadow:0 11px 28px rgba(23,115,185,.18);cursor:pointer}.sp-operator-primary:disabled{opacity:.6}.sp-operator-form fieldset{margin:0;padding:12px;border:1px solid #dce4ee;border-radius:13px;background:#fff}.sp-operator-form legend{padding:0 5px;color:#53647c;font-size:10px;font-weight:900;text-transform:uppercase}.sp-weekday-picks{display:grid;grid-template-columns:repeat(7,1fr);gap:5px}.sp-weekday-picks label{display:flex;align-items:center;justify-content:center;gap:4px;min-height:36px;border:1px solid #e2e8f0;border-radius:9px;background:#fafcff;font-size:10px;text-transform:none}.sp-weekday-picks input,.sp-check input{width:auto;min-height:0}.sp-check{display:flex!important;align-items:center!important;grid-template-columns:auto 1fr!important;gap:8px!important;min-height:40px;padding:0 11px;border:1px solid #dce4ee;border-radius:11px;background:#fff;text-transform:none!important}.sp-reuse-banner{display:grid;gap:3px;padding:12px 14px;border:1px solid #a7f3d0;border-radius:12px;background:#ecfdf5;color:#065f46}.sp-reuse-banner span{font-size:11px}.sp-manage-list{display:grid;gap:9px}.sp-manage-list article{display:grid;grid-template-columns:74px minmax(0,1fr) auto;gap:12px;align-items:center;padding:12px 14px;border:1px solid #dbe5ef;border-radius:15px;background:#fff}.sp-manage-time strong,.sp-manage-time small,.sp-manage-info strong,.sp-manage-info span{display:block}.sp-manage-time strong{font-size:16px;color:#1d4ed8}.sp-manage-time small{margin-top:3px;color:#66788f;font-size:9px}.sp-manage-info strong{font-size:12px}.sp-manage-info span{margin:3px 0 6px;color:#52647c;font-size:10px}.sp-manage-info em{display:inline-flex;padding:4px 7px;border-radius:999px;background:#f1f5f9;color:#475569;font-size:9px;font-style:normal;font-weight:850}.sp-manage-info em.confirmed,.sp-manage-info em.completed{background:#dcfce7;color:#166534}.sp-manage-info em.cancelled,.sp-manage-info em.no_show{background:#fee2e2;color:#991b1b}.sp-manage-actions{display:flex;flex-wrap:wrap;justify-content:flex-end;gap:5px}.sp-manage-actions button{min-height:32px;display:flex;align-items:center;gap:4px;border:1px solid #dce4ef;border-radius:9px;background:#fff;color:#334155;font:inherit;font-size:9px;font-weight:850;cursor:pointer}.sp-manage-actions button.danger{border-color:#fecaca;color:#b91c1c}.spin{animation:sp-operator-spin 1s linear infinite}@keyframes sp-operator-spin{to{transform:rotate(360deg)}}
@media(max-width:700px){.sp-global-agenda-operator{right:13px;bottom:13px;width:50px;height:50px;padding:0;justify-content:center;border-radius:50%}.sp-global-agenda-operator span{display:none}.sp-agenda-operator-backdrop{align-items:end;padding:0}.sp-agenda-operator{width:100vw;max-height:94dvh;border-radius:24px 24px 0 0;border-bottom:0}.sp-agenda-operator>header{padding:18px 16px 14px}.sp-agenda-operator header h2{font-size:22px}.sp-agenda-operator>nav{grid-template-columns:repeat(4,minmax(0,1fr));padding:8px}.sp-agenda-operator>nav button{display:grid;height:52px;gap:2px;font-size:9px}.sp-agenda-operator main{padding:14px 13px 28px}.sp-operator-grid{grid-template-columns:1fr}.sp-weekday-picks{grid-template-columns:repeat(4,1fr)}.sp-manage-list article{grid-template-columns:58px minmax(0,1fr);align-items:start}.sp-manage-actions{grid-column:1/-1;display:grid;grid-template-columns:repeat(2,1fr);justify-content:stretch}.sp-manage-actions button{min-height:40px;justify-content:center}.sp-operator-success,.sp-operator-error{margin:10px 13px 0}.sp-operator-form input,.sp-operator-form select,.sp-operator-form textarea{font-size:16px}.sp-customer-select-desktop{display:none!important}.sp-customer-picker-mobile{display:grid;gap:8px;max-height:280px;overflow:auto}.sp-customer-picker-mobile button{display:grid;gap:3px;width:100%;min-height:58px;padding:11px 12px;border:1px solid #dbe4ef;border-radius:13px;background:#fff;color:#1e293b;text-align:left;font:inherit}.sp-customer-picker-mobile button.selected{border-color:#38bdf8;background:#effaff}.sp-rule-summary{display:grid}.sp-rule-summary span{text-align:center}}
</style>
