<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, type CSSProperties } from 'vue'
import { CalendarDays, LoaderCircle, LogIn } from 'lucide-vue-next'
import { applyBindingsToHtml, createThemeTokens, normalizeBindingsManifest, themeTokensToCss } from '@argws/visual-builder'
import { applyBranding, type BrandingManifest } from './branding'
import HtmlTemplateFrame from './HtmlTemplateFrame.vue'
import PublicBookingWidget from './PublicBookingWidget.vue'
import PublicVisualLandingRenderer from './PublicVisualLandingRenderer.vue'
import { installPublicAnalytics, trackPublicEvent } from './publicAnalytics'

type Device='desktop'|'tablet'|'mobile'
type FieldMode='DISABLED'|'OPTIONAL'|'REQUIRED'
type Service={id:string;name:string;duration_minutes:number;price?:number|null}
type Professional={id:string;name:string}
type HtmlContent={render_mode:'HTML';html_document:string;surface?:string;template_key?:string;content_version?:number;contract?:string}
type BookingDesignContent={global_styles?:Record<string,unknown>;layout?:Record<string,unknown>;copy?:Record<string,unknown>}
type BookingTemplate={key:string;version:number;content:BookingDesignContent|HtmlContent}
type RuntimeContext={features?:Record<string,unknown>;pages?:Record<string,{enabled?:boolean}>;preferences?:Record<string,unknown>;tenant?:Record<string,unknown>}
type BookingConfig={enabled:boolean;title:string;subtitle:string;success_message:string;custom_html:string;allow_any_professional:boolean;require_name:boolean;require_phone:boolean;service_mode:FieldMode;email_mode:FieldMode;phone_mode:FieldMode;duration_mode:FieldMode;professional_mode:FieldMode;default_duration_minutes:number;default_professional_name:string;simultaneous_capacity?:number|null;unlimited_capacity?:boolean;public_url:string;booking_template?:BookingTemplate|null}
type Catalog={config:BookingConfig;services:Service[];professionals:Professional[];branding:BrandingManifest;context?:RuntimeContext}
type WidgetBookingTemplate={key:string;version:number;content:BookingDesignContent}
type WidgetCatalog={config:Omit<BookingConfig,'booking_template'>&{booking_template?:WidgetBookingTemplate|null};services:Service[];professionals:Professional[]}
type PageBlock={id:string;type:string;props:Record<string,unknown>;style?:CSSProperties;responsive?:{desktop?:CSSProperties;tablet?:CSSProperties;mobile?:CSSProperties;hidden?:Partial<Record<Device,boolean>>}}
type BuilderState={schema?:string;root_ids?:string[];nodes?:Record<string,unknown>}
type BlockPageContent={version:number;schema?:string;builder_version?:string;global_styles?:Record<string,unknown>;seo?:Record<string,unknown>;blocks?:PageBlock[];builder?:BuilderState}
type PageContent=BlockPageContent|HtmlContent
type LandingPage={status:string;template_key?:string|null;content:PageContent}
type LandingPayload={branding:BrandingManifest;landing_page:LandingPage;context?:RuntimeContext}
type LoginPayload={branding:BrandingManifest;login_page:{content:HtmlContent;template_key:string};context:RuntimeContext}
type ExperiencePayload={surface:'LANDING'|'BOOKING';page:{template_key?:string|null};version:{html:string;metadata?:Record<string,any>;bindings_values?:Record<string,any>;theme?:Record<string,any>};branding:BrandingManifest;context:RuntimeContext}
type Envelope<T>={data?:T;error?:{message?:string}}

const path=window.location.pathname.replace(/\/+$/,'')||'/'
const landingMode=computed(()=>path==='/pagina')
const loginMode=computed(()=>path==='/login')
const bookingMode=computed(()=>!landingMode.value&&!loginMode.value)
const catalog=ref<Catalog|null>(null),landing=ref<LandingPage|null>(null),loginPage=ref<HtmlContent|null>(null),branding=ref<BrandingManifest|null>(null),runtimeContext=ref<RuntimeContext>({})
const loading=ref(true),error=ref(''),experienceHtml=ref('')
let analyticsConfig:ReturnType<typeof installPublicAnalytics>={}
function isHtmlContent(value:unknown):value is HtmlContent{return Boolean(value&&typeof value==='object'&&(value as HtmlContent).render_mode==='HTML'&&typeof (value as HtmlContent).html_document==='string')}
function blockContent(value:PageContent):BlockPageContent{return value as BlockPageContent}
function widgetTemplate(template:BookingTemplate|null|undefined):WidgetBookingTemplate|null{if(!template||isHtmlContent(template.content))return null;return{key:template.key,version:template.version,content:template.content}}
const landingHtml=computed(()=>landing.value&&isHtmlContent(landing.value.content)?landing.value.content.html_document:'')
const bookingHtml=computed(()=>{const content=catalog.value?.config.booking_template?.content;return isHtmlContent(content)?content.html_document:''})
const loginHtml=computed(()=>loginPage.value?.html_document||'')
const templateGlobals=computed<Record<string,unknown>>(()=>{const content=catalog.value?.config.booking_template?.content;return content&&!isHtmlContent(content)?content.global_styles||{}:{}})
const widgetCatalog=computed<WidgetCatalog|null>(()=>{const current=catalog.value;if(!current)return null;return{config:{...current.config,booking_template:widgetTemplate(current.config.booking_template)},services:current.services,professionals:current.professionals}})
const bookingPageStyle=computed<CSSProperties>(()=>{const g=templateGlobals.value;return{'--booking-page-primary':String(g.primary||'var(--sp-primary,#2563eb)'),'--booking-page-secondary':String(g.secondary||'#071426'),'--booking-page-accent':String(g.accent||'var(--sp-accent,#7c3aed)'),'--booking-page-bg':String(g.background||'#f5f7fb'),'--booking-page-text':String(g.text||'#0f172a'),'--booking-page-radius':`${Number(g.radius||26)}px`} as CSSProperties})

async function request<T>(resource:string):Promise<T>{const response=await fetch(`${window.location.origin}/api/v1/public${resource}`,{cache:'no-store',headers:{Accept:'application/json'}});const payload=await response.json().catch(()=>({})) as Envelope<T>;if(!response.ok||payload.data===undefined)throw new Error(payload.error?.message||`Falha HTTP ${response.status}`);return payload.data}
function upsertMeta(selector:string,attribute:'name'|'property',key:string,value:string):void{let node=document.head.querySelector<HTMLMetaElement>(selector);if(!node){node=document.createElement('meta');node.setAttribute(attribute,key);document.head.appendChild(node)}node.content=value}
function applyHtmlMetadata(source:string,fallbackTitle:string):void{const doc=new DOMParser().parseFromString(source,'text/html');document.title=doc.title.trim()||fallbackTitle;for(const name of ['description','robots','theme-color','color-scheme','twitter:card','twitter:title','twitter:description','twitter:image']){const value=doc.head.querySelector<HTMLMetaElement>(`meta[name="${name}"]`)?.content?.trim();if(value)upsertMeta(`meta[name="${name}"]`,'name',name,value)}for(const property of ['og:type','og:locale','og:title','og:description','og:image','og:url']){const value=doc.head.querySelector<HTMLMetaElement>(`meta[property="${property}"]`)?.content?.trim();if(value)upsertMeta(`meta[property="${property}"]`,'property',property,value)}}
function applyMetadata(page:LandingPage):void{if(isHtmlContent(page.content)){applyHtmlMetadata(page.content.html_document,branding.value?.app.public_name||'Página pública');return}const seo=blockContent(page.content).seo||{};const title=String(seo.title||branding.value?.app.public_name||'Scheduler Pro'),description=String(seo.description||'Página pública do Scheduler Pro.');document.title=title;upsertMeta('meta[name="description"]','name','description',description)}
function automaticExperienceBindings(result:ExperiencePayload):Record<string,unknown>{
  const brand=result.branding
  const features=result.context?.features||{}
  return{
    'business.name':brand.app.public_name||brand.app.name||'Scheduler Pro',
    'brand.logo':brand.assets.logo_url||'',
    'brand.logo_dark':brand.assets.logo_dark_url||brand.assets.logo_url||'',
    'show_booking':Boolean(features.public_booking),
    'show_login':Boolean(features.show_login),
    'show_whatsapp':Boolean(features.show_whatsapp),
  }
}
function experienceTheme(result:ExperiencePayload):Record<string,unknown>{
  const source={...(result.version.theme||{})} as Record<string,any>
  if(result.page.template_key==='scheduler-pro-padrao-generico'){
    const colors=result.branding.theme?.colors||{}
    source.colors={...(source.colors||{}),primary:colors.primary,secondary:colors.secondary,accent:colors.accent,background:colors.background,text:colors.text}
    source.typography={...(source.typography||{}),body:result.branding.theme?.font_family,heading:result.branding.theme?.font_family}
  }
  return source
}
function experienceDocument(result:ExperiencePayload):string{
  const bindings=(normalizeBindingsManifest(result.version.metadata?.bindings||{}) as any).bindings||{}
  const values={...automaticExperienceBindings(result),...(result.version.bindings_values||{})}
  const body=applyBindingsToHtml(result.version.html,values,bindings)
  const css=themeTokensToCss(createThemeTokens(experienceTheme(result)),':root')
  const style=`<style data-argws-theme>${css}</style>`
  return /<head(?:\s[^>]*)?>/i.test(body)?body.replace(/<head(\s[^>]*)?>/i,m=>`${m}${style}`):`${style}${body}`
}
async function loadExperience(surface:'LANDING'|'BOOKING'):Promise<boolean>{
  try{
    const result=await request<ExperiencePayload>(`/experience/${surface}`)
    experienceHtml.value=experienceDocument(result)
    branding.value=result.branding
    runtimeContext.value={...(result.context||{}),branding:result.branding} as RuntimeContext
    applyBranding(result.branding)
    analyticsConfig=installPublicAnalytics((runtimeContext.value.preferences?.marketing_analytics||{}) as Record<string,unknown>);trackPublicEvent('page_view',{surface:surface.toLowerCase()},analyticsConfig)
    applyHtmlMetadata(experienceHtml.value,result.branding.app.public_name||'Scheduler Pro')
    return true
  }catch{return false}
}
async function loadLanding():Promise<void>{if(await loadExperience('LANDING'))return;const result=await request<LandingPayload>('/landing?slug=home');landing.value=result.landing_page;branding.value=result.branding;runtimeContext.value={...(result.context||await request<RuntimeContext>('/context').catch(()=>({}))),branding:result.branding} as RuntimeContext;applyBranding(result.branding);analyticsConfig=installPublicAnalytics((runtimeContext.value.preferences?.marketing_analytics||{}) as Record<string,unknown>);trackPublicEvent('page_view',{surface:'landing'},analyticsConfig);applyMetadata(result.landing_page);if(runtimeContext.value.features?.public_booking){catalog.value=await request<Catalog>('/booking').catch(()=>null)}}
async function loadBooking():Promise<void>{if(await loadExperience('BOOKING'))return;const result=await request<Catalog>('/booking');catalog.value=result;branding.value=result.branding;runtimeContext.value={...(result.context||await request<RuntimeContext>('/context').catch(()=>({}))),branding:result.branding} as RuntimeContext;applyBranding(result.branding);analyticsConfig=installPublicAnalytics((runtimeContext.value.preferences?.marketing_analytics||{}) as Record<string,unknown>);trackPublicEvent('page_view',{surface:'booking'},analyticsConfig);const html=result.config.booking_template?.content;if(isHtmlContent(html))applyHtmlMetadata(html.html_document,result.config.title||result.branding.app.public_name||'Agendamento online');else document.title=result.config.title||result.branding.app.public_name||'Agendamento online'}
async function loadLogin():Promise<void>{const result=await request<LoginPayload>('/login');loginPage.value=result.login_page.content;branding.value=result.branding;runtimeContext.value={...(result.context||{}),branding:result.branding} as RuntimeContext;applyBranding(result.branding);applyHtmlMetadata(result.login_page.content.html_document,result.branding.app.public_name||'Entrar')}
async function load():Promise<void>{loading.value=true;error.value='';try{if(landingMode.value)await loadLanding();else if(loginMode.value)await loadLogin();else await loadBooking()}catch(exc){error.value=exc instanceof Error?exc.message:'Página pública indisponível.'}finally{loading.value=false}}
function onAnalyticsEvent(event:Event):void{const detail=(event as CustomEvent).detail||{};trackPublicEvent(String(detail.name||''),detail.payload||{},analyticsConfig)}
onMounted(()=>{window.addEventListener('scheduler-pro-analytics-event',onAnalyticsEvent);void load()});onUnmounted(()=>window.removeEventListener('scheduler-pro-analytics-event',onAnalyticsEvent))
</script>

<template>
  <main class="public-site-page" :class="{'html-surface':Boolean(experienceHtml||landingHtml||bookingHtml||loginHtml)}" :style="bookingPageStyle">
    <div v-if="loading" class="public-state"><LoaderCircle :size="36" class="spin"/><strong>Carregando página...</strong></div>
    <template v-else-if="landingMode&&(experienceHtml||landing)">
      <HtmlTemplateFrame v-if="experienceHtml" :html="experienceHtml" mode="landing" :context="runtimeContext"/>
      <HtmlTemplateFrame v-else-if="landingHtml" :html="landingHtml" mode="landing" :context="runtimeContext"/>
      <PublicVisualLandingRenderer v-else :content="blockContent(landing.content)" :services="catalog?.services||[]" :professionals="catalog?.professionals||[]">
        <template #booking><PublicBookingWidget v-if="widgetCatalog&&runtimeContext.features?.public_booking" :catalog="widgetCatalog"/><div v-else class="booking-unavailable"><CalendarDays :size="30"/><strong>Agenda online indisponível neste momento.</strong><span>Você ainda pode usar os contatos desta página.</span></div></template>
      </PublicVisualLandingRenderer>
    </template>
    <template v-else-if="loginMode&&loginHtml"><HtmlTemplateFrame :html="loginHtml" mode="login" :context="runtimeContext"/></template>
    <template v-else-if="bookingMode&&(experienceHtml||catalog)">
      <HtmlTemplateFrame v-if="experienceHtml" :html="experienceHtml" mode="booking" :context="runtimeContext"/>
      <HtmlTemplateFrame v-else-if="bookingHtml" :html="bookingHtml" mode="booking" :context="runtimeContext"/>
      <section v-else class="direct-booking-shell" :data-template="catalog.config.booking_template?.key||''"><header class="direct-booking-header"><div class="direct-brand"><img v-if="catalog.branding.assets.logo_url" :src="catalog.branding.assets.logo_url" :alt="catalog.branding.app.public_name"/><div v-else class="direct-mark">SP</div><div><strong>{{catalog.branding.app.public_name||'Scheduler Pro'}}</strong><small>{{catalog.branding.app.slogan||'Agendamento online'}}</small></div></div><div class="direct-copy"><span>Agenda online</span><h1>{{catalog.config.title}}</h1><p>{{catalog.config.subtitle}}</p></div></header><PublicBookingWidget v-if="widgetCatalog" :catalog="widgetCatalog"/></section>
    </template>
    <section v-else class="public-state unavailable"><LogIn v-if="loginMode" :size="48"/><CalendarDays v-else :size="48"/><h1>{{loginMode?'Login indisponível':landingMode?'Página em preparação':'Agenda indisponível'}}</h1><p>{{error||'Este conteúdo ainda não está disponível.'}}</p></section>
  </main>
</template>

<style scoped>
.public-site-page{min-height:100dvh;background:var(--booking-page-bg,#f5f7fb);color:var(--booking-page-text,#0f172a);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.public-site-page.html-surface{background:#fff}.public-state{min-height:100dvh;display:grid;place-items:center;align-content:center;gap:12px;padding:24px;text-align:center}.public-state p{max-width:560px;color:#52647c}.booking-unavailable{display:grid;place-items:center;gap:6px;padding:28px;border:1px dashed #cbd5e1;border-radius:16px;background:#f8fafc;text-align:center;color:#52647c}.direct-booking-shell{width:min(100% - 28px,1080px);margin:0 auto;padding:clamp(14px,3vw,32px) 0 48px}.direct-booking-header{overflow:hidden;margin-bottom:18px;padding:clamp(24px,5vw,50px);border-radius:var(--booking-page-radius,26px);background:linear-gradient(145deg,var(--booking-page-secondary,#071426),color-mix(in srgb,var(--booking-page-secondary,#071426) 83%,#fff 17%));color:#fff;box-shadow:0 24px 70px rgba(15,23,42,.17)}.direct-brand{display:flex;align-items:center;gap:12px}.direct-brand img{max-width:180px;max-height:54px;object-fit:contain}.direct-brand>div:last-child strong,.direct-brand>div:last-child small{display:block}.direct-mark{width:48px;height:48px;border-radius:14px;display:grid;place-items:center;background:var(--booking-page-primary,#2563eb);font-weight:900}.direct-copy{max-width:680px;padding-top:clamp(30px,6vw,58px)}.direct-copy h1{margin:10px 0 12px;font-size:clamp(34px,7vw,64px);line-height:1}.spin{animation:site-spin 1s linear infinite}@keyframes site-spin{to{transform:rotate(360deg)}}@media(max-width:680px){.direct-booking-shell{width:min(100% - 16px,1080px);padding-top:8px}.direct-booking-header{padding:24px 18px}.direct-copy h1{font-size:38px}}
</style>
