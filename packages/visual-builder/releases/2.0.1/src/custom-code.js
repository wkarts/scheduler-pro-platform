import { evaluateConditions } from './dynamic.js';
import { sanitizeStylesheet, conservativeHtml } from './sanitize.js';

const PLACEMENTS = new Set(['head','body-start','body-end']);
export function normalizeCodeSnippet(snippet = {}) {
  const type=['css','html','js'].includes(snippet.type)?snippet.type:'html'; const placement=PLACEMENTS.has(snippet.placement)?snippet.placement:(type==='css'?'head':'body-end');
  return { id:String(snippet.id || `code-${Date.now()}-${Math.random().toString(36).slice(2,8)}`), name:String(snippet.name || 'Snippet'), type, placement, enabled:snippet.enabled!==false, trusted:Boolean(snippet.trusted), conditions:Array.isArray(snippet.conditions)?snippet.conditions:[], code:String(snippet.code || '') };
}
export function renderCustomCode(snippets = [], { placement='head', context={}, allowTrustedCode=false } = {}) {
  return (snippets||[]).map(normalizeCodeSnippet).filter(row=>row.enabled&&row.placement===placement&&evaluateConditions(row.conditions,context)).map(row=>{
    if(row.type==='css')return `<style data-upb-custom-code="${row.id}">${sanitizeStylesheet(row.code)}</style>`;
    if(row.type==='html')return conservativeHtml(row.code);
    if(row.type==='js'&&row.trusted&&allowTrustedCode)return `<script data-upb-custom-code="${row.id}">${row.code.replace(/<\/script/gi,'<\\/script')}</script>`;
    return '';
  }).join('');
}
