import test from 'node:test';
import assert from 'node:assert/strict';
import { normalizeDocument } from '../src/model.js';
import { toSchedulerProContent } from '../src/renderer.js';

test('save Scheduler Pro atualiza metadados legados sem reconstruir o HTML visual',()=>{
  const legacy='<!doctype html><html><head><meta name="scheduler-pro-template" content="legacy-page"><meta name="scheduler-pro-content-version" content="1"><meta name="scheduler-pro-surface" content="landing"><title>Legado</title></head><body><main class="original">Conteúdo existente</main></body></html>';
  const doc=normalizeDocument({render_mode:'HTML',contract:'scheduler-pro-html-template/v1',template_key:'legacy-page',surface:'LANDING',content_version:1,html_document:legacy});
  const payload=toSchedulerProContent(doc);
  assert.equal(payload.surface,'LANDING');
  assert.equal(payload.content_version,2);
  assert.match(payload.html_document,/name="viewport"/);
  assert.match(payload.html_document,/scheduler-pro-content-version" content="2"/);
  assert.match(payload.html_document,/<main class="original">Conteúdo existente<\/main>/);
});
