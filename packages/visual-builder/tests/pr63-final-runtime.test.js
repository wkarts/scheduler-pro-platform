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
