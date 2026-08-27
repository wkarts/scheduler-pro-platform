const FILTERS = new Map();
const TAGS = new Map();

export function registerDynamicFilter(name, handler) {
  const key = String(name || '').trim().toLowerCase();
  if (!/^[a-z][a-z0-9_-]{0,63}$/.test(key)) throw new Error('Nome de filtro dinâmico inválido.');
  if (typeof handler !== 'function') throw new Error('Handler de filtro inválido.');
  FILTERS.set(key, handler);
  return handler;
}

export function unregisterDynamicFilter(name) { FILTERS.delete(String(name || '').trim().toLowerCase()); }
export function dynamicFilter(name) { return FILTERS.get(String(name || '').trim().toLowerCase()) || null; }

export function registerDynamicTag(name, resolver) {
  const key = String(name || '').trim().toLowerCase();
  if (!/^[a-z][a-z0-9_.-]{0,95}$/.test(key)) throw new Error('Nome de Dynamic Tag inválido.');
  if (typeof resolver !== 'function') throw new Error('Resolver de Dynamic Tag inválido.');
  TAGS.set(key, resolver);
  return resolver;
}

export function unregisterDynamicTag(name) { TAGS.delete(String(name || '').trim().toLowerCase()); }
export function dynamicTag(name) { return TAGS.get(String(name || '').trim().toLowerCase()) || null; }

function parseArg(value) {
  const raw = String(value ?? '').trim();
  if (!raw) return '';
  if ((raw.startsWith('"') && raw.endsWith('"')) || (raw.startsWith("'") && raw.endsWith("'"))) return raw.slice(1, -1);
  if (/^-?\d+(\.\d+)?$/.test(raw)) return Number(raw);
  if (raw === 'true') return true;
  if (raw === 'false') return false;
  if (raw === 'null') return null;
  return raw;
}

export function parseDynamicExpression(expression) {
  const parts = String(expression || '').split('|').map(part => part.trim()).filter(Boolean);
  const source = parts.shift() || '';
  const filters = parts.map(part => {
    const [name, ...args] = part.split(':');
    return { name: String(name || '').trim().toLowerCase(), args: args.map(parseArg) };
  }).filter(item => item.name);
  return { source, filters };
}

export function applyDynamicFilters(value, filters = [], context = {}) {
  let current = value;
  for (const descriptor of filters) {
    const handler = dynamicFilter(descriptor?.name);
    if (!handler) continue;
    current = handler(current, ...(descriptor.args || []), context);
  }
  return current;
}

export async function applyDynamicFiltersAsync(value, filters = [], context = {}) {
  let current = value;
  for (const descriptor of filters) {
    const handler = dynamicFilter(descriptor?.name);
    if (!handler) continue;
    current = await handler(current, ...(descriptor.args || []), context);
  }
  return current;
}

export function resolveRegisteredTag(source, context = {}) {
  const resolver = dynamicTag(source);
  return resolver ? resolver(context) : undefined;
}

registerDynamicFilter('upper', value => String(value ?? '').toUpperCase());
registerDynamicFilter('lower', value => String(value ?? '').toLowerCase());
registerDynamicFilter('trim', value => String(value ?? '').trim());
registerDynamicFilter('default', (value, fallback = '') => (value == null || value === '' ? fallback : value));
registerDynamicFilter('number', (value, locale = 'pt-BR', decimals = 2) => new Intl.NumberFormat(String(locale), { minimumFractionDigits:Number(decimals), maximumFractionDigits:Number(decimals) }).format(Number(value || 0)));
registerDynamicFilter('currency', (value, currency = 'BRL', locale = 'pt-BR') => new Intl.NumberFormat(String(locale), { style:'currency', currency:String(currency) }).format(Number(value || 0)));
registerDynamicFilter('date', (value, locale = 'pt-BR', options = 'short') => {
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  if (options === 'iso') return date.toISOString();
  return new Intl.DateTimeFormat(String(locale), options === 'long' ? { dateStyle:'long' } : { dateStyle:'short' }).format(date);
});
registerDynamicFilter('json', value => JSON.stringify(value));
registerDynamicFilter('length', value => Array.isArray(value) || typeof value === 'string' ? value.length : value && typeof value === 'object' ? Object.keys(value).length : 0);
registerDynamicFilter('join', (value, separator = ', ') => Array.isArray(value) ? value.join(String(separator)) : value);
