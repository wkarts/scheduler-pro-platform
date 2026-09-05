<script setup lang="ts">
import EntityCombobox from "../../../packages/ui/EntityCombobox.vue"
import { computed, onMounted, ref, watch, type CSSProperties } from 'vue'
import { CalendarDays, CheckCircle2, Clock3, LoaderCircle, UserRound, Wrench } from 'lucide-vue-next'

type FieldMode='DISABLED'|'OPTIONAL'|'REQUIRED'
type Service={id:string;name:string;duration_minutes:number;price?:number|null}
type Professional={id:string;name:string}
type Slot={starts_at:string;ends_at:string;available:boolean;professional_id:string;professional_name:string;service_id?:string|null;remaining_capacity?:number|null;unlimited_capacity?:boolean}
type BookingTemplate={key:string;version:number;content:{global_styles?:Record<string,unknown>;layout?:Record<string,unknown>;copy?:Record<string,unknown>}}
type BookingConfig={
  enabled:boolean;title:string;subtitle:string;success_message:string;custom_html:string;allow_any_professional:boolean
  require_name:boolean;require_phone:boolean;service_mode:FieldMode;email_mode:FieldMode;phone_mode:FieldMode;duration_mode:FieldMode;professional_mode:FieldMode
  default_duration_minutes:number;default_professional_name:string;simultaneous_capacity?:number|null;unlimited_capacity?:boolean;public_url:string;booking_template?:BookingTemplate|null
}
type Catalog={config:BookingConfig;services:Service[];professionals:Professional[]}
type Envelope<T>={data?:T;error?:{message?:string;code?:string}}
type BookingSuccess={message:string;service_name?:string|null;professional_name:string;starts_at:string}

const props=defineProps<{catalog:Catalog}>()
const emit=defineEmits<{(event:'booked'):void}>()
const slotsLoading=ref(false),submitting=ref(false),error=ref('')
const success=ref<BookingSuccess|null>(null),serviceId=ref(''),professionalId=ref(''),day=ref(todayPlus(1))
const slots=ref<Slot[]>([]),selectedSlot=ref<Slot|null>(null),customer=ref({name:'',phone:'',email:''})

const serviceEnabled=computed(()=>props.catalog.config.service_mode!=='DISABLED')
const serviceRequired=computed(()=>props.catalog.config.service_mode==='REQUIRED')
const emailEnabled=computed(()=>props.catalog.config.email_mode!=='DISABLED')
const emailRequired=computed(()=>props.catalog.config.email_mode==='REQUIRED')
const phoneEnabled=computed(()=>props.catalog.config.phone_mode!=='DISABLED')
const phoneRequired=computed(()=>props.catalog.config.phone_mode==='REQUIRED')
const professionalEnabled=computed(()=>props.catalog.config.professional_mode!=='DISABLED')
const professionalRequired=computed(()=>props.catalog.config.professional_mode==='REQUIRED')
const durationEnabled=computed(()=>props.catalog.config.duration_mode!=='DISABLED')
const selectedService=computed(()=>props.catalog.services.find(item=>item.id===serviceId.value)||null)
const stepSchedule=computed(()=>serviceEnabled.value?2:1)
const stepCustomer=computed(()=>serviceEnabled.value?3:2)
const templateStyles=computed<CSSProperties>(()=>{
  const globals=props.catalog.config.booking_template?.content?.global_styles||{}
  return {
    '--booking-primary':String(globals.primary||'var(--sp-primary,#2563eb)'),
    '--booking-secondary':String(globals.secondary||'#0f172a'),
    '--booking-accent':String(globals.accent||'var(--sp-accent,#7c3aed)'),
    '--booking-bg':String(globals.background||'#f5f7fb'),
    '--booking-surface':String(globals.surface||'#ffffff'),
    '--booking-text':String(globals.text||'#17233a'),
    '--booking-muted':String(globals.muted||'#64748b'),
    '--booking-radius':`${Number(globals.radius||20)}px`,
  } as CSSProperties
})

function todayPlus(days:number):string{const value=new Date();value.setDate(value.getDate()+days);const offset=value.getTimezoneOffset()*60000;return new Date(value.getTime()-offset).toISOString().slice(0,10)}
function formatMoney(value?:number|null):string{return value==null?'':new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL'}).format(value)}
function formatDay(value:string):string{return new Date(`${value}T12:00:00`).toLocaleDateString('pt-BR',{weekday:'long',day:'2-digit',month:'long'})}
function formatTime(value:string):string{return new Date(value).toLocaleTimeString('pt-BR',{hour:'2-digit',minute:'2-digit'})}
async function request<T>(path:string,init:RequestInit={}):Promise<T>{const response=await fetch(`${window.location.origin}/api/v1/public${path}`,{...init,cache:'no-store',headers:{Accept:'application/json',...(init.body?{'content-type':'application/json'}:{}),...(init.headers||{})}});const payload=await response.json().catch(()=>({})) as Envelope<T>;if(!response.ok||payload.data===undefined)throw new Error(payload.error?.message||`Falha HTTP ${response.status}`);return payload.data}

async function loadSlots():Promise<void>{selectedSlot.value=null;slots.value=[];if(!day.value||(serviceRequired.value&&!serviceId.value))return;slotsLoading.value=true;error.value='';try{const query=new URLSearchParams({day:day.value});if(serviceId.value&&serviceEnabled.value)query.set('service_id',serviceId.value);if(professionalEnabled.value&&professionalId.value)query.set('professional_id',professionalId.value);slots.value=await request<Slot[]>(`/booking/availability?${query.toString()}`)}catch(exc){error.value=exc instanceof Error?exc.message:'Não foi possível consultar os horários.'}finally{slotsLoading.value=false}}
async function book():Promise<void>{if(!selectedSlot.value){error.value='Escolha um horário disponível.';return}if(!customer.value.name.trim()){error.value='Informe seu nome.';return}if(phoneRequired.value&&!customer.value.phone.trim()){error.value='Informe seu telefone/WhatsApp.';return}if(serviceRequired.value&&!serviceId.value){error.value='Escolha um serviço.';return}if(professionalRequired.value&&!selectedSlot.value.professional_id){error.value='Escolha um profissional.';return}if(emailRequired.value&&!customer.value.email.trim()){error.value='Informe seu e-mail.';return}submitting.value=true;error.value='';try{success.value=await request<BookingSuccess>('/booking',{method:'POST',body:JSON.stringify({service_id:serviceEnabled.value&&serviceId.value?serviceId.value:null,professional_id:professionalEnabled.value?selectedSlot.value.professional_id:null,starts_at:selectedSlot.value.starts_at,customer_name:customer.value.name.trim(),customer_phone:phoneEnabled.value&&customer.value.phone.trim()?customer.value.phone.trim():null,customer_email:emailEnabled.value&&customer.value.email.trim()?customer.value.email.trim():null})});slots.value=[];emit('booked')}catch(exc){error.value=exc instanceof Error?exc.message:'Não foi possível concluir o agendamento.';await loadSlots()}finally{submitting.value=false}}
function reset():void{success.value=null;selectedSlot.value=null;void loadSlots()}
watch([serviceId,professionalId,day],()=>void loadSlots())
onMounted(()=>{if(props.catalog.config.professional_mode==='REQUIRED'&&props.catalog.professionals.length&&!props.catalog.config.allow_any_professional)professionalId.value=props.catalog.professionals[0].id;void loadSlots()})
</script>

<template>
  <div class="public-booking-theme" :style="templateStyles" :data-booking-template="catalog.config.booking_template?.key||''">
    <section v-if="success" class="public-booking-success">
      <CheckCircle2 :size="52"/><span>Reserva criada</span><h2>{{ success.message }}</h2>
      <p><strong v-if="success.service_name">{{ success.service_name }}<template v-if="professionalEnabled"> · </template></strong><template v-if="professionalEnabled">{{ success.professional_name }}</template></p>
      <time>{{ new Date(success.starts_at).toLocaleString('pt-BR',{dateStyle:'full',timeStyle:'short'}) }}</time>
      <small>A confirmação será enviada pelos canais configurados pelo estabelecimento.</small><button type="button" @click="reset">Fazer outro agendamento</button>
    </section>

    <section v-else class="public-booking-workspace" :class="{'without-service':!serviceEnabled}">
      <article v-if="serviceEnabled" class="public-booking-card public-booking-options">
        <div class="section-title"><Wrench :size="20"/><div><span>1. Atendimento</span><strong>{{ serviceRequired?'Escolha o serviço':'Serviço opcional' }}</strong></div></div>
        <label>Serviço<EntityCombobox v-model="serviceId" :options="catalog.services.map(p=>({id:p.id,label:p.name}))" label="Serviço" :required="serviceRequired" placeholder="Buscar serviço"/></label>
        <div v-if="selectedService" class="service-summary"><strong>{{ selectedService.name }}</strong><span v-if="durationEnabled">{{ selectedService.duration_minutes }} minutos</span><span v-else-if="selectedService.price!=null">{{ formatMoney(selectedService.price) }}</span></div>
      </article>

      <article class="public-booking-card public-booking-slots">
        <div class="section-title"><CalendarDays :size="20"/><div><span>{{ stepSchedule }}. Data e horário</span><strong>{{ formatDay(day) }}</strong></div></div>
        <div class="schedule-fields" :class="{'date-only':!professionalEnabled}"><label v-if="professionalEnabled">Profissional / responsável<EntityCombobox v-model="professionalId" :options="catalog.professionals.map(p=>({id:p.id,label:p.name}))" label="Profissional" placeholder="Buscar responsável disponível"/></label><label>Data<input v-model="day" type="date" :min="todayPlus(0)"/></label></div>
        <div v-if="slotsLoading" class="slot-loading"><LoaderCircle :size="22" class="spin"/> Atualizando disponibilidade...</div>
        <div v-else-if="slots.length" class="slot-grid"><button v-for="slot in slots" :key="`${slot.professional_id}-${slot.starts_at}`" type="button" :class="{selected:selectedSlot?.professional_id===slot.professional_id&&selectedSlot?.starts_at===slot.starts_at}" @click="selectedSlot=slot"><Clock3 :size="17"/><strong>{{ formatTime(slot.starts_at) }}</strong><small v-if="professionalEnabled">{{ slot.professional_name }}</small><em v-if="!slot.unlimited_capacity&&(slot.remaining_capacity||0)>1">{{ slot.remaining_capacity }} vagas</em><em v-else-if="slot.unlimited_capacity">Agenda livre</em></button></div>
        <div v-else class="slot-empty">Nenhum horário disponível. Escolha outra data<template v-if="professionalEnabled"> ou profissional</template>.</div>
      </article>

      <article class="public-booking-card public-booking-customer">
        <div class="section-title"><UserRound :size="20"/><div><span>{{ stepCustomer }}. Seus dados</span><strong>Finalizar reserva</strong></div></div>
        <form @submit.prevent="book"><label>Nome<input v-model="customer.name" autocomplete="name" required minlength="2"/></label><label v-if="phoneEnabled">WhatsApp / telefone <small v-if="!phoneRequired">opcional</small><input v-model="customer.phone" type="tel" inputmode="tel" autocomplete="tel" :required="phoneRequired"/></label><label v-if="emailEnabled">E-mail <small v-if="!emailRequired">opcional</small><input v-model="customer.email" type="email" autocomplete="email" :required="emailRequired"/></label><p v-if="error" class="public-booking-error">{{ error }}</p><button class="public-booking-submit" :disabled="submitting||!selectedSlot"><LoaderCircle v-if="submitting" :size="18" class="spin"/><CalendarDays v-else :size="18"/>{{ submitting?'Reservando...':'Reservar horário' }}</button><small>Você receberá a confirmação pelos canais que estiverem disponíveis e configurados pelo estabelecimento.</small></form>
      </article>
    </section>
  </div>
</template>

<style scoped>
.public-booking-theme{color:var(--booking-text);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.public-booking-workspace{display:grid;grid-template-columns:.8fr 1.3fr .95fr;gap:16px;align-items:start}.public-booking-workspace.without-service{grid-template-columns:1.35fr .95fr}.public-booking-card{border:1px solid color-mix(in srgb,var(--booking-text) 12%,transparent);border-radius:var(--booking-radius);background:var(--booking-surface);padding:20px;box-shadow:0 12px 34px rgba(15,23,42,.055)}.section-title{display:flex;align-items:center;gap:10px;margin-bottom:18px;color:var(--booking-primary)}.section-title span{font-size:10px;font-weight:900;letter-spacing:.12em;text-transform:uppercase;color:var(--booking-muted)}.section-title strong{display:block;margin-top:3px;color:var(--booking-text)}.public-booking-card label{display:grid;gap:7px;margin:13px 0;color:color-mix(in srgb,var(--booking-text) 82%,transparent);font-size:12px;font-weight:800}.public-booking-card label small{color:var(--booking-muted);font-weight:600}.public-booking-card input,.public-booking-card select{width:100%;box-sizing:border-box;min-height:47px;border:1px solid color-mix(in srgb,var(--booking-text) 22%,transparent);border-radius:calc(var(--booking-radius) * .55);padding:0 12px;background:var(--booking-surface);color:var(--booking-text);font:inherit;font-size:16px;outline:none}.public-booking-card input:focus,.public-booking-card select:focus{border-color:var(--booking-primary);box-shadow:0 0 0 3px color-mix(in srgb,var(--booking-primary) 13%,transparent)}.schedule-fields{display:grid;grid-template-columns:1fr 1fr;gap:10px}.schedule-fields.date-only{grid-template-columns:1fr}.service-summary{display:flex;justify-content:space-between;gap:8px;margin-top:15px;padding:12px;border-radius:calc(var(--booking-radius) * .55);background:color-mix(in srgb,var(--booking-bg) 88%,var(--booking-primary) 12%);color:color-mix(in srgb,var(--booking-text) 75%,transparent);font-size:12px}.slot-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;max-height:480px;overflow:auto;padding-right:3px}.slot-grid button{min-height:70px;border:1px solid color-mix(in srgb,var(--booking-text) 15%,transparent);border-radius:calc(var(--booking-radius) * .62);background:var(--booking-surface);display:grid;grid-template-columns:auto 1fr;align-items:center;gap:4px 8px;padding:10px;text-align:left;color:color-mix(in srgb,var(--booking-text) 85%,transparent);cursor:pointer}.slot-grid button strong{font-size:15px}.slot-grid button small,.slot-grid button em{grid-column:1/-1;color:var(--booking-muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-style:normal;font-size:11px}.slot-grid button.selected{border-color:var(--booking-primary);background:color-mix(in srgb,var(--booking-primary) 8%,var(--booking-surface));box-shadow:0 0 0 2px color-mix(in srgb,var(--booking-primary) 12%,transparent)}.slot-empty,.slot-loading{padding:34px 12px;border-radius:calc(var(--booking-radius) * .65);background:color-mix(in srgb,var(--booking-bg) 88%,var(--booking-surface));color:var(--booking-muted);text-align:center;line-height:1.5}.slot-loading{display:flex;justify-content:center;align-items:center;gap:8px}.public-booking-customer form{display:grid}.public-booking-submit,.public-booking-success button{min-height:49px;border:0;border-radius:999px;background:linear-gradient(135deg,var(--booking-primary),var(--booking-accent));color:#fff;font:inherit;font-weight:900;display:flex;align-items:center;justify-content:center;gap:8px;cursor:pointer}.public-booking-submit:disabled{opacity:.5;cursor:not-allowed}.public-booking-customer form>small{margin-top:10px;color:var(--booking-muted);line-height:1.45}.public-booking-error{padding:10px 12px;border-radius:10px;background:#fef2f2;color:#b91c1c;font-size:12px}.public-booking-success{max-width:720px;margin:0 auto;padding:clamp(26px,6vw,46px);border:1px solid #bbf7d0;border-radius:var(--booking-radius);background:var(--booking-surface);text-align:center;box-shadow:0 22px 60px rgba(15,23,42,.08)}.public-booking-success>svg{color:#16a34a}.public-booking-success>span{display:block;margin-top:16px;color:#16a34a;font-size:11px;font-weight:900;text-transform:uppercase;letter-spacing:.12em}.public-booking-success h2{font-size:clamp(24px,5vw,30px);line-height:1.2}.public-booking-success p,.public-booking-success time,.public-booking-success small{display:block;margin:12px 0;color:var(--booking-muted)}.public-booking-success button{margin:22px auto 0;padding:0 20px}.spin{animation:sp-spin 1s linear infinite}@keyframes sp-spin{to{transform:rotate(360deg)}}
@media(max-width:960px){.public-booking-workspace,.public-booking-workspace.without-service{grid-template-columns:1fr 1fr}.public-booking-customer{grid-column:1/-1}.slot-grid{grid-template-columns:repeat(4,minmax(0,1fr))}}
@media(max-width:680px){.public-booking-workspace,.public-booking-workspace.without-service{grid-template-columns:1fr;gap:10px}.public-booking-customer{grid-column:auto}.public-booking-card{padding:16px;border-radius:calc(var(--booking-radius) * .75)}.schedule-fields{grid-template-columns:1fr}.slot-grid{grid-template-columns:repeat(2,minmax(0,1fr));max-height:none}.public-booking-success{margin:0}.public-booking-card input,.public-booking-card select{font-size:16px}}
</style>
