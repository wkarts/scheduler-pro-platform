import test from 'node:test';
import assert from 'node:assert/strict';
import { addNode, createDocument, createNode, normalizeDocument } from '../src/model.js';
import { HistoryStack } from '../src/history.js';
import { exportStandaloneHtml, renderDocument, toSchedulerProContent } from '../src/renderer.js';

test('migra conteúdo V2 do Scheduler Pro sem perder blocos',()=>{
  const old={version:2,global_styles:{primary:'#123456'},seo:{},blocks:[{id:'hero-1',type:'hero',props:{title:'Olá'},style:{},responsive:{desktop:{},tablet:{},mobile:{},hidden:{desktop:false,tablet:false,mobile:false}}}]};
  const doc=normalizeDocument(old);
  assert.equal(doc.builder.root_ids[0],'hero-1');
  assert.equal(doc.builder.nodes['hero-1'].props.title,'Olá');
  const compiled=toSchedulerProContent(doc);
  assert.equal(compiled.version,2);
  assert.equal(compiled.blocks[0].type,'hero');
  assert.equal(compiled.global_styles.primary,'#123456');
});

test('containers aninhados são preservados no builder e degradam com segurança no renderer legado',()=>{
  const doc=createDocument();
  const container=addNode(doc,createNode('container',{direction:'row',gap:20}));
  const heading=addNode(doc,createNode('heading',{text:'Título',level:'h2'}),container.id);
  addNode(doc,createNode('button',{label:'Ação',url:'#go'}),container.id);
  const compiled=toSchedulerProContent(doc);
  assert.equal(compiled.builder.nodes[container.id].children[0],heading.id);
  assert.deepEqual(compiled.blocks.map(b=>b.type),['title','button']);
});

test('renderer gera HTML seguro e exportável',()=>{
  const doc=createDocument();
  addNode(doc,createNode('heading',{text:'<script>alert(1)</script>',level:'h1'}));
  addNode(doc,createNode('button',{label:'Clique',url:'javascript:alert(1)'}));
  const {html}=renderDocument(doc);
  assert.match(html,/&lt;script&gt;/);
  assert.doesNotMatch(html,/href="javascript:/);
  const standalone=exportStandaloneHtml(doc);
  assert.match(standalone,/<!doctype html>/i);
  assert.match(standalone,/viewport/);
});

test('histórico suporta undo e redo',()=>{
  const h=new HistoryStack();h.reset({x:1});h.checkpoint({x:2});h.checkpoint({x:3});
  assert.equal(h.undo().x,2);assert.equal(h.undo().x,1);assert.equal(h.redo().x,2);
});

test('módulo raiz pode ser importado em ambiente Node/SSR', async()=>{
  const mod=await import('../src/index.js');
  assert.equal(typeof mod.createDocument,'function');
  assert.equal(typeof mod.ArgwsVisualBuilder,'function');
});

test('widget HTML remove tags e atributos executáveis', async()=>{
  const { conservativeHtml }=await import('../src/sanitize.js');
  const safe=conservativeHtml('<img src=x onerror=alert(1)><p style="color:red" onclick="x()">OK</p><script>alert(2)</script>');
  assert.equal(safe,'<p>OK</p>alert(2)');
});
