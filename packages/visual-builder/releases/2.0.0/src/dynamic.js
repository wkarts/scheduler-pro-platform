import { deepClone } from './model.js';
import { applyDynamicFilters, parseDynamicExpression, resolveRegisteredTag } from './dynamic-tags.js';

export function getPath(source, path, fallback = undefined) {
  if (!path) return source;
  const keys = String(path).replace(/\[(\d+)\]/g, '.$1').split('.').map(key => key.trim()).filter(Boolean);
  let value = source;
  for (const key of keys) {
    if (value == null || (typeof value !== 'object' && !Array.isArray(value))) return fallback;
    value = value[key];
  }
  return value === undefined ? fallback : value;
}

export function resolveDynamicExpression(expression, context = {}) {
  const descriptor = parseDynamicExpression(expression);
  let value = resolveRegisteredTag(descriptor.source, context);
  if (value === undefined) value = getPath(context, descriptor.source, '');
  return applyDynamicFilters(value, descriptor.filters, context);
}

export function interpolate(value, context = {}) {
  if (typeof value !== 'string') return value;
  return value.replace(/\{\{\s*([^{}]+?)\s*\}\}/g, (_, expression) => {
    const result = resolveDynamicExpression(expression, context);
    return result == null ? '' : String(result);
  });
}

export function resolveBindings(props = {}, bindings = {}, context = {}) {
  const result = deepClone(props || {});
  for (const [key, binding] of Object.entries(bindings || {})) {
    if (!binding) continue;
    const descriptor = typeof binding === 'string' ? { path: binding } : binding;
    const value = getPath(context, descriptor.path, descriptor.fallback);
    if (value !== undefined) result[key] = value;
  }
  for (const [key, value] of Object.entries(result)) {
    if (typeof value === 'string') result[key] = interpolate(value, context);
  }
  return result;
}

export function compareValues(actual, operator = 'eq', expected = true) {
  switch (operator) {
    case 'eq': return String(actual ?? '') === String(expected ?? '');
    case 'neq': return String(actual ?? '') !== String(expected ?? '');
    case 'strict_eq': return actual === expected;
    case 'gt': return Number(actual) > Number(expected);
    case 'gte': return Number(actual) >= Number(expected);
    case 'lt': return Number(actual) < Number(expected);
    case 'lte': return Number(actual) <= Number(expected);
    case 'contains': return Array.isArray(actual) ? actual.includes(expected) : String(actual ?? '').includes(String(expected ?? ''));
    case 'not_contains': return Array.isArray(actual) ? !actual.includes(expected) : !String(actual ?? '').includes(String(expected ?? ''));
    case 'starts_with': return String(actual ?? '').startsWith(String(expected ?? ''));
    case 'ends_with': return String(actual ?? '').endsWith(String(expected ?? ''));
    case 'in': return Array.isArray(expected) ? expected.map(String).includes(String(actual ?? '')) : String(expected ?? '').split(',').map(v => v.trim()).includes(String(actual ?? ''));
    case 'exists': return actual !== undefined && actual !== null && actual !== '';
    case 'empty': return actual == null || actual === '' || (Array.isArray(actual) && !actual.length);
    case 'truthy': return Boolean(actual);
    case 'falsy': return !actual;
    default: return true;
  }
}

export function evaluateConditions(conditions = [], context = {}) {
  if (!Array.isArray(conditions) || !conditions.length) return true;
  let result = true;
  for (const condition of conditions) {
    if (!condition || !condition.path) continue;
    const current = compareValues(getPath(context, condition.path), condition.operator || 'eq', condition.value);
    result = condition.logic === 'or' ? (result || current) : (result && current);
  }
  return result;
}

export function parseConditionsText(value) {
  return String(value || '').split(/\r?\n/).map(line => line.trim()).filter(Boolean).map((line, index) => {
    const [path = '', operator = 'eq', ...valueParts] = line.split('|').map(part => part.trim());
    return { path, operator: operator || 'eq', value: valueParts.join('|'), logic: index === 0 ? 'and' : 'and' };
  }).filter(item => item.path);
}

export function conditionsToText(conditions = []) {
  return (conditions || []).map(item => `${item.path || ''} | ${item.operator || 'eq'} | ${item.value ?? ''}`).join('\n');
}
