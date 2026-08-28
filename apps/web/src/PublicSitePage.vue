<script setup lang="ts">
import { computed, onMounted, ref, type CSSProperties } from 'vue'
import { CalendarDays, LoaderCircle } from 'lucide-vue-next'
import { applyBranding, type BrandingManifest } from './branding'
import HtmlTemplateFrame from './HtmlTemplateFrame.vue'
import PublicBookingWidget from './PublicBookingWidget.vue'
import PublicVisualLandingRenderer from './PublicVisualLandingRenderer.vue'

type Device='desktop'|'tablet'|'mobile'
type FieldMode='DISABLED'|'OPTIONAL'|'REQUIRED'
type Service={id:string;name:string;duration_minutes:number;price?:number|null}
type Professional={id:string;name:string}
type HtmlContent={render_mode:'HTML';html_document:string;surface?:string;template_key?:string;content_version?:number;contract?:string}
type BookingDesignContent={global_styles?:Record<string,unknown>;layout?:Record<string,unknown>;copy?:Record<string,unknown>}
type BookingTemplate={key:string;version:number;content:BookingDesignContent|HtmlContent}
type BookingConfig={enabled:boolean;title:string;subtitle:string;success_message:string;custom_html:string;allow_any_professional:boolean;require_name:boolean;require_phone:boolean;service_mode:FieldMode;email_mode:FieldMode;phone_mode:FieldMode;duration_mode:FieldMode;professional_mode:FieldMode;default_duration_minutes:number;default_professional_name:string;simultaneous_capacity?:number|null;unlimited_capacity?:boolean;public_url:string;booking_template?:BookingTemplate|null}
type Catalog={config:BookingConfig;services:Service[];professionals:Professional[];branding:BrandingManifest}
type WidgetBookingTemplate={key:string;version:number;content:BookingDesignContent}
type WidgetCatalog={config:Omit<BookingConfig,'booking_template'>&{booking_template?:WidgetBookingTemplate|null};services:Service[];professionals:Professional[]}
type PageBlock={id:string;type:string;props:Record<string,unknown>;style?:CSSProperties;responsive?:{desktop?:CSSProperties;tablet?:CSSProperties;mobile?:CSSProperties;hidden?:Partial<Record<Device,boolean>>}}
type BuilderState={schema?:string;root_ids?:string[];nodes?:Record<string,unknown>}
type BlockPageContent={version:number;schema?:string;builder_version?:string;global_styles?:Record<string,unknown>;seo?:Record<string,unknown>;blocks?:PageBlock[];builder?:BuilderState}
type PageContent=BlockPageContent|HtmlContent
type LandingPage={status:string;template_key?:string|null;content:PageContent}
type LandingPayload={branding:BrandingManifest;landing_page:LandingPage}
type Envelope<T>={data?:T;error?:{message?:string}}

const path=window.location.pathname.replace(/\/+$/,'')||'/'
const landingMode=computed(()=>path==='/pagina')
const catalog=ref<Catalog|null>(null),landing=ref<LandingPage|null>(null),branding=ref<BrandingManifest|null>(null)
const loading=ref(true),error=ref('')
function isHtmlContent(value:unknown):value is HtmlContent{return Boolean(value&&typeof value==='object'&&(value as HtmlContent).render_mode==='HTML'&&typeof (value as HtmlContent).html_document==='string')}
function blockContent(value:PageContent):BlockPageContent{return value as BlockPageContent}
function widgetTemplate(template:BookingTemplate|null|undefined):WidgetBookingTemplate|null{if(!template||isHtmlContent(template.content))return null;return{key:template.key,version:template.version,content:template.content}}
const landingHtml=computed(()=>landing.value&&isHtmlContent(landing.value.content)?landing.value.content.html_document:'')
const bookingHtml=computed(()=>{const content=catalog.value?.config.booking_template?.content;return isHtmlContent(content)?content.html_document:''})
const templateGlobals=computed<Record<string,unknown>>(()=>{const content=catalog.value?.config.booking_template?.content;return content&&!isHtmlContent(content)?content.global_styles||{}:{}})
const widgetCatalog=computed<WidgetCatalog|null>(()=>{const current=catalog.value;if(!current)return null;return{config:{...current.config,booking_template:widgetTemplate(current.config.booking_template)},services:current.services,professionals:current.professionals}})
const bookingPageStyle=computed<CSSProperties>(()=>{const g=templateGlobals.value;return{'--booking-page-primary':String(g.primary||'var(--sp-primary,#2563eb)'),'--booking-page-secondary':String(g.secondary||'#071426'),'--booking-page-accent':String(g.accent||'var(--sp-accent,#7c3aed)'),'--booking-page-bg':String(g.background||'#f5f7fb'),'--booking-page-text':String(g.text||'#0f172a'),'--booking-page-radius':`${Number(g.radius||26)}px`} as CSSProperties})

async function request<T>(resource:string):Promise<T>{const response=await fetch(`${window.location.origin}/api/v1/public${resource}`,{cache:'no-store',headers:{Accept:'application/json'}});const payload=await response.json().catch(()=>({})) as Envelope<T>;if(!response.ok||payload.data===undefined)throw new Error(payload.error?.message||`Falha HTTP ${response.status}`);return payload.data}
function upsertMeta(selector:string,attribute:'name'|'property',key:string,value:string):void{let node=document.head.querySelector<HTMLMetaElement>(selector);if(!node){node=document.createElement('meta');node.setAttribute(attribute,key);document.head.appendChild(node)}node.content=value}
function applyHtmlMetadata(source:string,fallbackTitle:string):void{const doc=new DOMParser().parseFromString(source,'text/html');document.title=doc.title.trim()||fallbackTitle;for(const name of ['description','robots','theme-color','color-scheme','twitter:card','twitter:title','twitter:description','twitter:image']){const value=doc.head.querySelector<HTMLMetaElement>(`meta[name="${name}"]`)?.content?.trim();if(value)upsertMeta(`meta[name="${name}"]`,'name',name,value)}for(const property of ['og:type','og:locale','og:title','og:description','og:image','og:url']){const value=doc.head.querySelector<HTMLMetaElement>(`meta[property="${property}"]`)?.content?.trim();if(value)upsertMeta(`meta[property="${property}"]`,'property',property,value)}document.head.querySelectorAll('script[data-scheduler-pro-html-jsonld]').forEach(node=>node.remove());doc.head.querySelectorAll<HTMLScriptElement>('script[type="application/ld+json"]').forEach(sourceNode=>{const raw=sourceNode.textContent?.trim();if(!raw)return;try{JSON.parse(raw)}catch{return}const node=document.createElement('script');node.type='application/ld+json';node.dataset.schedulerProHtmlJsonld='true';node.textContent=raw;document.head.appendChild(node)})}
function applyMetadata(page:LandingPage):void{if(isHtmlContent(page.content)){applyHtmlMetadata(page.content.html_document,branding.value?.app.public_name||'Página pública');return}const seo=blockContent(page.content).seo||{};const title=String(seo.title||branding.value?.app.public_name||'Agendamento online'),description=String(seo.description||'Agende seu horário online.'),image=String(seo.share_image||branding.value?.assets.logo_url||'');document.title=title;upsertMeta('meta[name="description"]','name','description',description);upsertMeta('meta[property="og:title"]','property','og:title',title);upsertMeta('meta[property="og:description"]','property','og:description',description);upsertMeta('meta[property="og:type"]','property','og:type','website');if(image)upsertMeta('meta[property="og:image"]','property','og:image',image)}
async function loadLanding():Promise<void>{const result=await request<LandingPayload>('/landing?slug=home');landing.value=result.landing_page;branding.value=result.branding;applyBranding(result.branding);applyMetadata(result.landing_page);try{catalog.value=await request<Catalog>('/booking')}catch{catalog.value=null}}
async function loadBooking():Promise<void>{const result=await request<Catalog>('/booking');catalog.value=result;branding.value=result.branding;applyBranding(result.branding);const html=result.config.booking_template?.content;if(isHtmlContent(html))applyHtmlMetadata(html.html_document,result.config.title||result.branding.app.public_name||'Agendamento online');else document.title=result.config.title||result.branding.app.public_name||'Agendamento online'}
async function load():Promise<void>{loading.value=true;error.value='';try{if(landingMode.value)await loadLanding();else await loadBooking()}catch(exc){error.value=exc instanceof Error?exc.message:'Página pública indisponível.'}finally{loading.value=false}}
onMounted(()=>void load())
</script>

<template>
  <main class="public-site-page" :class="{'html-surface':Boolean(landingHtml||bookingHtml)}" :style="bookingPageStyle">
    <div v-if="loading" class="public-state"><LoaderCircle :size="36" class="spin"/><strong>Carregando página...</strong></div>
    <template v-else-if="landingMode&&landing">
      <HtmlTemplateFrame v-if="landingHtml" :html="landingHtml" mode="landing"/>
      <PublicVisualLandingRenderer v-else :content="blockContent(landing.content)" :services="catalog?.services||[]" :professionals="catalog?.professionals||[]">
        <template #booking><PublicBookingWidget v-if="widgetCatalog" :catalog="widgetCatalog"/><div v-else class="booking-unavailable"><CalendarDays :size="30"/><strong>Agenda online indisponível neste momento.</strong><span>Você ainda pode usar os contatos desta página.</span></div></template>
      </PublicVisualLandingRenderer>
    </template>
    <template v-else-if="!landingMode&&catalog">
      <HtmlTemplateFrame v-if="bookingHtml" :html="bookingHtml" mode="booking"/>
      <section v-else class="direct-booking-shell" :data-template="catalog.config.booking_template?.key||''"><header class="direct-booking-header"><div class="direct-brand"><img v-if="catalog.branding.assets.logo_url" :src="catalog.branding.assets.logo_url" :alt="catalog.branding.app.public_name"/><div v-else class="direct-mark">SP</div><div><strong>{{catalog.branding.app.public_name||'Scheduler Pro'}}</strong><small>{{catalog.branding.app.slogan||'Agendamento online'}}</small></div></div><div class="direct-copy"><span>Agenda online</span><h1>{{catalog.config.title}}</h1><p>{{catalog.config.subtitle}}</p></div></header><PublicBookingWidget v-if="widgetCatalog" :catalog="widgetCatalog"/></section>
    </template>
    <section v-else class="public-state unavailable"><CalendarDays :size="48"/><h1>{{landingMode?'Página em preparação':'Agenda indisponível'}}</h1><p>{{error||'Este conteúdo ainda não está disponível.'}}</p><a v-if="landingMode" href="/agendar">Abrir agenda direta</a></section>
  </main>
</template>

<style scoped>
.public-site-page{min-height:100dvh;background:var(--booking-page-bg,#f5f7fb);color:var(--booking-page-text,#0f172a);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.public-site-page.html-surface{background:#fff}.public-state{min-height:100dvh;display:grid;place-items:center;align-content:center;gap:12px;padding:24px;text-align:center}.public-state p{max-width:560px;color:#52647c}.public-state a{display:inline-flex;min-height:44px;align-items:center;padding:0 16px;border-radius:12px;background:var(--booking-page-primary,#2563eb);color:#fff;text-decoration:none;font-weight:800}.booking-unavailable{display:grid;place-items:center;gap:6px;padding:28px;border:1px dashed #cbd5e1;border-radius:16px;background:#f8fafc;text-align:center;color:#52647c}.direct-booking-shell{width:min(100% - 28px,1080px);margin:0 auto;padding:clamp(14px,3vw,32px) 0 48px}.direct-booking-header{overflow:hidden;margin-bottom:18px;padding:clamp(24px,5vw,50px);border-radius:var(--booking-page-radius,26px);background:linear-gradient(145deg,var(--booking-page-secondary,#071426),color-mix(in srgb,var(--booking-page-secondary,#071426) 83%,#fff 17%));color:#fff;box-shadow:0 24px 70px rgba(15,23,42,.17)}.direct-brand{display:flex;align-items:center;gap:12px}.direct-brand img{max-width:180px;max-height:54px;object-fit:contain}.direct-brand>div:last-child strong,.direct-brand>div:last-child small{display:block}.direct-mark{width:48px;height:48px;border-radius:14px;display:grid;place-items:center;background:var(--booking-page-primary,#2563eb);font-weight:900}.direct-copy{max-width:680px;padding-top:clamp(30px,6vw,58px)}.direct-copy h1{margin:10px 0 12px;font-size:clamp(34px,7vw,64px);line-height:1}.spin{animation:site-spin 1s linear infinite}@keyframes site-spin{to{transform:rotate(360deg)}}@media(max-width:680px){.direct-booking-shell{width:min(100% - 16px,1080px);padding-top:8px}.direct-booking-header{padding:24px 18px}.direct-copy h1{font-size:38px}}
</style>
