import { deepClone, normalizeDocument } from './model.js';
import { createSiteKit } from './site-kit.js';

export const PROJECT_PACKAGE_SCHEMA = 'argws-visual-builder-project/v1';

export function createProjectPackage({ name='Projeto ARGWS', pages=[], siteKit=null, assets={}, templates=[], settings={}, metadata={} } = {}) {
  return { schema:PROJECT_PACKAGE_SCHEMA, version:1, name:String(name), created_at:new Date().toISOString(), settings:deepClone(settings), metadata:deepClone(metadata), assets:deepClone(assets), templates:deepClone(templates), site_kit:siteKit || createSiteKit({name}), pages:(pages||[]).map(row => ({ slug:String(row.slug || 'home'), title:String(row.title || row.document?.title || 'Página'), document:normalizeDocument(row.document || row) })) };
}

export function validateProjectPackage(value) {
  const errors=[]; if(!value||typeof value!=='object')errors.push('Pacote deve ser um objeto.'); else { if(value.schema!==PROJECT_PACKAGE_SCHEMA)errors.push('Schema de pacote inválido.'); if(!Array.isArray(value.pages))errors.push('pages deve ser uma lista.'); }
  return { valid:!errors.length, errors };
}

export function normalizeProjectPackage(value) {
  const report=validateProjectPackage(value); if(!report.valid){const error=new Error(report.errors.join(' '));error.code='UPB_PROJECT_PACKAGE_INVALID';throw error;}
  return createProjectPackage({ ...value, name:value.name, pages:value.pages, siteKit:value.site_kit, assets:value.assets, templates:value.templates, settings:value.settings, metadata:value.metadata });
}

export function exportProjectPackage(value, pretty=true) { return JSON.stringify(normalizeProjectPackage(value), null, pretty?2:0); }
export function importProjectPackage(value) { const parsed=typeof value==='string'?JSON.parse(value):value;return normalizeProjectPackage(parsed); }
