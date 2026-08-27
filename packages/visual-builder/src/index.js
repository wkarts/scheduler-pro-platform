export const ARGWS_VISUAL_BUILDER_RELEASES = Object.freeze([
  Object.freeze({version:'1.0.0',label:'ARGWS Visual Builder 1.0.0',schema:'argws-visual-builder/v2',channel:'legacy-test',recommended:false,description:'Release estável anterior, mantida para teste e compatibilidade.'}),
  Object.freeze({version:'2.0.0',label:'ARGWS Visual Builder 2.0.0',schema:'argws-visual-builder/v3',channel:'stable',recommended:false,description:'Release 2.0 original com recursos universais v3.'}),
  Object.freeze({version:'2.0.1',label:'ARGWS Visual Builder 2.0.1',schema:'argws-visual-builder/v3',channel:'current',recommended:true,description:'Release New-Only atual e recomendada para novas páginas.'}),
])

export const ARGWS_VISUAL_BUILDER_DEFAULT_VERSION = '2.0.1'
export const ARGWS_VISUAL_BUILDER_SUPPORTED_VERSIONS = Object.freeze(ARGWS_VISUAL_BUILDER_RELEASES.map(item=>item.version))

const runtimeLoaders = Object.freeze({
  '1.0.0': async()=>{await import('@argws/visual-builder-v1/styles.css');return import('@argws/visual-builder-v1')},
  '2.0.0': async()=>{await import('@argws/visual-builder-v2/styles.css');return import('@argws/visual-builder-v2')},
  '2.0.1': async()=>{await import('@argws/visual-builder-v201/styles.css');return import('@argws/visual-builder-v201')},
})

let activeRuntimeVersion = ''
let activeRuntimePromise = null

export function normalizeVisualBuilderVersion(value, fallback=ARGWS_VISUAL_BUILDER_DEFAULT_VERSION){
  const candidate=String(value||'').trim()
  return ARGWS_VISUAL_BUILDER_SUPPORTED_VERSIONS.includes(candidate)?candidate:fallback
}

export function visualBuilderRelease(value){
  const version=normalizeVisualBuilderVersion(value)
  return ARGWS_VISUAL_BUILDER_RELEASES.find(item=>item.version===version)||ARGWS_VISUAL_BUILDER_RELEASES.at(-1)
}

export function activeVisualBuilderRuntimeVersion(){return activeRuntimeVersion||null}

export function resolveVisualBuilderVersionFromContent(content){
  if(!content||typeof content!=='object')return ARGWS_VISUAL_BUILDER_DEFAULT_VERSION
  const explicit=String(content.builder_version||'').trim()
  if(ARGWS_VISUAL_BUILDER_SUPPORTED_VERSIONS.includes(explicit))return explicit
  const schema=String(content.schema||content.builder?.schema||'').toLowerCase()
  if(schema.includes('/v3'))return '2.0.1'
  if(schema.includes('/v2')||schema.includes('/v1'))return '1.0.0'
  return ARGWS_VISUAL_BUILDER_DEFAULT_VERSION
}

export async function loadVisualBuilderRuntime(value=ARGWS_VISUAL_BUILDER_DEFAULT_VERSION){
  const version=normalizeVisualBuilderVersion(value)
  if(activeRuntimeVersion&&activeRuntimeVersion!==version){
    const error=new Error(`O ARGWS Visual Builder ${activeRuntimeVersion} já está ativo neste carregamento. Recarregue a página para usar ${version}.`)
    error.code='ARGWS_VISUAL_BUILDER_RELOAD_REQUIRED'
    error.active_version=activeRuntimeVersion
    error.requested_version=version
    error.requires_reload=true
    throw error
  }
  if(activeRuntimePromise)return activeRuntimePromise
  activeRuntimeVersion=version
  activeRuntimePromise=runtimeLoaders[version]().catch(error=>{
    activeRuntimeVersion=''
    activeRuntimePromise=null
    throw error
  })
  return activeRuntimePromise
}

function versionedPayload(runtime,version,document){
  return {...runtime.toSchedulerProContent(document),builder_version:version}
}

export async function createSchedulerProAdapter(value,options={}){
  const version=normalizeVisualBuilderVersion(value)
  const runtime=await loadVisualBuilderRuntime(version)
  const adapter=new runtime.SchedulerProAdapter(options)

  adapter.saveDraft=async document=>{
    const payload=versionedPayload(runtime,version,document)
    const result=await adapter.request(`/landing-pages/${encodeURIComponent(adapter.slug)}/draft`,{method:'POST',body:JSON.stringify(payload)})
    adapter.state={...(adapter.state||{}),draft_version_id:result.version_id}
    return result
  }
  adapter.autosave=async document=>{
    const payload=versionedPayload(runtime,version,document)
    const result=await adapter.request(`/landing-pages/${encodeURIComponent(adapter.slug)}/autosave`,{method:'POST',body:JSON.stringify(payload)})
    adapter.state={...(adapter.state||{}),draft_version_id:result.version_id}
    return result
  }
  adapter.publish=async document=>{
    await adapter.saveDraft(document)
    return adapter.request(`/landing-pages/${encodeURIComponent(adapter.slug)}/publish`,{method:'POST',body:JSON.stringify({version_id:adapter.state?.draft_version_id||null})})
  }
  return {adapter,runtime,version}
}
