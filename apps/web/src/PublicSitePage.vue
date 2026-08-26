<script setup lang="ts">
import { computed, onMounted, ref, type CSSProperties } from 'vue'
import { CalendarDays, LoaderCircle } from 'lucide-vue-next'
import { applyBranding, type BrandingManifest } from './branding'
import PublicBookingWidget from './PublicBookingWidget.vue'
import PublicLandingRenderer from './PublicLandingRenderer.vue'

type Device='desktop'|'tablet'|'mobile'
type Service={id:string;name:string;duration_minutes:number;price?:number|null}
type Professional={id:string;name:string}
type BookingConfig={
  enabled:boolean
  title:string
  subtitle:string
  success_message:string
  custom_html:string
  allow_any_professional:boolean
  require_name:boolean
  require_phone:boolean
  service_mode:'DISABLED'|'OPTIONAL'|'REQUIRED'
  email_mode:'DISABLED'|'OPTIONAL'|'REQUIRED'
  default_duration_minutes:number
  simultaneous_capacity:number
  public_url:string
}
type Catalog={config:BookingConfig;services:Service[];professionals:Professional[];branding:BrandingManifest}
type PageBlock={
  id:string
  type:string
  props:Record<string,unknown>
  style?:CSSProperties
  responsive?:{
    desktop?:CSSProperties
    tablet?:CSSProperties
    mobile?:CSSProperties
    hidden?:Partial<Record<Device,boolean>>
  }
}
type PageContent={
  version:number
  global_styles?:Record<string,unknown>
  seo?:Record<string,unknown>
  blocks?:PageBlock[]
}
type LandingPage={status:string;template_key?:string|null;content:PageContent}
type LandingPayload={branding:BrandingManifest;landing_page:LandingPage}
type Envelope<T>={data?:T;error?:{message?:string}}

const path=window.location.pathname.replace(/\/+$/,'')||'/'
const landingMode=computed(()=>path==='/pagina')
const catalog=ref<Catalog|null>(null)
const landing=ref<LandingPage|null>(null)
const branding=ref<BrandingManifest|null>(null)
const loading=ref(true)
const error=ref('')

async function request<T>(resource:string):Promise<T>{
  const response=await fetch(`${window.location.origin}/api/v1/public${resource}`,{cache:'no-store',headers:{Accept:'application/json'}})
  const payload=await response.json().catch(()=>({})) as Envelope<T>
  if(!response.ok||payload.data===undefined)throw new Error(payload.error?.message||`Falha HTTP ${response.status}`)
  return payload.data
}

function upsertMeta(selector:string,attribute:'name'|'property',key:string,value:string):void{
  let node=document.head.querySelector<HTMLMetaElement>(selector)
  if(!node){node=document.createElement('meta');node.setAttribute(attribute,key);document.head.appendChild(node)}
  node.content=value
}
function applyMetadata(page:LandingPage):void{
  const seo=page.content.seo||{}
  const title=String(seo.title||branding.value?.app.public_name||'Agendamento online')
  const description=String(seo.description||'Agende seu horário online.')
  const image=String(seo.share_image||branding.value?.assets.logo_url||'')
  document.title=title
  upsertMeta('meta[name="description"]','name','description',description)
  upsertMeta('meta[property="og:title"]','property','og:title',title)
  upsertMeta('meta[property="og:description"]','property','og:description',description)
  upsertMeta('meta[property="og:type"]','property','og:type','website')
  if(image)upsertMeta('meta[property="og:image"]','property','og:image',image)
}

async function loadLanding():Promise<void>{
  const landingResult=await request<LandingPayload>('/landing?slug=home')
  landing.value=landingResult.landing_page
  branding.value=landingResult.branding
  applyBranding(landingResult.branding)
  applyMetadata(landingResult.landing_page)
  try{
    catalog.value=await request<Catalog>('/booking')
  }catch{
    catalog.value=null
  }
}
async function loadBooking():Promise<void>{
  const result=await request<Catalog>('/booking')
  catalog.value=result
  branding.value=result.branding
  applyBranding(result.branding)
  document.title=result.config.title||result.branding.app.public_name||'Agendamento online'
}
async function load():Promise<void>{
  loading.value=true;error.value=''
  try{if(landingMode.value)await loadLanding();else await loadBooking()}
  catch(exc){error.value=exc instanceof Error?exc.message:'Página pública indisponível.'}
  finally{loading.value=false}
}

onMounted(()=>void load())
</script>

<template>
  <main class="public-site-page">
    <div v-if="loading" class="public-state"><LoaderCircle :size="36" class="spin"/><strong>Carregando página...</strong></div>

    <template v-else-if="landingMode&&landing">
      <PublicLandingRenderer
        :content="landing.content"
        :services="catalog?.services||[]"
        :professionals="catalog?.professionals||[]"
        :template-key="landing.template_key"
      >
        <template #booking>
          <PublicBookingWidget v-if="catalog" :catalog="catalog"/>
          <div v-else class="booking-unavailable"><CalendarDays :size="30"/><strong>Agenda online indisponível neste momento.</strong><span>Você ainda pode usar os contatos desta página.</span></div>
        </template>
      </PublicLandingRenderer>
    </template>

    <template v-else-if="!landingMode&&catalog">
      <section class="direct-booking-shell">
        <header class="direct-booking-header">
          <div class="direct-brand">
            <img v-if="catalog.branding.assets.logo_url" :src="catalog.branding.assets.logo_url" :alt="catalog.branding.app.public_name"/>
            <div v-else class="direct-mark">SP</div>
            <div><strong>{{ catalog.branding.app.public_name||'Scheduler Pro' }}</strong><small>{{ catalog.branding.app.slogan||'Agendamento online' }}</small></div>
          </div>
          <div class="direct-copy"><span>Agenda online</span><h1>{{ catalog.config.title }}</h1><p>{{ catalog.config.subtitle }}</p></div>
        </header>
        <PublicBookingWidget :catalog="catalog"/>
      </section>
    </template>

    <section v-else class="public-state unavailable"><CalendarDays :size="48"/><h1>{{ landingMode?'Página em preparação':'Agenda indisponível' }}</h1><p>{{ error||'Este conteúdo ainda não está disponível.' }}</p><a v-if="landingMode" href="/agendar">Abrir agenda direta</a></section>
  </main>
</template>

<style scoped>
.public-site-page{min-height:100dvh;background:#f5f7fb;color:#0f172a;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.public-state{min-height:100dvh;display:grid;place-items:center;align-content:center;gap:12px;padding:24px;text-align:center}.public-state p{max-width:560px;color:#64748b}.public-state a{display:inline-flex;min-height:44px;align-items:center;padding:0 16px;border-radius:12px;background:var(--sp-primary,#2563eb);color:#fff;text-decoration:none;font-weight:800}.booking-unavailable{display:grid;place-items:center;gap:6px;padding:28px;border:1px dashed #cbd5e1;border-radius:16px;background:#f8fafc;text-align:center;color:#64748b}.booking-unavailable strong{color:#334155}.direct-booking-shell{width:min(100% - 28px,980px);margin:0 auto;padding:clamp(14px,3vw,32px) 0 48px}.direct-booking-header{overflow:hidden;margin-bottom:18px;padding:clamp(24px,5vw,46px);border-radius:26px;background:radial-gradient(circle at 86% 12%,color-mix(in srgb,var(--sp-primary,#2563eb) 38%,transparent),transparent 34%),linear-gradient(145deg,#071426,#112243 65%,#172554);color:#fff;box-shadow:0 24px 70px rgba(15,23,42,.17)}.direct-brand{display:flex;align-items:center;gap:12px}.direct-brand img{max-width:180px;max-height:54px;object-fit:contain}.direct-brand>div:last-child strong,.direct-brand>div:last-child small{display:block}.direct-brand small{margin-top:3px;color:#cbd5e1}.direct-mark{width:48px;height:48px;border-radius:14px;display:grid;place-items:center;background:var(--sp-primary,#2563eb);font-weight:900}.direct-copy{max-width:680px;padding-top:clamp(30px,6vw,58px)}.direct-copy>span{font-size:.72rem;font-weight:900;text-transform:uppercase;letter-spacing:.12em;color:#93c5fd}.direct-copy h1{margin:10px 0 12px;font-size:clamp(34px,7vw,64px);line-height:1;letter-spacing:-.04em}.direct-copy p{margin:0;color:#cbd5e1;font-size:clamp(15px,2vw,18px);line-height:1.6}.spin{animation:site-spin 1s linear infinite}@keyframes site-spin{to{transform:rotate(360deg)}}@media(max-width:680px){.direct-booking-shell{width:min(100% - 16px,980px);padding-top:8px}.direct-booking-header{padding:24px 18px;border-radius:20px}.direct-brand img{max-width:140px}.direct-copy h1{font-size:38px}}
</style>
