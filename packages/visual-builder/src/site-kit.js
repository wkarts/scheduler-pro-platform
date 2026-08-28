import { deepClone, normalizeDocument } from './model.js';
import { evaluateConditions } from './dynamic.js';

export function createSiteKit({ name='Novo projeto', settings={}, parts=[] }={}) {
  return { schema:'argws-site-kit/v1', version:1, name, settings:{...settings}, parts:parts.map(part=>normalizeSitePart(part)) };
}
export function normalizeSitePart(part={}) {
  return {
    id:String(part.id||`part-${Date.now()}-${Math.random().toString(36).slice(2,8)}`),
    type:String(part.type||'header').toLowerCase(),
    name:String(part.name||'Parte global'),
    priority:Number(part.priority||0),
    conditions:Array.isArray(part.conditions)?deepClone(part.conditions):[],
    document:normalizeDocument(part.document),
  };
}
export function resolveSiteParts(siteKit, type, context={}) {
  return (siteKit?.parts||[]).map(normalizeSitePart).filter(part=>part.type===String(type).toLowerCase()&&evaluateConditions(part.conditions,context)).sort((a,b)=>b.priority-a.priority);
}
export function upsertSitePart(siteKit, part) {
  const normalized=normalizeSitePart(part); const index=(siteKit.parts||[]).findIndex(row=>row.id===normalized.id);
  if(index>=0)siteKit.parts[index]=normalized;else(siteKit.parts||=[]).push(normalized);return normalized;
}
export function removeSitePart(siteKit,id){const index=(siteKit.parts||[]).findIndex(row=>row.id===id);if(index<0)return false;siteKit.parts.splice(index,1);return true;}
