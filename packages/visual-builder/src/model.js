export const SCHEMA = 'argws-visual-builder/v3';
export const LEGACY_SCHEMAS = new Set(['argws-visual-builder/v1', 'argws-visual-builder/v2', SCHEMA]);
export const DEFAULT_BREAKPOINTS = [
  { id: 'desktop', label: 'Desktop', max: null, canvas: 1180 },
  { id: 'tablet', label: 'Tablet', max: 1024, canvas: 820 },
  { id: 'mobile', label: 'Mobile', max: 680, canvas: 390 },
];
export const DEVICES = DEFAULT_BREAKPOINTS.map(item => item.id);

export function uid(prefix = 'node') {
  const random = globalThis.crypto?.randomUUID?.() || `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
  return `${prefix}-${random}`;
}

export function deepClone(value) {
  return value == null ? value : JSON.parse(JSON.stringify(value));
}

export function normalizeBreakpoints(value) {
  const rows = Array.isArray(value) ? value : DEFAULT_BREAKPOINTS;
  const result = [];
  const used = new Set();
  for (const row of rows) {
    const id = String(row?.id || '').trim().toLowerCase().replace(/[^a-z0-9_-]/g, '-');
    if (!id || used.has(id)) continue;
    const rawMax = row?.max;
    const max = rawMax == null || rawMax === '' ? null : Math.max(240, Number(rawMax) || 0);
    result.push({ id, label: String(row?.label || id), max, canvas: Math.max(240, Number(row?.canvas || (max ? Math.min(max, 1180) : 1180))) });
    used.add(id);
  }
  if (!used.has('desktop')) result.unshift(deepClone(DEFAULT_BREAKPOINTS[0]));
  if (!used.has('tablet')) result.push(deepClone(DEFAULT_BREAKPOINTS[1]));
  if (!used.has('mobile')) result.push(deepClone(DEFAULT_BREAKPOINTS[2]));
  const desktop = result.find(row => row.id === 'desktop');
  if (desktop) desktop.max = null;
  const head = result.filter(row => row.id === 'desktop');
  const rest = result.filter(row => row.id !== 'desktop').sort((a, b) => (b.max || 0) - (a.max || 0));
  return [...head, ...rest];
}

export function responsive(breakpoints = DEFAULT_BREAKPOINTS) {
  const result = { hidden: {} };
  for (const bp of normalizeBreakpoints(breakpoints)) {
    result[bp.id] = {};
    result.hidden[bp.id] = false;
  }
  return result;
}

function responsiveStates(breakpoints = DEFAULT_BREAKPOINTS) {
  const result = {};
  for (const bp of normalizeBreakpoints(breakpoints)) result[bp.id] = { hover: {}, focus: {}, active: {} };
  return result;
}

export function createNode(type, props = {}, extra = {}) {
  return normalizeNode({
    id: uid(type),
    type,
    props: deepClone(props),
    style: {},
    states: { hover: {}, focus: {}, active: {} },
    responsive: responsive(),
    responsive_states: responsiveStates(),
    bindings: {},
    conditions: [],
    interactions: [],
    motion: {},
    children: [],
    meta: {},
    ...deepClone(extra),
  });
}

export function createDocument({ title = 'Nova página', globalStyles = {}, seo = {}, nodes = [], breakpoints = DEFAULT_BREAKPOINTS } = {}) {
  const bps = normalizeBreakpoints(breakpoints);
  const nodeMap = {};
  const rootIds = [];
  for (const node of nodes) {
    const cloned = normalizeNode(node, bps);
    nodeMap[cloned.id] = cloned;
    rootIds.push(cloned.id);
  }
  return {
    schema: SCHEMA,
    version: 5,
    mode: 'VISUAL',
    surface: 'PAGE',
    html: null,
    title,
    settings: {
      content_width: 1180,
      page_layout: 'full-width',
      custom_css: '',
      language: 'pt-BR',
    },
    global_styles: {
      primary: '#3151cf', secondary: '#151c31', accent: '#6d72ef', background: '#ffffff', text: '#1d273a',
      heading_font: 'Inter', body_font: 'Inter', radius: 16, button_radius: 12, content_width: 1180,
      ...deepClone(globalStyles),
    },
    design_system: {
      breakpoints: bps,
      variables: {
        'space-xs': '4px', 'space-sm': '8px', 'space-md': '16px', 'space-lg': '32px', 'space-xl': '64px',
      },
      classes: {},
    },
    seo: { title: '', description: '', share_image: '', canonical: '', robots: 'index,follow', open_graph: {}, twitter: {}, structured_data: [], ...deepClone(seo) },
    project: {
      capabilities: {},
      assets: { fonts: [], icons: [], media: [] },
      custom_code: [],
      data_requirements: [],
      i18n: { default_locale: 'pt-BR', locales: ['pt-BR'], translations: {} },
      permissions: { roles: {} },
      collaboration: { revision: 0 },
      integrations: {},
    },
    builder: { schema: SCHEMA, root_ids: rootIds, nodes: nodeMap },
    blocks: [],
  };
}


export function createHtmlDocument({
  title = 'Página HTML',
  htmlDocument = '',
  surface = 'PAGE',
  contract = 'generic-html-page/v1',
  templateKey = '',
  contentVersion = 1,
  sourceName = '',
  globalStyles = {},
  seo = {},
  breakpoints = DEFAULT_BREAKPOINTS,
} = {}) {
  const doc = createDocument({ title, globalStyles, seo, breakpoints });
  doc.mode = 'HTML';
  doc.surface = String(surface || 'PAGE').toUpperCase();
  doc.html = {
    document: String(htmlDocument || ''),
    contract: String(contract || 'generic-html-page/v1'),
    template_key: String(templateKey || ''),
    surface: doc.surface,
    content_version: Math.max(1, Number(contentVersion || 1)),
    source_name: String(sourceName || ''),
  };
  doc.builder = { schema: SCHEMA, root_ids: [], nodes: {} };
  doc.blocks = [];
  doc.project.integrations ||= {};
  doc.project.integrations.html_document = {
    format: doc.html.contract,
    template_key: doc.html.template_key,
    active_surface: doc.html.surface,
    source_name: doc.html.source_name,
  };
  return doc;
}

export function isHtmlDocument(input) {
  const doc = input && typeof input === 'object' ? input : null;
  return Boolean(doc && String(doc.mode || '').toUpperCase() === 'HTML' && typeof doc.html?.document === 'string');
}

export function normalizeNode(raw = {}, breakpoints = DEFAULT_BREAKPOINTS) {
  const n = deepClone(raw);
  const id = String(n.id || uid(n.type || 'node'));
  const bps = normalizeBreakpoints(breakpoints);
  const responsiveMap = { hidden: {} };
  const responsiveStateMap = {};
  const incomingResponsive = n.responsive && typeof n.responsive === 'object' ? n.responsive : {};
  const incomingStates = n.responsive_states && typeof n.responsive_states === 'object' ? n.responsive_states : {};
  const allIds = new Set([...bps.map(bp => bp.id), ...Object.keys(incomingResponsive).filter(key => key !== 'hidden'), ...Object.keys(incomingStates)]);
  for (const device of allIds) {
    responsiveMap[device] = { ...(incomingResponsive?.[device] || {}) };
    responsiveMap.hidden[device] = Boolean(incomingResponsive?.hidden?.[device]);
    responsiveStateMap[device] = {
      hover: { ...(incomingStates?.[device]?.hover || {}) },
      focus: { ...(incomingStates?.[device]?.focus || {}) },
      active: { ...(incomingStates?.[device]?.active || {}) },
    };
  }
  return {
    id,
    type: String(n.type || 'text'),
    props: n.props && typeof n.props === 'object' ? n.props : {},
    style: n.style && typeof n.style === 'object' ? n.style : {},
    states: {
      hover: { ...(n.states?.hover || {}) },
      focus: { ...(n.states?.focus || {}) },
      active: { ...(n.states?.active || {}) },
    },
    responsive: responsiveMap,
    responsive_states: responsiveStateMap,
    bindings: n.bindings && typeof n.bindings === 'object' ? n.bindings : {},
    conditions: Array.isArray(n.conditions) ? n.conditions : [],
    interactions: Array.isArray(n.interactions) ? n.interactions : [],
    motion: n.motion && typeof n.motion === 'object' ? n.motion : {},
    children: Array.isArray(n.children) ? n.children.map(String) : [],
    meta: n.meta && typeof n.meta === 'object' ? n.meta : {},
  };
}

export function normalizeDocument(input) {
  if (!input || typeof input !== 'object') return createDocument();
  const doc = deepClone(input);

  // Wrapper HTML externo (ex.: Scheduler Pro) -> documento HTML de primeira classe.
  if (String(doc.render_mode || '').toUpperCase() === 'HTML' && typeof doc.html_document === 'string') {
    const result = createHtmlDocument({
      title: doc.title || doc.template_key || 'Template HTML',
      htmlDocument: doc.html_document,
      surface: doc.surface || 'PAGE',
      contract: doc.contract || 'scheduler-pro-html-template/v1',
      templateKey: doc.template_key || '',
      contentVersion: Number(doc.content_version || 2),
      sourceName: doc.source_name || '',
      seo: doc.seo || {},
      globalStyles: doc.global_styles || {},
    });
    result.seo.title ||= doc.template_key || '';
    return result;
  }

  // Documento HTML nativo do AVB 2.3+.
  if (String(doc.mode || '').toUpperCase() === 'HTML' && typeof doc.html?.document === 'string') {
    const seed = createHtmlDocument({
      title: doc.title || doc.html?.template_key || 'Página HTML',
      htmlDocument: doc.html.document,
      surface: doc.surface || doc.html.surface || 'PAGE',
      contract: doc.html.contract || 'generic-html-page/v1',
      templateKey: doc.html.template_key || '',
      contentVersion: Number(doc.html.content_version || 1),
      sourceName: doc.html.source_name || '',
      breakpoints: doc.design_system?.breakpoints || DEFAULT_BREAKPOINTS,
      seo: doc.seo || {},
      globalStyles: doc.global_styles || {},
    });
    return {
      ...seed,
      ...doc,
      schema: SCHEMA,
      version: Math.max(5, Number(doc.version || 5)),
      mode: 'HTML',
      surface: String(doc.surface || doc.html.surface || 'PAGE').toUpperCase(),
      settings: { ...seed.settings, ...(doc.settings || {}) },
      global_styles: { ...seed.global_styles, ...(doc.global_styles || {}) },
      design_system: {
        ...seed.design_system,
        ...(doc.design_system || {}),
        breakpoints: normalizeBreakpoints(doc.design_system?.breakpoints || seed.design_system.breakpoints),
        variables: { ...seed.design_system.variables, ...(doc.design_system?.variables || {}) },
        classes: { ...(doc.design_system?.classes || {}) },
      },
      seo: { ...seed.seo, ...(doc.seo || {}) },
      project: {
        ...seed.project,
        ...(doc.project || {}),
        assets: { ...seed.project.assets, ...(doc.project?.assets || {}) },
        i18n: { ...seed.project.i18n, ...(doc.project?.i18n || {}), translations: { ...(doc.project?.i18n?.translations || {}) } },
        permissions: { ...seed.project.permissions, ...(doc.project?.permissions || {}) },
        collaboration: { ...seed.project.collaboration, ...(doc.project?.collaboration || {}) },
        integrations: { ...seed.project.integrations, ...(doc.project?.integrations || {}) },
      },
      html: {
        ...seed.html,
        ...(doc.html || {}),
        document: String(doc.html.document || ''),
        surface: String(doc.surface || doc.html.surface || 'PAGE').toUpperCase(),
      },
      builder: { schema: SCHEMA, root_ids: [], nodes: {} },
      blocks: [],
    };
  }

  const incomingSchema = doc.builder?.schema || doc.schema;

  if (LEGACY_SCHEMAS.has(incomingSchema) && doc.builder?.nodes) {
    const seed = createDocument({ breakpoints: doc.design_system?.breakpoints || DEFAULT_BREAKPOINTS });
    const breakpoints = normalizeBreakpoints(doc.design_system?.breakpoints || seed.design_system.breakpoints);
    const nodes = {};
    for (const [id, node] of Object.entries(doc.builder.nodes)) nodes[id] = normalizeNode({ ...node, id }, breakpoints);
    const rootIds = Array.isArray(doc.builder.root_ids) ? doc.builder.root_ids.filter(id => nodes[id]) : [];

    // Migração automática do erro histórico: uma página HTML completa encapsulada
    // como único widget html_surface passa a ser um documento HTML de primeira classe.
    if (rootIds.length === 1) {
      const only = nodes[rootIds[0]];
      const html = only?.type === 'html_surface' ? String(only.props?.html_document || '') : '';
      if (html && /<!doctype\s+html/i.test(html) && /<html[\s>]/i.test(html)) {
        const migrated = createHtmlDocument({
          title: doc.title || only.props?.title || only.props?.template_key || 'Página HTML',
          htmlDocument: html,
          surface: only.props?.surface || doc.surface || 'PAGE',
          contract: only.props?.contract || 'generic-html-page/v1',
          templateKey: only.props?.template_key || '',
          contentVersion: Number(only.props?.content_version || 1),
          sourceName: doc.project?.integrations?.html_surface?.source_name || '',
          breakpoints,
          seo: doc.seo || {},
          globalStyles: doc.global_styles || {},
        });
        migrated.settings = { ...migrated.settings, ...(doc.settings || {}) };
        migrated.design_system = {
          ...migrated.design_system,
          ...(doc.design_system || {}),
          breakpoints,
          variables: { ...migrated.design_system.variables, ...(doc.design_system?.variables || {}) },
          classes: { ...(doc.design_system?.classes || {}) },
        };
        migrated.project = {
          ...migrated.project,
          ...(doc.project || {}),
          integrations: {
            ...(doc.project?.integrations || {}),
            html_document: {
              format: only.props?.contract || 'generic-html-page/v1',
              template_key: only.props?.template_key || '',
              active_surface: only.props?.surface || doc.surface || 'PAGE',
              source_name: doc.project?.integrations?.html_surface?.source_name || '',
              migrated_from: 'html_surface',
            },
          },
        };
        delete migrated.project.integrations.html_surface;
        return migrated;
      }
    }

    return {
      ...seed,
      ...doc,
      schema: SCHEMA,
      version: Math.max(5, Number(doc.version || 5)),
      mode: 'VISUAL',
      html: null,
      settings: { ...seed.settings, ...(doc.settings || {}) },
      global_styles: { ...seed.global_styles, ...(doc.global_styles || {}) },
      design_system: {
        ...seed.design_system,
        ...(doc.design_system || {}),
        breakpoints,
        variables: { ...seed.design_system.variables, ...(doc.design_system?.variables || {}) },
        classes: { ...(doc.design_system?.classes || {}) },
      },
      seo: { ...seed.seo, ...(doc.seo || {}) },
      project: {
        ...seed.project,
        ...(doc.project || {}),
        assets: { ...seed.project.assets, ...(doc.project?.assets || {}) },
        i18n: { ...seed.project.i18n, ...(doc.project?.i18n || {}), translations: { ...(doc.project?.i18n?.translations || {}) } },
        permissions: { ...seed.project.permissions, ...(doc.project?.permissions || {}) },
        collaboration: { ...seed.project.collaboration, ...(doc.project?.collaboration || {}) },
        integrations: { ...(doc.project?.integrations || {}) },
      },
      builder: { schema: SCHEMA, root_ids: rootIds, nodes },
      blocks: Array.isArray(doc.blocks) ? doc.blocks : [],
    };
  }

  // Migração transparente do formato V2 usado pelo Scheduler Pro.
  const result = createDocument({ title: doc.title || 'Landing Page', globalStyles: doc.global_styles || {}, seo: doc.seo || {} });
  const blocks = Array.isArray(doc.blocks) ? doc.blocks : [];
  for (const block of blocks) {
    const node = normalizeNode({ ...block, children: [] }, result.design_system.breakpoints);
    result.builder.nodes[node.id] = node;
    result.builder.root_ids.push(node.id);
  }
  result.blocks = deepClone(blocks);
  return result;
}

export function getBreakpoints(doc) { return normalizeBreakpoints(doc?.design_system?.breakpoints || DEFAULT_BREAKPOINTS); }
export function getNode(doc, id) { return doc?.builder?.nodes?.[id] || null; }

export function parentOf(doc, childId) {
  for (const node of Object.values(doc.builder.nodes)) if (node.children.includes(childId)) return node;
  return null;
}

export function descendants(doc, id, output = []) {
  const node = getNode(doc, id);
  if (!node) return output;
  for (const childId of node.children) {
    output.push(childId);
    descendants(doc, childId, output);
  }
  return output;
}

export function addNode(doc, node, parentId = null, index = null) {
  const normalized = normalizeNode(node, getBreakpoints(doc));
  doc.builder.nodes[normalized.id] = normalized;
  const target = parentId ? getNode(doc, parentId)?.children : doc.builder.root_ids;
  if (!target) throw new Error(`Container de destino não encontrado: ${parentId}`);
  const position = index == null ? target.length : Math.max(0, Math.min(index, target.length));
  target.splice(position, 0, normalized.id);
  return normalized;
}

export function removeNode(doc, id) {
  if (!getNode(doc, id)) return false;
  const ids = [id, ...descendants(doc, id, [])];
  const parent = parentOf(doc, id);
  const list = parent ? parent.children : doc.builder.root_ids;
  const pos = list.indexOf(id);
  if (pos >= 0) list.splice(pos, 1);
  for (const removeId of ids) delete doc.builder.nodes[removeId];
  return true;
}

export function exportSubtree(doc, id) {
  const root = getNode(doc, id);
  if (!root) return null;
  const ids = [id, ...descendants(doc, id, [])];
  const nodes = {};
  for (const nodeId of ids) nodes[nodeId] = deepClone(getNode(doc, nodeId));
  return { schema: SCHEMA, root_id: id, nodes };
}

export function importSubtree(doc, bundle, parentId = null, index = null) {
  if (!bundle?.nodes || !bundle.root_id || !bundle.nodes[bundle.root_id]) return null;
  const idMap = new Map();
  for (const oldId of Object.keys(bundle.nodes)) idMap.set(oldId, uid(bundle.nodes[oldId].type || 'node'));
  for (const [oldId, raw] of Object.entries(bundle.nodes)) {
    const fresh = normalizeNode({ ...raw, id: idMap.get(oldId), children: (raw.children || []).map(child => idMap.get(child)).filter(Boolean) }, getBreakpoints(doc));
    doc.builder.nodes[fresh.id] = fresh;
  }
  const rootId = idMap.get(bundle.root_id);
  const target = parentId ? getNode(doc, parentId)?.children : doc.builder.root_ids;
  if (!target) return null;
  const position = index == null ? target.length : Math.max(0, Math.min(index, target.length));
  target.splice(position, 0, rootId);
  return getNode(doc, rootId);
}

export function duplicateNode(doc, id) {
  const bundle = exportSubtree(doc, id);
  if (!bundle) return null;
  const parent = parentOf(doc, id);
  const list = parent ? parent.children : doc.builder.root_ids;
  return importSubtree(doc, bundle, parent?.id || null, list.indexOf(id) + 1);
}

export function moveNode(doc, id, parentId = null, index = null) {
  const node = getNode(doc, id);
  if (!node) return false;
  if (parentId === id || descendants(doc, id, []).includes(parentId)) return false;
  const currentParent = parentOf(doc, id);
  const current = currentParent ? currentParent.children : doc.builder.root_ids;
  const oldIndex = current.indexOf(id);
  if (oldIndex >= 0) current.splice(oldIndex, 1);
  const target = parentId ? getNode(doc, parentId)?.children : doc.builder.root_ids;
  if (!target) return false;
  const targetIndex = index == null ? target.length : Math.max(0, Math.min(index, target.length));
  target.splice(targetIndex, 0, id);
  return true;
}

export function deviceForWidth(doc, width) {
  const bps = getBreakpoints(doc);
  const responsive = bps.filter(bp => bp.max != null).sort((a, b) => a.max - b.max);
  for (const bp of responsive) if (width <= bp.max) return bp.id;
  return 'desktop';
}
