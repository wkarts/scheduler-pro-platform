import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import {
  createDocument, createHtmlDocument, createProject, createProjectPage, importSchedulerProTemplateFamily,
  isHtmlDocument, normalizeDocument, normalizeProject, PROJECT_SCHEMA, renderDocument, toSchedulerProContent,
} from '../src/index.js';

function schedulerHtml(key,surface,title){return `<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="scheduler-pro-template" content="${key}"><meta name="scheduler-pro-content-version" content="2"><meta name="scheduler-pro-surface" content="${surface}"><title>${title}</title><style>@media(max-width:680px){body{margin:0}}</style></head><body><main>${title}</main>${surface==='public-booking'?'<div data-scheduler-pro-booking></div>':''}</body></html>`;}

// ZIP stored mínimo, suficiente para o importador sem dependência externa.
function crc32(bytes){let c=0xffffffff;for(const b of bytes){c^=b;for(let k=0;k<8;k++)c=(c>>>1)^((c&1)?0xedb88320:0);}return(c^0xffffffff)>>>0;}
function u16(v){return [v&255,(v>>>8)&255]};function u32(v){return [v&255,(v>>>8)&255,(v>>>16)&255,(v>>>24)&255]};
function zipStored(entries){const enc=new TextEncoder();const locals=[];const centrals=[];let offset=0;for(const [name,text] of Object.entries(entries)){const nb=enc.encode(name),data=enc.encode(text),crc=crc32(data);const local=Uint8Array.from([...u32(0x04034b50),...u16(20),...u16(0),...u16(0),...u16(0),...u16(0),...u32(crc),...u32(data.length),...u32(data.length),...u16(nb.length),...u16(0),...nb,...data]);locals.push(local);const central=Uint8Array.from([...u32(0x02014b50),...u16(20),...u16(20),...u16(0),...u16(0),...u16(0),...u16(0),...u32(crc),...u32(data.length),...u32(data.length),...u16(nb.length),...u16(0),...u16(0),...u16(0),...u16(0),...u32(0),...u32(offset),...nb]);centrals.push(central);offset+=local.length;}const centralSize=centrals.reduce((n,b)=>n+b.length,0),count=centrals.length;return Uint8Array.from([...locals.flatMap(b=>[...b]),...centrals.flatMap(b=>[...b]),...u32(0x06054b50),...u16(0),...u16(0),...u16(count),...u16(count),...u32(centralSize),...u32(offset),...u16(0)]);}

test('documento HTML é página de primeira classe, não widget html_surface',()=>{
  const html=schedulerHtml('studio','landing','Studio');
  const doc=createHtmlDocument({title:'Studio',htmlDocument:html,surface:'LANDING',contract:'scheduler-pro-html-template/v1',templateKey:'studio',contentVersion:2});
  assert.equal(doc.mode,'HTML');assert.equal(doc.builder.root_ids.length,0);assert.equal(Object.keys(doc.builder.nodes).length,0);assert.equal(isHtmlDocument(doc),true);
  const compiled=toSchedulerProContent(doc);assert.equal(compiled.html_document,html);assert.equal(compiled.surface,'LANDING');
  const editor=renderDocument(doc,{context:{editor:true}});assert.match(editor.html,/data-upb-document-mode="HTML"/);assert.doesNotMatch(editor.html,/data-upb-node=/);
});

test('documento legado com único html_surface migra automaticamente para página HTML',()=>{
  const html=schedulerHtml('legacy','landing','Legacy');
  const legacy={schema:'argws-visual-builder/v3',version:4,title:'Legacy',surface:'LANDING',builder:{schema:'argws-visual-builder/v3',root_ids:['x'],nodes:{x:{id:'x',type:'html_surface',props:{html_document:html,contract:'scheduler-pro-html-template/v1',template_key:'legacy',surface:'LANDING',content_version:2},style:{},responsive:{desktop:{},tablet:{},mobile:{},hidden:{}},children:[]}}},design_system:{breakpoints:[]},project:{integrations:{html_surface:{source_name:'legacy.zip'}}}};
  const doc=normalizeDocument(legacy);assert.equal(doc.mode,'HTML');assert.equal(doc.html.document,html);assert.equal(doc.project.integrations.html_surface,undefined);assert.equal(doc.project.integrations.html_document.migrated_from,'html_surface');
});

test('projeto universal mantém páginas independentes',()=>{
  const p=createProject({name:'Site',pages:[createProjectPage({id:'home',title:'Home',slug:'home',route:'/',document:createDocument({title:'Home'})}),createProjectPage({id:'contact',title:'Contato',slug:'contato',route:'/contato',document:createDocument({title:'Contato'})})]});
  assert.equal(p.schema,PROJECT_SCHEMA);assert.equal(p.pages.length,2);assert.notEqual(p.pages[0].document,p.pages[1].document);assert.equal(normalizeProject(p).pages[1].route,'/contato');
});

test('pacote Scheduler Pro vira família com LANDING e BOOKING como duas páginas',async()=>{
  const key='studio-teste';const manifest={schema:'scheduler-pro-template-package/v1',package:{key,name:'Studio Teste',surfaces:{landing:{renderer:'HTML',entry:'landing.html',route:'/pagina',seo:{title:'Landing'}},booking:{renderer:'HTML',entry:'agendamento.html',route:'/agendar',seo:{title:'Agendamento'}}}}};
  const zip=zipStored({'template.json':JSON.stringify(manifest),'landing.html':schedulerHtml(key,'landing','Landing'),'agendamento.html':schedulerHtml(key,'public-booking','Agendamento')});
  const result=await importSchedulerProTemplateFamily(zip,{sourceName:'studio.zip'});assert.equal(result.project.pages.length,2);const landing=result.project.pages.find(p=>p.surface==='LANDING'),booking=result.project.pages.find(p=>p.surface==='BOOKING');assert.ok(landing);assert.ok(booking);assert.equal(landing.document.mode,'HTML');assert.equal(booking.document.mode,'HTML');assert.equal(landing.route,'/pagina');assert.equal(booking.route,'/agendar');assert.equal(landing.document.builder.root_ids.length,0);assert.equal(booking.document.builder.root_ids.length,0);
});

test('workspace universal e adapter Scheduler Pro são exportados pelo pacote',async()=>{
  const sdk=await import('../src/index.js');assert.equal(typeof sdk.ArgwsVisualBuilderApp,'function');assert.equal(typeof sdk.SchedulerProProjectAdapter,'function');assert.equal(typeof sdk.importSchedulerProTemplateFamily,'function');
  const vue=await fs.readFile(new URL('../integrations/scheduler-pro/TenantVisualPageBuilder.vue',import.meta.url),'utf8');assert.match(vue,/argws-visual-builder-app/);assert.match(vue,/SchedulerProProjectAdapter/);
});
