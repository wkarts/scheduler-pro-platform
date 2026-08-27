import { normalizeDocument } from './model.js';
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
  async services(){ return this.request('/services').catch(()=>[]); }
  async professionals(){ return this.request('/professionals').catch(()=>[]); }
  async upload(file){ const name=file.name.normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^A-Za-z0-9._-]+/g,'-').slice(0,120)||'arquivo'; const form=new FormData(); form.append('key',`landing/${Date.now()}-${name}`); form.append('file',file); const response=await fetch(`${this.baseUrl}/files/upload`,{method:'POST',body:form,headers:this.headers(false)}); const body=await response.json().catch(()=>({})); if(!response.ok||body.data===undefined)throw new Error(body?.error?.message||`HTTP ${response.status}`); return body.data.public_url||`${this.baseUrl}/public/assets/${encodeURI(body.data.key)}`; }
}
