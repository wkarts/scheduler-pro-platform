export const SCHEMA = 'argws-visual-builder/v1';
export const DEVICES = ['desktop', 'tablet', 'mobile'];

export function uid(prefix = 'node') {
  const random = globalThis.crypto?.randomUUID?.() || `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
  return `${prefix}-${random}`;
}

export function deepClone(value) {
  return value == null ? value : JSON.parse(JSON.stringify(value));
}

export function responsive() {
  return { desktop: {}, tablet: {}, mobile: {}, hidden: { desktop: false, tablet: false, mobile: false } };
}

export function createNode(type, props = {}, extra = {}) {
  return {
    id: uid(type),
    type,
    props: deepClone(props),
    style: {},
    responsive: responsive(),
    children: [],
    ...deepClone(extra),
  };
}

export function createDocument({ title = 'Nova página', globalStyles = {}, seo = {}, nodes = [] } = {}) {
  const nodeMap = {};
  const rootIds = [];
  for (const node of nodes) {
    const cloned = normalizeNode(node);
    nodeMap[cloned.id] = cloned;
    rootIds.push(cloned.id);
  }
  return {
    schema: SCHEMA,
    version: 2,
    title,
    global_styles: {
      primary: '#3151cf', secondary: '#151c31', accent: '#6d72ef', background: '#ffffff', text: '#1d273a',
      heading_font: 'Inter', body_font: 'Inter', radius: 16, ...deepClone(globalStyles),
    },
    seo: { title: '', description: '', share_image: '', ...deepClone(seo) },
    builder: { schema: SCHEMA, root_ids: rootIds, nodes: nodeMap },
    blocks: [],
  };
}

export function normalizeNode(raw = {}) {
  const n = deepClone(raw);
  const id = String(n.id || uid(n.type || 'node'));
  return {
    id,
    type: String(n.type || 'text'),
    props: n.props && typeof n.props === 'object' ? n.props : {},
    style: n.style && typeof n.style === 'object' ? n.style : {},
    responsive: {
      desktop: { ...(n.responsive?.desktop || {}) },
      tablet: { ...(n.responsive?.tablet || {}) },
      mobile: { ...(n.responsive?.mobile || {}) },
      hidden: { desktop: false, tablet: false, mobile: false, ...(n.responsive?.hidden || {}) },
    },
    children: Array.isArray(n.children) ? n.children.map(String) : [],
    meta: n.meta && typeof n.meta === 'object' ? n.meta : {},
  };
}

export function normalizeDocument(input) {
  if (!input || typeof input !== 'object') return createDocument();
  const doc = deepClone(input);
  if (doc.builder?.schema === SCHEMA && doc.builder?.nodes) {
    const nodes = {};
    for (const [id, node] of Object.entries(doc.builder.nodes)) nodes[id] = normalizeNode({ ...node, id });
    return {
      ...createDocument(),
      ...doc,
      version: Math.max(2, Number(doc.version || 2)),
      global_styles: { ...createDocument().global_styles, ...(doc.global_styles || {}) },
      seo: { ...createDocument().seo, ...(doc.seo || {}) },
      builder: { schema: SCHEMA, root_ids: Array.isArray(doc.builder.root_ids) ? doc.builder.root_ids.filter(id => nodes[id]) : [], nodes },
      blocks: Array.isArray(doc.blocks) ? doc.blocks : [],
    };
  }
  const result = createDocument({ title: doc.title || 'Landing Page', globalStyles: doc.global_styles || {}, seo: doc.seo || {} });
  const blocks = Array.isArray(doc.blocks) ? doc.blocks : [];
  for (const block of blocks) {
    const node = normalizeNode({ ...block, children: [] });
    result.builder.nodes[node.id] = node;
    result.builder.root_ids.push(node.id);
  }
  result.blocks = deepClone(blocks);
  return result;
}

export function getNode(doc, id) { return doc?.builder?.nodes?.[id] || null; }
export function parentOf(doc, childId) {
  for (const node of Object.values(doc.builder.nodes)) if (node.children.includes(childId)) return node;
  return null;
}
export function descendants(doc, id, output = []) {
  const node = getNode(doc, id);
  if (!node) return output;
  for (const childId of node.children) { output.push(childId); descendants(doc, childId, output); }
  return output;
}
export function addNode(doc, node, parentId = null, index = null) {
  const normalized = normalizeNode(node); doc.builder.nodes[normalized.id] = normalized;
  const target = parentId ? getNode(doc, parentId)?.children : doc.builder.root_ids;
  if (!target) throw new Error(`Container de destino não encontrado: ${parentId}`);
  const position = index == null ? target.length : Math.max(0, Math.min(index, target.length));
  target.splice(position, 0, normalized.id); return normalized;
}
export function removeNode(doc, id) {
  if (!getNode(doc, id)) return false;
  const ids = [id, ...descendants(doc, id, [])]; const parent = parentOf(doc, id); const list = parent ? parent.children : doc.builder.root_ids;
  const pos = list.indexOf(id); if (pos >= 0) list.splice(pos, 1); for (const removeId of ids) delete doc.builder.nodes[removeId]; return true;
}
export function duplicateNode(doc, id) {
  const source = getNode(doc, id); if (!source) return null;
  const cloneTree = sourceId => { const src = getNode(doc, sourceId); const copy = normalizeNode({ ...deepClone(src), id: uid(src.type), children: [] }); doc.builder.nodes[copy.id] = copy; for (const childId of src.children) copy.children.push(cloneTree(childId)); return copy.id; };
  const newId = cloneTree(id); const parent = parentOf(doc, id); const list = parent ? parent.children : doc.builder.root_ids; list.splice(list.indexOf(id) + 1, 0, newId); return getNode(doc, newId);
}
export function moveNode(doc, id, parentId = null, index = null) {
  const node = getNode(doc, id); if (!node) return false; if (parentId === id || descendants(doc, id, []).includes(parentId)) return false;
  const currentParent = parentOf(doc, id); const current = currentParent ? currentParent.children : doc.builder.root_ids; const oldIndex = current.indexOf(id); if (oldIndex >= 0) current.splice(oldIndex, 1);
  const target = parentId ? getNode(doc, parentId)?.children : doc.builder.root_ids; if (!target) return false; const targetIndex = index == null ? target.length : Math.max(0, Math.min(index, target.length)); target.splice(targetIndex, 0, id); return true;
}
