<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { CalendarDays, LoaderCircle } from 'lucide-vue-next'
import { applyBranding, type BrandingManifest } from './branding'
import PublicBookingWidget from './PublicBookingWidget.vue'
import PublicLandingRenderer from './PublicLandingRenderer.vue'

type Service = { id:string; name:string; duration_minutes:number; price?:number|null }
type Professional = { id:string; name:string }
type BookingConfig = {
  enabled:boolean; title:string; subtitle:string; success_message:string; custom_html:string; allow_any_professional:boolean
  require_name:boolean; require_phone:boolean; service_mode:'DISABLED'|'OPTIONAL'|'REQUIRED'; email_mode:'DISABLED'|'OPTIONAL'|'REQUIRED'
  default_duration_minutes:number; simultaneous_capacity:number; public_url:string
}
type Catalog = { config:BookingConfig; services:Service[]; professionals:Professional[]; branding:BrandingManifest }
type PageContent = { version:number; global_styles?:Record<string,unknown>; seo?:Record<string,unknown>; blocks?:Array<Record<string,unknown>> }
type LandingPage = { status:string; template_key?:string|null; content:PageContent }
type LandingEnvelope = { landing_page:LandingPage }
type Envelope<T> = { data?:T; error?:{message?:string;code?:string} }

const catalog=ref<Catalog|null>(null)
const landing=ref<LandingPage|null>(null)
const loading=ref(true)
const error=ref('')
const modernLanding=computed(()=>Boolean(landing.value?.content?.version>=2&&Array.isArray(landing.value?.content?.blocks)&&landing.value!.content.blocks!.length))

async function request<T>(path:string):Promise<T>{
  const response=await fetch(`${window.location.origin}/api/v1/public${path}`,{cache:'no-store',headers:{Accept:'application/json'}})
  const payload=await response.json().catch(()=>({})) as Envelope<T>
  if(!response.ok||payload.data===undefined)throw new Error(payload.error?.message||`Falha HTTP ${response.status}`)
  return payload.data
}

function upsertMeta(selector:string,attribute:'name'|'property',key:string,value:string):void{
  let element=document.head.querySelector<HTMLMetaElement>(selector)
  if(!element){element=document.createElement('meta');element.setAttribute(attribute,key);document.head.appendChild(element)}
  element.content=value
}
function applySocialMetadata(page:LandingPage):void{
  const seo=page.content.seo||{}
  const title=String(seo.title||catalog.value?.config.title||catalog.value?.branding.app.public_name||'Agendamento online')
  const description=String(seo.description||catalog.value?.config.subtitle||'Agende seu horário online.')
  const shareImage=String(seo.share_image||catalog.value?.branding.assets.logo_url||'')
  const canonical=String(seo.canonical_url||window.location.href.split('#')[0])
  document.title=title
  upsertMeta('meta[name="description"]','name','description',description)
  upsertMeta('meta[property="og:title"]','property','og:title',title)
  upsertMeta('meta[property="og:description"]','property','og:description',description)
  upsertMeta('meta[property="og:type"]','property','og:type','website')
  upsertMeta('meta[property="og:url"]','property','og:url',canonical)
  upsertMeta('meta[name="twitter:card"]','name','twitter:card',shareImage?'summary_large_image':'summary')
  if(shareImage){upsertMeta('meta[property="og:image"]','property','og:image',shareImage);upsertMeta('meta[name="twitter:image"]','name','twitter:image',shareImage)}
  let link=document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]')
  if(!link){link=document.createElement('link');link.rel='canonical';document.head.appendChild(link)}
  link.href=canonical
}

async function load():Promise<void>{
  loading.value=true;error.value=''
  try{
    const booking=await request<Catalog>('/booking')
    catalog.value=booking;applyBranding(booking.branding)
    try{
      const page=await request<LandingEnvelope>('/landing?slug=home')
      landing.value=page.landing_page
      if(page.landing_page?.content?.version>=2)applySocialMetadata(page.landing_page)
    }catch{
      // Compatibilidade: uma falha, capability ausente ou página antiga nunca
      // impede o formulário público que já existia antes do editor visual.
      landing.value=null
    }
  }catch(exc){error.value=exc instanceof Error?exc.message:'Agenda pública indisponível.'}
  finally{loading.value=false}
}

onMounted(()=>void load())
</script>

<template>
  <main class="public-booking-page">
    <div v-if="loading" class="public-booking-loading"><LoaderCircle :size="34" class="spin"/><strong>Carregando agenda...</strong></div>

    <template v-else-if="catalog">
      <PublicLandingRenderer
        v-if="modernLanding && landing"
        :content="landing.content"
        :services="catalog.services"
        :professionals="catalog.professionals"
        :template-key="landing.template_key"
      >
        <template #booking><PublicBookingWidget :catalog="catalog"/></template>
      </PublicLandingRenderer>

      <section v-else class="public-booking-shell">
        <header class="public-booking-hero">
          <div class="public-booking-brand">
            <img v-if="catalog.branding.assets.logo_url" :src="catalog.branding.assets.logo_url" :alt="catalog.branding.app.public_name"/>
            <span v-else>SP</span>
            <div><strong>{{ catalog.branding.app.public_name || 'Scheduler Pro' }}</strong><small>{{ catalog.branding.app.slogan || 'Agendamento online' }}</small></div>
          </div>
          <div class="public-booking-copy"><span>Agenda aberta</span><h1>{{ catalog.config.title }}</h1><p>{{ catalog.config.subtitle }}</p></div>
          <div v-if="catalog.config.custom_html" class="public-booking-custom" v-html="catalog.config.custom_html"></div>
        </header>
        <section class="legacy-booking"><PublicBookingWidget :catalog="catalog"/></section>
      </section>
    </template>

    <section v-else class="public-booking-unavailable"><CalendarDays :size="48"/><h1>Agenda indisponível</h1><p>{{ error || 'O estabelecimento não está recebendo agendamentos online neste momento.' }}</p></section>
  </main>
</template>

<style>
.public-booking-page{min-height:100dvh;background:linear-gradient(180deg,#eef4ff,#f8fafc 38%,#fff);color:#0f172a;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.public-booking-shell{max-width:1180px;margin:auto;padding:clamp(12px,3vw,26px)}.public-booking-hero{position:relative;overflow:hidden;border-radius:28px;padding:clamp(22px,5vw,36px);background:radial-gradient(circle at 88% 10%,color-mix(in srgb,var(--sp-primary,#2563eb) 38%,transparent),transparent 32%),linear-gradient(145deg,#071426,#112243 65%,#172554);color:#fff;box-shadow:0 24px 70px rgba(15,23,42,.18)}.public-booking-brand{display:flex;align-items:center;gap:12px}.public-booking-brand>img{max-width:180px;max-height:52px;object-fit:contain}.public-booking-brand>span{width:48px;height:48px;border-radius:15px;display:grid;place-items:center;background:linear-gradient(135deg,var(--sp-primary,#2563eb),var(--sp-accent,#7c3aed));font-weight:900}.public-booking-brand div strong,.public-booking-brand div small{display:block}.public-booking-brand div small{margin-top:3px;color:#cbd5e1}.public-booking-copy{max-width:760px;padding:clamp(34px,7vw,64px) 0 18px}.public-booking-copy>span{font-size:10px;font-weight:900;letter-spacing:.12em;text-transform:uppercase;color:#93c5fd}.public-booking-copy h1{font-size:clamp(34px,7vw,68px);line-height:1;margin:12px 0 15px;letter-spacing:-.045em}.public-booking-copy p{max-width:620px;color:#cbd5e1;font-size:17px;line-height:1.65}.public-booking-custom{margin-top:18px;padding:18px;border:1px solid rgba(255,255,255,.12);border-radius:18px;background:rgba(255,255,255,.06);line-height:1.6}.legacy-booking{padding:18px 0}.public-booking-loading,.public-booking-unavailable{min-height:100dvh;display:grid;place-items:center;align-content:center;gap:12px;text-align:center;padding:24px}.spin{animation:sp-page-spin 1s linear infinite}@keyframes sp-page-spin{to{transform:rotate(360deg)}}
@media(max-width:680px){.public-booking-shell{padding:10px}.public-booking-hero{border-radius:20px}.public-booking-brand>img{max-width:145px}.public-booking-copy p{font-size:15px}.public-booking-copy{padding-bottom:4px}.legacy-booking{padding-top:10px}}
</style>
