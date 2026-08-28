const SERVICES = new Map();

export function registerHostService(name, handler, options = {}) {
  const key = String(name || '').trim().toLowerCase();
  if (!/^[a-z][a-z0-9_.-]{1,95}$/.test(key)) throw new Error('Nome de serviço do host inválido.');
  if (typeof handler !== 'function') throw new Error('Handler de serviço do host inválido.');
  SERVICES.set(key, { handler, meta:{ ...(options.meta || {}) } });
  return handler;
}
export function unregisterHostService(name) { SERVICES.delete(String(name || '').trim().toLowerCase()); }
export function hostService(name) { return SERVICES.get(String(name || '').trim().toLowerCase()) || null; }
export function listHostServices() { return Array.from(SERVICES.entries()).map(([name,row])=>({name,meta:{...row.meta}})); }
export async function invokeHostService(name, payload = {}, runtime = {}) {
  const service = hostService(name);
  const runtimeHandler = runtime?.services?.[name];
  const handler = typeof runtimeHandler === 'function' ? runtimeHandler : service?.handler;
  if (!handler) throw new Error(`Serviço do host não registrado: ${name}`);
  return handler({ payload, runtime, name });
}
