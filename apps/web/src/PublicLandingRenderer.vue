<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, type CSSProperties } from 'vue'
import { CalendarDays, Clock3, Mail, MapPin, MessageCircle, Star, UserRound } from 'lucide-vue-next'

type Device = 'desktop' | 'tablet' | 'mobile'
type Service = { id:string; name:string; duration_minutes:number; price?:number|null }
type Professional = { id:string; name:string }
type Block = {
  id:string
  type:string
  props:Record<string,unknown>
  style?:CSSProperties
  responsive?:{
    desktop?:CSSProperties
    tablet?:CSSProperties
    mobile?:CSSProperties
    hidden?:{desktop?:boolean;tablet?:boolean;mobile?:boolean}
  }
}
type PageContent = {
  version:number
  global_styles?:Record<string,unknown>
  seo?:Record<string,unknown>
  blocks?:Block[]
}

const props=defineProps<{
  content:PageContent
  services?:Service[]
  professionals?:Professional[]
  templateKey?:string|null
  viewportOverride?:Device|null
}>()

const autoViewport=ref<Device>('desktop')
const viewport=computed<Device>(()=>props.viewportOverride||autoViewport.value)
const globals=computed(()=>props.content.global_styles||{})
const blocks=computed(()=>Array.isArray(props.content.blocks)?props.content.blocks:[])

function syncViewport():void{
  const width=window.innerWidth
  autoViewport.value=width<=680?'mobile':width<=1024?'tablet':'desktop'
}
function text(value:unknown):string{return String(value??'')}
function money(value?:number|null):string{
  return value==null?'':new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL'}).format(Number(value))
}
function safeStyle(block:Block):CSSProperties{
  return {...(block.style||{}),...(block.responsive?.[viewport.value]||{})}
}
function isHidden(block:Block):boolean{return Boolean(block.responsive?.hidden?.[viewport.value])}
function items(block:Block):Record<string,unknown>[] {
  return Array.isArray(block.props.items)?block.props.items as Record<string,unknown>[]:[]
}
function images(block:Block):string[]{
  return Array.isArray(block.props.images)?block.props.images.filter((item):item is string=>typeof item==='string'&&item.trim().length>0):[]
}
function safeLink(value:unknown,fallback='#'):string{
  const candidate=text(value).trim()
  if(!candidate)return fallback
  if(candidate.startsWith('#')||candidate.startsWith('/')||candidate.startsWith('mailto:')||candidate.startsWith('tel:'))return candidate
  try{
    const parsed=new URL(candidate,window.location.origin)
    if(parsed.protocol==='http:'||parsed.protocol==='https:')return parsed.href
  }catch{return fallback}
  return fallback
}
function rootStyle():CSSProperties{
  return {
    '--page-primary':String(globals.value.primary||'#3151cf'),
    '--page-secondary':String(globals.value.secondary||'#151c31'),
    '--page-accent':String(globals.value.accent||'#6d72ef'),
    '--page-bg':String(globals.value.background||'#ffffff'),
    '--page-text':String(globals.value.text||'#1d273a'),
    '--page-radius':`${Math.max(0,Math.min(60,Number(globals.value.radius||16)))}px`,
    '--page-heading':String(globals.value.heading_font||'Inter'),
    '--page-body':String(globals.value.body_font||'Inter'),
  } as CSSProperties
}
function whatsappHref(value:unknown):string{
  const digits=text(value).replace(/\D/g,'')
  return digits?`https://wa.me/${digits}`:'#agendamento'
}

onMounted(()=>{syncViewport();window.addEventListener('resize',syncViewport,{passive:true})})
onUnmounted(()=>window.removeEventListener('resize',syncViewport))
</script>

<template>
  <main class="sp-public-renderer" :data-template="templateKey||''" :data-viewport="viewport" :style="rootStyle()">
    <template v-for="block in blocks" :key="block.id">
      <template v-if="!isHidden(block)">
        <section v-if="block.type==='hero'" class="page-block block-hero" :style="safeStyle(block)">
          <div class="hero-copy">
            <span v-if="block.props.eyebrow" class="eyebrow">{{ block.props.eyebrow }}</span>
            <h1>{{ block.props.title }}</h1>
            <p v-if="block.props.text">{{ block.props.text }}</p>
            <a v-if="block.props.cta" class="primary-cta" href="#agendamento"><CalendarDays :size="18"/>{{ block.props.cta }}</a>
          </div>
          <figure v-if="block.props.image" class="hero-image"><img :src="safeLink(block.props.image)" :alt="text(block.props.title)" loading="eager"/></figure>
        </section>

        <section v-else-if="block.type==='title'" class="page-block block-text" :style="safeStyle(block)"><h2>{{ block.props.text }}</h2></section>
        <section v-else-if="block.type==='subtitle'" class="page-block block-text" :style="safeStyle(block)"><h3>{{ block.props.text }}</h3></section>
        <section v-else-if="block.type==='text'" class="page-block block-text" :style="safeStyle(block)"><h2 v-if="block.props.title">{{ block.props.title }}</h2><p>{{ block.props.text }}</p></section>
        <section v-else-if="block.type==='image'||block.type==='logo'" class="page-block block-image" :style="safeStyle(block)"><img v-if="block.props.image" :src="safeLink(block.props.image)" :alt="text(block.props.alt||'Imagem')" loading="lazy"/><div v-else class="content-empty">Adicione uma imagem no editor.</div></section>

        <section v-else-if="block.type==='gallery'" class="page-block block-gallery" :style="safeStyle(block)">
          <header><span class="eyebrow">Portfólio</span><h2>{{ block.props.title }}</h2></header>
          <div v-if="images(block).length" class="gallery-grid" :class="`layout-${text(block.props.layout)||'grid'}`"><figure v-for="(image,index) in images(block)" :key="`${image}-${index}`"><img :src="safeLink(image)" :alt="`${text(block.props.title)||'Galeria'} ${index+1}`" loading="lazy"/></figure></div>
          <div v-else class="content-empty portfolio-empty"><strong>Portfólio em atualização</strong><span>Envie fotos pelo editor para substituir esta área.</span></div>
        </section>

        <section v-else-if="block.type==='services'" class="page-block block-services" :style="safeStyle(block)">
          <header><span class="eyebrow">Atendimentos</span><h2>{{ block.props.title }}</h2><p v-if="block.props.subtitle">{{ block.props.subtitle }}</p></header>
          <div v-if="services?.length" class="public-cards"><article v-for="service in services" :key="service.id"><strong>{{ service.name }}</strong><span><Clock3 :size="15"/>{{ service.duration_minutes }} min</span><em v-if="block.props.show_prices!==false&&service.price!=null">{{ money(service.price) }}</em></article></div>
          <div v-else class="content-empty">Cadastre os serviços para preencher esta seção automaticamente.</div>
        </section>

        <section v-else-if="block.type==='professionals'" class="page-block block-professionals" :style="safeStyle(block)">
          <header><span class="eyebrow">Equipe</span><h2>{{ block.props.title }}</h2></header>
          <div v-if="professionals?.length" class="public-cards professional-cards"><article v-for="professional in professionals" :key="professional.id"><div class="avatar"><UserRound :size="22"/></div><strong>{{ professional.name }}</strong></article></div>
          <div v-else class="content-empty">Cadastre os profissionais para preencher esta seção automaticamente.</div>
        </section>

        <section v-else-if="block.type==='cards'||block.type==='card'||block.type==='columns'||block.type==='grid'" class="page-block block-cards" :style="safeStyle(block)">
          <header v-if="block.props.title"><h2>{{ block.props.title }}</h2></header>
          <div class="public-cards"><article v-for="(item,index) in items(block)" :key="index"><strong>{{ item.title }}</strong><p>{{ item.text }}</p></article><article v-if="block.type==='card'&&!items(block).length"><strong>{{ block.props.title }}</strong><p>{{ block.props.text }}</p></article></div>
        </section>

        <section v-else-if="block.type==='testimonials'" class="page-block block-testimonials" :style="safeStyle(block)">
          <header><span class="eyebrow">Avaliações</span><h2>{{ block.props.title }}</h2></header>
          <div v-if="items(block).length" class="public-cards"><blockquote v-for="(item,index) in items(block)" :key="index"><Star :size="17"/><p>{{ item.text }}</p><strong>{{ item.name||item.title }}</strong></blockquote></div>
          <div v-else class="content-empty">Depoimentos podem ser adicionados quando você quiser.</div>
        </section>

        <section v-else-if="block.type==='faq'" class="page-block block-faq" :style="safeStyle(block)"><header><h2>{{ block.props.title }}</h2></header><details v-for="(item,index) in items(block)" :key="index"><summary>{{ item.question||item.title }}</summary><p>{{ item.answer||item.text }}</p></details><div v-if="!items(block).length" class="content-empty">Adicione perguntas frequentes no editor.</div></section>
        <section v-else-if="block.type==='business_hours'" class="page-block block-info" :style="safeStyle(block)"><Clock3 :size="24"/><div><h2>{{ block.props.title }}</h2><p>Consulte os horários disponíveis diretamente na agenda.</p></div></section>
        <section v-else-if="block.type==='address'||block.type==='map'" class="page-block block-info" :style="safeStyle(block)"><MapPin :size="25"/><div><h2>{{ block.props.title }}</h2><p v-if="block.props.address">{{ block.props.address }}</p><p v-else>Informe o endereço no editor.</p></div></section>
        <section v-else-if="block.type==='contact'" class="page-block block-contact" :style="safeStyle(block)"><h2>{{ block.props.title }}</h2><div><a v-if="block.props.phone" :href="`tel:${text(block.props.phone)}`"><MessageCircle :size="18"/>{{ block.props.phone }}</a><a v-if="block.props.email" :href="`mailto:${text(block.props.email)}`"><Mail :size="18"/>{{ block.props.email }}</a></div></section>
        <section v-else-if="block.type==='social'" class="page-block block-social" :style="safeStyle(block)"><h2>{{ block.props.title }}</h2><div><a v-if="block.props.instagram" :href="safeLink(block.props.instagram)" target="_blank" rel="noopener noreferrer">Instagram</a><a v-if="block.props.facebook" :href="safeLink(block.props.facebook)" target="_blank" rel="noopener noreferrer">Facebook</a><a v-if="block.props.tiktok" :href="safeLink(block.props.tiktok)" target="_blank" rel="noopener noreferrer">TikTok</a></div></section>
        <section v-else-if="block.type==='button'" class="page-block block-button" :style="safeStyle(block)"><a class="primary-cta" :href="safeLink(block.props.url,'#agendamento')">{{ block.props.label }}</a></section>
        <section v-else-if="block.type==='whatsapp_button'" class="page-block block-button" :style="safeStyle(block)"><a class="primary-cta" :href="whatsappHref(block.props.phone)" target="_blank" rel="noopener noreferrer"><MessageCircle :size="18"/>{{ block.props.label }}</a></section>
        <section v-else-if="block.type==='cta'" class="page-block block-cta" :style="safeStyle(block)"><div><h2>{{ block.props.title }}</h2><p>{{ block.props.text }}</p></div><a class="primary-cta" href="#agendamento">{{ block.props.button }}</a></section>
        <section v-else-if="block.type==='notices'||block.type==='policies'" class="page-block block-note" :style="safeStyle(block)"><h2>{{ block.props.title }}</h2><p>{{ block.props.text }}</p></section>
        <section v-else-if="block.type==='video'" class="page-block block-video" :style="safeStyle(block)"><h2>{{ block.props.title }}</h2><a v-if="block.props.url" :href="safeLink(block.props.url)" target="_blank" rel="noopener noreferrer">Abrir vídeo</a></section>
        <section v-else-if="block.type==='divider'" class="page-block block-divider"><hr/></section>
        <section v-else-if="block.type==='spacer'" class="block-spacer" :style="{height:`${Math.max(0,Number(block.props.height||32))}px`}"></section>

        <section v-else-if="block.type==='booking'||block.type==='calendar'||block.type==='form'" id="agendamento" class="page-block block-booking" :style="safeStyle(block)"><header><span class="eyebrow">Agenda</span><h2>{{ block.props.title||'Agende seu horário' }}</h2><p v-if="block.props.subtitle">{{ block.props.subtitle }}</p></header><slot name="booking"/></section>
        <footer v-else-if="block.type==='footer'" class="page-block block-footer" :style="safeStyle(block)"><strong>{{ text(globals.site_name||'') }}</strong><span>{{ block.props.text }}</span></footer>
        <section v-else class="page-block block-generic" :style="safeStyle(block)"><h2 v-if="block.props.title">{{ block.props.title }}</h2><p v-if="block.props.text">{{ block.props.text }}</p></section>
      </template>
    </template>

    <section v-if="!blocks.some(block=>['booking','calendar','form'].includes(block.type))" id="agendamento" class="page-block block-booking"><slot name="booking"/></section>
  </main>
</template>

<style scoped>
.sp-public-renderer{container-type:inline-size;min-height:100dvh;overflow-x:hidden;background:var(--page-bg);color:var(--page-text);font-family:var(--page-body),Inter,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.page-block{box-sizing:border-box;width:min(calc(100% - 32px),1180px);margin:0 auto;padding:clamp(40px,7cqw,84px) 0}.page-block h1,.page-block h2,.page-block h3{font-family:var(--page-heading),Inter,system-ui;margin:0;overflow-wrap:anywhere}.page-block h2{font-size:clamp(28px,4cqw,46px);line-height:1.05}.page-block p{line-height:1.65;overflow-wrap:anywhere}.eyebrow{display:inline-block;margin-bottom:9px;color:var(--page-primary);font-size:.73rem;font-weight:900;letter-spacing:.12em;text-transform:uppercase}.block-hero{width:100%;min-height:min(720px,86dvh);display:grid;grid-template-columns:minmax(0,1.1fr) minmax(260px,.9fr);align-items:center;gap:clamp(24px,4cqw,48px);padding-block:clamp(50px,8cqw,106px);padding-inline:max(20px,calc((100% - 1180px)/2));background:var(--page-secondary);color:#fff}.block-hero .eyebrow{color:var(--page-accent)}.block-hero h1{max-width:800px;font-size:72px;font-size:clamp(48px,7cqw,88px);line-height:.96;letter-spacing:-.05em}.block-hero p{max-width:640px;color:color-mix(in srgb,#fff 78%,transparent);font-size:clamp(16px,1.7cqw,20px)}.hero-image{margin:0;overflow:hidden;border-radius:calc(var(--page-radius)*1.35);aspect-ratio:4/5;background:rgba(255,255,255,.08);box-shadow:0 24px 60px rgba(0,0,0,.18)}.hero-image img{width:100%;height:100%;object-fit:cover}.primary-cta{width:max-content;max-width:100%;box-sizing:border-box;display:inline-flex;align-items:center;justify-content:center;gap:8px;min-height:48px;margin-top:10px;padding:0 19px;border-radius:var(--page-radius);background:var(--page-primary);color:#fff;text-decoration:none;font-weight:850}.block-text{max-width:900px}.block-text p{font-size:1.08rem}.block-image img{display:block;max-width:100%;max-height:680px;margin:auto;border-radius:var(--page-radius);object-fit:cover}.page-block>header{max-width:760px;margin-bottom:26px}.page-block>header p{color:color-mix(in srgb,var(--page-text) 70%,transparent)}.gallery-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.gallery-grid figure{margin:0;overflow:hidden;border-radius:var(--page-radius);aspect-ratio:1;background:color-mix(in srgb,var(--page-primary) 5%,var(--page-bg))}.gallery-grid img{width:100%;height:100%;object-fit:cover}.gallery-grid.layout-editorial figure:first-child,.gallery-grid.layout-before_after figure:first-child{grid-column:span 2;grid-row:span 2}.gallery-grid.layout-carousel{display:flex;overflow:auto;scroll-snap-type:x mandatory;padding-bottom:8px}.gallery-grid.layout-carousel figure{min-width:min(74cqw,380px);scroll-snap-align:start}.public-cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}.public-cards article,.public-cards blockquote{box-sizing:border-box;min-width:0;display:grid;gap:9px;margin:0;padding:22px;border:1px solid color-mix(in srgb,var(--page-text) 14%,transparent);border-radius:var(--page-radius);background:color-mix(in srgb,var(--page-bg) 94%,var(--page-primary) 6%)}.public-cards span{display:flex;align-items:center;gap:5px;color:color-mix(in srgb,var(--page-text) 67%,transparent);font-size:.88rem}.public-cards em{font-style:normal;font-weight:850;color:var(--page-primary)}.professional-cards article{text-align:center;place-items:center}.avatar{width:50px;height:50px;border-radius:50%;display:grid;place-items:center;background:color-mix(in srgb,var(--page-primary) 14%,transparent);color:var(--page-primary)}.block-testimonials blockquote svg{color:var(--page-accent)}.block-faq details{max-width:820px;margin:8px 0;padding:15px 18px;border:1px solid color-mix(in srgb,var(--page-text) 14%,transparent);border-radius:var(--page-radius)}.block-faq summary{cursor:pointer;font-weight:800}.block-info{display:flex;gap:18px;align-items:flex-start}.block-info>svg{color:var(--page-primary);flex:none}.block-contact>div,.block-social>div{display:flex;flex-wrap:wrap;gap:10px;margin-top:18px}.block-contact a,.block-social a{display:inline-flex;align-items:center;gap:7px;color:var(--page-primary);text-decoration:none;font-weight:800}.block-cta{display:flex;align-items:center;justify-content:space-between;gap:24px;background:color-mix(in srgb,var(--page-primary) 8%,var(--page-bg));padding:clamp(24px,5cqw,50px);border-radius:calc(var(--page-radius)*1.4)}.block-note{padding:26px;border:1px solid color-mix(in srgb,var(--page-text) 14%,transparent);border-radius:var(--page-radius)}.block-divider{padding-top:10px;padding-bottom:10px}.block-divider hr{border:0;border-top:1px solid color-mix(in srgb,var(--page-text) 16%,transparent)}.block-booking{scroll-margin-top:20px}.block-footer{display:flex;justify-content:space-between;gap:20px;border-top:1px solid color-mix(in srgb,var(--page-text) 12%,transparent);padding-top:30px;padding-bottom:30px}.content-empty{display:grid;gap:4px;padding:24px;border:1px dashed color-mix(in srgb,var(--page-text) 20%,transparent);border-radius:var(--page-radius);background:color-mix(in srgb,var(--page-primary) 3%,var(--page-bg));color:color-mix(in srgb,var(--page-text) 62%,transparent);text-align:center}.content-empty strong{color:var(--page-text)}
.sp-public-renderer[data-template="studio-neils"] .block-hero{background:radial-gradient(circle at 78% 16%,color-mix(in srgb,var(--page-primary) 52%,transparent),transparent 34%),linear-gradient(145deg,#1e2a49,#111a30)}.sp-public-renderer[data-template="studio-neils"] .primary-cta{box-shadow:0 12px 30px color-mix(in srgb,var(--page-primary) 26%,transparent)}.sp-public-renderer[data-template="martelinho-de-ouro"] .block-hero{background:linear-gradient(140deg,#101317,#222a34)}.sp-public-renderer[data-template="cabeleireiro"] .block-hero{background:linear-gradient(145deg,#211d1b,#3b3028)}.sp-public-renderer[data-template="clinica"] .block-hero{background:linear-gradient(145deg,#123b47,#176b87)}.sp-public-renderer[data-template="servicos"] .block-hero{background:linear-gradient(145deg,#101c37,#183878)}.sp-public-renderer[data-template="reunioes"] .block-hero{background:linear-gradient(145deg,#17152f,#302a73)}
.sp-public-renderer[data-viewport="tablet"] .block-hero{grid-template-columns:minmax(0,1fr) minmax(220px,.72fr);min-height:620px}.sp-public-renderer[data-viewport="tablet"] .public-cards{grid-template-columns:repeat(2,minmax(0,1fr))}.sp-public-renderer[data-viewport="tablet"] .block-hero h1{font-size:58px}
.sp-public-renderer[data-viewport="mobile"] .page-block{width:min(calc(100% - 22px),1180px);padding:36px 0}.sp-public-renderer[data-viewport="mobile"] .page-block h2{font-size:30px}.sp-public-renderer[data-viewport="mobile"] .block-hero{min-height:auto;grid-template-columns:1fr;gap:24px;padding:48px 16px}.sp-public-renderer[data-viewport="mobile"] .block-hero h1{font-size:44px;line-height:.98;letter-spacing:-.035em}.sp-public-renderer[data-viewport="mobile"] .block-hero p{font-size:16px}.sp-public-renderer[data-viewport="mobile"] .hero-image{aspect-ratio:16/10}.sp-public-renderer[data-viewport="mobile"] .gallery-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.sp-public-renderer[data-viewport="mobile"] .gallery-grid.layout-editorial figure:first-child,.sp-public-renderer[data-viewport="mobile"] .gallery-grid.layout-before_after figure:first-child{grid-column:span 2;grid-row:span 1;aspect-ratio:16/10}.sp-public-renderer[data-viewport="mobile"] .public-cards{grid-template-columns:1fr}.sp-public-renderer[data-viewport="mobile"] .block-cta{align-items:flex-start;flex-direction:column}.sp-public-renderer[data-viewport="mobile"] .block-footer{flex-direction:column}.sp-public-renderer[data-viewport="mobile"] .primary-cta{width:100%}.sp-public-renderer[data-viewport="mobile"] .block-info{gap:12px}.sp-public-renderer[data-viewport="mobile"] .block-contact>div,.sp-public-renderer[data-viewport="mobile"] .block-social>div{display:grid}.sp-public-renderer[data-viewport="mobile"] .block-contact a,.sp-public-renderer[data-viewport="mobile"] .block-social a{min-height:44px}
@media(max-width:1024px){.sp-public-renderer:not([data-viewport="mobile"]) .public-cards{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:680px){.page-block{width:min(calc(100% - 22px),1180px);padding:36px 0}.block-hero{min-height:auto;grid-template-columns:1fr;gap:24px;padding:48px 16px}.block-hero h1{font-size:44px}.hero-image{aspect-ratio:16/10}.gallery-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.public-cards{grid-template-columns:1fr}.block-cta{align-items:flex-start;flex-direction:column}.block-footer{flex-direction:column}.primary-cta{width:100%}}
</style>
