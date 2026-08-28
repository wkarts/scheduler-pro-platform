import { registerWidget, unregisterWidget } from './registry.js';
import { registerRenderer, unregisterRenderer } from './renderer.js';
import { registerAction, unregisterAction } from './actions.js';
import { registerDataSource, unregisterDataSource } from './data-sources.js';
import { registerDynamicTag, unregisterDynamicTag, registerDynamicFilter, unregisterDynamicFilter } from './dynamic-tags.js';
import { registerHostService, unregisterHostService } from './services.js';

const PLUGINS = new Map();
function entries(value){return value && typeof value==='object'?Object.entries(value):[];}
export function registerBuilderPlugin(manifest = {}) {
  const id=String(manifest.id || '').trim().toLowerCase();
  if(!/^[a-z][a-z0-9_.-]{2,95}$/.test(id))throw new Error('ID de plugin inválido.');
  if(PLUGINS.has(id))unregisterBuilderPlugin(id);
  for(const [name,def] of entries(manifest.widgets))registerWidget(name,def);
  for(const [name,fn] of entries(manifest.renderers))registerRenderer(name,fn);
  for(const [name,fn] of entries(manifest.actions))registerAction(name,fn);
  for(const [name,def] of entries(manifest.dataSources)){if(typeof def==='function')registerDataSource(name,def);else registerDataSource(name,def.handler,def.options||{});}
  for(const [name,fn] of entries(manifest.dynamicTags))registerDynamicTag(name,fn);
  for(const [name,fn] of entries(manifest.dynamicFilters))registerDynamicFilter(name,fn);
  for(const [name,fn] of entries(manifest.services))registerHostService(name,typeof fn==='function'?fn:fn.handler,typeof fn==='function'?{}:fn.options||{});
  const normalized={id,name:String(manifest.name||id),version:String(manifest.version||'0.0.0'),description:String(manifest.description||''),capabilities:Array.isArray(manifest.capabilities)?manifest.capabilities.map(String):[],manifest};
  PLUGINS.set(id,normalized);return normalized;
}
export function unregisterBuilderPlugin(id){const row=PLUGINS.get(String(id||'').toLowerCase());if(!row)return false;const m=row.manifest;for(const [name] of entries(m.widgets))unregisterWidget(name);for(const [name] of entries(m.renderers))unregisterRenderer(name);for(const [name] of entries(m.actions))unregisterAction(name);for(const [name] of entries(m.dataSources))unregisterDataSource(name);for(const [name] of entries(m.dynamicTags))unregisterDynamicTag(name);for(const [name] of entries(m.dynamicFilters))unregisterDynamicFilter(name);for(const [name] of entries(m.services))unregisterHostService(name);PLUGINS.delete(row.id);return true;}
export function listBuilderPlugins(){return Array.from(PLUGINS.values()).map(({manifest,...row})=>({...row}));}
export function builderPlugin(id){const row=PLUGINS.get(String(id||'').toLowerCase());return row?{id:row.id,name:row.name,version:row.version,description:row.description,capabilities:[...row.capabilities]}:null;}
