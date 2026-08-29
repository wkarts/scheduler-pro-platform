export const EXPERIENCE_CONTRACT_SCHEMA='argws-experience-package/v2';
export const EXPERIENCE_CONTRACT_VERSION=2;
export const EXPERIENCE_SURFACES=Object.freeze(['LANDING','BOOKING']);
export const EXPERIENCE_AUTHORING_MODES=Object.freeze(['runtime-html','compiled-output']);

const isObject=value=>Boolean(value&&typeof value==='object'&&!Array.isArray(value));
const str=(value,fallback='')=>String(value??fallback).trim();

export function createExperienceManifest(input={}){
  const source=isObject(input)?input:{};
  const pkg=isObject(source.package)?source.package:{};
  const pages=isObject(source.pages)?source.pages:{};
  return {
    schema:EXPERIENCE_CONTRACT_SCHEMA,
    version:EXPERIENCE_CONTRACT_VERSION,
    package:{
      key:str(pkg.key||source.key,'experience-template'),
      name:str(pkg.name||source.name,'Experience Template'),
      description:str(pkg.description||source.description,''),
      author:str(pkg.author||source.author,''),
      package_version:str(pkg.package_version||source.package_version,'1.0.0'),
      authoring_mode:EXPERIENCE_AUTHORING_MODES.includes(pkg.authoring_mode)?pkg.authoring_mode:'runtime-html',
      capabilities:Array.isArray(pkg.capabilities)?[...new Set(pkg.capabilities.map(String))]:[],
    },
    pages:{
      landing:{entry:str(pages?.landing?.entry,'pages/landing.html'),route:str(pages?.landing?.route,'/pagina'),surface:'LANDING',enabled:pages?.landing?.enabled!==false},
      booking:{entry:str(pages?.booking?.entry,'pages/booking.html'),route:str(pages?.booking?.route,'/agendar'),surface:'BOOKING',enabled:pages?.booking?.enabled!==false},
    },
    files:{
      bindings:str(source?.files?.bindings,'bindings.json'),
      theme:str(source?.files?.theme,'theme.json'),
    },
    branding:isObject(source.branding)?structuredClone(source.branding):{},
    analytics:isObject(source.analytics)?structuredClone(source.analytics):{},
    metadata:isObject(source.metadata)?structuredClone(source.metadata):{},
  };
}

export function validateExperienceManifest(input){
  const errors=[]; const warnings=[];
  if(!isObject(input)) return {valid:false,errors:['Manifest precisa ser um objeto JSON.'],warnings,manifest:null};
  const manifest=createExperienceManifest(input);
  if(input.schema!==EXPERIENCE_CONTRACT_SCHEMA) errors.push(`schema deve ser ${EXPERIENCE_CONTRACT_SCHEMA}.`);
  if(Number(input.version)!==EXPERIENCE_CONTRACT_VERSION) errors.push(`version deve ser ${EXPERIENCE_CONTRACT_VERSION}.`);
  if(!/^[a-z0-9][a-z0-9._-]{1,127}$/i.test(manifest.package.key)) errors.push('package.key inválido.');
  if(!manifest.package.name) errors.push('package.name é obrigatório.');
  for(const [name,page] of Object.entries(manifest.pages)){
    if(!page.entry.endsWith('.html')) errors.push(`pages.${name}.entry precisa apontar para HTML.`);
    if(!page.route.startsWith('/')) errors.push(`pages.${name}.route precisa começar com /.`);
  }
  if(manifest.package.authoring_mode==='compiled-output') warnings.push('compiled-output deve fornecer HTML/CSS/JS final; o host não compila o template.');
  return {valid:errors.length===0,errors,warnings,manifest};
}

export function isExperienceManifest(input){return validateExperienceManifest(input).valid;}
