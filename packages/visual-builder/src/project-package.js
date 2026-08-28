import { deepClone } from './model.js';
import { createSiteKit } from './site-kit.js';
import { createProject, createProjectPage, normalizeProject, PROJECT_SCHEMA } from './project.js';

export const PROJECT_PACKAGE_SCHEMA = 'argws-visual-builder-project-package/v2';
export const LEGACY_PROJECT_PACKAGE_SCHEMAS = new Set(['argws-visual-builder-project/v1','argws-visual-builder-project-package/v1',PROJECT_SCHEMA,PROJECT_PACKAGE_SCHEMA]);

export function createProjectPackage({ name='Projeto ARGWS', pages=[], siteKit=null, assets={}, templates=[], settings={}, metadata={}, components=[], popups=[], integrations={} } = {}) {
  const project=createProject({name,pages,siteKit,assets,templates,settings,metadata,components,popups,integrations});
  return {
    schema:PROJECT_PACKAGE_SCHEMA,
    version:2,
    exported_at:new Date().toISOString(),
    project,
    // Campos espelhados ajudam integrações simples/legadas sem alterar o core.
    name:project.name,
    settings:deepClone(project.settings),
    metadata:deepClone(project.metadata),
    assets:deepClone(project.assets),
    templates:deepClone(project.templates),
    components:deepClone(project.components),
    popups:deepClone(project.popups),
    site_kit:deepClone(project.site_kit || createSiteKit({name:project.name})),
    pages:project.pages.map(page=>createProjectPage(page)),
  };
}

export function validateProjectPackage(value) {
  const errors=[];
  if(!value||typeof value!=='object') errors.push('Pacote deve ser um objeto.');
  else {
    const schema=String(value.schema||'');
    if(!LEGACY_PROJECT_PACKAGE_SCHEMAS.has(schema)) errors.push('Schema de pacote inválido.');
    const pages=value.project?.pages || value.pages;
    if(!Array.isArray(pages)) errors.push('pages deve ser uma lista.');
  }
  return { valid:!errors.length, errors };
}

export function normalizeProjectPackage(value) {
  const report=validateProjectPackage(value);
  if(!report.valid){const error=new Error(report.errors.join(' '));error.code='AVB_PROJECT_PACKAGE_INVALID';throw error;}
  const project=normalizeProject(value.project || {
    schema:PROJECT_SCHEMA,
    name:value.name,
    pages:value.pages,
    site_kit:value.site_kit,
    assets:value.assets,
    templates:value.templates,
    components:value.components,
    popups:value.popups,
    settings:value.settings,
    metadata:value.metadata,
    integrations:value.integrations,
  });
  return createProjectPackage({
    name:project.name,
    pages:project.pages,
    siteKit:project.site_kit,
    assets:project.assets,
    templates:project.templates,
    components:project.components,
    popups:project.popups,
    settings:project.settings,
    metadata:project.metadata,
    integrations:project.integrations,
  });
}

export function exportProjectPackage(value, pretty=true) { return JSON.stringify(normalizeProjectPackage(value), null, pretty?2:0); }
export function importProjectPackage(value) { const parsed=typeof value==='string'?JSON.parse(value):value;return normalizeProjectPackage(parsed); }
