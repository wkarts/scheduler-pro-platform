import { deepClone } from './model.js';
import { safeUrl } from './sanitize.js';

export class AssetLibrary {
  constructor(initial = {}) { this.assets = { fonts:[], icons:[], media:[], ...(deepClone(initial || {})) }; }
  list(kind='media') { return deepClone(this.assets[kind] || []); }
  add(kind, asset) { const list=this.assets[kind] ||= []; const normalized={ id:String(asset?.id || `${kind}-${Date.now()}-${Math.random().toString(36).slice(2,8)}`), name:String(asset?.name || asset?.family || 'Ativo'), ...deepClone(asset || {}) }; list.push(normalized); return deepClone(normalized); }
  remove(kind,id){const list=this.assets[kind]||[];const i=list.findIndex(item=>item.id===id);if(i<0)return false;list.splice(i,1);return true;}
  toJSON(){return deepClone(this.assets);}
}

export function fontFaceCss(assets = {}) {
  return (assets.fonts || []).map(font => {
    const family=String(font.family || font.name || '').replace(/["'{};]/g,'').trim(); const url=safeUrl(font.url,''); if(!family||!url)return'';
    const weight=String(font.weight || '100 900').replace(/[^0-9\s-]/g,''); const style=['normal','italic','oblique'].includes(font.style)?font.style:'normal';
    return `@font-face{font-family:"${family}";src:url("${url}") format("${String(font.format||'woff2').replace(/[^a-z0-9-]/gi,'')}");font-style:${style};font-weight:${weight};font-display:${font.display==='block'?'block':'swap'}}`;
  }).filter(Boolean).join('\n');
}
