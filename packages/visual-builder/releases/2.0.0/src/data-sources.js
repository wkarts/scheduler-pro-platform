import { deepClone, getNode, normalizeDocument } from './model.js';

const SOURCES = new Map();

export function registerDataSource(name, handler, options = {}) {
  const key = String(name || '').trim().toLowerCase();
  if (!/^[a-z][a-z0-9_.-]{0,95}$/.test(key)) throw new Error('Nome de Data Source inválido.');
  if (typeof handler !== 'function') throw new Error('Handler de Data Source inválido.');
  SOURCES.set(key, { handler, cacheTtl:Number(options.cacheTtl || 0), meta:{ ...(options.meta || {}) } });
  return handler;
}
export function unregisterDataSource(name) { SOURCES.delete(String(name || '').trim().toLowerCase()); }
export function dataSource(name) { return SOURCES.get(String(name || '').trim().toLowerCase()) || null; }
export function listDataSources() { return Array.from(SOURCES.entries()).map(([name, entry]) => ({ name, cacheTtl:entry.cacheTtl, meta:deepClone(entry.meta) })); }

export class QueryCache {
  constructor() { this.rows = new Map(); }
  key(source, query) { return `${source}:${JSON.stringify(query || {})}`; }
  get(source, query) {
    const row = this.rows.get(this.key(source, query));
    if (!row || (row.expires && row.expires < Date.now())) { if (row) this.rows.delete(this.key(source, query)); return undefined; }
    return deepClone(row.value);
  }
  set(source, query, value, ttl = 0) { this.rows.set(this.key(source, query), { value:deepClone(value), expires:ttl > 0 ? Date.now() + ttl : 0 }); return value; }
  clear() { this.rows.clear(); }
}

export async function executeDataQuery(sourceName, query = {}, runtime = {}) {
  const source = dataSource(sourceName);
  if (!source) throw new Error(`Data Source não registrado: ${sourceName}`);
  const cache = runtime.queryCache instanceof QueryCache ? runtime.queryCache : null;
  const cached = cache?.get(sourceName, query);
  if (cached !== undefined) return cached;
  const value = await source.handler({ query:deepClone(query || {}), runtime });
  if (cache) cache.set(sourceName, query, value, source.cacheTtl);
  return value;
}

function parseQueryJson(value) {
  if (!value) return {};
  if (typeof value === 'object') return deepClone(value);
  try { const parsed = JSON.parse(String(value)); return parsed && typeof parsed === 'object' ? parsed : {}; } catch { return {}; }
}

export function collectDataRequirements(input) {
  const doc = normalizeDocument(input); const rows = [];
  for (const id of Object.keys(doc.builder.nodes || {})) {
    const node = getNode(doc, id); if (!node) continue;
    if (node.type === 'query_loop' && node.props?.source) rows.push({ key:`query:${id}`, nodeId:id, source:String(node.props.source), query:parseQueryJson(node.props.query_json || node.props.query) });
    const req = node.meta?.data_source;
    if (req?.source) rows.push({ key:req.key || `node:${id}`, nodeId:id, source:String(req.source), query:parseQueryJson(req.query) });
  }
  for (const req of doc.project?.data_requirements || []) if (req?.source) rows.push({ key:String(req.key || req.source), nodeId:null, source:String(req.source), query:parseQueryJson(req.query) });
  return rows;
}

export async function resolveDataRequirements(input, runtime = {}) {
  const context = { ...(runtime.context || {}) }; const errors = [];
  context.__queries = { ...(context.__queries || {}) };
  const rows = collectDataRequirements(input);
  for (const row of rows) {
    try {
      const value = await executeDataQuery(row.source, row.query, runtime);
      if (row.nodeId) context.__queries[row.nodeId] = value;
      context[row.key] = value;
    } catch (error) {
      errors.push({ requirement:row, message:error?.message || String(error) });
      if (runtime.strictData) throw error;
    }
  }
  return { context, errors, requirements:rows };
}
