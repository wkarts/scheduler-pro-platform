export const BINDINGS_SCHEMA='argws-bindings/v1';
export const BINDING_TYPES=Object.freeze(['text','richtext','image','color','phone','url','boolean','section','list','number','select']);
const isObject=v=>Boolean(v&&typeof v==='object'&&!Array.isArray(v));
// PR63_FINAL_RUNTIME_FIX: bindings de imagem persistidos como text continuam visuais.
const semanticImageKey=key=>/(?:^|\.)(?:logo(?:_dark)?|image|photo|avatar)(?:$|\.)/i.test(String(key||''));
function normalizedBindingType(key,type){const candidate=BINDING_TYPES.includes(type)?type:'text';return candidate==='text'&&semanticImageKey(key)?'image':candidate;}

export function normalizeBindingsManifest(input={}){
  const source=isObject(input)?input:{};
  const raw=isObject(source.bindings)?source.bindings:source;
  const bindings={};
  for(const [key,value] of Object.entries(raw)){
    if(key==='schema'||key==='version') continue;
    const definition=isObject(value)?value:{};
    bindings[key]={
      type:normalizedBindingType(key,definition.type),
      label:String(definition.label||key),
      group:String(definition.group||'Conteúdo'),
      default:definition.default??null,
      required:Boolean(definition.required),
      options:Array.isArray(definition.options)?definition.options:[],
      help:String(definition.help||''),
      permissions:Array.isArray(definition.permissions)?definition.permissions.map(String):[],
    };
  }
  return {schema:BINDINGS_SCHEMA,version:1,bindings};
}

export function validateBindingsManifest(input){
  const normalized=normalizeBindingsManifest(input); const errors=[];
  if(input?.schema&&input.schema!==BINDINGS_SCHEMA) errors.push(`schema deve ser ${BINDINGS_SCHEMA}.`);
  for(const [key,definition] of Object.entries(normalized.bindings)){
    if(!/^[a-zA-Z0-9][a-zA-Z0-9._-]*$/.test(key)) errors.push(`Binding inválido: ${key}`);
    if(!BINDING_TYPES.includes(definition.type)) errors.push(`Tipo inválido em ${key}.`);
  }
  return {valid:errors.length===0,errors,manifest:normalized};
}

export function extractBindingKeys(html=''){
  const keys=new Set();
  const re=/\bdata-sp-(?:bind|show|list)\s*=\s*["']([^"']+)["']/gi;
  for(const match of String(html).matchAll(re)) keys.add(match[1].trim());
  return [...keys];
}

function escText(value){return String(value??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function escAttr(value){return escText(value).replace(/"/g,'&quot;');}

export function applyBindingsToHtml(html,values={},definitions={}){
  let output=String(html??'');
  output=output.replace(/(<[^>]+\bdata-sp-bind=["']([^"']+)["'][^>]*>)([\s\S]*?)(<\/[^>]+>)/gi,(all,open,key,current,close)=>{
    if(!(key in values)) return all;
    const type=normalizedBindingType(key,definitions?.[key]?.type||'text');
    const value=values[key];
    if(type==='image') return `${open}<img src="${escAttr(value)}" alt="">${close}`;
    if(type==='richtext') return `${open}${String(value??'')}${close}`;
    if(type==='boolean'||type==='section') return value?all:'';
    return `${open}${escText(value)}${close}`;
  });
  output=output.replace(/(<(?:img|source)[^>]+\bdata-sp-bind=["']([^"']+)["'][^>]*\bsrc=["'])([^"']*)(["'][^>]*>)/gi,(all,a,key,current,z)=>key in values?`${a}${escAttr(values[key])}${z}`:all);
  output=output.replace(/(<a[^>]+\bdata-sp-bind=["']([^"']+)["'][^>]*\bhref=["'])([^"']*)(["'][^>]*>)/gi,(all,a,key,current,z)=>key in values?`${a}${escAttr(values[key])}${z}`:all);
  output=output.replace(/<([a-z0-9-]+)([^>]*\bdata-sp-show=["']([^"']+)["'][^>]*)>([\s\S]*?)<\/\1>/gi,(all,tag,attrs,key,body)=>values[key]===false||values[key]===0||values[key]===''?'':all);
  return output;
}
