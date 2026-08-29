import { createDocument, isHtmlDocument, normalizeDocument } from './model.js';
import { createProject, createProjectPage, normalizeProject, projectPage } from './project.js';
import { toSchedulerProContent } from './renderer.js';

export class MemoryAdapter {
  constructor(initial=null) { this.value=normalizeDocument(initial); this.published=null; this.revisions=[]; }
  async load() { return normalizeDocument(this.value); }
  async saveDraft(document) { this.value=normalizeDocument(document); const revision={id:`memory-${Date.now()}`,version_number:this.revisions.length+1,label:'Rascunho local',created_at:new Date().toISOString(),document:normalizeDocument(document)};this.revisions.unshift(revision);return { document:this.value, version_id:revision.id }; }
  async autosave(document) { this.value=normalizeDocument(document); return {document:this.value,version_id:`autosave-${Date.now()}`}; }
  async publish(document) { this.value=normalizeDocument(document); this.published=normalizeDocument(document); return { document:this.published, published:true }; }
  async listTemplates() { return []; }
  async versions(){return this.revisions.map(({document,...rest})=>rest);}
  async restoreVersion(id){const revision=this.revisions.find(row=>row.id===id);if(!revision)throw new Error('Versão não encontrada.');this.value=normalizeDocument(revision.document);return{restored:true};}
}

export class RestAdapter {
  constructor({baseUrl='/api/pages',slug='home',headers=()=>({}),unwrap=data=>data?.data??data,assetsUrl=null}={}) { this.baseUrl=baseUrl.replace(/\/$/,''); this.slug=slug; this.headers=headers; this.unwrap=unwrap; this.assetsUrl=assetsUrl; }
  async request(path, init={}) {
    const bodyIsForm=typeof FormData!=='undefined'&&init.body instanceof FormData;
    const response=await fetch(`${this.baseUrl}/${encodeURIComponent(this.slug)}${path}`,{...init,cache:'no-store',headers:{accept:'application/json',...(init.body&&!bodyIsForm?{'content-type':'application/json'}:{}),...this.headers(),...(init.headers||{})}});
    const data=await response.json().catch(()=>({})); if(!response.ok) throw new Error(data?.error?.message||data?.message||`HTTP ${response.status}`); return this.unwrap(data);
  }
  async load(){ const data=await this.request(''); return normalizeDocument(data.document||data.content||data); }
  async saveDraft(document){ return this.request('/draft',{method:'POST',body:JSON.stringify(document)}); }
  async autosave(document){ return this.request('/autosave',{method:'POST',body:JSON.stringify(document)}).catch(()=>this.saveDraft(document)); }
  async publish(document){ await this.saveDraft(document); return this.request('/publish',{method:'POST',body:JSON.stringify({})}); }
  async listTemplates(){return this.request('/templates').catch(()=>[]);}
  async versions(){return this.request('/versions').catch(()=>[]);}
  async restoreVersion(id){return this.request(`/versions/${encodeURIComponent(id)}/restore`,{method:'POST',body:'{}'});}
  async upload(file){if(!this.assetsUrl)throw new Error('Endpoint de assets não configurado no RestAdapter.');const form=new FormData();form.append('file',file);const response=await fetch(this.assetsUrl,{method:'POST',body:form,headers:{...this.headers()}});const data=await response.json().catch(()=>({}));if(!response.ok)throw new Error(data?.error?.message||data?.message||`HTTP ${response.status}`);const value=this.unwrap(data);return value.public_url||value.url;}
}

export class SchedulerProAdapter {
  constructor({baseUrl='/api/v1',slug='home',token=()=>globalThis.localStorage?.getItem('scheduler_pro_access_token')||''}={}) { this.baseUrl=baseUrl.replace(/\/$/,''); this.slug=slug; this.token=token; this.state=null; }
  headers(hasBody=false){ const token=this.token?.()||''; return {accept:'application/json',...(hasBody?{'content-type':'application/json'}:{}),...(token?{authorization:`Bearer ${token}`}:{})}; }
  async request(path,init={}){ const response=await fetch(`${this.baseUrl}${path}`,{...init,cache:'no-store',headers:{...this.headers(Boolean(init.body)),...(init.headers||{})}}); const body=await response.json().catch(()=>({})); if(!response.ok||body.data===undefined)throw new Error(body?.error?.message||`HTTP ${response.status}`); return body.data; }
  async load(){ this.state=await this.request(`/landing-pages/${encodeURIComponent(this.slug)}`); return normalizeDocument(this.state.content); }
  async saveDraft(document){ const payload=toSchedulerProContent(document); const result=await this.request(`/landing-pages/${encodeURIComponent(this.slug)}/draft`,{method:'POST',body:JSON.stringify(payload)}); this.state={...(this.state||{}),draft_version_id:result.version_id}; return result; }
  async autosave(document){ const payload=toSchedulerProContent(document); const result=await this.request(`/landing-pages/${encodeURIComponent(this.slug)}/autosave`,{method:'POST',body:JSON.stringify(payload)}); this.state={...(this.state||{}),draft_version_id:result.version_id}; return result; }
  async publish(document){ await this.saveDraft(document); return this.request(`/landing-pages/${encodeURIComponent(this.slug)}/publish`,{method:'POST',body:JSON.stringify({version_id:this.state?.draft_version_id||null})}); }
  async listTemplates(){ return this.request('/landing-pages/templates'); }
  async applyTemplate(key){ return this.request(`/landing-pages/${encodeURIComponent(this.slug)}/templates/${encodeURIComponent(key)}`,{method:'POST',body:'{}'}); }
  async versions(){ return this.request(`/landing-pages/${encodeURIComponent(this.slug)}/versions`); }
  async restoreVersion(id){ return this.request(`/landing-pages/${encodeURIComponent(this.slug)}/versions/${encodeURIComponent(id)}/restore`,{method:'POST',body:'{}'}); }
  async emergencyRollback(){ return this.request(`/landing-pages/${encodeURIComponent(this.slug)}/emergency-rollback`,{method:'POST',body:'{}'}); }
  async emergencyBlank(){ return this.request(`/landing-pages/${encodeURIComponent(this.slug)}/emergency-blank`,{method:'POST',body:'{}'}); }
  async services(){ return this.request('/services').catch(()=>[]); }
  async professionals(){ return this.request('/professionals').catch(()=>[]); }
  async upload(file){ const name=file.name.normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^A-Za-z0-9._-]+/g,'-').slice(0,120)||'arquivo'; const form=new FormData(); form.append('key',`landing/${Date.now()}-${name}`); form.append('file',file); const response=await fetch(`${this.baseUrl}/files/upload`,{method:'POST',body:form,headers:this.headers(false)}); const body=await response.json().catch(()=>({})); if(!response.ok||body.data===undefined)throw new Error(body?.error?.message||`HTTP ${response.status}`); return body.data.public_url||`${this.baseUrl}/public/assets/${encodeURI(body.data.key)}`; }
}

export class MemoryProjectAdapter {
  constructor(initial=null){this.value=normalizeProject(initial);this.published=new Map();this.revisions=new Map();}
  async loadProject(){return normalizeProject(this.value);}
  async saveProject(project){this.value=normalizeProject(project);return this.loadProject();}
  async savePageDraft(page){const normalized=createProjectPage(page);const index=this.value.pages.findIndex(row=>row.id===normalized.id);if(index>=0)this.value.pages[index]=normalized;else this.value.pages.push(normalized);const rows=this.revisions.get(normalized.id)||[];rows.unshift({id:`memory-${normalized.id}-${Date.now()}`,version_number:rows.length+1,label:'Rascunho local',created_at:new Date().toISOString(),document:normalizeDocument(normalized.document)});this.revisions.set(normalized.id,rows);return{version_id:rows[0].id,page:normalized};}
  async autosavePage(page){return this.savePageDraft(page);}
  async publishPage(page){await this.savePageDraft(page);this.published.set(page.id,normalizeDocument(page.document));return{published:true,page_id:page.id};}
  async versions(pageId){return (this.revisions.get(String(pageId))||[]).map(({document,...row})=>row);}
  async restorePageVersion(pageId,id){const row=(this.revisions.get(String(pageId))||[]).find(item=>item.id===id);if(!row)throw new Error('Versão não encontrada.');const page=projectPage(this.value,pageId);if(!page)throw new Error('Página não encontrada.');page.document=normalizeDocument(row.document);return{restored:true};}
}

export class RestProjectAdapter {
  constructor({baseUrl='/api/builder/projects',projectId='default',headers=()=>({}),unwrap=data=>data?.data??data}={}){this.baseUrl=baseUrl.replace(/\/$/,'');this.projectId=projectId;this.headers=headers;this.unwrap=unwrap;}
  async request(path='',init={}){const response=await fetch(`${this.baseUrl}/${encodeURIComponent(this.projectId)}${path}`,{...init,cache:'no-store',headers:{accept:'application/json',...(init.body?{'content-type':'application/json'}:{}),...this.headers(),...(init.headers||{})}});const data=await response.json().catch(()=>({}));if(!response.ok)throw new Error(data?.error?.message||data?.message||`HTTP ${response.status}`);return this.unwrap(data);}
  async loadProject(){return normalizeProject(await this.request(''));}
  async saveProject(project){return normalizeProject(await this.request('',{method:'PUT',body:JSON.stringify(normalizeProject(project))}));}
  async savePageDraft(page){return this.request(`/pages/${encodeURIComponent(page.id)}/draft`,{method:'POST',body:JSON.stringify(createProjectPage(page))});}
  async autosavePage(page){return this.request(`/pages/${encodeURIComponent(page.id)}/autosave`,{method:'POST',body:JSON.stringify(createProjectPage(page))}).catch(()=>this.savePageDraft(page));}
  async publishPage(page){await this.savePageDraft(page);return this.request(`/pages/${encodeURIComponent(page.id)}/publish`,{method:'POST',body:'{}'});}
  async versions(pageId){return this.request(`/pages/${encodeURIComponent(pageId)}/versions`).catch(()=>[]);}
  async restorePageVersion(pageId,id){return this.request(`/pages/${encodeURIComponent(pageId)}/versions/${encodeURIComponent(id)}/restore`,{method:'POST',body:'{}'});}
}

function schedulerBookingContent(document){
  const doc=normalizeDocument(document);
  if(!isHtmlDocument(doc)) throw new Error('No Scheduler Pro, a superfície BOOKING visual ainda precisa ser publicada como página HTML completa. Importe/edite o agendamento.html da família ou use um plugin de compilação BOOKING.');
  const payload=toSchedulerProContent(doc);
  payload.surface='BOOKING';
  return payload;
}

export class SchedulerProProjectAdapter {
  constructor({baseUrl='/api/v1',landingSlug='home',token=()=>globalThis.localStorage?.getItem('scheduler_pro_access_token')||''}={}){this.baseUrl=baseUrl.replace(/\/$/,'');this.landingSlug=landingSlug;this.token=token;this.landing=new SchedulerProAdapter({baseUrl:this.baseUrl,slug:landingSlug,token});this.settings=null;this.project=null;}
  headers(hasBody=false){const token=this.token?.()||'';return{accept:'application/json',...(hasBody?{'content-type':'application/json'}:{}),...(token?{authorization:`Bearer ${token}`}:{})};}
  async request(path,init={}){const response=await fetch(`${this.baseUrl}${path}`,{...init,cache:'no-store',headers:{...this.headers(Boolean(init.body)),...(init.headers||{})}});const body=await response.json().catch(()=>({}));if(!response.ok||body.data===undefined)throw new Error(body?.error?.message||`HTTP ${response.status}`);return body.data;}
  async putSetting(key,value){return this.request(`/settings/tenant/${encodeURIComponent(key)}`,{method:'PUT',body:JSON.stringify(value)});}
  async loadProject(){
    const [landingState,settings]=await Promise.all([
      this.request(`/landing-pages/${encodeURIComponent(this.landingSlug)}`),
      this.request('/settings/tenant').catch(()=>({preferences:{},slug:'scheduler-pro'})),
    ]);
    this.landing.state=landingState;this.settings=settings;
    const preferences=settings?.preferences||{};
    const landingDoc=normalizeDocument(landingState?.content||createDocument({title:'Landing Page'}));landingDoc.surface='LANDING';
    let bookingDoc;
    const bookingContent=preferences.booking_page_template_content;
    if(bookingContent&&typeof bookingContent==='object') bookingDoc=normalizeDocument(bookingContent);
    else {bookingDoc=createDocument({title:'Página de Agendamento'});bookingDoc.surface='BOOKING';}
    bookingDoc.surface='BOOKING';
    this.project=createProject({
      id:`scheduler-${settings?.slug||'tenant'}`,
      name:'Scheduler Pro — Páginas públicas',
      pages:[
        createProjectPage({id:'landing',title:'Landing Page',slug:'pagina',route:'/pagina',surface:'LANDING',document:landingDoc,source:{provider:'scheduler-pro',target:'landing-pages'}}),
        createProjectPage({id:'booking',title:'Página de Agendamento',slug:'agendar',route:'/agendar',surface:'BOOKING',document:bookingDoc,source:{provider:'scheduler-pro',target:'booking-template'}}),
      ],
      activePageId:'landing',
      integrations:{scheduler_pro:{landing_slug:this.landingSlug}},
    });
    return normalizeProject(this.project);
  }
  async saveProject(project){this.project=normalizeProject(project);return this.project;}
  async savePageDraft(page){
    const normalized=createProjectPage(page);
    if(normalized.surface==='LANDING'||normalized.id==='landing'){
      this.landing.state=this.landing.state||{};
      return this.landing.saveDraft(normalized.document);
    }
    if(normalized.surface==='BOOKING'||normalized.id==='booking'){
      const content=schedulerBookingContent(normalized.document);
      await this.putSetting('booking_page_template_content',content);
      await this.putSetting('booking_page_template_key',content.template_key||'argws-booking');
      await this.putSetting('booking_page_template_version',Number(content.content_version||2));
      return{saved:true,page_id:normalized.id,content};
    }
    throw new Error(`Superfície Scheduler Pro não suportada: ${normalized.surface}`);
  }
  async autosavePage(page){return this.savePageDraft(page);}
  async publishPage(page){
    const normalized=createProjectPage(page);
    if(normalized.surface==='LANDING'||normalized.id==='landing')return this.landing.publish(normalized.document);
    if(normalized.surface==='BOOKING'||normalized.id==='booking')return this.savePageDraft(normalized);
    throw new Error(`Superfície Scheduler Pro não suportada: ${normalized.surface}`);
  }
  async versions(pageId){return String(pageId)==='landing'?this.landing.versions():[];}
  async restorePageVersion(pageId,id){if(String(pageId)!=='landing')throw new Error('Histórico remoto de BOOKING ainda não é fornecido pelo Scheduler Pro.');return this.landing.restoreVersion(id);}
  async emergencyRollbackPage(pageId){if(String(pageId)!=='landing')throw new Error('Recuperação de emergência disponível somente para Landing no adapter atual.');return this.landing.emergencyRollback();}
  async emergencyBlankPage(pageId){if(String(pageId)!=='landing')throw new Error('Página em branco de emergência disponível somente para Landing no adapter atual.');return this.landing.emergencyBlank();}
  async upload(file){return this.landing.upload(file);}
  async services(){return this.landing.services();}
  async professionals(){return this.landing.professionals();}
}

export class ProjectPageAdapter {
  constructor(projectAdapter,pageProvider){this.projectAdapter=projectAdapter;this.pageProvider=typeof pageProvider==='function'?pageProvider:()=>pageProvider;const page=this.pageProvider?.();if(!projectAdapter?.emergencyRollbackPage||String(page?.surface||'').toUpperCase()!=='LANDING')this.emergencyRollback=undefined;if(!projectAdapter?.emergencyBlankPage||String(page?.surface||'').toUpperCase()!=='LANDING')this.emergencyBlank=undefined;}
  page(){const page=this.pageProvider?.();if(!page)throw new Error('Página ativa não encontrada.');return page;}
  async load(){return normalizeDocument(this.page().document);}
  async saveDraft(document){const page=createProjectPage({...this.page(),document});return this.projectAdapter.savePageDraft(page);}
  async autosave(document){const page=createProjectPage({...this.page(),document});return this.projectAdapter.autosavePage?.(page)??this.projectAdapter.savePageDraft(page);}
  async publish(document){const page=createProjectPage({...this.page(),document});return this.projectAdapter.publishPage(page);}
  async versions(){return this.projectAdapter.versions?.(this.page().id)??[];}
  async restoreVersion(id){return this.projectAdapter.restorePageVersion?.(this.page().id,id);}
  async emergencyRollback(){return this.projectAdapter.emergencyRollbackPage?.(this.page().id);}
  async emergencyBlank(){return this.projectAdapter.emergencyBlankPage?.(this.page().id);}
  async upload(file){if(!this.projectAdapter.upload)throw new Error('Upload não configurado.');return this.projectAdapter.upload(file);}
  async listTemplates(){return[];}
}

