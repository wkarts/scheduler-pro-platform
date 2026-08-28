import { executeActions } from './actions.js';

function parseJson(value, fallback) { try { return JSON.parse(value || ''); } catch { return fallback; } }

export function hydratePage(root, { actionRuntime = {}, onFormSubmit = null } = {}) {
  if (!root || root.__upbHydrated) return () => {};
  root.__upbHydrated = true;
  const cleanups = [];
  const queryAll = selector => Array.from(root.querySelectorAll(selector));

  const openOverlay = name => {
    const overlay = root.querySelector(`[data-upb-overlay-name="${globalThis.CSS?.escape ? CSS.escape(name) : name}"]`);
    if (!overlay) return;
    if (typeof overlay.showModal === 'function') overlay.showModal(); else overlay.setAttribute('open', '');
    overlay.dispatchEvent(new CustomEvent('upb-overlay-open', { bubbles: true, composed: true, detail: { name } }));
  };
  const closeOverlay = overlay => { if (!overlay) return; if (typeof overlay.close === 'function') overlay.close(); else overlay.removeAttribute('open'); };
  const closeOverlayByName = name => closeOverlay(root.querySelector(`[data-upb-overlay-name="${globalThis.CSS?.escape ? CSS.escape(name) : name}"]`));
  if (actionRuntime && typeof actionRuntime === 'object') { actionRuntime.openOverlay = openOverlay; actionRuntime.closeOverlay = closeOverlayByName; actionRuntime.eventTarget ||= root; }

  const click = event => {
    const open = event.target.closest?.('[data-upb-open]');
    if (open) { event.preventDefault(); openOverlay(open.dataset.upbOpen); return; }
    const close = event.target.closest?.('[data-upb-close]');
    if (close) { event.preventDefault(); closeOverlay(close.closest('[data-upb-overlay]')); return; }
    const tab = event.target.closest?.('[data-upb-tab]');
    if (tab) {
      event.preventDefault(); const tabs = tab.closest('[data-upb-tabs]'); const index = Number(tab.dataset.upbTab || 0);
      tabs?.querySelectorAll('[data-upb-tab]').forEach((el, i) => el.setAttribute('aria-selected', i === index ? 'true' : 'false'));
      tabs?.querySelectorAll('[data-upb-tab-panel]').forEach((el, i) => { el.hidden = i !== index; });
      return;
    }
    const formNext = event.target.closest?.('[data-upb-form-next]');
    const formPrev = event.target.closest?.('[data-upb-form-prev]');
    if (formNext || formPrev) {
      event.preventDefault(); const form=(formNext||formPrev).closest('form[data-upb-form]'); const steps=Array.from(form?.querySelectorAll('[data-upb-form-step]')||[]); const current=Math.max(0,steps.findIndex(step=>!step.hidden));
      if(formNext){const controls=Array.from(steps[current]?.querySelectorAll('input,select,textarea')||[]).filter(control=>!control.disabled);if(controls.some(control=>typeof control.reportValidity==='function'&&!control.reportValidity()))return;}
      const target=Math.max(0,Math.min(steps.length-1,current+(formNext?1:-1)));steps.forEach((step,index)=>{step.hidden=index!==target;});steps[target]?.querySelector('input,select,textarea,button')?.focus?.();return;
    }
    const next = event.target.closest?.('[data-upb-carousel-next]');
    const prev = event.target.closest?.('[data-upb-carousel-prev]');
    if (next || prev) {
      const carousel = (next || prev).closest('[data-upb-carousel]'); const track = carousel?.querySelector('[data-upb-carousel-track]');
      if (track) track.scrollBy({ left: (next ? 1 : -1) * Math.max(240, track.clientWidth * 0.85), behavior: 'smooth' });
      return;
    }
    const menuToggle = event.target.closest?.('[data-upb-menu-toggle]');
    if (menuToggle) {
      event.preventDefault(); const menu=menuToggle.closest('[data-upb-mega-menu]'); const index=menuToggle.dataset.upbMenuToggle; const panel=menu?.querySelector(`[data-upb-menu-panel="${index}"]`); const expanded=menuToggle.getAttribute('aria-expanded')==='true';
      menu?.querySelectorAll('[data-upb-menu-panel]').forEach(el=>{if(el!==panel)el.hidden=true;}); menu?.querySelectorAll('[data-upb-menu-toggle]').forEach(el=>{if(el!==menuToggle)el.setAttribute('aria-expanded','false');}); if(panel)panel.hidden=expanded; menuToggle.setAttribute('aria-expanded',expanded?'false':'true'); return;
    }
    const dismiss = event.target.closest?.('[data-upb-dismiss]'); if(dismiss){event.preventDefault();dismiss.closest('[data-upb-floating-bar]')?.remove();return;}
    const slideNext=event.target.closest?.('[data-upb-slide-next]'),slidePrev=event.target.closest?.('[data-upb-slide-prev]');
    if(slideNext||slidePrev){event.preventDefault();const slides=(slideNext||slidePrev).closest('[data-upb-slides]');const rows=Array.from(slides?.querySelectorAll('[data-upb-slide]')||[]);const current=Math.max(0,rows.findIndex(row=>!row.hidden));const next=(current+(slideNext?1:-1)+rows.length)%rows.length;rows.forEach((row,i)=>row.hidden=i!==next);return;}
    const cookie=event.target.closest?.('[data-upb-cookie]'); if(cookie){event.preventDefault();const box=cookie.closest('[data-upb-cookie-consent]');const choice=cookie.dataset.upbCookie;try{localStorage.setItem('argws_cookie_consent',choice);}catch{}box?.remove();root.dispatchEvent(new CustomEvent('upb-cookie-consent',{detail:{choice},bubbles:true,composed:true}));return;}
    const lightbox = event.target.closest?.('[data-upb-lightbox]');
    if (lightbox) {
      event.preventDefault(); const source = lightbox.getAttribute('href'); if (!source) return;
      const dialog = document.createElement('dialog'); dialog.className = 'upb-lightbox'; dialog.innerHTML = `<button type="button" aria-label="Fechar">×</button><img alt="" src="${source.replace(/"/g, '&quot;')}">`;
      document.body.appendChild(dialog); dialog.querySelector('button').onclick = () => dialog.close(); dialog.addEventListener('close', () => dialog.remove(), { once: true }); dialog.showModal();
    }
  };
  root.addEventListener('click', click); cleanups.push(() => root.removeEventListener('click', click));

  for (const host of queryAll('[data-upb-interactions]')) {
    const descriptors=parseJson(host.dataset.upbInteractions,[]); if(!Array.isArray(descriptors))continue;
    for(const descriptor of descriptors){const eventName=String(descriptor?.event||'').toLowerCase();if(!['click','dblclick','mouseenter','mouseleave','focus','blur','change','input'].includes(eventName))continue;const handler=event=>{const target=event.target;const payload={node_id:host.dataset.upbNode||null,event:eventName,value:target?.value??null,checked:target?.checked??null,dataset:{...(target?.dataset||{})}};void executeActions(Array.isArray(descriptor.actions)?descriptor.actions:[],payload,actionRuntime).catch(error=>host.dispatchEvent(new CustomEvent('upb-interaction-error',{detail:{error,message:error?.message||String(error)},bubbles:true,composed:true})));};host.addEventListener(eventName,handler);cleanups.push(()=>host.removeEventListener(eventName,handler));}
  }

  for(const toc of queryAll('[data-upb-toc]')){const levels=(toc.dataset.levels||'h2,h3').split(',').map(v=>v.trim()).filter(v=>/^h[1-6]$/i.test(v));const headings=levels.length?Array.from(root.querySelectorAll(levels.join(','))).filter(el=>!toc.contains(el)):[];const list=toc.querySelector('[data-upb-toc-list]');if(list){headings.forEach((heading,index)=>{if(!heading.id)heading.id=`upb-heading-${index+1}`;const li=document.createElement('li');const a=document.createElement('a');a.href=`#${heading.id}`;a.textContent=heading.textContent?.trim()||`Seção ${index+1}`;li.appendChild(a);list.appendChild(li);});}}
  for(const accordion of queryAll('[data-upb-accordion][data-multiple="false"]')){const handler=event=>{const detail=event.target;if(!(detail instanceof HTMLDetailsElement)||!detail.open)return;accordion.querySelectorAll('details[open]').forEach(row=>{if(row!==detail)row.open=false;});};accordion.addEventListener('toggle',handler,true);cleanups.push(()=>accordion.removeEventListener('toggle',handler,true));}
  for(const menu of queryAll('[data-upb-mega-menu][data-trigger="hover"]')){for(const item of menu.querySelectorAll('.upb-menu-item')){const button=item.querySelector('[data-upb-menu-toggle]'),panel=item.querySelector('[data-upb-menu-panel]');if(!button||!panel)continue;const enter=()=>{panel.hidden=false;button.setAttribute('aria-expanded','true')},leave=()=>{panel.hidden=true;button.setAttribute('aria-expanded','false')};item.addEventListener('mouseenter',enter);item.addEventListener('mouseleave',leave);cleanups.push(()=>{item.removeEventListener('mouseenter',enter);item.removeEventListener('mouseleave',leave);});}}
  for(const cookie of queryAll('[data-upb-cookie-consent]')){try{if(localStorage.getItem('argws_cookie_consent'))cookie.remove();}catch{}}
  for(const lottieHost of queryAll('[data-upb-lottie]')){const engine=actionRuntime?.lottie||globalThis.lottie;if(engine?.loadAnimation){const animation=engine.loadAnimation({container:lottieHost,renderer:'svg',loop:lottieHost.dataset.loop==='true',autoplay:lottieHost.dataset.autoplay==='true',path:lottieHost.dataset.url});cleanups.push(()=>animation?.destroy?.());}else lottieHost.dispatchEvent(new CustomEvent('upb-lottie-required',{detail:{url:lottieHost.dataset.url},bubbles:true,composed:true}));}

  for (const overlay of queryAll('[data-upb-overlay]')) {
    if (overlay.dataset.trigger === 'delay') {
      const timer = setTimeout(() => openOverlay(overlay.dataset.upbOverlayName), Math.max(0, Number(overlay.dataset.delay || 0)));
      cleanups.push(() => clearTimeout(timer));
    }
    if (overlay.dataset.trigger === 'scroll') {
      const handler = () => {
        const doc = document.documentElement; const denominator = Math.max(1, doc.scrollHeight - innerHeight); const pct = scrollY / denominator * 100;
        if (pct >= Number(overlay.dataset.scrollPercent || 50)) { openOverlay(overlay.dataset.upbOverlayName); removeEventListener('scroll', handler); }
      };
      addEventListener('scroll', handler, { passive: true }); cleanups.push(() => removeEventListener('scroll', handler));
    }
    if (overlay.dataset.trigger === 'exit') {
      const handler = event => { if (event.clientY <= 0) { openOverlay(overlay.dataset.upbOverlayName); document.removeEventListener('mouseout', handler); } };
      document.addEventListener('mouseout', handler); cleanups.push(() => document.removeEventListener('mouseout', handler));
    }
  }

  for (const counter of queryAll('[data-upb-counter]')) {
    const start = Number(counter.dataset.start || 0), end = Number(counter.dataset.end || 0), duration = Math.max(100, Number(counter.dataset.duration || 1200)); const suffix = counter.dataset.suffix || '';
    let started = false; const run = () => { if (started) return; started = true; const t0 = performance.now(); const step = now => { const progress = Math.min(1, (now - t0) / duration); counter.textContent = `${Math.round(start + (end - start) * progress)}${suffix}`; if (progress < 1) requestAnimationFrame(step); }; requestAnimationFrame(step); };
    if ('IntersectionObserver' in globalThis) { const observer = new IntersectionObserver(entries => { if (entries.some(e => e.isIntersecting)) { run(); observer.disconnect(); } }); observer.observe(counter); cleanups.push(() => observer.disconnect()); } else run();
  }

  for (const countdown of queryAll('[data-upb-countdown]')) {
    const target = Date.parse(countdown.dataset.target || ''); const expired = countdown.dataset.expiredText || 'Encerrado';
    if (!Number.isFinite(target)) continue;
    const update = () => { const diff = target - Date.now(); if (diff <= 0) { countdown.textContent = expired; return false; } const days = Math.floor(diff/86400000), hours=Math.floor(diff/3600000)%24, minutes=Math.floor(diff/60000)%60, seconds=Math.floor(diff/1000)%60; countdown.textContent=`${days}d ${String(hours).padStart(2,'0')}h ${String(minutes).padStart(2,'0')}m ${String(seconds).padStart(2,'0')}s`; return true; };
    update(); const timer = setInterval(() => { if (!update()) clearInterval(timer); }, 1000); cleanups.push(() => clearInterval(timer));
  }

  for (const carousel of queryAll('[data-upb-carousel][data-autoplay="true"]')) {
    const interval = Math.max(1000, Number(carousel.dataset.interval || 5000)); const timer = setInterval(() => { const track = carousel.querySelector('[data-upb-carousel-track]'); track?.scrollBy({ left: Math.max(240, track.clientWidth * 0.85), behavior:'smooth' }); if (track && track.scrollLeft + track.clientWidth >= track.scrollWidth - 4) track.scrollTo({left:0,behavior:'smooth'}); }, interval); cleanups.push(() => clearInterval(timer));
  }

  for(const slides of queryAll('[data-upb-slides][data-autoplay="true"]')){const rows=Array.from(slides.querySelectorAll('[data-upb-slide]'));if(rows.length>1){const timer=setInterval(()=>{const current=Math.max(0,rows.findIndex(row=>!row.hidden));const next=(current+1)%rows.length;rows.forEach((row,i)=>row.hidden=i!==next);},Math.max(1000,Number(slides.dataset.interval||5000)));cleanups.push(()=>clearInterval(timer));}}

  for (const form of queryAll('form[data-upb-form]')) {
    const submit = async event => {
      event.preventDefault(); const data = Object.fromEntries(new FormData(form).entries()); const actions = parseJson(form.dataset.actions, ['event']).map(type => typeof type === 'string' ? { type } : type); const detail = { values: data, form, actions };
      form.dispatchEvent(new CustomEvent('upb-form-submit', { detail, bubbles: true, composed: true }));
      try {
        if (typeof onFormSubmit === 'function') await onFormSubmit(detail);
        await executeActions(actions.filter(action => action.type !== 'event'), data, actionRuntime);
        const status = form.querySelector('[data-upb-form-status]'); if (status) { status.textContent = form.dataset.successMessage || 'Enviado com sucesso.'; status.dataset.state = 'success'; }
        form.reset();
      } catch (error) {
        const status = form.querySelector('[data-upb-form-status]'); if (status) { status.textContent = error?.message || 'Não foi possível enviar.'; status.dataset.state = 'error'; }
      }
    };
    form.addEventListener('submit', submit); cleanups.push(() => form.removeEventListener('submit', submit));
  }

  return () => { for (const cleanup of cleanups.splice(0)) cleanup(); root.__upbHydrated = false; };
}

export function standaloneRuntimeSource() {
  return `(()=>{
const root=document.querySelector('.upb-page');if(!root)return;const q=s=>Array.from(root.querySelectorAll(s));
const open=n=>{const e=root.querySelector('[data-upb-overlay-name="'+CSS.escape(n)+'"]');if(e){e.showModal?e.showModal():e.setAttribute('open','')}};
const showSlide=(host,delta)=>{const rows=Array.from(host.querySelectorAll('[data-upb-slide]'));if(!rows.length)return;const cur=Math.max(0,rows.findIndex(x=>!x.hidden)),next=(cur+delta+rows.length)%rows.length;rows.forEach((x,i)=>x.hidden=i!==next)};
root.addEventListener('click',e=>{const ih=e.target.closest('[data-upb-interactions]');if(ih){let rows=[];try{rows=JSON.parse(ih.dataset.upbInteractions||'[]')}catch{}for(const row of rows.filter(r=>(r.event||'').toLowerCase()==='click'))for(const a of (row.actions||[])){if(a.type==='open_popup')open(a.name||a.target||'');else if(a.type==='close_popup'){const d=ih.closest('[data-upb-overlay]');d?.close?d.close():d?.removeAttribute('open')}else if(a.type==='redirect'&&a.url){location.assign(a.url)}}}let x=e.target.closest('[data-upb-open]');if(x){e.preventDefault();open(x.dataset.upbOpen);return}x=e.target.closest('[data-upb-close]');if(x){e.preventDefault();const d=x.closest('[data-upb-overlay]');d?.close?d.close():d?.removeAttribute('open');return}x=e.target.closest('[data-upb-tab]');if(x){e.preventDefault();const t=x.closest('[data-upb-tabs]'),i=+x.dataset.upbTab;t?.querySelectorAll('[data-upb-tab]').forEach((a,j)=>a.setAttribute('aria-selected',j===i?'true':'false'));t?.querySelectorAll('[data-upb-tab-panel]').forEach((a,j)=>a.hidden=j!==i);return}x=e.target.closest('[data-upb-form-next],[data-upb-form-prev]');if(x){e.preventDefault();const f=x.closest('form[data-upb-form]'),r=Array.from(f?.querySelectorAll('[data-upb-form-step]')||[]),c=Math.max(0,r.findIndex(a=>!a.hidden)),dir=x.hasAttribute('data-upb-form-next')?1:-1;if(dir>0){const controls=Array.from(r[c]?.querySelectorAll('input,select,textarea')||[]).filter(a=>!a.disabled);if(controls.some(a=>a.reportValidity&&!a.reportValidity()))return}const n=Math.max(0,Math.min(r.length-1,c+dir));r.forEach((a,i)=>a.hidden=i!==n);r[n]?.querySelector('input,select,textarea,button')?.focus?.();return}x=e.target.closest('[data-upb-menu-toggle]');if(x){e.preventDefault();const m=x.closest('[data-upb-mega-menu]'),i=x.dataset.upbMenuToggle,p=m?.querySelector('[data-upb-menu-panel="'+i+'"]'),expanded=x.getAttribute('aria-expanded')==='true';m?.querySelectorAll('[data-upb-menu-panel]').forEach(a=>{if(a!==p)a.hidden=true});m?.querySelectorAll('[data-upb-menu-toggle]').forEach(a=>{if(a!==x)a.setAttribute('aria-expanded','false')});if(p)p.hidden=expanded;x.setAttribute('aria-expanded',expanded?'false':'true');return}x=e.target.closest('[data-upb-dismiss]');if(x){x.closest('[data-upb-floating-bar]')?.remove();return}const sn=e.target.closest('[data-upb-slide-next]'),sp=e.target.closest('[data-upb-slide-prev]');if(sn||sp){showSlide((sn||sp).closest('[data-upb-slides]'),sn?1:-1);return}x=e.target.closest('[data-upb-cookie]');if(x){const b=x.closest('[data-upb-cookie-consent]');try{localStorage.setItem('argws_cookie_consent',x.dataset.upbCookie)}catch{}b?.remove();return}const n=e.target.closest('[data-upb-carousel-next]'),p=e.target.closest('[data-upb-carousel-prev]');if(n||p){const tr=(n||p).closest('[data-upb-carousel]')?.querySelector('[data-upb-carousel-track]');tr?.scrollBy({left:(n?1:-1)*Math.max(240,tr.clientWidth*.85),behavior:'smooth'});return}x=e.target.closest('[data-upb-lightbox]');if(x){e.preventDefault();const src=x.getAttribute('href');if(!src)return;const d=document.createElement('dialog');d.className='upb-lightbox';d.innerHTML='<button type="button" aria-label="Fechar">×</button><img alt="" src="'+src.replace(/"/g,'&quot;')+'">';document.body.appendChild(d);d.querySelector('button').onclick=()=>d.close();d.addEventListener('close',()=>d.remove(),{once:true});d.showModal()}});
q('[data-upb-toc]').forEach(t=>{const levels=(t.dataset.levels||'h2,h3').split(',').map(v=>v.trim()).filter(v=>/^h[1-6]$/i.test(v)),list=t.querySelector('[data-upb-toc-list]');if(!list)return;Array.from(root.querySelectorAll(levels.join(','))).filter(h=>!t.contains(h)).forEach((h,i)=>{h.id||=( 'upb-heading-'+(i+1));const li=document.createElement('li'),a=document.createElement('a');a.href='#'+h.id;a.textContent=h.textContent.trim()||('Seção '+(i+1));li.appendChild(a);list.appendChild(li)})});
q('[data-upb-cookie-consent]').forEach(c=>{try{if(localStorage.getItem('argws_cookie_consent'))c.remove()}catch{}});
q('[data-upb-overlay]').forEach(o=>{if(o.dataset.trigger==='delay')setTimeout(()=>open(o.dataset.upbOverlayName),+o.dataset.delay||0);if(o.dataset.trigger==='scroll'){const h=()=>{const d=document.documentElement,p=scrollY/Math.max(1,d.scrollHeight-innerHeight)*100;if(p>=+(o.dataset.scrollPercent||50)){open(o.dataset.upbOverlayName);removeEventListener('scroll',h)}};addEventListener('scroll',h,{passive:true})}if(o.dataset.trigger==='exit'){const h=e=>{if(e.clientY<=0){open(o.dataset.upbOverlayName);document.removeEventListener('mouseout',h)}};document.addEventListener('mouseout',h)}});
q('[data-upb-counter]').forEach(c=>{const a=+c.dataset.start||0,b=+c.dataset.end||0,d=Math.max(100,+c.dataset.duration||1200),s=c.dataset.suffix||'',t=performance.now();const f=n=>{const p=Math.min(1,(n-t)/d);c.textContent=Math.round(a+(b-a)*p)+s;p<1&&requestAnimationFrame(f)};requestAnimationFrame(f)});
q('[data-upb-countdown]').forEach(c=>{const t=Date.parse(c.dataset.target||''),x=c.dataset.expiredText||'Encerrado';if(!Number.isFinite(t))return;const f=()=>{const d=t-Date.now();if(d<=0){c.textContent=x;return false}c.textContent=Math.floor(d/86400000)+'d '+String(Math.floor(d/3600000)%24).padStart(2,'0')+'h '+String(Math.floor(d/60000)%60).padStart(2,'0')+'m '+String(Math.floor(d/1000)%60).padStart(2,'0')+'s';return true};f();const i=setInterval(()=>{if(!f())clearInterval(i)},1000)});
q('[data-upb-carousel][data-autoplay="true"]').forEach(c=>setInterval(()=>{const tr=c.querySelector('[data-upb-carousel-track]');if(!tr)return;tr.scrollBy({left:Math.max(240,tr.clientWidth*.85),behavior:'smooth'});if(tr.scrollLeft+tr.clientWidth>=tr.scrollWidth-4)tr.scrollTo({left:0,behavior:'smooth'})},Math.max(1000,+c.dataset.interval||5000)));
q('[data-upb-slides][data-autoplay="true"]').forEach(s=>setInterval(()=>showSlide(s,1),Math.max(1000,+s.dataset.interval||5000)));
q('form[data-upb-form]').forEach(f=>f.addEventListener('submit',e=>{e.preventDefault();const data=new FormData(f),v=Object.fromEntries(data.entries());f.dispatchEvent(new CustomEvent('upb-form-submit',{detail:{values:v,formData:data},bubbles:true,composed:true}));const s=f.querySelector('[data-upb-form-status]');if(s){s.textContent=f.dataset.successMessage||'Enviado com sucesso.';s.dataset.state='success'}}));
})();`;
}
