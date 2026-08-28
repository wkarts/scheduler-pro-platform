import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');

test('project workspace custom element constructor does not add attributes',()=>{
  const source=fs.readFileSync(path.join(root,'src/project-workspace.js'),'utf8');
  const match=source.match(/export class ArgwsVisualBuilderApp[\s\S]*?constructor\(\)\{([\s\S]*?)\}\n  set adapter/);
  assert.ok(match,'constructor do workspace precisa existir');
  assert.doesNotMatch(match[1],/dataset\.|setAttribute\(|className\s*=|classList\./);
  assert.match(source,/connectedCallback\(\).*dataset\.projectTheme/);
});
