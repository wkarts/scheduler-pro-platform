import { invokeHostService } from './services.js';
const ACTION_HANDLERS = new Map();

export function registerAction(name, handler) {
  if (!/^[a-z][a-z0-9_-]{1,63}$/.test(String(name))) throw new Error('Nome de ação inválido.');
  if (typeof handler !== 'function') throw new Error('Handler de ação inválido.');
  ACTION_HANDLERS.set(name, handler); return handler;
}
export function unregisterAction(name) { ACTION_HANDLERS.delete(name); }
export function actionHandler(name) { return ACTION_HANDLERS.get(name) || null; }

export async function executeActions(actions = [], payload = {}, runtime = {}) {
  const results = [];
  for (const action of actions || []) {
    const descriptor = typeof action === 'string' ? { type: action } : action;
    const handler = ACTION_HANDLERS.get(descriptor.type);
    if (!handler) { results.push({ type: descriptor.type, skipped: true }); continue; }
    results.push({ type: descriptor.type, result: await handler({ action: descriptor, payload, runtime }) });
  }
  return results;
}

registerAction('webhook', async ({ action, payload }) => {
  if (!action.url) throw new Error('URL do webhook não configurada.');
  const response = await fetch(action.url, { method: action.method || 'POST', headers: { 'content-type': 'application/json', ...(action.headers || {}) }, body: JSON.stringify(payload) });
  if (!response.ok) throw new Error(`Webhook HTTP ${response.status}`);
  return response.json().catch(() => ({ ok: true }));
});

registerAction('redirect', async ({ action }) => {
  const url = String(action.url || action.to || '').trim();
  if (!url) return { skipped:true };
  if (globalThis.location && /^(https?:\/\/|\/|#)/i.test(url)) globalThis.location.assign(url);
  return { redirected:url };
});
registerAction('event', async ({ action, payload, runtime }) => {
  const name = String(action.name || 'upb-action');
  runtime?.eventTarget?.dispatchEvent?.(new CustomEvent(name, { detail:payload, bubbles:true, composed:true }));
  return { event:name };
});
registerAction('open_popup', async ({ action, runtime }) => { runtime?.openOverlay?.(String(action.name || action.target || '')); return { opened:action.name || action.target || '' }; });
registerAction('close_popup', async ({ action, runtime }) => { runtime?.closeOverlay?.(String(action.name || action.target || '')); return { closed:action.name || action.target || '' }; });

registerAction('service', async ({ action, payload, runtime }) => invokeHostService(String(action.service || action.name || ''), payload, runtime));
