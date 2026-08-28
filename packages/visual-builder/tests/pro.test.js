import test from 'node:test';
import assert from 'node:assert/strict';
import {
  addNode, auditDocument, createDocument, createNode, createSiteKit, deviceForWidth, evaluateConditions,
  exportStandaloneHtml, getPath, LocalComponentLibrary, normalizeDocument, renderDocument, resolveBindings,
  resolveSiteParts, toSchedulerProContent,
} from '../src/index.js';

function memoryStorage(){let value='';return{getItem(){return value||null},setItem(_k,v){value=v}}}

test('migra schemas legados para v3 preservando árvore',()=>{
  const old={schema:'argws-visual-builder/v1',version:2,builder:{schema:'argws-visual-builder/v1',root_ids:['x'],nodes:{x:{id:'x',type:'text',props:{text:'ok'},style:{},responsive:{desktop:{},tablet:{},mobile:{},hidden:{}}}}}};
  const doc=normalizeDocument(old);assert.equal(doc.schema,'argws-visual-builder/v3');assert.equal(doc.builder.nodes.x.props.text,'ok');assert.equal(doc.version,5);
});

test('breakpoints customizados determinam viewport',()=>{
  const doc=createDocument({breakpoints:[{id:'desktop',label:'Desktop',max:null,canvas:1280},{id:'laptop',label:'Laptop',max:1440,canvas:1100},{id:'tablet',label:'Tablet',max:900,canvas:760},{id:'mobile',label:'Mobile',max:600,canvas:390}]});
  assert.equal(deviceForWidth(doc,1500),'desktop');assert.equal(deviceForWidth(doc,1200),'laptop');assert.equal(deviceForWidth(doc,850),'tablet');assert.equal(deviceForWidth(doc,500),'mobile');
});

test('bindings e interpolação resolvem conteúdo dinâmico',()=>{
  const props=resolveBindings({title:'Olá {{tenant.name}}',text:'fallback'},{text:'customer.message'},{tenant:{name:'Studio'},customer:{message:'Bem-vinda'}});
  assert.equal(props.title,'Olá Studio');assert.equal(props.text,'Bem-vinda');assert.equal(getPath({a:{b:2}},'a.b'),2);
});

test('condições de exibição suportam comparação e existência',()=>{
  const context={tenant:{plan:'pro'},user:{active:true}};
  assert.equal(evaluateConditions([{path:'tenant.plan',operator:'eq',value:'pro'},{path:'user.active',operator:'truthy'}],context),true);
  assert.equal(evaluateConditions([{path:'tenant.plan',operator:'eq',value:'starter'}],context),false);
});

test('renderer aplica estados e responsive CSS com prioridade',()=>{
  const doc=createDocument();const node=addNode(doc,createNode('button',{label:'A',url:'#'}));node.style.color='#111111';node.states.hover.color='#222222';node.responsive.mobile.fontSize=14;node.responsive_states.mobile.hover.color='#333333';
  const {css}=renderDocument(doc);assert.match(css,/hover/);assert.match(css,/color:#222222!important/);assert.match(css,/@media\(max-width:680px\)/);assert.match(css,/font-size:14px!important/);
});

test('loop repete filhos usando contexto dinâmico',()=>{
  const doc=createDocument();const loop=addNode(doc,createNode('loop',{source:'items',limit:3}));addNode(doc,createNode('dynamic_text',{path:'item.name',fallback:'Sem nome'}),loop.id);
  const {html}=renderDocument(doc,{context:{items:[{name:'A'},{name:'B'}]}});assert.match(html,/>A</);assert.match(html,/>B</);
});

test('form builder renderiza campos e evento runtime',()=>{
  const doc=createDocument();addNode(doc,createNode('form',{title:'Contato',fields_text:'Nome | name | text | required\nE-mail | email | email | required',actions_text:'event',submit_label:'Enviar'}));const {html}=renderDocument(doc);assert.match(html,/data-upb-form/);assert.match(html,/name="email"/);assert.match(html,/required/);
});

test('popup e offcanvas são renderizados como overlays',()=>{
  const doc=createDocument();const popup=addNode(doc,createNode('popup',{name:'lead',trigger:'delay',delay:10}));addNode(doc,createNode('heading',{text:'Oferta',level:'h2'}),popup.id);const {html}=renderDocument(doc,{context:{editor:false}});assert.match(html,/<dialog/);assert.match(html,/data-upb-overlay-name="lead"/);assert.match(html,/data-trigger="delay"/);
});

test('standalone inclui runtime para interações',()=>{
  const doc=createDocument();addNode(doc,createNode('counter',{start:0,end:10}));const html=exportStandaloneHtml(doc);assert.match(html,/data-upb-counter/);assert.match(html,/<script>/);assert.match(html,/requestAnimationFrame/);
});

test('biblioteca local salva e reinsere subárvore com ids novos',()=>{
  const storage=memoryStorage(),library=new LocalComponentLibrary({storage});const doc=createDocument();const container=addNode(doc,createNode('container'));const child=addNode(doc,createNode('heading',{text:'Reutilizável'}),container.id);const saved=library.saveFromDocument(doc,container.id,{name:'Bloco'});assert.equal(library.list()[0].name,'Bloco');const inserted=library.insert(doc,saved.id);assert.notEqual(inserted.id,container.id);assert.equal(doc.builder.nodes[inserted.children[0]].props.text,doc.builder.nodes[child.id].props.text);
});

test('site kit resolve partes globais por condição',()=>{
  const partDoc=createDocument({title:'Header'});const kit=createSiteKit({parts:[{id:'h1',type:'header',name:'Header Pro',priority:10,conditions:[{path:'tenant.plan',operator:'eq',value:'pro'}],document:partDoc}]});assert.equal(resolveSiteParts(kit,'header',{tenant:{plan:'pro'}}).length,1);assert.equal(resolveSiteParts(kit,'header',{tenant:{plan:'starter'}}).length,0);
});

test('auditoria detecta problemas básicos de SEO e acessibilidade',()=>{
  const doc=createDocument();addNode(doc,createNode('image',{image:'https://example.com/a.jpg',alt:''}));const report=auditDocument(doc);assert.ok(report.warnings>=2);assert.ok(report.score<100);assert.ok(report.issues.some(i=>i.code==='IMAGE_ALT_EMPTY'));
});

test('compiler do Scheduler mantém contrato V2 e não converte formulário genérico em agenda',()=>{
  const doc=createDocument();addNode(doc,createNode('form',{title:'Lead',fields_text:'Nome | name | text'}));addNode(doc,createNode('booking',{title:'Agenda'}));const compiled=toSchedulerProContent(doc);assert.equal(compiled.version,2);assert.ok(compiled.blocks.some(b=>b.type==='booking'));const formFallback=compiled.blocks.find(b=>b.id!==compiled.blocks.find(x=>x.type==='booking')?.id);assert.notEqual(formFallback?.type,'form');assert.equal(compiled.builder.schema,'argws-visual-builder/v3');
});

test('API pública expõe aliases de integração para pacote distribuído', async () => {
  const sdk = await import('../src/index.js');
  const doc = sdk.createPageDocument({ title: 'API pública' });
  const compiled = sdk.compileSchedulerProV2(doc);
  const html = sdk.renderPage(doc);
  assert.equal(compiled.version, 2);
  assert.ok(Array.isArray(compiled.blocks));
  assert.equal(typeof html, 'string');
});
