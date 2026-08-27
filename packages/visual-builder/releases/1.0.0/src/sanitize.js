export function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
}
export function safeUrl(value, fallback = '#') {
  const raw = String(value ?? '').trim();
  if (!raw) return fallback;
  if (raw.startsWith('#') || raw.startsWith('/') || raw.startsWith('mailto:') || raw.startsWith('tel:')) return raw;
  try { const url = new URL(raw, 'https://local.invalid'); if (['http:','https:'].includes(url.protocol)) return raw; } catch {}
  return fallback;
}
export function sanitizeStyleValue(value) {
  const raw = String(value ?? '').trim();
  if (/expression\s*\(|javascript:|url\s*\(\s*['"]?javascript:/i.test(raw)) return '';
  if (/[{};<>]/.test(raw)) return '';
  return raw.replace(/[\r\n]/g, ' ').slice(0, 500);
}
export function conservativeHtml(value) {
  const allowed = new Set(['p','span','strong','em','b','i','u','br','ul','ol','li','h1','h2','h3','h4','h5','h6','blockquote','code','pre']);
  return String(value ?? '').replace(/<!--[\s\S]*?-->/g, '').replace(/<[^>]*>/g, raw => {
    const match = raw.match(/^<\s*(\/?)\s*([a-z0-9-]+)[^>]*>$/i);
    if (!match) return '';
    const closing = Boolean(match[1]); const tag = match[2].toLowerCase();
    if (!allowed.has(tag)) return '';
    if (tag === 'br') return '<br>';
    return closing ? `</${tag}>` : `<${tag}>`;
  });
}
