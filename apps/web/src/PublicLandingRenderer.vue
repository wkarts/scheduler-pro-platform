<script setup lang="ts">
import { computed } from 'vue'
import { CalendarDays, Clock3, Mail, MapPin, MessageCircle, Star, UserRound } from 'lucide-vue-next'

type Service = { id:string; name:string; duration_minutes:number; price?:number|null }
type Professional = { id:string; name:string }
type Block = {
  id:string
  type:string
  props:Record<string,unknown>
  style?:Record<string,unknown>
  responsive?:{
    desktop?:Record<string,unknown>
    tablet?:Record<string,unknown>
    mobile?:Record<string,unknown>
    hidden?:{desktop?:boolean;tablet?:boolean;mobile?:boolean}
  }
}
type PageContent = { version:number; global_styles?:Record<string,unknown>; seo?:Record<string,unknown>; blocks?:Block[] }

const props=defineProps<{content:PageContent;services?:Service[];professionals?:Professional[];templateKey?:string|null}>()
const globals=computed(()=>props.content.global_styles||{})
const blocks=computed(()=>Array.isArray(props.content.blocks)?props.content.blocks:[])

function text(value:unknown):string{return String(value||'')}
function money(value?:number|null):string{return value==null?'':new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL'}).format(Number(value))}
function safeStyle(block:Block):Record<string,unknown>{return block.style||{}}
function items(block:Block):Record<string,unknown>[] {return Array.isArray(block.props.items)?block.props.items as Record<string,unknown>[]:[]}
function images(block:Block):string[]{return Array.isArray(block.props.images)?block.props.images.filter(item=>typeof item==='string'&&item.length>0) as string[]:[]}
function externalLink(value:unknown):string{return text(value)}
</script>

<template>
  <main
    class="sp-public-renderer"
    :data-template="templateKey || ''"
    :style="{
      '--page-primary':String(globals.primary||'#3151cf'),
      '--page-secondary':String(globals.secondary||'#151c31'),
      '--page-accent':String(globals.accent||'#6d72ef'),
      '--page-bg':String(globals.background||'#ffffff'),
      '--page-text':String(globals.text||'#1d273a'),
      '--page-radius':`${Number(globals.radius||16)}px`,
      '--page-heading':String(globals.heading_font||'Inter'),
      '--page-body':String(globals.body_font||'Inter'),
    }"
  >
    <template v-for="block in blocks" :key="block.id">
      <section v-if="block.type==='hero'" class="page-block block-hero" :style="safeStyle(block)">
        <div class="hero-copy">
          <span v-if="block.props.eyebrow" class="eyebrow">{{ block.props.eyebrow }}</span>
          <h1>{{ block.props.title }}</h1><p v-if="block.props.text">{{ block.props.text }}</p>
          <a v-if="block.props.cta" class="primary-cta" href="#agendamento"><CalendarDays :size="18"/>{{ block.props.cta }}</a>
        </div>
        <figure v-if="block.props.image" class="hero-image"><img :src="text(block.props.image)" :alt="text(block.props.title)" loading="eager"/></figure>
      </section>

      <section v-else-if="block.type==='title'" class="page-block block-text" :style="safeStyle(block)"><h2>{{ block.props.text }}</h2></section>
      <section v-else-if="block.type==='subtitle'" class="page-block block-text" :style="safeStyle(block)"><h3>{{ block.props.text }}</h3></section>
      <section v-else-if="block.type==='text'" class="page-block block-text" :style="safeStyle(block)"><h2 v-if="block.props.title">{{ block.props.title }}</h2><p>{{ block.props.text }}</p></section>

      <section v-else-if="block.type==='image'||block.type==='logo'" class="page-block block-image" :style="safeStyle(block)"><img v-if="block.props.image" :src="text(block.props.image)" :alt="text(block.props.alt||'Imagem')" loading="lazy"/></section>

      <section v-else-if="block.type==='gallery'" class="page-block block-gallery" :style="safeStyle(block)">
        <header><span class="eyebrow">Portfólio</span><h2>{{ block.props.title }}</h2></header>
        <div v-if="images(block).length" class="gallery-grid" :class="`layout-${text(block.props.layout)||'grid'}`"><figure v-for="(image,index) in images(block)" :key="`${image}-${index}`"><img :src="image" :alt="`${text(block.props.title)||'Galeria'} ${index+1}`" loading="lazy"/></figure></div>
        <div v-else class="content-empty">Novos trabalhos serão publicados aqui.</div>
      </section>

      <section v-else-if="block.type==='services'" class="page-block block-services" :style="safeStyle(block)">
        <header><span class="eyebrow">Atendimentos</span><h2>{{ block.props.title }}</h2><p v-if="block.props.subtitle">{{ block.props.subtitle }}</p></header>
        <div class="public-cards"><article v-for="service in services||[]" :key="service.id"><strong>{{ service.name }}</strong><span><Clock3 :size="15"/>{{ service.duration_minutes }} min</span><em v-if="block.props.show_prices!==false&&service.price!=null">{{ money(service.price) }}</em></article></div>
      </section>

      <section v-else-if="block.type==='professionals'" class="page-block block-professionals" :style="safeStyle(block)">
        <header><span class="eyebrow">Equipe</span><h2>{{ block.props.title }}</h2></header>
        <div class="public-cards professional-cards"><article v-for="professional in professionals||[]" :key="professional.id"><div class="avatar"><UserRound :size="22"/></div><strong>{{ professional.name }}</strong></article></div>
      </section>

      <section v-else-if="block.type==='cards'||block.type==='card'" class="page-block block-cards" :style="safeStyle(block)">
        <header v-if="block.props.title"><h2>{{ block.props.title }}</h2></header>
        <div class="public-cards"><article v-for="(item,index) in items(block)" :key="index"><strong>{{ item.title }}</strong><p>{{ item.text }}</p></article><article v-if="block.type==='card'&&!items(block).length"><strong>{{ block.props.title }}</strong><p>{{ block.props.text }}</p></article></div>
      </section>

      <section v-else-if="block.type==='testimonials'" class="page-block block-testimonials" :style="safeStyle(block)">
        <header><span class="eyebrow">Avaliações</span><h2>{{ block.props.title }}</h2></header>
        <div v-if="items(block).length" class="public-cards"><blockquote v-for="(item,index) in items(block)" :key="index"><Star :size="17"/><p>{{ item.text }}</p><strong>{{ item.name||item.title }}</strong></blockquote></div>
        <div v-else class="content-empty">Avaliações do estabelecimento aparecerão aqui.</div>
      </section>

      <section v-else-if="block.type==='faq'" class="page-block block-faq" :style="safeStyle(block)"><header><h2>{{ block.props.title }}</h2></header><details v-for="(item,index) in items(block)" :key="index"><summary>{{ item.question||item.title }}</summary><p>{{ item.answer||item.text }}</p></details><div v-if="!items(block).length" class="content-empty">As perguntas mais frequentes serão exibidas aqui.</div></section>

      <section v-else-if="block.type==='business_hours'" class="page-block block-info" :style="safeStyle(block)"><Clock3 :size="24"/><div><h2>{{ block.props.title }}</h2><p>Consulte os horários disponíveis diretamente na agenda.</p></div></section>

      <section v-else-if="block.type==='address'||block.type==='map'" class="page-block block-info" :style="safeStyle(block)"><MapPin :size="25"/><div><h2>{{ block.props.title }}</h2><p v-if="block.props.address">{{ block.props.address }}</p><p v-else>Consulte o estabelecimento para informações de localização.</p></div></section>

      <section v-else-if="block.type==='contact'" class="page-block block-contact" :style="safeStyle(block)"><h2>{{ block.props.title }}</h2><div><a v-if="block.props.phone" :href="`tel:${text(block.props.phone)}`"><MessageCircle :size="18"/>{{ block.props.phone }}</a><a v-if="block.props.email" :href="`mailto:${text(block.props.email)}`"><Mail :size="18"/>{{ block.props.email }}</a></div></section>

      <section v-else-if="block.type==='social'" class="page-block block-social" :style="safeStyle(block)"><h2>{{ block.props.title }}</h2><div><a v-if="block.props.instagram" :href="externalLink(block.props.instagram)" target="_blank" rel="noopener noreferrer">Instagram</a><a v-if="block.props.facebook" :href="externalLink(block.props.facebook)" target="_blank" rel="noopener noreferrer">Facebook</a><a v-if="block.props.tiktok" :href="externalLink(block.props.tiktok)" target="_blank" rel="noopener noreferrer">TikTok</a></div></section>

      <section v-else-if="block.type==='button'" class="page-block block-button" :style="safeStyle(block)"><a class="primary-cta" :href="externalLink(block.props.url||'#agendamento')">{{ block.props.label }}</a></section>
      <section v-else-if="block.type==='whatsapp_button'" class="page-block block-button" :style="safeStyle(block)"><a class="primary-cta" :href="block.props.phone?`https://wa.me/${text(block.props.phone)}`:'#agendamento'" rel="noopener"><MessageCircle :size="18"/>{{ block.props.label }}</a></section>

      <section v-else-if="block.type==='cta'" class="page-block block-cta" :style="safeStyle(block)"><div><h2>{{ block.props.title }}</h2><p>{{ block.props.text }}</p></div><a class="primary-cta" href="#agendamento">{{ block.props.button }}</a></section>

      <section v-else-if="block.type==='notices'||block.type==='policies'" class="page-block block-note" :style="safeStyle(block)"><h2>{{ block.props.title }}</h2><p>{{ block.props.text }}</p></section>

      <section v-else-if="block.type==='video'" class="page-block block-video" :style="safeStyle(block)"><h2>{{ block.props.title }}</h2><a v-if="block.props.url" :href="externalLink(block.props.url)" target="_blank" rel="noopener noreferrer">Abrir vídeo</a></section>

      <section v-else-if="block.type==='custom_html'" class="page-block block-custom" :style="safeStyle(block)" v-html="block.props.html"></section>

      <section v-else-if="block.type==='divider'" class="page-block block-divider"><hr/></section>
      <section v-else-if="block.type==='spacer'" class="block-spacer" :style="{height:`${Number(block.props.height||32)}px`}"></section>

      <section v-else-if="block.type==='booking'||block.type==='calendar'||block.type==='form'" id="agendamento" class="page-block block-booking" :style="safeStyle(block)"><header><span class="eyebrow">Agenda</span><h2>{{ block.props.title||'Agende seu horário' }}</h2><p v-if="block.props.subtitle">{{ block.props.subtitle }}</p></header><slot name="booking"/></section>

      <footer v-else-if="block.type==='footer'" class="page-block block-footer" :style="safeStyle(block)"><strong>Scheduler Pro</strong><span>{{ block.props.text }}</span></footer>

      <section v-else class="page-block block-generic" :style="safeStyle(block)"><h2 v-if="block.props.title">{{ block.props.title }}</h2><p v-if="block.props.text">{{ block.props.text }}</p></section>
    </template>

    <section v-if="!blocks.some(block=>['booking','calendar','form'].includes(block.type))" id="agendamento" class="page-block block-booking"><slot name="booking"/></section>
  </main>
</template>

<style scoped>
.sp-public-renderer{min-height:100dvh;background:var(--page-bg);color:var(--page-text);font-family:var(--page-body),Inter,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.page-block{box-sizing:border-box;width:min(1180px,calc(100% - 32px));margin:0 auto;padding:clamp(42px,7vw,88px) 0}.page-block h1,.page-block h2,.page-block h3{font-family:var(--page-heading),Inter,system-ui;margin:0}.page-block h2{font-size:clamp(28px,4vw,46px);line-height:1.05}.page-block p{line-height:1.65}.eyebrow{display:inline-block;margin-bottom:9px;color:var(--page-primary);font-size:.73rem;font-weight:900;letter-spacing:.12em;text-transform:uppercase}.block-hero{width:100%;min-height:min(720px,86dvh);display:grid;grid-template-columns:minmax(0,1.1fr) minmax(280px,.9fr);align-items:center;gap:40px;padding:clamp(46px,8vw,110px) max(20px,calc((100vw - 1180px)/2));background:var(--page-secondary);color:#fff}.block-hero .eyebrow{color:var(--page-accent)}.block-hero h1{max-width:800px;font-size:clamp(46px,7vw,88px);line-height:.94;letter-spacing:-.055em}.block-hero p{max-width:640px;color:color-mix(in srgb,#fff 76%,transparent);font-size:clamp(16px,2vw,20px)}.hero-image{margin:0;overflow:hidden;border-radius:calc(var(--page-radius) * 1.4);aspect-ratio:4/5;background:rgba(255,255,255,.08)}.hero-image img{width:100%;height:100%;object-fit:cover}.primary-cta{width:max-content;display:inline-flex;align-items:center;justify-content:center;gap:8px;min-height:48px;margin-top:10px;padding:0 18px;border-radius:var(--page-radius);background:var(--page-primary);color:#fff;text-decoration:none;font-weight:850}.block-text{max-width:900px}.block-text p{font-size:1.08rem}.block-image img{display:block;max-width:100%;max-height:680px;margin:auto;border-radius:var(--page-radius);object-fit:cover}.page-block>header{max-width:720px;margin-bottom:26px}.page-block>header p{color:color-mix(in srgb,var(--page-text) 70%,transparent)}.gallery-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.gallery-grid figure{margin:0;overflow:hidden;border-radius:var(--page-radius);aspect-ratio:1}.gallery-grid img{width:100%;height:100%;object-fit:cover}.gallery-grid.layout-editorial figure:first-child,.gallery-grid.layout-before_after figure:first-child{grid-column:span 2;grid-row:span 2}.gallery-grid.layout-carousel{display:flex;overflow:auto}.gallery-grid.layout-carousel figure{min-width:min(78vw,380px)}.public-cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.public-cards article,.public-cards blockquote{display:grid;gap:9px;margin:0;padding:22px;border:1px solid color-mix(in srgb,var(--page-text) 14%,transparent);border-radius:var(--page-radius);background:color-mix(in srgb,var(--page-bg) 94%,var(--page-primary) 6%)}.public-cards span{display:flex;align-items:center;gap:5px;color:color-mix(in srgb,var(--page-text) 67%,transparent);font-size:.88rem}.public-cards em{font-style:normal;font-weight:850;color:var(--page-primary)}.professional-cards article{text-align:center;place-items:center}.avatar{width:48px;height:48px;display:grid;place-items:center;border-radius:50%;background:color-mix(in srgb,var(--page-primary) 14%,transparent);color:var(--page-primary)}.block-testimonials blockquote>svg{color:var(--page-accent)}.block-faq details{max-width:850px;margin:8px auto;padding:15px 18px;border:1px solid color-mix(in srgb,var(--page-text) 14%,transparent);border-radius:var(--page-radius)}.block-faq summary{font-weight:800;cursor:pointer}.block-info{display:flex;align-items:flex-start;gap:15px;max-width:850px}.block-info>svg{flex:0 0 auto;color:var(--page-primary)}.block-info h2{font-size:clamp(24px,3vw,36px)}.block-contact>div,.block-social>div{display:flex;flex-wrap:wrap;gap:9px;margin-top:18px}.block-contact a,.block-social a{display:inline-flex;align-items:center;gap:7px;padding:10px 13px;border:1px solid color-mix(in srgb,var(--page-text) 15%,transparent);border-radius:var(--page-radius);color:inherit;text-decoration:none}.block-button{text-align:center}.block-cta{width:min(1080px,calc(100% - 32px));display:flex;align-items:center;justify-content:space-between;gap:24px;padding:clamp(28px,5vw,52px);border-radius:calc(var(--page-radius) * 1.4);background:var(--page-secondary);color:#fff}.block-cta p{color:color-mix(in srgb,#fff 75%,transparent)}.block-note{max-width:900px;padding-block:26px}.block-video a{display:inline-block;margin-top:14px;color:var(--page-primary);font-weight:800}.block-divider{padding-block:10px}.block-divider hr{border:0;border-top:1px solid color-mix(in srgb,var(--page-text) 15%,transparent)}.block-booking{width:100%;padding:clamp(46px,7vw,84px) max(12px,calc((100vw - 1180px)/2));background:color-mix(in srgb,var(--page-bg) 93%,var(--page-primary) 7%)}.block-booking>header{width:min(1180px,100%);margin-inline:auto}.block-footer{width:100%;display:flex;justify-content:space-between;gap:15px;padding:28px max(18px,calc((100vw - 1180px)/2));background:var(--page-secondary);color:#fff}.content-empty{padding:28px;border:1px dashed color-mix(in srgb,var(--page-text) 25%,transparent);border-radius:var(--page-radius);color:color-mix(in srgb,var(--page-text) 65%,transparent);text-align:center}
.sp-public-renderer[data-template="martelinho-de-ouro"] .block-hero{background:linear-gradient(120deg,#121212,#2a2415)}.sp-public-renderer[data-template="studio-neils"] .block-hero{background:linear-gradient(140deg,#6f3048,#c16c89)}.sp-public-renderer[data-template="clinica"] .block-hero{background:linear-gradient(135deg,#0d4f67,#237e91)}.sp-public-renderer[data-template="reunioes"] .block-hero{min-height:600px;background:linear-gradient(135deg,#24205c,#574bd8)}.sp-public-renderer[data-template="agenda-essencial"] .block-hero{min-height:560px;background:linear-gradient(135deg,#121a32,#2a43a7)}
@media(max-width:780px){.page-block{width:calc(100% - 24px);padding-block:42px}.block-hero{min-height:auto;grid-template-columns:1fr;padding:56px 20px}.block-hero h1{font-size:clamp(40px,12vw,64px)}.hero-image{aspect-ratio:16/11}.public-cards{grid-template-columns:1fr}.gallery-grid{grid-template-columns:1fr 1fr}.gallery-grid.layout-editorial figure:first-child,.gallery-grid.layout-before_after figure:first-child{grid-column:span 2}.block-cta{width:calc(100% - 24px);align-items:flex-start;flex-direction:column}.block-booking{padding-inline:10px}.block-footer{flex-direction:column}.sp-public-renderer[data-template="cabeleireiro"] .block-hero,.sp-public-renderer[data-template="studio-neils"] .block-hero{padding-top:42px}}
</style>
