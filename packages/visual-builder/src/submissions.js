import { deepClone } from './model.js';
import { registerAction } from './actions.js';

function uid(){return globalThis.crypto?.randomUUID?.()||`submission-${Date.now()}-${Math.random().toString(36).slice(2,8)}`;}
export class MemorySubmissionStore {
  constructor(initial=[]){this.rows=(initial||[]).map(row=>deepClone(row));}
  async create(input={}){const row={id:String(input.id||uid()),created_at:input.created_at||new Date().toISOString(),form_id:String(input.form_id||'form'),page_id:input.page_id||null,values:deepClone(input.values||{}),meta:deepClone(input.meta||{})};this.rows.unshift(row);return deepClone(row);}
  async list({form_id=null,limit=100,offset=0}={}){const rows=form_id?this.rows.filter(row=>row.form_id===form_id):this.rows;return deepClone(rows.slice(offset,offset+limit));}
  async get(id){const row=this.rows.find(item=>item.id===id);return row?deepClone(row):null;}
  async remove(id){const index=this.rows.findIndex(item=>item.id===id);if(index<0)return false;this.rows.splice(index,1);return true;}
}
export class RestSubmissionStore {
  constructor({baseUrl='/api/submissions',fetchImpl=globalThis.fetch,headers=()=>({})}={}){this.baseUrl=baseUrl.replace(/\/$/,'');this.fetch=fetchImpl;this.headers=headers;}
  async request(path='',init={}){const response=await this.fetch(`${this.baseUrl}${path}`,{...init,headers:{accept:'application/json',...(init.body?{'content-type':'application/json'}:{}),...this.headers(),...(init.headers||{})}});const payload=await response.json().catch(()=>({}));if(!response.ok)throw new Error(payload?.error?.message||payload?.message||`Submissions HTTP ${response.status}`);return payload.data??payload;}
  create(input){return this.request('',{method:'POST',body:JSON.stringify(input)});} list({form_id=null,limit=100,offset=0}={}){const q=new URLSearchParams({limit:String(limit),offset:String(offset)});if(form_id)q.set('form_id',form_id);return this.request(`?${q}`);} get(id){return this.request(`/${encodeURIComponent(id)}`);} remove(id){return this.request(`/${encodeURIComponent(id)}`,{method:'DELETE'});}
}
function csvCell(value){const text=typeof value==='string'?value:JSON.stringify(value??'');return `"${String(text).replace(/"/g,'""')}"`;}
export function submissionsToCsv(rows=[]){const values=rows.map(row=>row?.values||{});const keys=Array.from(new Set(values.flatMap(row=>Object.keys(row))));const headers=['id','created_at','form_id',...keys];return [headers.map(csvCell).join(','),...(rows||[]).map(row=>[row.id,row.created_at,row.form_id,...keys.map(key=>row.values?.[key]??'')].map(csvCell).join(','))].join('\n');}

registerAction('collect_submission',async({action,payload,runtime})=>{
  const store=runtime?.submissionStore;if(!store?.create)throw new Error('Submission Store não configurado no runtime.');
  return store.create({form_id:String(action.form_id||action.formId||'form'),page_id:action.page_id||null,values:payload,meta:action.meta||{}});
});
