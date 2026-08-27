import { normalizeDocument } from './model.js';
import { toSchedulerProContent } from './renderer.js';

function htmlProtectedError(content){ const error=new Error('Esta Landing Page usa HTML completo e não pode ser convertida automaticamente sem preservar o layout.'); error.code='HTML_TEMPLATE_PROTECTED'; error.content=content; return error; }

export class MemoryAdapter {
  constructor(initial=null) { this.value=normalizeDocument(initial); this.published=null; }
  async load() { return normalizeDocument(this.value); }
  async saveDraft(document) { this.value=normalizeDocument(document); return { document:this.value, version_id:`memory-${Date.now()}` }; }
  async autosave(document) { return this.saveDraft(document); }
  async publish(document) { this.value=normalizeDocument(document); this.published=normalizeDocument(document); return { document:this.published, published:true }; }
  async listTemplates() { return []; }
}

export class RestAdapter {
  constructor({baseUrl='/api/pages',slug='home',headers=()=>({}),unwrap=data=>data?.data??data}={}) { this.baseUrl=baseUrl.replace(/\/$/,''); this.slug=slug; this.headers=headers; this.unwrap=unwrap; }
  async request(path, init={}) { const response=await fetch(`${this.baseUrl}/${encodeURIComponent(this.slug)}${path}`,{...init,cache:'no-store',headers:{accept:'application/json',...(init.body?{'content-type':'application/json'}:{}),...this.headers(),...(init.headers||{})}}); const data=await response.json().catch(()=>({})); if(!response.ok) throw new Error(data?.error?.message||data?.message||`HTTP ${response.status}`); return this.unwrap(data); }
  async load(){ const data=await this.request(''); return normalizeDocument(data.document||data.content||data); }
  async saveDraft(document){ return this.request('/draft',{method:'POST',body:JSON.stringify(document)}); }
  async autosave(document){ return this.request('/autosave',{method:'POST',body:JSON.stringify(document)}).catch(()=>this.saveDraft(document)); }
  async publish(document){ await this.saveDraft(document); return this.request('/publish',{method:'POST',body:JSON.stringify({})}); }
}

export class SchedulerProAdapter {
  constructor({baseUrl='/api/v1',slug='home',token=()=>globalThis.localStorage?.getItem('scheduler_pro_access_token')||''}={}) { this.baseUrl=baseUrl.replace(/\/$/,''); this.slug=slug; this.token=token; this.state=null; }
  headers(hasBody=false){ const token=this.token?.()||''; return {accept:'application/json',...(hasBody?{'content-type':'application/json'}:{}),...(token?{authorization:`Bearer ${token}`}:{})}; }
  async request(path,init={}){ const response=await fetch(`${this.baseUrl}${path}`,{...init,cache:'no-store',headers:{...this.headers(Boolean(init.body)),...(init.headers||{})}}); const body=await response.json().catch(()=>({})); if(!response.ok||body.data===undefined)throw new Error(body?.error?.message||`HTTP ${response.status}`); return body.data; }
  async load(){ this.state=await this.request(`/landing-pages/${encodeURIComponent(this.slug)}`); if(this.state?.content?.render_mode==='HTML') throw htmlProtectedError(this.state.content); return normalizeDocument(this.state.content); }
  async saveDraft(document){ const payload=toSchedulerProContent(document); const result=await this.request(`/landing-pages/${encodeURIComponent(this.slug)}/draft`,{method:'POST',body:JSON.stringify(payload)}); this.state={...(this.state||{}),draft_version_id:result.version_id}; return result; }
  async autosave(document){ const payload=toSchedulerProContent(document); const result=await this.request(`/landing-pages/${encodeURIComponent(this.slug)}/autosave`,{method:'POST',body:JSON.stringify(payload)}); this.state={...(this.state||{}),draft_version_id:result.version_id}; return result; }
  async publish(document){ await this.saveDraft(document); return this.request(`/landing-pages/${encodeURIComponent(this.slug)}/publish`,{method:'POST',body:JSON.stringify({version_id:this.state?.draft_version_id||null})}); }
  async listTemplates(){ return this.request('/landing-pages/templates'); }
  async applyTemplate(key){ return this.request(`/landing-pages/${encodeURIComponent(this.slug)}/templates/${encodeURIComponent(key)}`,{method:'POST',body:'{}'}); }
  async versions(){ return this.request(`/landing-pages/${encodeURIComponent(this.slug)}/versions`); }
  async restoreVersion(id){ return this.request(`/landing-pages/${encodeURIComponent(this.slug)}/versions/${encodeURIComponent(id)}/restore`,{method:'POST',body:'{}'}); }
  async services(){ return this.request('/services').catch(()=>[]); }
  async professionals(){ return this.request('/professionals').catch(()=>[]); }
  async upload(file){ const name=file.name.normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^A-Za-z0-9._-]+/g,'-').slice(0,120)||'arquivo'; const form=new FormData(); form.append('key',`landing/${Date.now()}-${name}`); form.append('file',file); const response=await fetch(`${this.baseUrl}/files/upload`,{method:'POST',body:form,headers:this.headers(false)}); const body=await response.json().catch(()=>({})); if(!response.ok||body.data===undefined)throw new Error(body?.error?.message||`HTTP ${response.status}`); return body.data.public_url||`${this.baseUrl}/public/assets/${encodeURI(body.data.key)}`; }
}
