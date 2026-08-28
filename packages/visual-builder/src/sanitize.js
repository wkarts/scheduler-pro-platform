export function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
}

export function safeUrl(value, fallback = '#') {
  const raw = String(value ?? '').trim();
  if (!raw) return fallback;
  if (raw.startsWith('#') || raw.startsWith('/') || raw.startsWith('mailto:') || raw.startsWith('tel:')) return raw;
  try {
    const url = new URL(raw, 'https://local.invalid');
    if (['http:','https:'].includes(url.protocol)) return raw;
  } catch {}
  return fallback;
}

export function safeEmbedUrl(value, fallback = '') {
  const url = safeUrl(value, '');
  if (!url || url.startsWith('#') || url.startsWith('/') || url.startsWith('mailto:') || url.startsWith('tel:')) return fallback;
  return url;
}

export function sanitizeStyleValue(value) {
  const raw = String(value ?? '').trim();
  if (/expression\s*\(|javascript:|vbscript:|behavior\s*:|-moz-binding|url\s*\(\s*['"]?(?:javascript|data):/i.test(raw)) return '';
  if (/[{};<>]/.test(raw)) return '';
  return raw.replace(/[\r\n]/g, ' ').slice(0, 800);
}

export function sanitizeDeclarationList(value) {
  return String(value ?? '').split(';').map(part => part.trim()).filter(Boolean).map(part => {
    const pos = part.indexOf(':');
    if (pos <= 0) return '';
    const name = part.slice(0, pos).trim();
    const rawValue = part.slice(pos + 1).trim();
    if (!/^--[a-z0-9_-]+$/i.test(name) && !/^[a-z][a-z0-9-]*$/i.test(name)) return '';
    const safe = sanitizeStyleValue(rawValue);
    return safe ? `${name}:${safe}` : '';
  }).filter(Boolean).join(';');
}

export function sanitizeStylesheet(value) {
  const source = String(value ?? '').replace(/\/\*[\s\S]*?\*\//g, '');
  if (!source) return '';
  if (/@import|@charset|expression\s*\(|javascript:|vbscript:|behavior\s*:|-moz-binding|<|>/i.test(source)) return '';
  // CSS customizado é sempre escopado em .upb-page pelo renderer. Mantém regras comuns e @media.
  return source.replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g, '').slice(0, 50000);
}

export function conservativeHtml(value) {
  const allowed = new Set(['p','span','strong','em','b','i','u','s','small','br','ul','ol','li','h1','h2','h3','h4','h5','h6','blockquote','code','pre','mark','sub','sup']);
  return String(value ?? '').replace(/<!--[\s\S]*?-->/g, '').replace(/<[^>]*>/g, raw => {
    const match = raw.match(/^<\s*(\/?)\s*([a-z0-9-]+)[^>]*>$/i);
    if (!match) return '';
    const closing = Boolean(match[1]); const tag = match[2].toLowerCase();
    if (!allowed.has(tag)) return '';
    if (tag === 'br') return '<br>';
    return closing ? `</${tag}>` : `<${tag}>`;
  });
}
