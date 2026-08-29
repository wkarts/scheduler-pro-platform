import {readZipEntries} from './template-packages.js';
import {validateExperienceManifest,createExperienceManifest,EXPERIENCE_CONTRACT_SCHEMA} from './experience-contract.js';
import {normalizeBindingsManifest,validateBindingsManifest} from './bindings-v1.js';
import {createThemeTokens} from './theme-tokens.js';
const decoder=new TextDecoder('utf-8');
const text=(entries,name)=>entries.has(name)?decoder.decode(entries.get(name)):null;
export async function importExperiencePackage(source,options={}){
  const entries=await readZipEntries(source,options.zip||{});
  const rawManifest=text(entries,'experience.json');
  if(!rawManifest) throw new Error('experience.json ausente.');
  let decoded; try{decoded=JSON.parse(rawManifest);}catch{throw new Error('experience.json inválido.');}
  const report=validateExperienceManifest(decoded); if(!report.valid)throw new Error(`Experience Contract inválido: ${report.errors.join(' ')}`);
  const manifest=report.manifest;
  const landing=text(entries,manifest.pages.landing.entry);
  const booking=text(entries,manifest.pages.booking.entry);
  if(manifest.pages.landing.enabled&&!landing)throw new Error(`Arquivo ${manifest.pages.landing.entry} ausente.`);
  if(manifest.pages.booking.enabled&&!booking)throw new Error(`Arquivo ${manifest.pages.booking.entry} ausente.`);
  const bindingsRaw=text(entries,manifest.files.bindings); let bindings=normalizeBindingsManifest({});
  if(bindingsRaw){let b;try{b=JSON.parse(bindingsRaw);}catch{throw new Error('bindings.json inválido.');}const br=validateBindingsManifest(b);if(!br.valid)throw new Error(`Bindings inválidos: ${br.errors.join(' ')}`);bindings=br.manifest;}
  const themeRaw=text(entries,manifest.files.theme); let theme=createThemeTokens({});
  if(themeRaw){let t;try{t=JSON.parse(themeRaw);}catch{throw new Error('theme.json inválido.');}theme=createThemeTokens(t);}
  const assets=[];for(const [name,bytes] of entries){if(name.startsWith('assets/')&&!name.endsWith('/'))assets.push({name,size:bytes.byteLength,bytes});}
  return {schema:EXPERIENCE_CONTRACT_SCHEMA,manifest,pages:{landing,booking},bindings,theme,assets,entries};
}
export function createExperiencePackageDescriptor(input={}){return{manifest:createExperienceManifest(input.manifest||input),bindings:normalizeBindingsManifest(input.bindings||{}),theme:createThemeTokens(input.theme||{}),pages:{landing:String(input.pages?.landing||''),booking:String(input.pages?.booking||'')}};}
