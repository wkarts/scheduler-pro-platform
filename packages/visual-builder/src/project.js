import { createDocument, deepClone, normalizeDocument, uid } from './model.js';

export const PROJECT_SCHEMA = 'argws-visual-builder-project/v2';
export const PROJECT_VERSION = 2;

export function normalizeSlug(value, fallback='pagina') {
  const slug=String(value||'').trim().replace(/^\/+|\/+$/g,'').toLowerCase()
    .normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-z0-9/_-]+/g,'-').replace(/-+/g,'-');
  return slug || fallback;
}

export function createProjectPage({
  id=null,
  title='Nova página',
  slug='pagina',
  route=null,
  surface='PAGE',
  kind='PAGE',
  document=null,
  status='DRAFT',
  metadata={},
  source=null,
}={}) {
  const normalizedDocument=normalizeDocument(document || createDocument({title}));
  const pageSurface=String(surface || normalizedDocument.surface || 'PAGE').toUpperCase();
  normalizedDocument.surface=pageSurface;
  return {
    id:String(id || uid('page')),
    type:'page',
    kind:String(kind || 'PAGE').toUpperCase(),
    title:String(title || normalizedDocument.title || 'Página'),
    slug:normalizeSlug(slug, 'pagina'),
    route:String(route || `/${normalizeSlug(slug,'pagina')}`),
    surface:pageSurface,
    status:String(status || 'DRAFT').toUpperCase(),
    document:normalizedDocument,
    source:source && typeof source==='object' ? deepClone(source) : null,
    metadata:metadata && typeof metadata==='object' ? deepClone(metadata) : {},
  };
}

export function createProject({
  id=null,
  name='Projeto ARGWS',
  pages=[],
  activePageId=null,
  settings={},
  assets={},
  templates=[],
  components=[],
  popups=[],
  siteKit=null,
  metadata={},
  integrations={},
}={}) {
  const normalizedPages=(pages||[]).map(row=>createProjectPage(row?.document ? row : {document:row}));
  if(!normalizedPages.length) normalizedPages.push(createProjectPage({id:'home',title:'Home',slug:'home',route:'/',document:createDocument({title:'Home'})}));
  const wanted=String(activePageId||'');
  const active=normalizedPages.some(row=>row.id===wanted) ? wanted : normalizedPages[0].id;
  return {
    schema:PROJECT_SCHEMA,
    version:PROJECT_VERSION,
    id:String(id || uid('project')),
    type:'project',
    name:String(name || 'Projeto ARGWS'),
    active_page_id:active,
    pages:normalizedPages,
    settings:settings&&typeof settings==='object'?deepClone(settings):{},
    assets:assets&&typeof assets==='object'?deepClone(assets):{},
    templates:Array.isArray(templates)?deepClone(templates):[],
    components:Array.isArray(components)?deepClone(components):[],
    popups:Array.isArray(popups)?deepClone(popups):[],
    site_kit:siteKit&&typeof siteKit==='object'?deepClone(siteKit):null,
    integrations:integrations&&typeof integrations==='object'?deepClone(integrations):{},
    metadata:metadata&&typeof metadata==='object'?deepClone(metadata):{},
  };
}

export function normalizeProject(input) {
  if(!input || typeof input!=='object') return createProject();
  const value=deepClone(input);
  if(value.schema===PROJECT_SCHEMA && Array.isArray(value.pages)) {
    const pages=value.pages.map(page=>createProjectPage(page));
    return createProject({
      ...value,
      pages,
      activePageId:value.active_page_id,
      siteKit:value.site_kit,
    });
  }
  // Project Package v1 e formatos equivalentes.
  if(Array.isArray(value.pages)) {
    return createProject({
      id:value.id,
      name:value.name || 'Projeto importado',
      pages:value.pages.map(row=>({
        id:row.id,
        title:row.title,
        slug:row.slug,
        route:row.route,
        surface:row.surface,
        kind:row.kind,
        status:row.status,
        metadata:row.metadata,
        source:row.source,
        document:row.document || row.content || row,
      })),
      settings:value.settings,
      assets:value.assets,
      templates:value.templates,
      components:value.components,
      popups:value.popups,
      siteKit:value.site_kit,
      metadata:value.metadata,
      integrations:value.integrations,
      activePageId:value.active_page_id,
    });
  }
  // Documento solto vira um projeto de uma única página.
  const doc=normalizeDocument(value.document || value.content || value);
  return createProject({
    name:doc.title || 'Projeto',
    pages:[createProjectPage({id:'page-1',title:doc.title||'Página',slug:'pagina',surface:doc.surface,document:doc})],
  });
}

export function projectPage(project, id) {
  const normalized=normalizeProject(project);
  return normalized.pages.find(page=>page.id===String(id)) || null;
}

export function activeProjectPage(project) {
  const normalized=normalizeProject(project);
  return projectPage(normalized, normalized.active_page_id) || normalized.pages[0] || null;
}

export function setActiveProjectPage(project, id) {
  const target=(project.pages||[]).find(page=>page.id===String(id));
  if(!target) return false;
  project.active_page_id=target.id;
  return true;
}

export function upsertProjectPage(project, page) {
  const normalized=createProjectPage(page);
  const index=(project.pages||[]).findIndex(row=>row.id===normalized.id);
  if(index>=0) project.pages[index]=normalized; else project.pages.push(normalized);
  project.active_page_id ||= normalized.id;
  return normalized;
}

export function removeProjectPage(project, id) {
  const index=(project.pages||[]).findIndex(row=>row.id===String(id));
  if(index<0) return false;
  project.pages.splice(index,1);
  if(project.active_page_id===String(id)) project.active_page_id=project.pages[0]?.id || null;
  return true;
}

export function replaceProjectPages(project, pages, {activePageId=null}={}) {
  project.pages=(pages||[]).map(row=>createProjectPage(row));
  project.active_page_id=project.pages.some(row=>row.id===activePageId)?activePageId:(project.pages[0]?.id||null);
  return project;
}

export function projectSummary(project) {
  const p=normalizeProject(project);
  return {
    schema:p.schema,
    version:p.version,
    id:p.id,
    name:p.name,
    active_page_id:p.active_page_id,
    pages:p.pages.map(page=>({id:page.id,title:page.title,slug:page.slug,route:page.route,surface:page.surface,kind:page.kind,status:page.status,mode:page.document.mode||'VISUAL'})),
  };
}
