import test from 'node:test'
import assert from 'node:assert/strict'
import { applyBindingsToHtml, normalizeBindingsManifest } from '../src/bindings-v1.js'

test('brand.logo legado classificado como text é normalizado para image', () => {
  const manifest = normalizeBindingsManifest({ bindings: { 'brand.logo': { type: 'text' } } })
  assert.equal(manifest.bindings['brand.logo'].type, 'image')
})

test('binding visual não imprime URL como texto em span legado', () => {
  const html = '<span class="brand" data-sp-bind="brand.logo">antigo</span>'
  const output = applyBindingsToHtml(html, { 'brand.logo': '/branding/scheduler-pro-symbol.png' }, { 'brand.logo': { type: 'text' } })
  assert.match(output, /<img src="\/branding\/scheduler-pro-symbol\.png" alt="">/)
  assert.doesNotMatch(output, />\/branding\/scheduler-pro-symbol\.png<\/span>/)
})

test('bindings v2 aplicam defaults de texto e imagem mesmo sem src original', () => {
  const raw={schema:'argws-bindings/v1',version:1,defaults:{'hero.title':'Título padrão','hero.image':'/img/default.png'},bindings:{'hero.title':{type:'text'},'hero.image':{type:'image'}}};
  const manifest=normalizeBindingsManifest(raw);
  const html=applyBindingsToHtml('<h1 data-sp-bind="hero.title"></h1><img data-sp-bind="hero.image">',{},manifest.bindings);
  assert.match(html,/Título padrão/);
  assert.match(html,/src="\/img\/default\.png"/);
});
