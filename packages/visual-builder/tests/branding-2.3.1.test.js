import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '..');
const editorCssSource = fs.readFileSync(path.join(root, 'src/editor-styles.js'), 'utf8');
const projectWorkspaceSource = fs.readFileSync(path.join(root, 'src/project-workspace.js'), 'utf8');
const rendererSource = fs.readFileSync(path.join(root, 'src/renderer.js'), 'utf8');
const pageRendererSource = fs.readFileSync(path.join(root, 'src/page-renderer.js'), 'utf8');
const brandTokens = JSON.parse(fs.readFileSync(path.join(root, 'assets/brand/brand-tokens.json'), 'utf8'));

function rgb(hex) {
  const clean = hex.replace('#', '');
  return [0, 2, 4].map(i => parseInt(clean.slice(i, i + 2), 16) / 255);
}
function luminance(hex) {
  const channels = rgb(hex).map(c => c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
  return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
}
function contrast(a, b) {
  const [l1, l2] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (l1 + 0.05) / (l2 + 0.05);
}

test('2.3.1 usa exatamente a paleta oficial AVB', () => {
  assert.equal(brandTokens.version, '2.3.1');
  assert.deepEqual(brandTokens.palette, {
    deep_navy: '#0B1020',
    charcoal: '#1E2435',
    cyan: '#1AD5E8',
    electric_blue: '#2563FF',
    violet: '#7A4DFF',
    light_gray: '#E9EEF5',
  });
  for (const value of Object.values(brandTokens.palette)) assert.match(editorCssSource, new RegExp(value.replace('#', '#'), 'i'));
});

test('tipografia do produto usa Space Grotesk em headings e Inter no corpo', () => {
  assert.match(editorCssSource, /--font-heading:var\(--avb-font-heading,"Space Grotesk",Inter/);
  assert.match(editorCssSource, /--font-body:var\(--avb-font-body,Inter/);
  assert.match(editorCssSource, /\.inspector-title\{font-family:var\(--font-heading\)/);
  assert.match(projectWorkspaceSource, /\.hero h1\{font-family:var\(--font-heading\)/);
});

test('tipografia AVB não é imposta ao documento renderizado', () => {
  assert.equal(rendererSource.includes('Space Grotesk'), false);
  assert.equal(pageRendererSource.includes('Space Grotesk'), false);
});

test('light e dark mantêm contraste AA nos textos essenciais', () => {
  const pairs = [
    ['#F7F9FC', '#0B1020'],
    ['#D9E1EC', '#121827'],
    ['#A6B2C4', '#121827'],
    ['#A6B2C4', '#1E2435'],
    ['#0B1020', '#FFFFFF'],
    ['#1E2435', '#FFFFFF'],
    ['#5B677A', '#FFFFFF'],
    ['#5B677A', '#F6F8FB'],
    ['#FFFFFF', '#2563FF'],
    ['#FFFFFF', '#7A4DFF'],
  ];
  for (const [fg, bg] of pairs) {
    assert.ok(contrast(fg, bg) >= 4.5, `${fg} sobre ${bg}: ${contrast(fg, bg).toFixed(2)}`);
  }
});

test('ações primárias evitam texto branco diretamente sobre cyan', () => {
  assert.match(editorCssSource, /\.btn\.primary\{background:var\(--accent\)/);
  assert.doesNotMatch(editorCssSource, /\.btn\.primary\{background:var\(--brand-gradient\)/);
});

test('Project Workspace possui light/dark persistente e usa o mesmo tema do editor', () => {
  assert.match(projectWorkspaceSource, /data-project-theme="dark"/);
  assert.match(projectWorkspaceSource, /data-action="theme-toggle"/);
  assert.match(projectWorkspaceSource, /argws_visual_builder_editor_theme/);
  assert.match(projectWorkspaceSource, /editor\.setAttribute\('theme',this\._theme\)/);
});

test('UI AVB não usa pesos tipográficos acima de 700', () => {
  const combined = `${editorCssSource}\n${projectWorkspaceSource}`;
  const weights = [...combined.matchAll(/font-weight:(\d{3})/g)].map(match => Number(match[1]));
  assert.ok(weights.length > 0);
  assert.ok(Math.max(...weights) <= 700, `peso máximo encontrado: ${Math.max(...weights)}`);
});
