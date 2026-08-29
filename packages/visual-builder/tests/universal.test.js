import test from 'node:test';
import assert from 'node:assert/strict';
import {
  AssetLibrary, PROJECT_PACKAGE_SCHEMA, QueryCache, addNode, applyOperation, can, compileSchedulerProV2,
  createDocument, createEmbedSnippet, createOperation, createProjectPackage, createEditorPolicy, createNode,
  executeDataQuery, exportProjectPackage, fontFaceCss, importProjectPackage, interpolate, localizeDocument,
  normalizeDocument, normalizeFormSchema, parseFormFieldsText, registerDataSource, registerDynamicTag,
  renderCustomCode, renderDocument, renderDocumentAsync, setNodeTranslation, unregisterDataSource,
  documentFromSchedulerHtmlWrapper, toSchedulerProContent, SchedulerProAdapter,
  unregisterDynamicTag, validateFormValues, validateProjectPackage, WIDGETS,
} from '../src/index.js';

test('schema universal v3 migra documento v2 e adiciona projeto',()=>{
  const old={schema:'argws-visual-builder/v2',version:3,title:'Legacy',builder:{schema:'argws-visual-builder/v2',root_ids:[],nodes:{}},global_styles:{},seo:{},blocks:[]};
  const doc=normalizeDocument(old);assert.equal(doc.schema,'argws-visual-builder/v3');assert.equal(doc.version,5);assert.equal(doc.project.i18n.default_locale,'pt-BR');assert.deepEqual(doc.project.assets.fonts,[]);
});

test('Dynamic Tags e filtros são extensíveis',()=>{
  registerDynamicTag('tenant.brand',ctx=>ctx.tenant?.brand||'');
  assert.equal(interpolate('Olá {{ tenant.brand | upper }}',{tenant:{brand:'Argws'}}),'Olá ARGWS');
  unregisterDynamicTag('tenant.brand');
});

test('Data Source assíncrono alimenta Query Loop com cache',async()=>{
  let calls=0;registerDataSource('catalog.products',async({query})=>{calls++;return{items:[{name:`Produto ${query.category}`}]}},{cacheTtl:10000});
  const cache=new QueryCache();
  const a=await executeDataQuery('catalog.products',{category:'A'},{queryCache:cache});
  const b=await executeDataQuery('catalog.products',{category:'A'},{queryCache:cache});
  assert.equal(a.items[0].name,'Produto A');assert.equal(b.items[0].name,'Produto A');assert.equal(calls,1);
  const doc=createDocument();const loop=addNode(doc,createNode('query_loop',{source:'catalog.products',query_json:'{"category":"A"}',limit:10}));addNode(doc,createNode('dynamic_text',{path:'item.name'}),loop.id);
  const rendered=await renderDocumentAsync(doc,{runtime:{queryCache:cache}});assert.match(rendered.html,/Produto A/);unregisterDataSource('catalog.products');
});

test('permissões distinguem conteúdo, design e publicação',()=>{
  const content=createEditorPolicy({role:'content_editor'}),designer=createEditorPolicy({role:'designer'}),admin=createEditorPolicy({role:'admin'});
  assert.equal(can(content,'content.edit'),true);assert.equal(can(content,'style.edit'),false);assert.equal(can(designer,'page.publish'),false);assert.equal(can(admin,'custom_code.edit'),true);
});

test('i18n traduz propriedades por locale sem alterar origem',()=>{
  const doc=createDocument({title:'Página'});const heading=addNode(doc,createNode('heading',{text:'Olá'}));const translated=setNodeTranslation(doc,'en-US',heading.id,{text:'Hello'});const localized=localizeDocument(translated,'en-US');
  assert.equal(localized.builder.nodes[heading.id].props.text,'Hello');assert.equal(doc.builder.nodes[heading.id].props.text,'Olá');
});

test('Project Package exporta e importa site completo',()=>{
  const page=createDocument({title:'Home'});const pack=createProjectPackage({name:'Site',pages:[{slug:'home',document:page}],assets:{media:[{id:'m1'}]}});assert.equal(pack.schema,PROJECT_PACKAGE_SCHEMA);assert.equal(validateProjectPackage(pack).valid,true);const restored=importProjectPackage(exportProjectPackage(pack));assert.equal(restored.pages[0].document.schema,'argws-visual-builder/v3');
});

test('operações incrementais aplicam patch e revisão',()=>{
  const doc=createDocument();const node=addNode(doc,createNode('text',{text:'A'}));const op=createOperation('node.props.patch',{id:node.id,patch:{text:'B'}});const next=applyOperation(doc,op);assert.equal(next.builder.nodes[node.id].props.text,'B');assert.equal(next.project.collaboration.revision,1);
});

test('Asset Library e fontes customizadas geram CSS seguro',()=>{
  const lib=new AssetLibrary();lib.add('fonts',{family:'Minha Fonte',url:'https://cdn.example.com/font.woff2',weight:'400'});const css=fontFaceCss(lib.toJSON());assert.match(css,/@font-face/);assert.match(css,/Minha Fonte/);assert.doesNotMatch(css,/<script/i);
});

test('Custom Code só permite JavaScript trusted com opt-in explícito',()=>{
  const snippets=[{id:'x',type:'js',placement:'body-end',trusted:true,code:'window.x=1'}];assert.equal(renderCustomCode(snippets,{placement:'body-end',allowTrustedCode:false}),'');assert.match(renderCustomCode(snippets,{placement:'body-end',allowTrustedCode:true}),/<script/);
});

test('embeds são gerados para stacks universais',()=>{
  for(const target of ['html','blade','php','jinja2','twig','vue','react','svelte']){const out=createEmbedSnippet(target,{documentUrl:'/api/pages/home'});assert.equal(typeof out,'string');assert.ok(out.length>30, target);}
  assert.match(createEmbedSnippet('blade'),/asset\(/);assert.match(createEmbedSnippet('vue'),/<template>/);
});

test('Form Builder suporta tipos avançados e múltiplas etapas',()=>{
  const fields=parseFormFieldsText('Nome | name | text | required | | 1\nPlano | plan | select | required | Pro,Business | 2\nContrato | contract | file | | | 2');const schema=normalizeFormSchema({fields,actions:[{type:'event'}]});assert.equal(schema.steps,2);assert.equal(schema.fields[1].options.length,2);assert.equal(validateFormValues(schema,{name:'Wallace',plan:'Pro'}).valid,true);
  const doc=createDocument();addNode(doc,createNode('form',{title:'Cadastro',fields_text:'Nome | name | text | required | | 1\nPlano | plan | select | required | Pro,Business | 2',multi_step:true}));const {html}=renderDocument(doc);assert.match(html,/data-upb-form-step="2"/);assert.match(html,/data-upb-form-next/);assert.match(html,/data-upb-form-prev/);
});

test('catálogo universal inclui widgets estruturais modernos',()=>{
  for(const type of ['query_loop','nested_tabs','nested_accordion','mega_menu','floating_bar','table_of_contents','search','share_buttons','lottie','hotspot','flip_box','slides','host_component','login_form','cookie_consent'])assert.ok(WIDGETS[type],type);
  assert.ok(Object.keys(WIDGETS).length>=65);
});

test('Scheduler Pro continua recebendo contrato V2 com metadata universal v3',()=>{
  const doc=createDocument();addNode(doc,createNode('nested_tabs'));addNode(doc,createNode('booking',{title:'Agenda'}));const compiled=compileSchedulerProV2(doc);assert.equal(compiled.version,2);assert.equal(compiled.builder.schema,'argws-visual-builder/v3');assert.ok(compiled.blocks.some(row=>row.type==='booking'));
});

test('Host Services desacoplam integrações de infraestrutura e negócio',async()=>{
  const sdk=await import('../src/index.js');
  sdk.registerHostService('mail.send',async({payload})=>({queued:true,to:payload.to}));
  const result=await sdk.invokeHostService('mail.send',{to:'cliente@example.com'});assert.deepEqual(result,{queued:true,to:'cliente@example.com'});sdk.unregisterHostService('mail.send');
});

test('plugin universal registra e remove widget, action, data source e serviço',async()=>{
  const sdk=await import('../src/index.js');
  sdk.registerBuilderPlugin({id:'argws.demo',name:'Demo',version:'1',widgets:{demo_widget:{label:'Demo',defaults:{text:'ok'},fields:[]}},actions:{demo_action:async()=>42},dataSources:{'demo.rows':async()=>[{id:1}]},services:{'demo.service':async()=>({ok:true})}});
  assert.ok(sdk.WIDGETS.demo_widget);assert.equal(sdk.listBuilderPlugins()[0].id,'argws.demo');assert.deepEqual(await sdk.executeDataQuery('demo.rows'),[{id:1}]);assert.deepEqual(await sdk.invokeHostService('demo.service'),{ok:true});assert.equal(sdk.unregisterBuilderPlugin('argws.demo'),true);assert.equal(sdk.WIDGETS.demo_widget,undefined);
});

test('widgets Commerce são provider-driven e não dependem de WooCommerce',()=>{
  const doc=createDocument();addNode(doc,createNode('commerce_product_grid',{title:'Loja',component:'commerce.product_grid'}));const {html}=renderDocument(doc,{context:{hostComponents:{'commerce.product_grid':({props})=>`<div data-catalog>${props.title}</div>`}}});assert.match(html,/data-catalog/);assert.match(html,/Loja/);
});

test('standalone assíncrono resolve Data Sources antes de exportar',async()=>{
  const sdk=await import('../src/index.js');sdk.registerDataSource('async.rows',async()=>[{name:'SSR Item'}]);const doc=createDocument();const loop=addNode(doc,createNode('query_loop',{source:'async.rows'}));addNode(doc,createNode('dynamic_text',{path:'item.name'}),loop.id);const html=await sdk.exportStandaloneHtmlAsync(doc);assert.match(html,/SSR Item/);sdk.unregisterDataSource('async.rows');
});

test('Submission Store coleta, lista e exporta formulários sem depender de WordPress',async()=>{
  const sdk=await import('../src/index.js');const store=new sdk.MemorySubmissionStore();const [action]=await sdk.executeActions([{type:'collect_submission',form_id:'lead'}],{name:'Cliente',email:'a@b.com'},{submissionStore:store});assert.equal(action.result.form_id,'lead');const rows=await store.list({form_id:'lead'});assert.equal(rows.length,1);assert.match(sdk.submissionsToCsv(rows),/Cliente/);
});

test('Interactions e custom attributes são preservados com whitelist segura',()=>{
  const doc=createDocument();const node=addNode(doc,createNode('button',{label:'Abrir',url:'#'},{interactions:[{event:'click',actions:[{type:'open_popup',target:'lead'}]}],meta:{attributes:{'data-track':'cta','aria-label':'CTA',onclick:'alert(1)'}}}));const {html}=renderDocument(doc);assert.match(html,/data-upb-interactions=/);assert.match(html,/data-track="cta"/);assert.match(html,/aria-label="CTA"/);assert.doesNotMatch(html,/onclick=/);
});


test('wrapper HTML Scheduler Pro vira superfície editável e republica sem alterar o HTML',()=>{
  const html='<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="scheduler-pro-template" content="teste-html"><meta name="scheduler-pro-content-version" content="2"><meta name="scheduler-pro-surface" content="landing"><title>Teste</title><style>@media(max-width:680px){body{margin:0}}</style></head><body><main>OK</main></body></html>';
  const wrapper={render_mode:'HTML',contract:'scheduler-pro-html-template/v1',template_key:'teste-html',surface:'LANDING',content_version:2,html_document:html};
  const doc=documentFromSchedulerHtmlWrapper(wrapper);
  assert.equal(doc.mode,'HTML');assert.equal(doc.builder.root_ids.length,0);assert.equal(doc.html.document,html);
  const compiled=toSchedulerProContent(doc);
  assert.equal(compiled.render_mode,'HTML');assert.equal(compiled.template_key,'teste-html');assert.equal(compiled.html_document,html);
});

test('SchedulerProAdapter expõe recuperação de emergência sem acoplar adapters genéricos',async()=>{
  const adapter=new SchedulerProAdapter({slug:'home',token:()=>''});
  const calls=[];adapter.request=async(path,init)=>{calls.push([path,init?.method]);return{ok:true};};
  await adapter.emergencyRollback();await adapter.emergencyBlank();
  assert.deepEqual(calls,[['/landing-pages/home/emergency-rollback','POST'],['/landing-pages/home/emergency-blank','POST']]);
});

test('tema do editor possui modo claro e scrollbars discretas',async()=>{
  const {EDITOR_CSS}=await import('../src/editor-styles.js');
  assert.match(EDITOR_CSS,/data-editor-theme="light"/);assert.match(EDITOR_CSS,/::-webkit-scrollbar\{width:5px;height:5px\}/);assert.match(EDITOR_CSS,/@media\(max-width:980px\)/);
});

test('2.2 mantém guias laterais persistentes e painéis com scroll independente', async()=>{
  const {EDITOR_CSS}=await import('../src/editor-styles.js');
  assert.match(EDITOR_CSS,/\.tabs\{[^}]*flex:0 0 40px/);
  assert.match(EDITOR_CSS,/\.panel-scroll\{[^}]*height:0;flex:1 1 auto/);
  assert.match(EDITOR_CSS,/\.inspector-head\{[^}]*flex:0 0 auto/);
});

test('toolbar 2.2 usa controles compactos por ícone e mantém ações essenciais', async()=>{
  const fs=await import('node:fs/promises');
  const source=await fs.readFile(new URL('../src/editor.js',import.meta.url),'utf8');
  for(const action of ['page-settings','elements-panel','properties-panel','audit','import','export-json','export-html','preview','save','publish','close']) assert.match(source,new RegExp(`data-action=\\"?${action}|iconButton\\('${action}'`));
  assert.match(source,/class="btn icon device-btn/);
  assert.match(source,/ARGWS Visual Builder/);
});

test('HTML Surface importado pode medir altura no editor sem habilitar scripts',()=>{
  const html='<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="scheduler-pro-template" content="altura-teste"><meta name="scheduler-pro-content-version" content="2"><meta name="scheduler-pro-surface" content="landing"></head><body><div style="height:1800px">Teste</div></body></html>';
  const doc=documentFromSchedulerHtmlWrapper({render_mode:'HTML',contract:'scheduler-pro-html-template/v1',template_key:'altura-teste',surface:'LANDING',content_version:2,html_document:html});
  const rendered=renderDocument(doc,{context:{editor:true}});
  assert.match(rendered.html,/sandbox="allow-forms allow-same-origin"/);
  assert.match(rendered.html,/data-upb-html-surface-frame/);
  assert.doesNotMatch(rendered.html,/allow-scripts allow-same-origin/);
});

test('HTML Surface mostra conteúdo com reveal no editor sem alterar o HTML publicado',()=>{
  const html='<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="scheduler-pro-template" content="reveal-teste"><meta name="scheduler-pro-content-version" content="2"><meta name="scheduler-pro-surface" content="landing"><style>.reveal{opacity:0;transform:translateY(20px)}@media(max-width:680px){body{margin:0}}</style></head><body><section class="reveal">Conteúdo</section></body></html>';
  const doc=documentFromSchedulerHtmlWrapper({render_mode:'HTML',contract:'scheduler-pro-html-template/v1',template_key:'reveal-teste',surface:'LANDING',content_version:2,html_document:html});
  const editor=renderDocument(doc,{context:{editor:true}});
  assert.match(editor.html,/data-argws-editor-surface/);
  assert.match(editor.html,/\.reveal,\[data-reveal\]/);
  const compiled=toSchedulerProContent(doc);
  assert.equal(compiled.html_document,html);
  assert.doesNotMatch(compiled.html_document,/data-argws-editor-surface/);
});

test('identidade visual AVB é distribuída junto do pacote', async()=>{
  const fs=await import('node:fs/promises');
  for(const name of ['argws-visual-builder-symbol-64.png','argws-visual-builder-symbol-192.png','argws-visual-builder-logo-1024.png','argws-visual-builder-logo-dark.png','brand-tokens.json']){
    const stat=await fs.stat(new URL(`../assets/brand/${name}`,import.meta.url));
    assert.ok(stat.size>100,name);
  }
});

test('instalador Scheduler Pro 2.3.2 copia assets de branding e Project Workspace', async()=>{
  const fs=await import('node:fs/promises');
  const source=await fs.readFile(new URL('../integrations/scheduler-pro/install.py',import.meta.url),'utf8');
  assert.match(source,/\['src', 'styles', 'assets'\]/);
  assert.match(source,/ARGWS Visual Builder Universal \{PACKAGE_VERSION\}/);
});
