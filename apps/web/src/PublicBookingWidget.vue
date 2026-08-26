<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { CalendarDays, CheckCircle2, Clock3, LoaderCircle, UserRound, Wrench } from 'lucide-vue-next'

type Service = { id:string; name:string; duration_minutes:number; price?:number|null }
type Professional = { id:string; name:string }
type Slot = { starts_at:string; ends_at:string; available:boolean; professional_id:string; professional_name:string; service_id?:string|null; remaining_capacity?:number }
type BookingConfig = {
  enabled:boolean; title:string; subtitle:string; success_message:string; custom_html:string; allow_any_professional:boolean
  require_name:boolean; require_phone:boolean; service_mode:'DISABLED'|'OPTIONAL'|'REQUIRED'; email_mode:'DISABLED'|'OPTIONAL'|'REQUIRED'
  default_duration_minutes:number; simultaneous_capacity:number; public_url:string
}
type Catalog = { config:BookingConfig; services:Service[]; professionals:Professional[] }
type Envelope<T> = { data?:T; error?:{message?:string;code?:string} }
type BookingSuccess = { message:string; service_name?:string|null; professional_name:string; starts_at:string }

const props=defineProps<{catalog:Catalog}>()
const emit=defineEmits<{(event:'booked'):void}>()
const slotsLoading=ref(false),submitting=ref(false),error=ref('')
const success=ref<BookingSuccess|null>(null),serviceId=ref(''),professionalId=ref(''),day=ref(todayPlus(1))
const slots=ref<Slot[]>([]),selectedSlot=ref<Slot|null>(null),customer=ref({name:'',phone:'',email:''})

const serviceEnabled=computed(()=>props.catalog.config.service_mode!=='DISABLED')
const serviceRequired=computed(()=>props.catalog.config.service_mode==='REQUIRED')
const emailEnabled=computed(()=>props.catalog.config.email_mode!=='DISABLED')
const emailRequired=computed(()=>props.catalog.config.email_mode==='REQUIRED')
const selectedService=computed(()=>props.catalog.services.find(item=>item.id===serviceId.value)||null)
const stepSchedule=computed(()=>serviceEnabled.value?2:1),stepCustomer=computed(()=>serviceEnabled.value?3:2)

function todayPlus(days:number):string{const value=new Date();value.setDate(value.getDate()+days);const offset=value.getTimezoneOffset()*60000;return new Date(value.getTime()-offset).toISOString().slice(0,10)}
function formatMoney(value?:number|null):string{return value==null?'':new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL'}).format(value)}
function formatDay(value:string):string{return new Date(`${value}T12:00:00`).toLocaleDateString('pt-BR',{weekday:'long',day:'2-digit',month:'long'})}
function formatTime(value:string):string{return new Date(value).toLocaleTimeString('pt-BR',{hour:'2-digit',minute:'2-digit'})}
async function request<T>(path:string,init:RequestInit={}):Promise<T>{const response=await fetch(`${window.location.origin}/api/v1/public${path}`,{...init,cache:'no-store',headers:{Accept:'application/json',...(init.body?{'content-type':'application/json'}:{}),...(init.headers||{})}});const payload=await response.json().catch(()=>({})) as Envelope<T>;if(!response.ok||payload.data===undefined)throw new Error(payload.error?.message||`Falha HTTP ${response.status}`);return payload.data}

async function loadSlots():Promise<void>{selectedSlot.value=null;slots.value=[];if(!day.value||(serviceRequired.value&&!serviceId.value))return;slotsLoading.value=true;error.value='';try{const query=new URLSearchParams({day:day.value});if(serviceId.value&&serviceEnabled.value)query.set('service_id',serviceId.value);if(professionalId.value)query.set('professional_id',professionalId.value);slots.value=await request<Slot[]>(`/booking/availability?${query.toString()}`)}catch(exc){error.value=exc instanceof Error?exc.message:'Não foi possível consultar os horários.'}finally{slotsLoading.value=false}}
async function book():Promise<void>{if(!selectedSlot.value){error.value='Escolha um horário disponível.';return}if(!customer.value.name.trim()){error.value='Informe seu nome.';return}if(!customer.value.phone.trim()){error.value='Informe seu telefone/WhatsApp.';return}if(serviceRequired.value&&!serviceId.value){error.value='Escolha um serviço.';return}if(emailRequired.value&&!customer.value.email.trim()){error.value='Informe seu e-mail.';return}submitting.value=true;error.value='';try{success.value=await request<BookingSuccess>('/booking',{method:'POST',body:JSON.stringify({service_id:serviceEnabled.value&&serviceId.value?serviceId.value:null,professional_id:selectedSlot.value.professional_id,starts_at:selectedSlot.value.starts_at,customer_name:customer.value.name.trim(),customer_phone:customer.value.phone.trim(),customer_email:emailEnabled.value&&customer.value.email.trim()?customer.value.email.trim():null})});slots.value=[];emit('booked')}catch(exc){error.value=exc instanceof Error?exc.message:'Não foi possível concluir o agendamento.';await loadSlots()}finally{submitting.value=false}}
function reset():void{success.value=null;selectedSlot.value=null;void loadSlots()}
watch([serviceId,professionalId,day],()=>void loadSlots())
onMounted(()=>{if(props.catalog.config.service_mode==='REQUIRED'&&props.catalog.services.length)serviceId.value=props.catalog.services[0].id;void loadSlots()})
</script>

<template>
  <section v-if="success" class="public-booking-success">
    <CheckCircle2 :size="52"/><span>Reserva criada</span><h2>{{ success.message }}</h2>
    <p><strong v-if="success.service_name">{{ success.service_name }} · </strong>{{ success.professional_name }}</p>
    <time>{{ new Date(success.starts_at).toLocaleString('pt-BR',{dateStyle:'full',timeStyle:'short'}) }}</time>
    <small>A confirmação será enviada pelos canais configurados pelo estabelecimento.</small><button type="button" @click="reset">Fazer outro agendamento</button>
  </section>

  <section v-else class="public-booking-workspace" :class="{'without-service':!serviceEnabled}">
    <article v-if="serviceEnabled" class="public-booking-card public-booking-options">
      <div class="section-title"><Wrench :size="20"/><div><span>1. Atendimento</span><strong>{{ serviceRequired?'Escolha o serviço':'Serviço opcional' }}</strong></div></div>
      <label>Serviço<select v-model="serviceId"><option v-if="!serviceRequired" value="">Sem serviço específico</option><option v-for="item in catalog.services" :key="item.id" :value="item.id">{{ item.name }} · {{ item.duration_minutes }} min{{ item.price!=null?` · ${formatMoney(item.price)}`:'' }}</option></select></label>
      <div v-if="selectedService" class="service-summary"><strong>{{ selectedService.name }}</strong><span>{{ selectedService.duration_minutes }} minutos</span></div>
    </article>

    <article class="public-booking-card public-booking-slots">
      <div class="section-title"><CalendarDays :size="20"/><div><span>{{ stepSchedule }}. Data e horário</span><strong>{{ formatDay(day) }}</strong></div></div>
      <div class="schedule-fields"><label>Profissional<select v-model="professionalId"><option v-if="catalog.config.allow_any_professional" value="">Qualquer profissional disponível</option><option v-for="item in catalog.professionals" :key="item.id" :value="item.id">{{ item.name }}</option></select></label><label>Data<input v-model="day" type="date" :min="todayPlus(0)"/></label></div>
      <div v-if="slotsLoading" class="slot-loading"><LoaderCircle :size="22" class="spin"/> Atualizando disponibilidade...</div>
      <div v-else-if="slots.length" class="slot-grid"><button v-for="slot in slots" :key="`${slot.professional_id}-${slot.starts_at}`" type="button" :class="{selected:selectedSlot?.professional_id===slot.professional_id&&selectedSlot?.starts_at===slot.starts_at}" @click="selectedSlot=slot"><Clock3 :size="17"/><strong>{{ formatTime(slot.starts_at) }}</strong><small>{{ slot.professional_name }}</small><em v-if="(slot.remaining_capacity||0)>1">{{ slot.remaining_capacity }} vagas</em></button></div>
      <div v-else class="slot-empty">Nenhum horário disponível. Escolha outra data ou profissional.</div>
    </article>

    <article class="public-booking-card public-booking-customer">
      <div class="section-title"><UserRound :size="20"/><div><span>{{ stepCustomer }}. Seus dados</span><strong>Finalizar reserva</strong></div></div>
      <form @submit.prevent="book"><label>Nome<input v-model="customer.name" autocomplete="name" required minlength="2"/></label><label>WhatsApp / telefone<input v-model="customer.phone" type="tel" inputmode="tel" autocomplete="tel" required/></label><label v-if="emailEnabled">E-mail<input v-model="customer.email" type="email" autocomplete="email" :required="emailRequired"/></label><p v-if="error" class="public-booking-error">{{ error }}</p><button class="public-booking-submit" :disabled="submitting||!selectedSlot"><LoaderCircle v-if="submitting" :size="18" class="spin"/><CalendarDays v-else :size="18"/>{{ submitting?'Reservando...':'Reservar horário' }}</button><small>Você receberá a confirmação pelos canais configurados pelo estabelecimento.</small></form>
    </article>
  </section>
</template>

<style scoped>
.public-booking-workspace{display:grid;grid-template-columns:.8fr 1.3fr .95fr;gap:16px;align-items:start}.public-booking-workspace.without-service{grid-template-columns:1.35fr .95fr}.public-booking-card{border:1px solid #e0e7ef;border-radius:20px;background:#fff;padding:20px;box-shadow:0 12px 34px rgba(15,23,42,.055)}.section-title{display:flex;align-items:center;gap:10px;margin-bottom:18px;color:var(--sp-primary,var(--page-primary,#2563eb))}.section-title span{font-size:10px;font-weight:900;letter-spacing:.12em;text-transform:uppercase;color:#64748b}.section-title strong{display:block;margin-top:3px;color:#0f172a}.public-booking-card label{display:grid;gap:7px;margin:13px 0;color:#334155;font-size:12px;font-weight:800}.public-booking-card input,.public-booking-card select{width:100%;box-sizing:border-box;min-height:47px;border:1px solid #cbd5e1;border-radius:12px;padding:0 12px;background:#fff;color:#0f172a;font:inherit;font-size:16px;outline:none}.public-booking-card input:focus,.public-booking-card select:focus{border-color:var(--sp-primary,var(--page-primary,#2563eb));box-shadow:0 0 0 3px color-mix(in srgb,var(--sp-primary,var(--page-primary,#2563eb)) 13%,transparent)}.schedule-fields{display:grid;grid-template-columns:1fr 1fr;gap:10px}.service-summary{display:flex;justify-content:space-between;gap:8px;margin-top:15px;padding:12px;border-radius:12px;background:#f1f5f9;color:#475569;font-size:12px}.slot-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;max-height:480px;overflow:auto;padding-right:3px}.slot-grid button{min-height:70px;border:1px solid #dbe4ef;border-radius:13px;background:#fff;display:grid;grid-template-columns:auto 1fr;align-items:center;gap:4px 8px;padding:10px;text-align:left;color:#334155;cursor:pointer}.slot-grid button strong{font-size:15px}.slot-grid button small,.slot-grid button em{grid-column:1/-1;color:#64748b;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-style:normal;font-size:11px}.slot-grid button.selected{border-color:var(--sp-primary,var(--page-primary,#2563eb));background:color-mix(in srgb,var(--sp-primary,var(--page-primary,#2563eb)) 8%,white);box-shadow:0 0 0 2px color-mix(in srgb,var(--sp-primary,var(--page-primary,#2563eb)) 12%,transparent)}.slot-empty,.slot-loading{padding:34px 12px;border-radius:14px;background:#f8fafc;color:#64748b;text-align:center;line-height:1.5}.slot-loading{display:flex;justify-content:center;align-items:center;gap:8px}.public-booking-customer form{display:grid}.public-booking-submit,.public-booking-success button{min-height:49px;border:0;border-radius:13px;background:linear-gradient(135deg,var(--sp-primary,var(--page-primary,#2563eb)),var(--sp-accent,var(--page-accent,#7c3aed)));color:#fff;font:inherit;font-weight:900;display:flex;align-items:center;justify-content:center;gap:8px;cursor:pointer}.public-booking-submit:disabled{opacity:.5;cursor:not-allowed}.public-booking-customer form>small{margin-top:10px;color:#64748b;line-height:1.45}.public-booking-error{padding:10px 12px;border-radius:10px;background:#fef2f2;color:#b91c1c;font-size:12px}.public-booking-success{max-width:720px;margin:0 auto;padding:clamp(26px,6vw,46px);border:1px solid #bbf7d0;border-radius:26px;background:#fff;text-align:center;box-shadow:0 22px 60px rgba(15,23,42,.08)}.public-booking-success>svg{color:#16a34a}.public-booking-success>span{display:block;margin-top:16px;color:#16a34a;font-size:11px;font-weight:900;text-transform:uppercase;letter-spacing:.12em}.public-booking-success h2{font-size:clamp(24px,5vw,30px);line-height:1.2}.public-booking-success p,.public-booking-success time,.public-booking-success small{display:block;margin:12px 0;color:#475569}.public-booking-success button{margin:22px auto 0;padding:0 20px}.spin{animation:sp-spin 1s linear infinite}@keyframes sp-spin{to{transform:rotate(360deg)}}
@media(max-width:960px){.public-booking-workspace,.public-booking-workspace.without-service{grid-template-columns:1fr 1fr}.public-booking-customer{grid-column:1/-1}.slot-grid{grid-template-columns:repeat(4,minmax(0,1fr))}}
@media(max-width:680px){.public-booking-workspace,.public-booking-workspace.without-service{grid-template-columns:1fr;gap:10px}.public-booking-customer{grid-column:auto}.public-booking-card{padding:16px;border-radius:17px}.schedule-fields{grid-template-columns:1fr}.slot-grid{grid-template-columns:repeat(2,minmax(0,1fr));max-height:none}.public-booking-success{margin:0}.public-booking-card input,.public-booking-card select{font-size:16px}}
</style>
