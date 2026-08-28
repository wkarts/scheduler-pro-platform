import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { SchedulerProProjectAdapter } from '../src/adapters.js';
import { createHtmlDocument } from '../src/model.js';
import { createProjectPage } from '../src/project.js';

const here=path.dirname(fileURLToPath(import.meta.url));
const root=path.resolve(here,'..');

test('2.3.2 não sobrescreve página HTML de primeira classe com estado Página vazia',()=>{
  const source=fs.readFileSync(path.join(root,'src/editor.js'),'utf8');
  assert.match(source,/if\(!isHtmlDocument\(this\._document\)&&!this\._document\.builder\.root_ids\.length\)preview\.innerHTML=/);
  assert.match(source,/\.upb-html-document-frame\.editor iframe/);
});

test('SchedulerProProjectAdapter carrega Workspace leve sem baixar templates ou HTMLs completos',async()=>{
  const oldFetch=globalThis.fetch;
  const calls=[];
  globalThis.fetch=async url=>{
    calls.push(String(url));
    const pathname=new URL(String(url),'https://example.test').pathname;
    let data={};
    if(pathname.endsWith('/settings/tenant')) data={slug:'tenant-demo',timezone:'America/Bahia',preferences:{}};
    else if(pathname.endsWith('/public/context')) data={tenant:{slug:'tenant-demo'},features:{landing:true,public_booking:true,login:true}};
    else throw new Error(`chamada pesada inesperada no loadProject: ${pathname}`);
    return new Response(JSON.stringify({data}),{status:200,headers:{'content-type':'application/json'}});
  };
  try{
    const adapter=new SchedulerProProjectAdapter({baseUrl:'https://example.test/api/v1',token:()=>''});
    const project=await adapter.loadProject();
    assert.equal(project.pages.length,3);
    assert.deepEqual(project.pages.map(p=>p.surface),['LANDING','BOOKING','LOGIN']);
    assert.equal(calls.length,2);
    assert.ok(calls.every(x=>!x.includes('template-families')&&!x.includes('landing-pages/home')));
  }finally{globalThis.fetch=oldFetch;}
});

test('aplicar template em BOOKING salva conteúdo, chave e versão no tenant',async()=>{
  const oldFetch=globalThis.fetch;
  const writes=[];
  globalThis.fetch=async (url,init={})=>{
    const pathname=new URL(String(url),'https://example.test').pathname;
    if(init.method==='PUT'&&pathname.includes('/settings/tenant/')){
      writes.push([pathname,JSON.parse(String(init.body))]);
      return new Response(JSON.stringify({data:{saved:true}}),{status:200,headers:{'content-type':'application/json'}});
    }
    throw new Error(`request inesperado: ${pathname}`);
  };
  try{
    const adapter=new SchedulerProProjectAdapter({baseUrl:'https://example.test/api/v1',token:()=>''});
    adapter.settings={preferences:{}};
    const document=createHtmlDocument({title:'Agenda Modelo',htmlDocument:'<!doctype html><html><body>agenda</body></html>',surface:'BOOKING',contract:'scheduler-pro-html-template/v1',templateKey:'barber-shop-neo-generico',contentVersion:3});
    const page=createProjectPage({id:'booking',title:'Agenda Pública',surface:'BOOKING',route:'/agendar',slug:'agendar',document});
    const result=await adapter.savePageDraft(page);
    assert.equal(result.saved,true);
    assert.equal(writes.length,3);
    assert.ok(writes.some(([p,v])=>p.endsWith('/booking_page_template_content')&&v.template_key==='barber-shop-neo-generico'));
    assert.ok(writes.some(([p,v])=>p.endsWith('/booking_page_template_key')&&v==='barber-shop-neo-generico'));
    assert.ok(writes.some(([p,v])=>p.endsWith('/booking_page_template_version')&&v===3));
  }finally{globalThis.fetch=oldFetch;}
});

test('Workspace persiste o template antes de abrir o editor',()=>{
  const source=fs.readFileSync(path.join(root,'src/project-workspace.js'),'utf8');
  const start=source.indexOf('async _applyTemplate');
  const end=source.indexOf('async _setPreference',start);
  const body=source.slice(start,end);
  assert.ok(body.indexOf('savePageDraft')>=0);
  assert.ok(body.indexOf('savePageDraft')<body.indexOf('openPage'));
  assert.match(body,/reload:false/);
});

test('LANDING pode salvar e publicar após loadProject leve sem carregar estado anterior',async()=>{
  const oldFetch=globalThis.fetch;
  const requests=[];
  globalThis.fetch=async (url,init={})=>{
    const pathname=new URL(String(url),'https://example.test').pathname;
    requests.push([pathname,init.method||'GET',init.body?JSON.parse(String(init.body)):null]);
    if(pathname.endsWith('/landing-pages/home/draft')&&init.method==='POST') return new Response(JSON.stringify({data:{version_id:'draft-232'}}),{status:200,headers:{'content-type':'application/json'}});
    if(pathname.endsWith('/landing-pages/home/publish')&&init.method==='POST') return new Response(JSON.stringify({data:{published:true,version_id:'published-232'}}),{status:200,headers:{'content-type':'application/json'}});
    throw new Error(`request inesperado: ${pathname}`);
  };
  try{
    const adapter=new SchedulerProProjectAdapter({baseUrl:'https://example.test/api/v1',landingSlug:'home',token:()=>''});
    const document=createHtmlDocument({title:'Landing Modelo',htmlDocument:'<!doctype html><html><body>landing 232</body></html>',surface:'LANDING',contract:'scheduler-pro-html-template/v1',templateKey:'scheduler-pro-padrao-generico',contentVersion:2});
    const page=createProjectPage({id:'landing',title:'Landing Page',surface:'LANDING',route:'/pagina',slug:'pagina',document});
    const saved=await adapter.savePageDraft(page);
    assert.equal(saved.version_id,'draft-232');
    const published=await adapter.publishPage(page);
    assert.equal(published.published,true);
    assert.ok(requests.some(([p,m])=>p.endsWith('/landing-pages/home/draft')&&m==='POST'));
    assert.ok(requests.some(([p,m,b])=>p.endsWith('/landing-pages/home/publish')&&m==='POST'&&b.version_id==='draft-232'));
  }finally{globalThis.fetch=oldFetch;}
});

test('LOGIN salva o template selecionado como documento HTML completo do tenant',async()=>{
  const oldFetch=globalThis.fetch;
  const writes=[];
  globalThis.fetch=async (url,init={})=>{
    const pathname=new URL(String(url),'https://example.test').pathname;
    if(init.method==='PUT'&&pathname.includes('/settings/tenant/')){
      writes.push([pathname,JSON.parse(String(init.body))]);
      return new Response(JSON.stringify({data:{saved:true}}),{status:200,headers:{'content-type':'application/json'}});
    }
    throw new Error(`request inesperado: ${pathname}`);
  };
  try{
    const adapter=new SchedulerProProjectAdapter({baseUrl:'https://example.test/api/v1',token:()=>''});
    adapter.settings={preferences:{}};
    const document=createHtmlDocument({title:'Login Modelo',htmlDocument:'<!doctype html><html><body>login 232</body></html>',surface:'LOGIN',contract:'scheduler-pro-html-template/v1',templateKey:'clinica-medica-generico',contentVersion:1});
    const page=createProjectPage({id:'login',title:'Login',surface:'LOGIN',route:'/login',slug:'login',document});
    const result=await adapter.publishPage(page);
    assert.equal(result.saved,true);
    assert.ok(writes.some(([p,v])=>p.endsWith('/login_page_template_content')&&v.template_key==='clinica-medica-generico'&&v.render_mode==='HTML'));
    assert.ok(writes.some(([p,v])=>p.endsWith('/login_page_template_key')&&v==='clinica-medica-generico'));
  }finally{globalThis.fetch=oldFetch;}
});


test('Workspace liga eventos do ShadowRoot uma única vez no lifecycle',()=>{
  const source=fs.readFileSync(path.join(root,'src/project-workspace.js'),'utf8');
  assert.match(source,/connectedCallback\(\).*shadowRoot\.addEventListener\('click',this\._boundProjectClick,true\)/s);
  assert.match(source,/disconnectedCallback\(\).*shadowRoot\.removeEventListener\('click',this\._boundProjectClick,true\)/s);
  assert.doesNotMatch(source,/shadowRoot\.onclick=/);
  assert.match(source,/event\.composedPath\?\.\(\)/);
});

test('Workspace confirma template e usa aplicação atômica no backend',()=>{
  const source=fs.readFileSync(path.join(root,'src/project-workspace.js'),'utf8');
  assert.match(source,/_internalConfirm\('Aplicar template'/);
  assert.match(source,/applyTemplateSurface\?await this\._adapter\.applyTemplateSurface/);
});

test('Adapter carrega settings compactos e conteúdo pesado somente ao editar',()=>{
  const source=fs.readFileSync(path.join(root,'src/adapters.js'),'utf8');
  assert.match(source,/settings\/tenant\/compact/);
  assert.match(source,/settings\/tenant\/value\/\$\{encodeURIComponent\(key\)\}/);
});

test('Editor usa delegação robusta via composedPath e listener único',()=>{
  const source=fs.readFileSync(path.join(root,'src/editor.js'),'utf8');
  assert.match(source,/root\.addEventListener\('click',this\._boundClick,true\)/);
  assert.match(source,/const path=event\.composedPath\?\.\(\)\|\|\[\]/);
  assert.match(source,/if\(this\._eventsBound\)return/);
});

test('Importação Scheduler Pro persiste páginas canônicas no backend',()=>{
  const source=fs.readFileSync(path.join(root,'src/project-workspace.js'),'utf8');
  assert.match(source,/await this\._adapter\.savePageDraft\(target\)/);
  assert.match(source,/\['LANDING','BOOKING','LOGIN'\]/);
});
