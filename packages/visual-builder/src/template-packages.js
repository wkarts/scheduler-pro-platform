import { createHtmlDocument } from './model.js';
import { createProject, createProjectPage } from './project.js';

const ZIP_EOCD = 0x06054b50;
const ZIP_CENTRAL = 0x02014b50;
const ZIP_LOCAL = 0x04034b50;
const MAX_ENTRIES = 64;
const MAX_TOTAL_UNCOMPRESSED = 16 * 1024 * 1024;
const MAX_ENTRY_UNCOMPRESSED = 8 * 1024 * 1024;

function asUint8Array(value) {
  if (value instanceof Uint8Array) return value;
  if (value instanceof ArrayBuffer) return new Uint8Array(value);
  if (ArrayBuffer.isView(value)) return new Uint8Array(value.buffer, value.byteOffset, value.byteLength);
  throw new TypeError('Conteúdo binário inválido.');
}

async function sourceBytes(source) {
  if (source instanceof Uint8Array || source instanceof ArrayBuffer || ArrayBuffer.isView(source)) return asUint8Array(source);
  if (source && typeof source.arrayBuffer === 'function') return new Uint8Array(await source.arrayBuffer());
  throw new TypeError('Informe File, Blob, ArrayBuffer ou Uint8Array.');
}

function findEndOfCentralDirectory(bytes) {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const minimum = Math.max(0, bytes.length - 0xffff - 22);
  for (let offset = bytes.length - 22; offset >= minimum; offset -= 1) {
    if (view.getUint32(offset, true) === ZIP_EOCD) return offset;
  }
  throw new Error('ZIP inválido: diretório central não encontrado.');
}

async function inflateRaw(compressed, expectedSize) {
  if (typeof DecompressionStream !== 'function') throw new Error('Este navegador não oferece descompressão ZIP nativa.');
  const stream = new Blob([compressed]).stream().pipeThrough(new DecompressionStream('deflate-raw'));
  const result = new Uint8Array(await new Response(stream).arrayBuffer());
  if (expectedSize != null && expectedSize >= 0 && result.length !== expectedSize) {
    throw new Error('ZIP inválido: tamanho descompactado divergente.');
  }
  return result;
}

/** Lê ZIPs comuns (stored/deflate) sem dependência externa. */
export async function readZipEntries(source, options = {}) {
  const bytes = await sourceBytes(source);
  const maxEntries = Number(options.maxEntries || MAX_ENTRIES);
  const maxTotal = Number(options.maxTotalUncompressed || MAX_TOTAL_UNCOMPRESSED);
  const maxEntry = Number(options.maxEntryUncompressed || MAX_ENTRY_UNCOMPRESSED);
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const eocd = findEndOfCentralDirectory(bytes);
  const totalEntries = view.getUint16(eocd + 10, true);
  const centralOffset = view.getUint32(eocd + 16, true);
  if (totalEntries > maxEntries) throw new Error(`ZIP possui entradas demais (${totalEntries}).`);

  const decoder = new TextDecoder('utf-8');
  const entries = new Map();
  let cursor = centralOffset;
  let totalUncompressed = 0;

  for (let index = 0; index < totalEntries; index += 1) {
    if (cursor + 46 > bytes.length || view.getUint32(cursor, true) !== ZIP_CENTRAL) throw new Error('ZIP inválido: entrada do diretório central corrompida.');
    const flags = view.getUint16(cursor + 8, true);
    const method = view.getUint16(cursor + 10, true);
    const compressedSize = view.getUint32(cursor + 20, true);
    const uncompressedSize = view.getUint32(cursor + 24, true);
    const nameLength = view.getUint16(cursor + 28, true);
    const extraLength = view.getUint16(cursor + 30, true);
    const commentLength = view.getUint16(cursor + 32, true);
    const localOffset = view.getUint32(cursor + 42, true);
    const nameBytes = bytes.slice(cursor + 46, cursor + 46 + nameLength);
    const name = decoder.decode(nameBytes).replace(/\\/g, '/');
    cursor += 46 + nameLength + extraLength + commentLength;

    if (!name || name.endsWith('/')) continue;
    if (name.includes('../') || name.startsWith('/') || /^[A-Za-z]:\//.test(name)) throw new Error(`ZIP contém caminho inseguro: ${name}`);
    if (flags & 0x1) throw new Error(`ZIP criptografado não é suportado: ${name}`);
    if (uncompressedSize > maxEntry) throw new Error(`Arquivo do ZIP excede o limite: ${name}`);
    totalUncompressed += uncompressedSize;
    if (totalUncompressed > maxTotal) throw new Error('ZIP excede o limite total de descompactação.');
    if (localOffset + 30 > bytes.length || view.getUint32(localOffset, true) !== ZIP_LOCAL) throw new Error(`ZIP inválido: cabeçalho local ausente para ${name}.`);
    const localNameLength = view.getUint16(localOffset + 26, true);
    const localExtraLength = view.getUint16(localOffset + 28, true);
    const dataStart = localOffset + 30 + localNameLength + localExtraLength;
    const dataEnd = dataStart + compressedSize;
    if (dataEnd > bytes.length) throw new Error(`ZIP truncado: ${name}.`);
    const compressed = bytes.slice(dataStart, dataEnd);
    let output;
    if (method === 0) output = compressed;
    else if (method === 8) output = await inflateRaw(compressed, uncompressedSize);
    else throw new Error(`Método ZIP não suportado (${method}) em ${name}.`);
    entries.set(name, output);
  }
  return entries;
}

function entryByBasename(entries, basename) {
  const wanted = String(basename).toLowerCase();
  for (const [name, value] of entries) if (name.split('/').pop()?.toLowerCase() === wanted) return value;
  return null;
}

function metaContent(html, name) {
  const escaped = String(name).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const patterns = [
    new RegExp(`<meta\\s+[^>]*name=["']${escaped}["'][^>]*content=["']([^"']*)["'][^>]*>`, 'i'),
    new RegExp(`<meta\\s+[^>]*content=["']([^"']*)["'][^>]*name=["']${escaped}["'][^>]*>`, 'i'),
  ];
  for (const pattern of patterns) { const match = String(html).match(pattern); if (match) return match[1].trim(); }
  return '';
}

function htmlTitle(html) { return String(html).match(/<title[^>]*>([\s\S]*?)<\/title>/i)?.[1]?.replace(/<[^>]+>/g, '').trim() || ''; }
function cssVariable(html, key) { const match = String(html).match(new RegExp(`--${key}\\s*:\\s*([^;}{]+)`, 'i')); return match?.[1]?.trim() || ''; }

export function schedulerHtmlWrapper(htmlDocument, expectedSurface = null) {
  const html = String(htmlDocument || '');
  const declared = metaContent(html, 'scheduler-pro-surface').toLowerCase();
  const surface = declared === 'booking' || declared === 'public-booking' || declared === 'agendamento' ? 'BOOKING' : (declared === 'login' || declared === 'sign-in' ? 'LOGIN' : 'LANDING');
  const expected = String(expectedSurface || '').toUpperCase();
  if (expected && expected !== surface) throw new Error(`O HTML declara ${surface}, mas a importação exige ${expected}.`);
  const key = metaContent(html, 'scheduler-pro-template');
  const contentVersion = Number(metaContent(html, 'scheduler-pro-content-version') || 2);
  if (!/^[-a-z0-9]{2,120}$/i.test(key)) throw new Error('HTML do Scheduler Pro sem meta scheduler-pro-template válida.');
  if (!html.match(/<!doctype\s+html/i) || !html.match(/<html[\s>]/i) || !html.match(/<body[\s>]/i)) throw new Error('O template precisa ser um documento HTML completo.');
  return {
    render_mode: 'HTML',
    contract: 'scheduler-pro-html-template/v1',
    template_key: key.toLowerCase(),
    surface,
    content_version: surface === 'LOGIN' ? Math.max(1, contentVersion || 1) : Math.max(2, contentVersion || 2),
    html_document: html,
  };
}

function applyExtractedDesign(doc, html) {
  const mapping = {
    primary: 'page-primary', secondary: 'page-secondary', accent: 'page-accent', background: 'page-bg', text: 'page-text',
  };
  for (const [target, source] of Object.entries(mapping)) { const value = cssVariable(html, source); if (value) doc.global_styles[target] = value; }
  const radius = cssVariable(html, 'page-radius');
  if (radius) { const value = Number.parseFloat(radius); if (Number.isFinite(value)) doc.global_styles.radius = value; }
  const max = cssVariable(html, 'max');
  if (max) { const value = Number.parseFloat(max); if (Number.isFinite(value)) { doc.settings.content_width = value; doc.global_styles.content_width = value; } }
  doc.seo.title = htmlTitle(html);
  doc.seo.description = metaContent(html, 'description');
}

export function documentFromHtmlSurface(htmlDocument, options = {}) {
  const html = String(htmlDocument || '');
  let wrapper = null;
  try { wrapper = schedulerHtmlWrapper(html, options.expectedSurface || null); } catch (error) { if (options.requireScheduler) throw error; }
  const title = options.title || wrapper?.template_key || htmlTitle(html) || 'Página HTML importada';
  const doc = createHtmlDocument({
    title,
    htmlDocument: html,
    surface: wrapper?.surface || String(options.surface || 'PAGE').toUpperCase(),
    contract: wrapper?.contract || 'generic-html-page/v1',
    templateKey: wrapper?.template_key || '',
    contentVersion: wrapper?.content_version || 1,
    sourceName: options.sourceName || '',
  });
  applyExtractedDesign(doc, html);
  if (options.packageMeta) {
    doc.project.integrations ||= {};
    doc.project.integrations.scheduler_pro_package = options.packageMeta;
  }
  return doc;
}

export function documentFromSchedulerHtmlWrapper(wrapper, options = {}) {
  if (!wrapper || String(wrapper.render_mode || '').toUpperCase() !== 'HTML' || typeof wrapper.html_document !== 'string') throw new Error('Wrapper HTML do Scheduler Pro inválido.');
  return documentFromHtmlSurface(wrapper.html_document, {
    ...options,
    title: options.title || wrapper.template_key || 'Template Scheduler Pro',
    expectedSurface: wrapper.surface || options.expectedSurface || null,
    requireScheduler: true,
  });
}

function schedulerPackageMeta(manifest) {
  return {
    schema: manifest.schema,
    key: manifest.package.key || '',
    name: manifest.package.name || manifest.package.key || 'Scheduler Pro',
    description: manifest.package.description || '',
    segment: manifest.package.segment || '',
    scope: manifest.package.scope || '',
    surfaces: Object.fromEntries(Object.entries(manifest.package.surfaces || {}).map(([key, value]) => [key, {
      version: value?.version ?? null,
      surface: value?.surface ?? key.toUpperCase(),
      renderer: value?.renderer ?? '',
      entry: value?.entry ?? '',
      route: value?.route ?? '',
      seo: value?.seo ?? {},
    }])),
  };
}

function schedulerSurfacePage(entries, manifest, surfaceName, options={}) {
  const descriptor = manifest.package.surfaces?.[surfaceName];
  if (!descriptor) return null;
  if (String(descriptor.renderer || '').toUpperCase() !== 'HTML') throw new Error(`Renderer ${descriptor.renderer || 'desconhecido'} ainda não é suportado por este importador.`);
  const defaults={landing:'landing.html',booking:'agendamento.html',login:'login.html'};
  const entry = String(descriptor.entry || defaults[surfaceName] || 'landing.html');
  const htmlBytes = entries.get(entry) || entryByBasename(entries, entry.split('/').pop());
  if (!htmlBytes) throw new Error(`Arquivo ${entry} não encontrado no pacote.`);
  const html = new TextDecoder('utf-8').decode(htmlBytes);
  const expectedSurface = surfaceName === 'booking' ? 'BOOKING' : (surfaceName === 'login' ? 'LOGIN' : 'LANDING');
  const wrapper = schedulerHtmlWrapper(html, expectedSurface);
  const packageMeta = schedulerPackageMeta(manifest);
  const seo = descriptor.seo || {};
  const suffix=surfaceName==='booking'?' — Agendamento':(surfaceName==='login'?' — Login':'');
  const title = seo.title || `${manifest.package.name || wrapper.template_key}${suffix}`;
  const document = documentFromHtmlSurface(html, {
    title,
    expectedSurface,
    requireScheduler:true,
    sourceName: options.sourceName || '',
    packageMeta:{...packageMeta, active_surface:surfaceName},
  });
  if (seo.title) document.seo.title = seo.title;
  if (seo.description) document.seo.description = seo.description;
  const routeDefaults={landing:'/pagina',booking:'/agendar',login:'/login'};
  const slugDefaults={landing:'pagina',booking:'agendar',login:'login'};
  const route=String(descriptor.route||routeDefaults[surfaceName]||'/pagina');
  const slug=route.replace(/^\/+|\/+$/g,'')||slugDefaults[surfaceName]||'pagina';
  return {
    page:createProjectPage({
      id:`scheduler-${surfaceName}`,
      title,
      slug,
      route,
      surface:expectedSurface,
      kind:'PAGE',
      document,
      source:{provider:'scheduler-pro',package_key:packageMeta.key,surface:surfaceName,entry},
      metadata:{template_family:packageMeta.key,template_name:packageMeta.name,descriptor},
    }),
    wrapper,
  };
}

/**
 * Importa a família inteira do Scheduler Pro como um Projeto AVB.
 * landing.html, agendamento.html e login.html viram páginas independentes de primeira classe.
 */
export async function importSchedulerProTemplateFamily(source, options = {}) {
  const entries = await readZipEntries(source, options.zip || {});
  const manifestBytes = entryByBasename(entries, 'template.json');
  if (!manifestBytes) throw new Error('Pacote Scheduler Pro sem template.json.');
  let manifest;
  try { manifest = JSON.parse(new TextDecoder('utf-8').decode(manifestBytes)); } catch { throw new Error('template.json inválido.'); }
  if (manifest?.schema !== 'scheduler-pro-template-package/v1' || !manifest?.package?.surfaces) throw new Error('Formato de pacote não suportado. Esperado scheduler-pro-template-package/v1.');
  const pages=[];
  const wrappers={};
  for (const surfaceName of ['landing','booking','login']) {
    const result=schedulerSurfacePage(entries,manifest,surfaceName,options);
    if(!result) continue;
    pages.push(result.page);
    wrappers[surfaceName]=result.wrapper;
  }
  if(!pages.length) throw new Error('O pacote não possui páginas HTML suportadas.');
  const meta=schedulerPackageMeta(manifest);
  const project=createProject({
    id:`scheduler-package-${meta.key || Date.now()}`,
    name:meta.name,
    pages,
    activePageId:pages.find(page=>page.surface==='LANDING')?.id || pages[0].id,
    metadata:{source_name:options.sourceName||'',description:meta.description,segment:meta.segment,template_family:meta.key},
    integrations:{scheduler_pro_package:meta},
  });
  return {project,manifest,wrappers,pages:project.pages};
}

/**
 * Compatibilidade com integrações 2.1/2.2: retorna uma única página selecionada,
 * porém internamente usa a família multi-página do AVB 2.3.
 */
export async function importSchedulerProTemplatePackage(source, options = {}) {
  const family=await importSchedulerProTemplateFamily(source,options);
  const surfaceName=String(options.surface||'landing').toLowerCase();
  const wanted=surfaceName==='booking'?'BOOKING':(surfaceName==='login'?'LOGIN':'LANDING');
  const page=family.project.pages.find(item=>item.surface===wanted);
  if(!page) throw new Error(`Superfície ${surfaceName} não encontrada no pacote.`);
  return {
    document:page.document,
    page,
    project:family.project,
    manifest:family.manifest,
    wrapper:family.wrappers[surfaceName],
    surface:surfaceName,
  };
}

export function isSchedulerProTemplatePackageName(name) { return /\.zip$/i.test(String(name || '')); }
