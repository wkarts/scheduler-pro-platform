export const THEME_SCHEMA='argws-theme-tokens/v1';
const isObject=v=>Boolean(v&&typeof v==='object'&&!Array.isArray(v));
const safeToken=(v,f)=>typeof v==='string'&&v.trim()?v.trim():f;
export function createThemeTokens(input={}){
  const s=isObject(input)?input:{}; const c=isObject(s.colors)?s.colors:{}; const t=isObject(s.typography)?s.typography:{}; const r=isObject(s.radius)?s.radius:{}; const sp=isObject(s.spacing)?s.spacing:{};
  return {schema:THEME_SCHEMA,version:1,name:safeToken(s.name,'Default'),colors:{primary:safeToken(c.primary,'#2563eb'),secondary:safeToken(c.secondary,'#0f172a'),accent:safeToken(c.accent,'#7c3aed'),background:safeToken(c.background,'#ffffff'),surface:safeToken(c.surface,'#ffffff'),text:safeToken(c.text,'#0f172a'),muted:safeToken(c.muted,'#64748b')},typography:{heading:safeToken(t.heading,'Inter, system-ui, sans-serif'),body:safeToken(t.body,'Inter, system-ui, sans-serif')},radius:{sm:safeToken(r.sm,'8px'),md:safeToken(r.md,'14px'),lg:safeToken(r.lg,'24px')},spacing:{sm:safeToken(sp.sm,'8px'),md:safeToken(sp.md,'16px'),lg:safeToken(sp.lg,'32px')},branding:isObject(s.branding)?structuredClone(s.branding):{}};
}
export function themeTokensToCss(tokens={},selector=':root'){
  const t=createThemeTokens(tokens); const vars={
    '--avb-primary':t.colors.primary,'--avb-secondary':t.colors.secondary,'--avb-accent':t.colors.accent,'--avb-background':t.colors.background,'--avb-surface':t.colors.surface,'--avb-text':t.colors.text,'--avb-muted':t.colors.muted,'--avb-font-heading':t.typography.heading,'--avb-font-body':t.typography.body,'--avb-radius-sm':t.radius.sm,'--avb-radius-md':t.radius.md,'--avb-radius-lg':t.radius.lg,'--avb-space-sm':t.spacing.sm,'--avb-space-md':t.spacing.md,'--avb-space-lg':t.spacing.lg,
  }; return `${selector}{${Object.entries(vars).map(([k,v])=>`${k}:${v}`).join(';')}}`;
}
export function mapThemeToHostTokens(tokens={},prefix='--sp-'){
  const t=createThemeTokens(tokens); return {[`${prefix}primary`]:t.colors.primary,[`${prefix}secondary`]:t.colors.secondary,[`${prefix}accent`]:t.colors.accent,[`${prefix}background`]:t.colors.background,[`${prefix}surface`]:t.colors.surface,[`${prefix}text`]:t.colors.text,[`${prefix}font-heading`]:t.typography.heading,[`${prefix}font-body`]:t.typography.body};
}
