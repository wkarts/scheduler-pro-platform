import { deepClone, getBreakpoints, getNode, isHtmlDocument, normalizeDocument } from './model.js';
import { evaluateConditions, getPath, resolveBindings } from './dynamic.js';
import { conservativeHtml, escapeHtml, safeEmbedUrl, safeUrl, sanitizeDeclarationList, sanitizeStyleValue, sanitizeStylesheet } from './sanitize.js';
import { standaloneRuntimeSource } from './runtime.js';
import { resolveDataRequirements } from './data-sources.js';
import { fontFaceCss } from './assets.js';
import { localizeDocument } from './i18n.js';
import { renderCustomCode } from './custom-code.js';
import { normalizeFormSchema, parseFormFieldsText } from './forms.js';

const CUSTOM_RENDERERS = new Map();
export function registerRenderer(type, renderer) { if (typeof renderer !== 'function') throw new Error('Renderer inválido.'); CUSTOM_RENDERERS.set(type, renderer); }
export function unregisterRenderer(type) { CUSTOM_RENDERERS.delete(type); }

const SCHEDULER_SUPPORTED = new Set([
  'section','container','columns','grid','hero','title','subtitle','text','logo','image','gallery','video','button','whatsapp_button','social','divider','spacer','card','cards','services','professionals','booking','calendar','business_hours','address','map','contact','faq','testimonials','cta','notices','policies','footer'
]);
const UNIT_LESS = new Set(['fontWeight','opacity','zIndex','order','flexGrow','flexShrink','lineHeight','scale']);
const PX_PROPS = new Set(['fontSize','borderRadius','gap','rowGap','columnGap','padding','paddingTop','paddingRight','paddingBottom','paddingLeft','margin','marginTop','marginRight','marginBottom','marginLeft','width','maxWidth','minWidth','minHeight','height','letterSpacing','top','right','bottom','left','outlineOffset']);
const STATE_KEYS = ['hover','focus','active'];

function cssName(key) { return key.replace(/[A-Z]/g, match => `-${match.toLowerCase()}`); }
function cssValue(key, value) {
  if (value == null || value === '') return '';
  if (typeof value === 'number' && PX_PROPS.has(key) && !UNIT_LESS.has(key)) return `${value}px`;
  return sanitizeStyleValue(value);
}
function styleText(style) {
  return Object.entries(style || {}).map(([key, value]) => { const v = cssValue(key, value); return v ? `${cssName(key)}:${v}` : ''; }).filter(Boolean).join(';');
}
function importantStyleText(style) {
  return Object.entries(style || {}).map(([key, value]) => { const v = cssValue(key, value); return v ? `${cssName(key)}:${v}!important` : ''; }).filter(Boolean).join(';');
}
function classNames(node) {
  const raw = node?.meta?.classes;
  const values = Array.isArray(raw) ? raw : String(raw || '').split(/[\s,]+/);
  return values.map(v => String(v).trim().replace(/[^a-zA-Z0-9_-]/g, '')).filter(Boolean);
}
function classDefinition(doc, name) { const value = doc?.design_system?.classes?.[name]; return value && typeof value === 'object' ? value : {}; }
function cascadeDevices(doc, device) {
  const bps = getBreakpoints(doc); const index = Math.max(0, bps.findIndex(bp => bp.id === device));
  return bps.slice(0, index + 1).map(bp => bp.id);
}
function styleObject(doc, node, device = 'desktop', state = null) {
  const base = {};
  const devices = cascadeDevices(doc, device);
  for (const className of classNames(node)) {
    const def = classDefinition(doc, className);
    Object.assign(base, state ? (def.states?.[state] || {}) : (def.style || {}));
    for (const current of devices.slice(1)) Object.assign(base, state ? (def.responsive_states?.[current]?.[state] || {}) : (def.responsive?.[current] || {}));
  }
  if (state) {
    Object.assign(base, node.states?.[state] || {});
    for (const current of devices.slice(1)) Object.assign(base, node.responsive_states?.[current]?.[state] || {});
  } else {
    Object.assign(base, node.style || {});
    for (const current of devices.slice(1)) Object.assign(base, node.responsive?.[current] || {});
    if (node.type === 'container') Object.assign(base, { display:'flex', flexDirection:node.props.direction || 'column', flexWrap:node.props.wrap || 'nowrap', gap:Number(node.props.gap ?? 20), maxWidth:Number(node.props.max_width ?? doc.global_styles?.content_width ?? 1180), marginLeft:'auto', marginRight:'auto' });
    if (node.type === 'grid') {
      const columns = Math.max(1, Number(node.props.columns || 3));
      Object.assign(base, { display:'grid', gridTemplateColumns:`repeat(${columns}, minmax(0,1fr))`, gap:Number(node.props.gap ?? 20) });
    }
    if (node.motion?.sticky) { base.position = 'sticky'; base.top = Number(node.motion?.sticky_offset || 0); base.zIndex = Number(node.motion?.z_index || 20); }
  }
  return base;
}
function hidden(doc, node, device) {
  for (const current of cascadeDevices(doc, device).slice().reverse()) if (node.responsive?.hidden?.[current] != null) return Boolean(node.responsive.hidden[current]);
  return false;
}
function parseListText(value, mode = 'generic') {
  return String(value || '').split(/\r?\n/).map(s => s.trim()).filter(Boolean).map(line => {
    const [left, ...rest] = line.split('|'); const right = rest.join('|').trim();
    if (mode === 'faq') return { question:left.trim(), answer:right };
    if (mode === 'testimonial') return { name:left.trim(), text:right };
    if (mode === 'link') return { label:left.trim(), url:right };
    return { title:left.trim(), text:right };
  });
}
function parseFormFields(value) { return parseFormFieldsText(value); }
function parseActions(value) { return String(value || '').split(/[\n,]+/).map(v => v.trim()).filter(Boolean); }

export function materializeProps(node, context = {}) {
  const props = resolveBindings(deepClone(node.props || {}), node.bindings || {}, context);
  if (['gallery','carousel'].includes(node.type) && typeof props.images_text === 'string') props.images = props.images_text.split(/\r?\n/).map(s=>s.trim()).filter(Boolean);
  if (node.type === 'faq' && typeof props.items_text === 'string') props.items = parseListText(props.items_text, 'faq');
  if (node.type === 'testimonials' && typeof props.items_text === 'string') props.items = parseListText(props.items_text, 'testimonial');
  if (['accordion','tabs'].includes(node.type) && typeof props.items_text === 'string') props.items = parseListText(props.items_text);
  if (['nav_menu','breadcrumbs'].includes(node.type) && typeof props.items_text === 'string') props.items = parseListText(props.items_text, 'link');
  if (node.type === 'list' && typeof props.items_text === 'string') props.items = props.items_text.split(/\r?\n/).map(s=>s.trim()).filter(Boolean);
  if (node.type === 'price_table' && typeof props.features_text === 'string') props.features = props.features_text.split(/\r?\n/).map(s=>s.trim()).filter(Boolean);
  if (node.type === 'form' && typeof props.fields_text === 'string') props.fields = parseFormFields(props.fields_text);
  if (node.type === 'form' && typeof props.actions_text === 'string') props.actions = parseActions(props.actions_text);
  if (node.type === 'form' && typeof props.fields_json === 'string' && props.fields_json.trim()) { try { const parsed=JSON.parse(props.fields_json); if(Array.isArray(parsed)) props.fields=parsed; } catch {} }
  if (node.type === 'form' && typeof props.actions_json === 'string' && props.actions_json.trim()) { try { const parsed=JSON.parse(props.actions_json); if(Array.isArray(parsed)) props.actions=parsed; } catch {} }
  for (const key of ['items_json','slides_json','query_json']) if (typeof props[key] === 'string') { try { props[key.replace(/_json$/, '')] = JSON.parse(props[key]); } catch { props[key.replace(/_json$/, '')] = key === 'query_json' ? {} : []; } }
  delete props.images_text; delete props.items_text; delete props.features_text; delete props.fields_text; delete props.actions_text; delete props.fields_json; delete props.actions_json;
  return props;
}

function textFallback(node, props) {
  const text = [props.title, props.text, props.label, props.name, props.price].filter(Boolean).join(' — ');
  return { id:node.id, type:'text', props:{ title:'', text }, style:deepClone(node.style || {}), responsive:schedulerResponsive(node) };
}
function schedulerResponsive(node) {
  return {
    desktop: deepClone(node.responsive?.desktop || {}), tablet: deepClone(node.responsive?.tablet || {}), mobile: deepClone(node.responsive?.mobile || {}),
    hidden: { desktop:Boolean(node.responsive?.hidden?.desktop), tablet:Boolean(node.responsive?.hidden?.tablet), mobile:Boolean(node.responsive?.hidden?.mobile) },
  };
}
export function toSchedulerProContent(input) {
  const doc = normalizeDocument(input);
  if (isHtmlDocument(doc) && String(doc.html?.contract || '').startsWith('scheduler-pro-html-template/')) {
    return {
      render_mode: 'HTML',
      contract: doc.html.contract || 'scheduler-pro-html-template/v1',
      template_key: String(doc.html.template_key || 'argws-importado'),
      surface: String(doc.surface || doc.html.surface || 'LANDING').toUpperCase(),
      content_version: Math.max(2, Number(doc.html.content_version || 2)),
      html_document: String(doc.html.document || ''),
    };
  }
  // Compatibilidade defensiva com documentos antigos ainda não normalizados.
  const htmlSurface = Object.values(doc.builder?.nodes || {}).find(node => node?.type === 'html_surface' && typeof node?.props?.html_document === 'string' && node.props.html_document.trim());
  if (htmlSurface && String(htmlSurface.props.contract || '').startsWith('scheduler-pro-html-template/')) {
    return {
      render_mode: 'HTML',
      contract: htmlSurface.props.contract || 'scheduler-pro-html-template/v1',
      template_key: String(htmlSurface.props.template_key || 'argws-importado'),
      surface: String(htmlSurface.props.surface || 'LANDING').toUpperCase(),
      content_version: Math.max(2, Number(htmlSurface.props.content_version || 2)),
      html_document: String(htmlSurface.props.html_document),
    };
  }
  const blocks = [];
  const visit = id => {
    const node = getNode(doc, id); if (!node) return;
    if (['container','grid','loop','query_loop','nested_tabs','tab_item','nested_accordion','accordion_item','mega_menu','menu_item','floating_bar','popup','offcanvas'].includes(node.type)) { node.children.forEach(visit); return; }
    let type = node.type; const props = materializeProps(node, {});
    if (type === 'heading') { type = ['h3','h4','h5','h6'].includes(props.level) ? 'subtitle' : 'title'; props.text = props.text || props.title || ''; delete props.level; }
    if (['html','rich_text'].includes(type)) { type = 'text'; props.text = String(props.html || '').replace(/<[^>]+>/g, ' ').replace(/\s+/g,' ').trim(); delete props.html; }
    if (type === 'form') { blocks.push(textFallback(node, { text:props.title || 'Formulário' })); return; }
    if (!SCHEDULER_SUPPORTED.has(type)) { blocks.push(textFallback(node, props)); node.children.forEach(visit); return; }
    blocks.push({ id:node.id, type, props, style:deepClone(node.style || {}), responsive:schedulerResponsive(node) }); node.children.forEach(visit);
  };
  doc.builder.root_ids.forEach(visit);
  if (!blocks.length) blocks.push({ id:'upb-empty', type:'text', props:{title:'',text:''}, style:{}, responsive:{desktop:{},tablet:{},mobile:{},hidden:{desktop:false,tablet:false,mobile:false}} });
  return { version:2, title:doc.title, global_styles:deepClone(doc.global_styles || {}), seo:deepClone(doc.seo || {}), blocks, builder:deepClone(doc.builder), design_system:deepClone(doc.design_system), settings:deepClone(doc.settings), schema:doc.schema };
}

function motionClass(node) { const name=String(node.motion?.entrance||'').replace(/[^a-z0-9_-]/gi,''); return name ? ` upb-motion upb-motion-${name}` : ''; }
function nodeClass(doc, node) { return `upb-node upb-${escapeHtml(node.type)}${motionClass(node)}${classNames(node).map(v=>` ${escapeHtml(v)}`).join('')}`; }
function attrStyle(doc, node, device) {
  const css = styleText(styleObject(doc, node, device)); const extra = sanitizeDeclarationList(node.meta?.customStyle || ''); return escapeHtml([css, extra].filter(Boolean).join(';'));
}
function img(src, alt='Imagem', attrs='') { const url=safeUrl(src,''); return url ? `<img src="${escapeHtml(url)}" alt="${escapeHtml(alt)}" loading="lazy" decoding="async" ${attrs}>` : '<div class="upb-empty">Adicione uma imagem.</div>'; }
function customAttributes(node){const raw=node?.meta?.attributes;if(!raw||typeof raw!=='object'||Array.isArray(raw))return'';const allowed=/^(data-[a-z0-9_.:-]+|aria-[a-z0-9_.:-]+|title|role|tabindex|lang|dir)$/i;return Object.entries(raw).filter(([name,value])=>allowed.test(name)&&value!=null).map(([name,value])=>` ${name}="${escapeHtml(String(value))}"`).join('');}
function interactionAttribute(node){const rows=Array.isArray(node?.interactions)?node.interactions:[];return rows.length?` data-upb-interactions="${escapeHtml(JSON.stringify(rows))}"`:'';}
function inline(prop) { return ` data-upb-inline-prop="${escapeHtml(prop)}"`; }
function editorImportedHtmlSource(htmlDocument, context={}) {
  const source=String(htmlDocument||'');
  const features=context?.features||{};
  const booking=Boolean(features.public_booking??features.booking);
  const login=Boolean(features.show_login??features.login);
  const contact=features.show_contact!==false;
  const whatsapp=features.show_whatsapp!==false;
  const conditionalCss=[
    !booking?'[data-booking-only],[data-booking-link],[data-action="booking"]{display:none!important}':'',
    !login?'[data-login-link],[data-sp-role="login-link"]{display:none!important}':'',
    !contact?'[data-contact-only],[data-section="contact"],a[href^="tel:"],a[href^="mailto:"]{display:none!important}':'',
    !whatsapp?'[data-whatsapp-link],a[href*="wa.me"],a[href*="whatsapp"]{display:none!important}':'',
  ].filter(Boolean).join('');
  const editorCss=`<style data-argws-editor-surface>html{scroll-behavior:auto!important}.reveal,[data-reveal],[data-aos],.animate-on-scroll,.scroll-reveal,.fade-in{opacity:1!important;visibility:visible!important;transform:none!important;animation:none!important;transition:none!important}${conditionalCss}</style>`;
  if (/<\/head\s*>/i.test(source)) return source.replace(/<\/head\s*>/i,`${editorCss}</head>`);
  return `${editorCss}${source}`;
}
function renderChildren(doc, node, device, context) { return node.children.map(id => renderNode(doc, getNode(doc,id), device, context)).join(''); }
function buttonMarkup(p) {
  const label = escapeHtml(p.label || p.button || 'Continuar'); const action = String(p.action || 'link');
  if (action === 'popup' && p.target) return `<a class="upb-btn" href="#" data-upb-open="${escapeHtml(p.target)}">${label}</a>`;
  const href = safeUrl(p.url || '#'); return `<a class="upb-btn" href="${escapeHtml(href)}"${p.new_tab?' target="_blank" rel="noopener noreferrer"':''}>${label}</a>`;
}
function formField(field) {
  const types = new Set(['text','email','tel','number','date','time','datetime-local','url','password','checkbox','radio','textarea','select','file','hidden','range','color']);
  const type = types.has(field.type) ? field.type : 'text'; const name = escapeHtml(field.name); const label = escapeHtml(field.label || field.name);
  const placeholder=field.placeholder?` placeholder="${escapeHtml(field.placeholder)}"`:''; const accept=field.accept?` accept="${escapeHtml(field.accept)}"`:'';
  if (type === 'hidden') return `<input type="hidden" name="${name}" value="${escapeHtml(field.value||'')}">`;
  if (type === 'textarea') return `<label><span>${label}</span><textarea name="${name}"${placeholder} ${field.required?'required':''}></textarea></label>`;
  if (type === 'select') { const options=Array.isArray(field.options)?field.options:[]; return `<label><span>${label}</span><select name="${name}" ${field.required?'required':''}><option value="">Selecione</option>${options.map(option=>{const value=typeof option==='string'?option:option.value;const text=typeof option==='string'?option:option.label;return `<option value="${escapeHtml(value)}">${escapeHtml(text)}</option>`;}).join('')}</select></label>`; }
  if (type === 'radio') { const options=Array.isArray(field.options)?field.options:[]; return `<fieldset class="upb-fieldset"><legend>${label}</legend>${options.map(option=>{const value=typeof option==='string'?option:option.value;const text=typeof option==='string'?option:option.label;return `<label class="upb-check"><input type="radio" name="${name}" value="${escapeHtml(value)}" ${field.required?'required':''}><span>${escapeHtml(text)}</span></label>`;}).join('')}</fieldset>`; }
  if (type === 'checkbox') return `<label class="upb-check"><input type="checkbox" name="${name}" value="1" ${field.required?'required':''}><span>${label}</span></label>`;
  return `<label><span>${label}</span><input type="${type}" name="${name}"${placeholder}${accept} ${field.required?'required':''}></label>`;
}
function jsonArray(value){if(Array.isArray(value))return value;return [];}
function childNodesOfType(doc,node,type){return node.children.map(id=>getNode(doc,id)).filter(child=>child&&child.type===type);}
function hostComponentValue(name,node,p,context){const components=context.hostComponents||{};const value=components[name];return typeof value==='function'?String(value({node,props:p,context})):value||`<div class="upb-dynamic">${escapeHtml(p.fallback||`Componente ${name} fornecido pelo projeto hospedeiro.`)}</div>`;}
function networkShareUrl(network,url,title){const u=encodeURIComponent(url),t=encodeURIComponent(title||'');switch(network){case'whatsapp':return`https://wa.me/?text=${t}%20${u}`;case'facebook':return`https://www.facebook.com/sharer/sharer.php?u=${u}`;case'linkedin':return`https://www.linkedin.com/sharing/share-offsite/?url=${u}`;case'x':return`https://twitter.com/intent/tweet?url=${u}&text=${t}`;case'email':return`mailto:?subject=${t}&body=${u}`;default:return'#';}}

export function renderNode(doc, node, device='desktop', context={}) {
  if (!node || hidden(doc, node, device) || !evaluateConditions(node.conditions, context)) return '';
  const p = materializeProps(node, context); const s = attrStyle(doc,node,device); const id=escapeHtml(node.id); const cls=nodeClass(doc,node);
  const motionAttrs = node.motion?.entrance ? ` data-upb-entrance="${escapeHtml(node.motion.entrance)}" style="${s};--upb-motion-duration:${Math.max(100,Number(node.motion.duration||600))}ms;--upb-motion-delay:${Math.max(0,Number(node.motion.delay||0))}ms"` : ` style="${s}"`;
  const anchor = node.meta?.anchor ? ` id="${escapeHtml(String(node.meta.anchor).replace(/[^a-zA-Z0-9_-]/g,''))}"` : '';
  const wrap = inner => `<section class="${cls}" data-upb-node="${id}"${anchor}${customAttributes(node)}${interactionAttribute(node)}${motionAttrs}>${inner}</section>`;
  const custom=CUSTOM_RENDERERS.get(node.type);
  if(custom){const output=custom({document:doc,node,props:p,device,context,wrap,escapeHtml,safeUrl,renderChildren:()=>renderChildren(doc,node,device,context)});if(typeof output==='string')return output;}
  switch (node.type) {
    case 'container': case 'grid': return wrap(renderChildren(doc,node,device,context) || '<div class="upb-empty">Arraste elementos para este container.</div>');
    case 'hero': return wrap(`<div class="upb-hero-copy">${p.eyebrow?`<span class="upb-eyebrow"${inline('eyebrow')}>${escapeHtml(p.eyebrow)}</span>`:''}<h1${inline('title')}>${escapeHtml(p.title)}</h1><p${inline('text')}>${escapeHtml(p.text)}</p>${p.cta?buttonMarkup({label:p.cta,url:p.cta_url||'#agendamento'}):''}</div>${p.image?`<figure>${img(p.image,p.title)}</figure>`:''}`);
    case 'heading': { const level=['h1','h2','h3','h4','h5','h6'].includes(p.level)?p.level:'h2'; return wrap(`<${level}${inline('text')}>${escapeHtml(p.text)}</${level}>`); }
    case 'title': return wrap(`<h2${inline('text')}>${escapeHtml(p.text)}</h2>`);
    case 'subtitle': return wrap(`<h3${inline('text')}>${escapeHtml(p.text)}</h3>`);
    case 'text': return wrap(`${p.title?`<h2${inline('title')}>${escapeHtml(p.title)}</h2>`:''}<p${inline('text')}>${escapeHtml(p.text)}</p>`);
    case 'rich_text': return wrap(conservativeHtml(p.html));
    case 'button': return wrap(buttonMarkup(p));
    case 'image': case 'logo': { const image=img(p.image,p.alt); return wrap(p.lightbox&&p.image?`<a href="${escapeHtml(safeUrl(p.image,''))}" data-upb-lightbox>${image}</a>${p.caption?`<small>${escapeHtml(p.caption)}</small>`:''}`:`${image}${p.caption?`<small>${escapeHtml(p.caption)}</small>`:''}`); }
    case 'icon': return wrap(p.url?`<a class="upb-icon" href="${escapeHtml(safeUrl(p.url))}" aria-label="${escapeHtml(p.label||'Ícone')}">${escapeHtml(p.icon)}</a>`:`<span class="upb-icon" role="img" aria-label="${escapeHtml(p.label||'Ícone')}">${escapeHtml(p.icon)}</span>`);
    case 'icon_box': return wrap(`<article class="upb-icon-box"><span class="upb-icon">${escapeHtml(p.icon)}</span><h3${inline('title')}>${escapeHtml(p.title)}</h3><p${inline('text')}>${escapeHtml(p.text)}</p></article>`);
    case 'video': { const url=safeEmbedUrl(p.url,''); const mp4=/\.(mp4|webm|ogg)(\?|$)/i.test(url); return wrap(`<h2>${escapeHtml(p.title)}</h2>${url?(mp4?`<video controls ${p.autoplay?'autoplay muted playsinline':''} ${p.poster?`poster="${escapeHtml(safeUrl(p.poster,''))}"`:''}><source src="${escapeHtml(url)}"></video>`:`<a class="upb-btn upb-btn-secondary" href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">Abrir vídeo</a>`):''}`); }
    case 'divider': return `<div class="${cls}" data-upb-node="${id}" style="${s}"><hr></div>`;
    case 'spacer': return `<div class="${cls}" data-upb-node="${id}" style="height:${Math.max(0,Number(p.height||32))}px;${s}"></div>`;
    case 'gallery': return wrap(`<h2>${escapeHtml(p.title)}</h2><div class="upb-gallery layout-${escapeHtml(p.layout||'grid')}">${(p.images||[]).map((url,i)=>`<figure>${img(url,`${p.title||'Galeria'} ${i+1}`)}</figure>`).join('')}</div>`);
    case 'carousel': return wrap(`<div data-upb-carousel data-autoplay="${Boolean(p.autoplay)}" data-interval="${Math.max(1000,Number(p.interval||5000))}"><div class="upb-carousel-head"><h2>${escapeHtml(p.title)}</h2><div><button type="button" data-upb-carousel-prev aria-label="Anterior">‹</button><button type="button" data-upb-carousel-next aria-label="Próximo">›</button></div></div><div class="upb-carousel-track" data-upb-carousel-track>${(p.images||[]).map((url,i)=>`<figure>${img(url,`${p.title||'Carrossel'} ${i+1}`)}</figure>`).join('')}</div></div>`);
    case 'card': return wrap(`<article class="upb-card">${p.url?`<a href="${escapeHtml(safeUrl(p.url))}">`:''}<h3${inline('title')}>${escapeHtml(p.title)}</h3><p${inline('text')}>${escapeHtml(p.text)}</p>${p.url?'</a>':''}</article>`);
    case 'list': return wrap(`${p.title?`<h2>${escapeHtml(p.title)}</h2>`:''}<ul class="upb-list">${(p.items||[]).map(item=>`<li>${escapeHtml(item)}</li>`).join('')}</ul>`);
    case 'counter': return wrap(`<strong class="upb-counter" data-upb-counter data-start="${Number(p.start||0)}" data-end="${Number(p.end||0)}" data-duration="${Math.max(100,Number(p.duration||1400))}" data-suffix="${escapeHtml(p.suffix||'')}">${escapeHtml(`${p.end||0}${p.suffix||''}`)}</strong><span>${escapeHtml(p.title||'')}</span>`);
    case 'progress': return wrap(`<div class="upb-progress"><div><strong>${escapeHtml(p.title)}</strong><span>${escapeHtml(p.label||`${p.value}%`)}</span></div><progress max="100" value="${Math.max(0,Math.min(100,Number(p.value||0)))}"></progress></div>`);
    case 'rating': { const max=Math.max(1,Math.min(10,Number(p.max||5))),value=Math.max(0,Math.min(max,Number(p.value||0))); return wrap(`<div class="upb-rating" aria-label="${escapeHtml(p.label||`${value} de ${max}`)}"><span aria-hidden="true">${'★'.repeat(Math.round(value))}${'☆'.repeat(Math.max(0,max-Math.round(value)))}</span><small>${escapeHtml(p.label||'')}</small></div>`); }
    case 'price_table': return wrap(`<article class="upb-price"><h3>${escapeHtml(p.name)}</h3><div class="upb-price-value"><strong>${escapeHtml(p.price)}</strong><span>${escapeHtml(p.period)}</span></div><ul>${(p.features||[]).map(item=>`<li>${escapeHtml(item)}</li>`).join('')}</ul>${buttonMarkup({label:p.button,url:p.url})}</article>`);
    case 'services': return wrap(`<span class="upb-eyebrow">Atendimentos</span><h2>${escapeHtml(p.title)}</h2><p>${escapeHtml(p.subtitle)}</p><div class="upb-dynamic" data-upb-dynamic="services">${context.servicesHtml || 'Os serviços são carregados pelo projeto hospedeiro.'}</div>`);
    case 'professionals': return wrap(`<span class="upb-eyebrow">Equipe</span><h2>${escapeHtml(p.title)}</h2><div class="upb-dynamic" data-upb-dynamic="professionals">${context.professionalsHtml || 'Os profissionais são carregados pelo projeto hospedeiro.'}</div>`);
    case 'booking': case 'calendar': return `<section id="agendamento" class="${cls}" data-upb-node="${id}" style="${s}"><span class="upb-eyebrow">Agenda</span><h2>${escapeHtml(p.title||'Agende seu horário')}</h2><p>${escapeHtml(p.subtitle||'')}</p><div class="upb-dynamic" data-upb-dynamic="booking">${context.bookingHtml || 'O componente de agendamento é injetado aqui pelo projeto hospedeiro.'}</div></section>`;
    case 'testimonials': return wrap(`<h2>${escapeHtml(p.title)}</h2><div class="upb-cards">${(p.items||[]).map(item=>`<blockquote class="upb-card"><p>“${escapeHtml(item.text)}”</p><strong>${escapeHtml(item.name||item.title||'')}</strong></blockquote>`).join('') || '<div class="upb-empty">Adicione depoimentos.</div>'}</div>`);
    case 'faq': case 'accordion': return wrap(`<h2>${escapeHtml(p.title)}</h2>${(p.items||[]).map(item=>`<details><summary>${escapeHtml(item.question||item.title)}</summary><p>${escapeHtml(item.answer||item.text)}</p></details>`).join('') || '<div class="upb-empty">Adicione itens.</div>'}`);
    case 'tabs': return wrap(`<div class="upb-tabs" data-upb-tabs><div class="upb-tab-list" role="tablist">${(p.items||[]).map((item,i)=>`<button type="button" role="tab" data-upb-tab="${i}" aria-selected="${i===0?'true':'false'}">${escapeHtml(item.title)}</button>`).join('')}</div>${(p.items||[]).map((item,i)=>`<div role="tabpanel" data-upb-tab-panel ${i?'hidden':''}><p>${escapeHtml(item.text)}</p></div>`).join('')}</div>`);
    case 'alert': return wrap(`<div class="upb-alert kind-${escapeHtml(p.kind||'info')}" role="status"><strong>${escapeHtml(p.title)}</strong><p>${escapeHtml(p.text)}</p></div>`);
    case 'business_hours': return wrap(`<h2>${escapeHtml(p.title)}</h2><p>Consulte os horários disponíveis.</p>`);
    case 'address': return wrap(`<h2>${escapeHtml(p.title)}</h2><p>${escapeHtml(p.address||'Informe o endereço.')}</p>`);
    case 'contact': return wrap(`<h2>${escapeHtml(p.title)}</h2>${p.phone?`<a href="tel:${escapeHtml(String(p.phone).replace(/[^0-9+]/g,''))}">${escapeHtml(p.phone)}</a>`:''}${p.email?`<a href="mailto:${escapeHtml(String(p.email))}">${escapeHtml(p.email)}</a>`:''}`);
    case 'social': return wrap(`<h2>${escapeHtml(p.title)}</h2><div class="upb-social">${['instagram','facebook','tiktok','youtube','linkedin'].filter(k=>p[k]).map(k=>`<a href="${escapeHtml(safeUrl(p[k]))}" target="_blank" rel="noopener noreferrer">${escapeHtml(k)}</a>`).join('')}</div>`);
    case 'whatsapp_button': { const digits=String(p.phone||'').replace(/\D/g,''); const message=p.message?`?text=${encodeURIComponent(p.message)}`:''; return wrap(`<a class="upb-btn" href="${digits?`https://wa.me/${digits}${message}`:'#agendamento'}" target="_blank" rel="noopener noreferrer">${escapeHtml(p.label)}</a>`); }
    case 'cta': return wrap(`<div><h2${inline('title')}>${escapeHtml(p.title)}</h2><p${inline('text')}>${escapeHtml(p.text)}</p></div>${buttonMarkup({label:p.button,url:p.url||'#agendamento'})}`);
    case 'form': { const schema=normalizeFormSchema({id:node.id,fields:p.fields||[],actions:p.actions||['event'],success_message:p.success_message}); const multi=Boolean(p.multi_step)&&schema.steps>1; const body=multi?Array.from({length:schema.steps},(_,i)=>{const step=i+1;const fields=schema.fields.filter(field=>Number(field.step||1)===step);return `<div class="upb-form-step" data-upb-form-step="${step}" ${step===1?'':'hidden'}><div class="upb-form-fields">${fields.map(formField).join('')}</div><div class="upb-form-navigation">${step>1?`<button class="upb-btn upb-btn-secondary" type="button" data-upb-form-prev>${escapeHtml(p.previous_label||'Voltar')}</button>`:''}${step<schema.steps?`<button class="upb-btn" type="button" data-upb-form-next>${escapeHtml(p.next_label||'Continuar')}</button>`:`<button class="upb-btn" type="submit">${escapeHtml(p.submit_label||'Enviar')}</button>`}</div></div>`;}).join(''):`<div class="upb-form-fields">${schema.fields.map(formField).join('')}</div><button class="upb-btn" type="submit">${escapeHtml(p.submit_label||'Enviar')}</button>`; return wrap(`<form class="upb-form" data-upb-form data-steps="${schema.steps}" data-actions="${escapeHtml(JSON.stringify(schema.actions||['event']))}" data-success-message="${escapeHtml(schema.success_message)}"><h2>${escapeHtml(p.title)}</h2>${body}<div data-upb-form-status aria-live="polite"></div></form>`); }
    case 'loop': { const collection=getPath(context,p.source,[]); const rows=Array.isArray(collection)?collection.slice(0,Math.max(1,Number(p.limit||12))):[]; if (!rows.length) return wrap(context.editor?`${renderChildren(doc,node,device,{...context,item:{},index:0})}<div class="upb-empty">Preview do loop: ${escapeHtml(p.source)}</div>`:`<div class="upb-empty">${escapeHtml(p.empty||'Nenhum item encontrado.')}</div>`); return wrap(rows.map((item,index)=>`<div class="upb-loop-item">${renderChildren(doc,node,device,{...context,item,index})}</div>`).join('')); }
    case 'dynamic_text': { const value=getPath(context,p.path,p.fallback); return wrap(`<span>${escapeHtml(`${p.prefix||''}${value??''}${p.suffix||''}`)}</span>`); }
    case 'nav_menu': return wrap(`<nav class="upb-nav" aria-label="Menu principal">${p.brand?`<strong>${escapeHtml(p.brand)}</strong>`:''}<div>${(p.items||[]).map(item=>`<a href="${escapeHtml(safeUrl(item.url))}">${escapeHtml(item.label)}</a>`).join('')}</div></nav>`);
    case 'breadcrumbs': return wrap(`<nav class="upb-breadcrumbs" aria-label="Breadcrumb">${(p.items||[]).map((item,i)=>`${i?'<span>›</span>':''}<a href="${escapeHtml(safeUrl(item.url))}">${escapeHtml(item.label)}</a>`).join('')}</nav>`);
    case 'popup': case 'offcanvas': { const inner=renderChildren(doc,node,device,context); if(context.editor)return wrap(`<div class="upb-overlay-editor"><strong>${node.type==='popup'?'Popup':'Off Canvas'} · ${escapeHtml(p.name)}</strong>${inner||'<div class="upb-empty">Adicione conteúdo.</div>'}</div>`); const overlayClass=node.type==='offcanvas'?`upb-overlay upb-offcanvas side-${escapeHtml(p.side||'right')}`:'upb-overlay upb-popup'; return `<dialog class="${overlayClass}" data-upb-node="${id}" data-upb-overlay data-upb-overlay-name="${escapeHtml(p.name||node.id)}" data-trigger="${escapeHtml(p.trigger||'manual')}" data-delay="${Math.max(0,Number(p.delay||0))}" data-scroll-percent="${Math.max(1,Math.min(100,Number(p.scroll_percent||50)))}" style="--upb-overlay-width:${Math.max(260,Number(p.width||560))}px;${s}"><button class="upb-overlay-close" type="button" data-upb-close aria-label="${escapeHtml(p.close_label||'Fechar')}">×</button><div class="upb-overlay-body">${inner}</div></dialog>`; }
    case 'countdown': return wrap(`<strong class="upb-countdown" data-upb-countdown data-target="${escapeHtml(p.target||'')}" data-expired-text="${escapeHtml(p.expired_text||'Encerrado')}">--</strong>`);
    case 'embed': { const url=safeEmbedUrl(p.url,''); return wrap(url?(context.allowEmbeds?`<iframe class="upb-embed" src="${escapeHtml(url)}" title="${escapeHtml(p.title||'Conteúdo incorporado')}" loading="lazy" sandbox="allow-forms allow-popups allow-presentation"></iframe>`:`<a class="upb-btn upb-btn-secondary" href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(p.title||'Abrir conteúdo')}</a>`):'<div class="upb-empty">Informe uma URL HTTPS.</div>'); }
    case 'query_loop': { const source=context.__queries?.[node.id]; const collection=Array.isArray(source)?source:Array.isArray(source?.items)?source.items:[]; const rows=collection.slice(0,Math.max(1,Number(p.limit||12))); if(!rows.length)return wrap(context.editor?`${renderChildren(doc,node,device,{...context,item:{},index:0})}<div class="upb-empty">Query Loop · ${escapeHtml(p.source)}</div>`:`<div class="upb-empty">${escapeHtml(p.empty||'Nenhum item encontrado.')}</div>`); return wrap(rows.map((item,index)=>`<div class="upb-loop-item">${renderChildren(doc,node,device,{...context,item,index,query:source})}</div>`).join('')); }
    case 'nested_tabs': { const items=childNodesOfType(doc,node,'tab_item'); if(context.editor)return wrap(`<div class="upb-nested-editor"><strong>Abas aninhadas</strong>${renderChildren(doc,node,device,context)}</div>`); return wrap(`<div class="upb-tabs upb-nested-tabs orientation-${escapeHtml(p.orientation||'horizontal')}" data-upb-tabs><div class="upb-tab-list" role="tablist">${items.map((item,i)=>`<button type="button" role="tab" data-upb-tab="${i}" aria-selected="${i===0?'true':'false'}">${escapeHtml(item.props?.icon||'')}${escapeHtml(item.props?.title||`Aba ${i+1}`)}</button>`).join('')}</div>${items.map((item,i)=>`<div role="tabpanel" data-upb-tab-panel ${i?'hidden':''}>${renderChildren(doc,item,device,context)}</div>`).join('')}</div>`); }
    case 'tab_item': return context.editor?wrap(`<strong>${escapeHtml(p.title||'Aba')}</strong>${renderChildren(doc,node,device,context)}`):renderChildren(doc,node,device,context);
    case 'nested_accordion': { const items=childNodesOfType(doc,node,'accordion_item'); if(context.editor)return wrap(`<div class="upb-nested-editor"><strong>Acordeão aninhado</strong>${renderChildren(doc,node,device,context)}</div>`); return wrap(`<div class="upb-nested-accordion" data-upb-accordion data-multiple="${Boolean(p.multiple)}">${items.map(item=>`<details ${item.props?.open?'open':''}><summary>${escapeHtml(item.props?.title||'Item')}</summary><div class="upb-accordion-panel">${renderChildren(doc,item,device,context)}</div></details>`).join('')}</div>`); }
    case 'accordion_item': return context.editor?wrap(`<strong>${escapeHtml(p.title||'Item')}</strong>${renderChildren(doc,node,device,context)}`):renderChildren(doc,node,device,context);
    case 'mega_menu': { const items=childNodesOfType(doc,node,'menu_item'); if(context.editor)return wrap(`<div class="upb-nested-editor"><strong>Mega Menu · ${escapeHtml(p.brand||'')}</strong>${renderChildren(doc,node,device,context)}</div>`); return wrap(`<nav class="upb-mega-menu" data-upb-mega-menu data-trigger="${escapeHtml(p.trigger||'click')}" aria-label="Menu principal"><strong class="upb-menu-brand">${escapeHtml(p.brand||'')}</strong><div class="upb-menu-items">${items.map((item,i)=>{const hasPanel=Boolean(item.props?.panel&&item.children.length);return `<div class="upb-menu-item">${hasPanel?`<button type="button" data-upb-menu-toggle="${i}" aria-expanded="false">${escapeHtml(item.props?.label||'Menu')}</button><div class="upb-mega-panel" data-upb-menu-panel="${i}" hidden>${renderChildren(doc,item,device,context)}</div>`:`<a href="${escapeHtml(safeUrl(item.props?.url||'#'))}">${escapeHtml(item.props?.label||'Menu')}</a>`}</div>`;}).join('')}</div></nav>`); }
    case 'menu_item': return context.editor?wrap(`<strong>${escapeHtml(p.label||'Menu')}</strong>${renderChildren(doc,node,device,context)}`):renderChildren(doc,node,device,context);
    case 'floating_bar': return wrap(`<div class="upb-floating-bar position-${escapeHtml(p.position||'bottom')}" data-upb-floating-bar data-upb-sticky="${Boolean(p.sticky)}">${p.dismissible?'<button type="button" data-upb-dismiss aria-label="Fechar">×</button>':''}<div>${renderChildren(doc,node,device,context)||'<span>Adicione conteúdo à barra.</span>'}</div></div>`);
    case 'table_of_contents': return wrap(`<nav class="upb-toc" data-upb-toc data-levels="${escapeHtml(p.levels||'h2,h3')}"><strong>${escapeHtml(p.title||'Nesta página')}</strong><${p.ordered?'ol':'ul'} data-upb-toc-list></${p.ordered?'ol':'ul'}></nav>`);
    case 'search': return wrap(`<form class="upb-search" action="${escapeHtml(safeUrl(p.action||'/buscar'))}" method="${String(p.method).toLowerCase()==='post'?'post':'get'}"><input type="search" name="${escapeHtml(p.param||'q')}" placeholder="${escapeHtml(p.placeholder||'Buscar…')}" aria-label="${escapeHtml(p.placeholder||'Buscar')}"><button class="upb-btn" type="submit">Buscar</button></form>`);
    case 'share_buttons': { const networks=String(p.networks||'whatsapp,facebook,linkedin,x,email').split(',').map(x=>x.trim()).filter(Boolean); const pageUrl=context.pageUrl||doc.seo?.canonical||'#'; const title=doc.seo?.title||doc.title; return wrap(`<div class="upb-share"><strong>${escapeHtml(p.title||'Compartilhe')}</strong><div>${networks.map(n=>`<a class="upb-share-btn" data-network="${escapeHtml(n)}" href="${escapeHtml(networkShareUrl(n,pageUrl,title))}" target="${n==='email'?'_self':'_blank'}" rel="noopener noreferrer">${escapeHtml(n)}</a>`).join('')}</div></div>`); }
    case 'map': { const url=safeEmbedUrl(p.embed_url,''); return wrap(`<h2>${escapeHtml(p.title||'Localização')}</h2>${p.address?`<p>${escapeHtml(p.address)}</p>`:''}${url&&context.allowEmbeds?`<iframe class="upb-embed" src="${escapeHtml(url)}" title="${escapeHtml(p.title||'Mapa')}" loading="lazy" sandbox="allow-scripts allow-same-origin allow-popups"></iframe>`:''}`); }
    case 'lottie': { const url=safeUrl(p.url,''); return wrap(url?`<div class="upb-lottie" data-upb-lottie data-url="${escapeHtml(url)}" data-loop="${Boolean(p.loop)}" data-autoplay="${Boolean(p.autoplay)}" role="img" aria-label="${escapeHtml(p.label||'Animação')}"><span>Carregando animação…</span></div>`:'<div class="upb-empty">Informe a URL do JSON Lottie.</div>'); }
    case 'hotspot': { const points=jsonArray(p.items); return wrap(`<div class="upb-hotspot">${img(p.image,p.alt||'Imagem interativa')}<div class="upb-hotspot-layer">${points.map((point,i)=>`<button type="button" class="upb-hotspot-point" style="left:${Math.max(0,Math.min(100,Number(point.x||0)))}%;top:${Math.max(0,Math.min(100,Number(point.y||0)))}%" aria-label="${escapeHtml(point.label||`Ponto ${i+1}`)}"><span>${i+1}</span><span class="upb-hotspot-tip">${escapeHtml(point.label||'')} ${point.text?`<small>${escapeHtml(point.text)}</small>`:''}</span></button>`).join('')}</div></div>`); }
    case 'flip_box': return wrap(`<div class="upb-flip" tabindex="0"><div class="upb-flip-inner"><article class="upb-flip-face front"><h3>${escapeHtml(p.front_title)}</h3><p>${escapeHtml(p.front_text)}</p></article><article class="upb-flip-face back"><h3>${escapeHtml(p.back_title)}</h3><p>${escapeHtml(p.back_text)}</p>${buttonMarkup({label:p.button,url:p.url})}</article></div></div>`);
    case 'slides': { const slides=jsonArray(p.slides); return wrap(`<div class="upb-slides" data-upb-slides data-autoplay="${Boolean(p.autoplay)}" data-interval="${Math.max(1000,Number(p.interval||5000))}">${slides.map((slide,i)=>`<article class="upb-slide" data-upb-slide="${i}" ${i?'hidden':''} style="${slide.image?`background-image:linear-gradient(#0006,#0006),url('${escapeHtml(safeUrl(slide.image,''))}')`:''}"><div><h2>${escapeHtml(slide.title||'')}</h2><p>${escapeHtml(slide.text||'')}</p>${slide.button?buttonMarkup({label:slide.button,url:slide.url||'#'}):''}</div></article>`).join('')}<div class="upb-slide-nav"><button type="button" data-upb-slide-prev>‹</button><button type="button" data-upb-slide-next>›</button></div></div>`); }
    case 'host_component': return wrap(hostComponentValue(p.name,node,p,context));
    case 'commerce_product_grid': case 'commerce_product': case 'commerce_cart': case 'commerce_checkout': case 'commerce_account': return wrap(`${p.title?`<h2>${escapeHtml(p.title)}</h2>`:''}${hostComponentValue(p.component||node.type,node,p,context)}`);
    case 'login_form': return wrap(`<form class="upb-form upb-login" data-upb-form data-actions="${escapeHtml(JSON.stringify([{type:p.action||'auth.login'}]))}" data-success-message="Autenticado."><h2>${escapeHtml(p.title||'Entrar')}</h2><label><span>${escapeHtml(p.identity_label||'E-mail')}</span><input type="text" name="identity" autocomplete="username" required></label><label><span>${escapeHtml(p.password_label||'Senha')}</span><input type="password" name="password" autocomplete="current-password" required></label><button class="upb-btn" type="submit">${escapeHtml(p.submit_label||'Entrar')}</button><div data-upb-form-status aria-live="polite"></div></form>`);
    case 'cookie_consent': return wrap(`<aside class="upb-cookie" data-upb-cookie-consent><p>${escapeHtml(p.text)}</p><div><button type="button" class="upb-btn" data-upb-cookie="accept">${escapeHtml(p.accept||'Aceitar')}</button><button type="button" class="upb-btn upb-btn-secondary" data-upb-cookie="reject">${escapeHtml(p.reject||'Recusar')}</button>${p.policy_url?`<a href="${escapeHtml(safeUrl(p.policy_url))}">Política</a>`:''}</div></aside>`);
    case 'code_block': return wrap(`<pre class="upb-code" data-language="${escapeHtml(p.language||'text')}"><code>${escapeHtml(p.code||'')}</code></pre>`);
    case 'anchor': return `<span class="upb-anchor" id="${escapeHtml(String(p.name||node.id).replace(/[^a-zA-Z0-9_-]/g,''))}" data-upb-node="${id}"></span>`;
    case 'footer': return `<footer class="${cls}" data-upb-node="${id}" style="${s}">${escapeHtml(p.text)}</footer>`;
    case 'html_surface': {
      const sandbox = context.editor ? 'allow-forms allow-same-origin' : (context.allowImportedHtmlScripts ? 'allow-forms allow-scripts allow-modals allow-popups allow-downloads' : 'allow-forms');
      const editorClass = context.editor ? ' upb-html-surface-editor' : '';
      const htmlSource = context.editor ? editorImportedHtmlSource(p.html_document||'',context) : String(p.html_document||'');
      return wrap(`<div class="upb-html-surface-frame${editorClass}"><iframe data-upb-html-surface-frame title="${escapeHtml(p.title||p.template_key||'Template HTML')}" sandbox="${sandbox}" srcdoc="${escapeHtml(htmlSource)}"></iframe></div>`);
    }
    case 'html': return wrap(conservativeHtml(p.html));
    default: return wrap(`${p.title?`<h2>${escapeHtml(p.title)}</h2>`:''}${p.text?`<p>${escapeHtml(p.text)}</p>`:''}${renderChildren(doc,node,device,context)}`);
  }
}

function selectorForNode(id, suffix='') { return `.upb-page [data-upb-node="${String(id).replace(/"/g,'\\"')}"]${suffix}`; }
function classCss(doc, name) {
  const def=classDefinition(doc,name); const safeName=String(name).replace(/[^a-zA-Z0-9_-]/g,''); if(!safeName)return'';
  let css=`.upb-page .${safeName}{${styleText(def.style||{})}}`;
  for(const state of STATE_KEYS)if(Object.keys(def.states?.[state]||{}).length)css+=`.upb-page .${safeName}:${state}{${styleText(def.states[state])}}`;
  for(const bp of getBreakpoints(doc).filter(x=>x.max!=null)){
    const body=styleText(def.responsive?.[bp.id]||{});if(body)css+=`@media(max-width:${bp.max}px){.upb-page .${safeName}{${body}}}`;
    for(const state of STATE_KEYS){const stateBody=styleText(def.responsive_states?.[bp.id]?.[state]||{});if(stateBody)css+=`@media(max-width:${bp.max}px){.upb-page .${safeName}:${state}{${stateBody}}}`;}
  }
  return css;
}
function nodeResponsiveCss(doc,node){let css='';for(const state of STATE_KEYS){const body=importantStyleText(node.states?.[state]||{});if(body)css+=`${selectorForNode(node.id,`:${state}`)}{${body}}`;}for(const bp of getBreakpoints(doc).filter(x=>x.max!=null)){const body=importantStyleText(node.responsive?.[bp.id]||{});const hiddenValue=node.responsive?.hidden?.[bp.id];let rules=body;if(hiddenValue===true)rules+=`${rules?';':''}display:none!important`;if(rules)css+=`@media(max-width:${bp.max}px){${selectorForNode(node.id)}{${rules}}}`;for(const state of STATE_KEYS){const stateBody=importantStyleText(node.responsive_states?.[bp.id]?.[state]||{});if(stateBody)css+=`@media(max-width:${bp.max}px){${selectorForNode(node.id,`:${state}`)}{${stateBody}}}`;}}return css;}


export async function exportStandaloneHtmlAsync(input, options={}) {
  const normalized=normalizeDocument(input);
  const data=await resolveDataRequirements(normalized,{...(options.runtime||{}),context:options.context||{},queryCache:options.queryCache||options.runtime?.queryCache||null,strictData:Boolean(options.strictData||options.runtime?.strictData)});
  return exportStandaloneHtml(normalized,{...options,context:data.context});
}

export function baseRenderCss(globalStyles={}, documentSettings={}, designSystem={}) {
  const g={primary:'#3151cf',secondary:'#151c31',accent:'#6d72ef',background:'#fff',text:'#1d273a',heading_font:'Inter',body_font:'Inter',radius:16,button_radius:12,content_width:1180,...globalStyles};
  const variables=Object.entries(designSystem?.variables||{}).map(([key,value])=>`--upb-${String(key).replace(/[^a-z0-9_-]/gi,'-')}:${sanitizeStyleValue(value)}`).filter(Boolean).join(';');
  return `
.upb-page{--upb-primary:${sanitizeStyleValue(g.primary)};--upb-secondary:${sanitizeStyleValue(g.secondary)};--upb-accent:${sanitizeStyleValue(g.accent)};--upb-bg:${sanitizeStyleValue(g.background)};--upb-text:${sanitizeStyleValue(g.text)};--upb-radius:${Number(g.radius)||16}px;--upb-button-radius:${Number(g.button_radius)||12}px;--upb-content-width:${Number(documentSettings.content_width||g.content_width)||1180}px;--upb-heading:${sanitizeStyleValue(g.heading_font)};--upb-body:${sanitizeStyleValue(g.body_font)};${variables}}
.upb-page,.upb-page *{box-sizing:border-box}.upb-page{min-height:100%;background:var(--upb-bg);color:var(--upb-text);font-family:var(--upb-body),system-ui,sans-serif;overflow-x:hidden}.upb-node{width:min(calc(100% - 32px),var(--upb-content-width));margin:0 auto;padding:clamp(28px,5vw,72px) 0}.upb-node h1,.upb-node h2,.upb-node h3,.upb-node h4,.upb-node h5,.upb-node h6{font-family:var(--upb-heading),system-ui,sans-serif;margin:0 0 .55em;line-height:1.05}.upb-node h1{font-size:clamp(42px,7vw,88px)}.upb-node h2{font-size:clamp(28px,4vw,48px)}.upb-node p{line-height:1.65}.upb-container,.upb-grid{padding:20px}.upb-container>.upb-node,.upb-grid>.upb-node,.upb-loop-item>.upb-node,.upb-overlay-body>.upb-node{width:100%;margin:0;padding:0}.upb-hero{width:100%;max-width:none;padding:clamp(54px,8vw,110px) max(20px,calc((100% - var(--upb-content-width))/2));display:grid;grid-template-columns:minmax(0,1.1fr) minmax(280px,.9fr);align-items:center;gap:48px;background:var(--upb-secondary);color:#fff}.upb-hero figure{margin:0}.upb-hero img,.upb-image img,.upb-logo img,.upb-gallery img,.upb-carousel img{display:block;width:100%;height:auto;border-radius:var(--upb-radius)}.upb-eyebrow{text-transform:uppercase;letter-spacing:.12em;font-weight:650;font-size:.75rem;color:var(--upb-accent)}.upb-btn{display:inline-flex;align-items:center;justify-content:center;min-height:44px;padding:10px 20px;border:0;border-radius:var(--upb-button-radius);background:var(--upb-primary);color:#fff;text-decoration:none;font-weight:650;cursor:pointer}.upb-btn-secondary{background:var(--upb-secondary)}.upb-gallery,.upb-cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px}.upb-gallery figure{margin:0}.upb-card,.upb-dynamic,.upb-empty,.upb-price,.upb-alert{padding:20px;border:1px solid color-mix(in srgb,var(--upb-text) 14%,transparent);border-radius:var(--upb-radius);background:color-mix(in srgb,var(--upb-bg) 97%,var(--upb-text))}.upb-card a{color:inherit;text-decoration:none}.upb-icon{display:inline-grid;place-items:center;font-size:2rem;text-decoration:none}.upb-icon-box{text-align:center}.upb-contact a,.upb-social a{margin-right:14px}.upb-faq details,.upb-accordion details,details{padding:14px 0;border-bottom:1px solid color-mix(in srgb,var(--upb-text) 16%,transparent)}.upb-footer{text-align:center;padding:28px}.upb-divider{width:min(calc(100% - 32px),var(--upb-content-width));margin:0 auto}.upb-divider hr{border:0;border-top:1px solid color-mix(in srgb,var(--upb-text) 18%,transparent)}.upb-list{display:grid;gap:8px}.upb-counter,.upb-countdown{display:block;font-size:clamp(38px,6vw,72px);font-family:var(--upb-heading);line-height:1}.upb-progress>div{display:flex;justify-content:space-between;gap:12px}.upb-progress progress{width:100%;height:14px;accent-color:var(--upb-primary)}.upb-rating>span{color:#f59e0b;font-size:1.5rem;letter-spacing:.08em}.upb-price-value{display:flex;align-items:end;gap:6px}.upb-price-value strong{font-size:2.5rem}.upb-price ul{padding-left:20px}.upb-tabs .upb-tab-list{display:flex;gap:6px;flex-wrap:wrap;border-bottom:1px solid color-mix(in srgb,var(--upb-text) 16%,transparent)}.upb-tabs [role=tab]{border:0;background:transparent;padding:12px 14px;font-weight:650;cursor:pointer}.upb-tabs [aria-selected=true]{color:var(--upb-primary);box-shadow:inset 0 -2px var(--upb-primary)}.upb-tabs [role=tabpanel]{padding:18px 0}.upb-alert.kind-success{border-color:#22c55e}.upb-alert.kind-warning{border-color:#f59e0b}.upb-alert.kind-danger{border-color:#ef4444}.upb-nav{display:flex;align-items:center;justify-content:space-between;gap:24px}.upb-nav>div{display:flex;gap:18px;flex-wrap:wrap}.upb-nav a,.upb-breadcrumbs a{color:inherit;text-decoration:none}.upb-breadcrumbs{display:flex;gap:8px;flex-wrap:wrap}.upb-carousel-head{display:flex;justify-content:space-between;align-items:center;gap:12px}.upb-carousel-head button{width:40px;height:40px;border-radius:50%;border:1px solid color-mix(in srgb,var(--upb-text) 18%,transparent);background:var(--upb-bg);cursor:pointer;font-size:1.5rem}.upb-carousel-track{display:grid;grid-auto-flow:column;grid-auto-columns:minmax(260px,42%);gap:16px;overflow:auto;scroll-snap-type:x mandatory;padding-bottom:8px}.upb-carousel-track figure{scroll-snap-align:start;margin:0}.upb-form{display:grid;gap:18px}.upb-form-fields{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.upb-form label{display:grid;gap:6px;font-weight:600}.upb-form label:has(textarea),.upb-form .upb-check{grid-column:1/-1}.upb-form input,.upb-form textarea,.upb-form select{width:100%;min-height:44px;padding:10px 12px;border:1px solid color-mix(in srgb,var(--upb-text) 20%,transparent);border-radius:calc(var(--upb-radius)*.55);background:var(--upb-bg);color:var(--upb-text);font:inherit}.upb-form textarea{min-height:120px}.upb-check{display:flex!important;align-items:center}.upb-check input{width:auto;min-height:auto}.upb-overlay{width:min(calc(100% - 28px),var(--upb-overlay-width,560px));border:0;border-radius:var(--upb-radius);padding:0;color:var(--upb-text);background:var(--upb-bg);box-shadow:0 30px 100px #0006}.upb-overlay::backdrop{background:#020617a8;backdrop-filter:blur(4px)}.upb-overlay-body{padding:28px}.upb-overlay-close{position:absolute;top:10px;right:10px;width:38px;height:38px;border:0;border-radius:50%;background:#0001;cursor:pointer;font-size:1.5rem}.upb-offcanvas{height:100dvh;max-height:100dvh;margin:0;border-radius:0}.upb-offcanvas.side-right{margin-left:auto}.upb-offcanvas.side-left{margin-right:auto}.upb-embed{width:100%;min-height:480px;border:0;border-radius:var(--upb-radius)}.upb-motion{animation-duration:var(--upb-motion-duration,600ms);animation-delay:var(--upb-motion-delay,0ms);animation-fill-mode:both}.upb-motion-fade{animation-name:upbFade}.upb-motion-slide-up{animation-name:upbSlideUp}.upb-motion-slide-left{animation-name:upbSlideLeft}.upb-motion-zoom{animation-name:upbZoom}@keyframes upbFade{from{opacity:0}to{opacity:1}}@keyframes upbSlideUp{from{opacity:0;transform:translateY(30px)}to{opacity:1;transform:none}}@keyframes upbSlideLeft{from{opacity:0;transform:translateX(30px)}to{opacity:1;transform:none}}@keyframes upbZoom{from{opacity:0;transform:scale(.92)}to{opacity:1;transform:none}}.upb-lightbox{max-width:min(94vw,1200px);border:0;padding:44px 12px 12px;background:#05070b}.upb-lightbox img{max-width:90vw;max-height:84vh}.upb-lightbox button{position:absolute;right:8px;top:6px;color:#fff;background:transparent;border:0;font-size:2rem;cursor:pointer}.upb-nested-editor{padding:16px;border:1px dashed color-mix(in srgb,var(--upb-primary) 45%,transparent);border-radius:var(--upb-radius)}.upb-nested-tabs.orientation-vertical{display:grid;grid-template-columns:minmax(160px,260px) 1fr;gap:20px}.upb-nested-tabs.orientation-vertical .upb-tab-list{display:grid;align-content:start;border-bottom:0;border-right:1px solid color-mix(in srgb,var(--upb-text) 16%,transparent)}.upb-accordion-panel{padding:16px 0}.upb-mega-menu{position:relative;display:flex;align-items:center;justify-content:space-between;gap:28px}.upb-menu-items{display:flex;align-items:center;gap:10px}.upb-menu-item>a,.upb-menu-item>button{padding:10px 12px;border:0;background:transparent;color:inherit;text-decoration:none;font:inherit;font-weight:600;cursor:pointer}.upb-mega-panel{position:absolute;z-index:50;left:0;right:0;top:calc(100% + 8px);padding:24px;border:1px solid color-mix(in srgb,var(--upb-text) 14%,transparent);border-radius:var(--upb-radius);background:var(--upb-bg);box-shadow:0 24px 70px #0002}.upb-floating-bar{position:relative;width:100%;max-width:none!important;padding:12px max(16px,calc((100% - var(--upb-content-width))/2));background:var(--upb-secondary);color:#fff;z-index:80}.upb-floating-bar.position-top{top:0}.upb-floating-bar.position-bottom{bottom:0}.upb-floating-bar[data-upb-sticky=true]{position:sticky}.upb-floating-bar>[data-upb-dismiss],.upb-floating-bar>button{float:right;border:0;background:transparent;color:inherit;font-size:1.25rem;cursor:pointer}.upb-toc{padding:18px;border:1px solid color-mix(in srgb,var(--upb-text) 14%,transparent);border-radius:var(--upb-radius)}.upb-toc ul,.upb-toc ol{margin:12px 0 0;padding-left:22px}.upb-toc a{color:inherit;text-decoration:none}.upb-search{display:flex;gap:10px}.upb-search input{flex:1;min-height:44px;padding:10px 12px;border:1px solid color-mix(in srgb,var(--upb-text) 20%,transparent);border-radius:var(--upb-button-radius);font:inherit}.upb-share>div{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}.upb-share-btn{display:inline-flex;padding:8px 12px;border:1px solid color-mix(in srgb,var(--upb-text) 16%,transparent);border-radius:999px;color:inherit;text-decoration:none}.upb-hotspot{position:relative}.upb-hotspot>img{width:100%;height:auto;border-radius:var(--upb-radius)}.upb-hotspot-layer{position:absolute;inset:0}.upb-hotspot-point{position:absolute;transform:translate(-50%,-50%);width:34px;height:34px;border-radius:50%;border:2px solid #fff;background:var(--upb-primary);color:#fff;cursor:pointer}.upb-hotspot-tip{display:none;position:absolute;left:50%;bottom:calc(100% + 10px);min-width:180px;max-width:260px;padding:10px;border-radius:10px;background:#111827;color:#fff;transform:translateX(-50%);text-align:left;box-shadow:0 12px 32px #0004}.upb-hotspot-tip small{display:block;margin-top:4px;color:#d1d5db}.upb-hotspot-point:hover .upb-hotspot-tip,.upb-hotspot-point:focus .upb-hotspot-tip{display:block}.upb-flip{perspective:1000px;min-height:260px}.upb-flip-inner{position:relative;min-height:260px;transition:transform .55s;transform-style:preserve-3d}.upb-flip:hover .upb-flip-inner,.upb-flip:focus .upb-flip-inner{transform:rotateY(180deg)}.upb-flip-face{position:absolute;inset:0;padding:28px;border-radius:var(--upb-radius);backface-visibility:hidden;background:color-mix(in srgb,var(--upb-bg) 96%,var(--upb-text));border:1px solid color-mix(in srgb,var(--upb-text) 14%,transparent)}.upb-flip-face.back{transform:rotateY(180deg);background:var(--upb-secondary);color:#fff}.upb-slides{position:relative;overflow:hidden;border-radius:var(--upb-radius)}.upb-slide{min-height:420px;padding:60px;display:grid;align-items:end;background-size:cover;background-position:center;background-color:var(--upb-secondary);color:#fff}.upb-slide>div{max-width:700px}.upb-slide-nav{position:absolute;right:16px;bottom:16px;display:flex;gap:8px}.upb-slide-nav button{width:42px;height:42px;border-radius:50%;border:0;background:#fff;color:#111827;font-size:1.5rem;cursor:pointer}.upb-lottie{display:grid;place-items:center;min-height:180px;border:1px dashed color-mix(in srgb,var(--upb-text) 18%,transparent);border-radius:var(--upb-radius)}.upb-cookie{display:flex;align-items:center;justify-content:space-between;gap:20px;padding:18px;border:1px solid color-mix(in srgb,var(--upb-text) 14%,transparent);border-radius:var(--upb-radius);background:var(--upb-bg);box-shadow:0 18px 50px #0002}.upb-cookie>div{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.upb-code{overflow:auto;padding:18px;border-radius:var(--upb-radius);background:#0b1020;color:#e5e7eb;font-family:ui-monospace,SFMono-Regular,Menlo,monospace}.upb-anchor{display:block;position:relative;top:-80px;visibility:hidden}.upb-fieldset{display:grid;gap:8px;border:1px solid color-mix(in srgb,var(--upb-text) 14%,transparent);border-radius:calc(var(--upb-radius)*.65);padding:12px}.upb-fieldset legend{font-weight:600}.upb-form input[type=file]{padding:8px}.upb-form input[type=color]{padding:4px;height:44px}.upb-form input[type=range]{padding:0}.upb-form-step{display:grid;gap:16px}.upb-form-navigation{display:flex;justify-content:space-between;gap:12px;margin-top:14px}.upb-form-step[hidden]{display:none!important}.upb-html_surface,.upb-html-surface{width:100%;max-width:none;padding:0}.upb-html-surface-frame{width:100%;min-height:760px;background:#fff}.upb-html-surface-frame iframe{display:block;width:100%;height:760px;border:0;background:#fff}.upb-html-surface-editor iframe{pointer-events:none}.upb-page [hidden]{display:none!important}
@media(max-width:1024px){.upb-hero{grid-template-columns:1fr}.upb-gallery,.upb-cards{grid-template-columns:repeat(2,minmax(0,1fr))}.upb-form-fields{grid-template-columns:1fr}}
@media(max-width:680px){.upb-node{width:min(calc(100% - 24px),var(--upb-content-width));padding:36px 0}.upb-hero{padding:54px 20px}.upb-gallery,.upb-cards,.upb-grid{grid-template-columns:1fr!important}.upb-carousel-track{grid-auto-columns:86%}.upb-nav{align-items:flex-start;flex-direction:column}.upb-nav>div{flex-direction:column}.upb-overlay-body{padding:22px 16px}}
`;
}

function generatedCss(doc) {
  let css = '';
  for (const name of Object.keys(doc.design_system?.classes || {})) css += classCss(doc,name);
  for (const node of Object.values(doc.builder.nodes || {})) css += nodeResponsiveCss(doc,node);
  const custom=sanitizeStylesheet(doc.settings?.custom_css||''); if(custom)css+=`\n/* custom css */\n${custom}`;
  return css;
}

export function renderDocument(input, { device='desktop', context={}, responsive=true, locale=null } = {}) {
  const normalized=normalizeDocument(input); const doc=locale?localizeDocument(normalized,locale):normalized;
  if(isHtmlDocument(doc)) {
    const source=String(doc.html?.document||'');
    const sandbox=context.editor
      ? 'allow-forms allow-same-origin'
      : (context.allowImportedHtmlScripts ? 'allow-forms allow-scripts allow-modals allow-popups allow-downloads' : 'allow-forms');
    const htmlSource=context.editor ? editorImportedHtmlSource(source,context) : source;
    const html=`<main class="upb-page upb-html-document-page" data-upb-device="${escapeHtml(device)}" data-upb-document-mode="HTML"><div class="upb-html-document-frame${context.editor?' editor':''}"><iframe data-upb-html-document-frame data-upb-html-surface-frame title="${escapeHtml(doc.title||doc.html?.template_key||'Página HTML')}" sandbox="${sandbox}" srcdoc="${escapeHtml(htmlSource)}"></iframe></div></main>`;
    const css=`:host{display:block}.upb-page.upb-html-document-page{display:block;min-height:100%;width:100%;background:transparent}.upb-html-document-frame{width:100%;min-height:100dvh}.upb-html-document-frame iframe{display:block;width:100%;min-height:100dvh;border:0;background:#fff}.upb-html-document-frame.editor iframe{min-height:760px}`;
    return {html,css,document:doc};
  }
  const renderContext={...context}; let html=doc.builder.root_ids.map(id=>renderNode(doc,getNode(doc,id),device,renderContext)).join('');
  const hasBooking=Object.values(doc.builder.nodes).some(node=>['booking','calendar'].includes(node.type));
  if(context.ensureBooking&&!hasBooking)html+=`<section id="agendamento" class="upb-node upb-booking"><span class="upb-eyebrow">Agenda</span><h2>Agende seu horário</h2><div class="upb-dynamic" data-upb-dynamic="booking">${context.bookingHtml||'O componente de agendamento é injetado aqui pelo projeto hospedeiro.'}</div></section>`;
  const css=fontFaceCss(doc.project?.assets||{})+baseRenderCss(doc.global_styles,doc.settings,doc.design_system)+(responsive?generatedCss(doc):'');
  return { html:`<main class="upb-page" data-upb-device="${escapeHtml(device)}">${html}</main>`, css, document:doc };
}

export async function renderDocumentAsync(input, { device='desktop', context={}, responsive=true, locale=null, queryCache=null, strictData=false, runtime={} } = {}) {
  const normalized=normalizeDocument(input);
  const data=await resolveDataRequirements(normalized,{...runtime,context,queryCache:queryCache||runtime.queryCache||null,strictData:Boolean(strictData||runtime.strictData)});
  const rendered=renderDocument(normalized,{device,context:data.context,responsive,locale});
  return {...rendered,data_errors:data.errors,data_requirements:data.requirements};
}

export function exportStandaloneHtml(input, options={}) {
  const normalized=normalizeDocument(input);
  if(isHtmlDocument(normalized)) return String(normalized.html?.document||'');
  const {html,css,document:doc}=renderDocument(normalized,{device:'desktop',context:options.context||{},responsive:true,locale:options.locale||null});
  const title=escapeHtml(doc.seo?.title||doc.title||'Página'), description=escapeHtml(doc.seo?.description||''), canonical=safeUrl(doc.seo?.canonical,'');
  const og=doc.seo?.open_graph||{},twitter=doc.seo?.twitter||{},structured=Array.isArray(doc.seo?.structured_data)?doc.seo.structured_data:[];
  const headCode=renderCustomCode(doc.project?.custom_code||[],{placement:'head',context:options.context||{},allowTrustedCode:Boolean(options.allowTrustedCode)});
  const bodyStart=renderCustomCode(doc.project?.custom_code||[],{placement:'body-start',context:options.context||{},allowTrustedCode:Boolean(options.allowTrustedCode)});
  const bodyEnd=renderCustomCode(doc.project?.custom_code||[],{placement:'body-end',context:options.context||{},allowTrustedCode:Boolean(options.allowTrustedCode)});
  const metaOg=Object.entries(og).map(([k,v])=>`<meta property="og:${escapeHtml(k)}" content="${escapeHtml(v)}">`).join('');
  const metaTw=Object.entries(twitter).map(([k,v])=>`<meta name="twitter:${escapeHtml(k)}" content="${escapeHtml(v)}">`).join('');
  const jsonLd=structured.map(item=>`<script type="application/ld+json">${JSON.stringify(item).replace(/<\/script/gi,'<\\/script')}</script>`).join('');
  return `<!doctype html><html lang="${escapeHtml(doc.settings?.language||'pt-BR')}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${title}</title><meta name="description" content="${description}"><meta name="robots" content="${escapeHtml(doc.seo?.robots||'index,follow')}">${canonical?`<link rel="canonical" href="${escapeHtml(canonical)}">`:''}${metaOg}${metaTw}${jsonLd}<style>${css}</style>${headCode}</head><body>${bodyStart}${html}<script>${standaloneRuntimeSource().replace(/<\/script/gi,'<\\/script')}</script>${bodyEnd}</body></html>`;
}
