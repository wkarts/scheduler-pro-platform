import '../runtime/package/styles/builder.css'
import * as runtime from '../runtime/package/src/index.js'
export * from '../runtime/package/src/index.js'

export const ARGWS_VISUAL_BUILDER_VERSION='2.1.0'
export const ARGWS_VISUAL_BUILDER_DEFAULT_VERSION='2.1.0'
export const ARGWS_VISUAL_BUILDER_SUPPORTED_VERSIONS=Object.freeze(['2.1.0'])
export const ARGWS_VISUAL_BUILDER_RELEASES=Object.freeze([
  Object.freeze({version:'2.1.0',label:'ARGWS Visual Builder 2.1.0',schema:'argws-visual-builder/v3',channel:'canonical',recommended:true,description:'Release canônica New-Only do editor visual responsivo do Scheduler Pro.'}),
])

export function normalizeVisualBuilderVersion(){return ARGWS_VISUAL_BUILDER_VERSION}
export function visualBuilderRelease(){return ARGWS_VISUAL_BUILDER_RELEASES[0]}
export function activeVisualBuilderRuntimeVersion(){return ARGWS_VISUAL_BUILDER_VERSION}
export function resolveVisualBuilderVersionFromContent(){return ARGWS_VISUAL_BUILDER_VERSION}
export async function loadVisualBuilderRuntime(){return runtime}

function versionedPayload(document){
  return {...runtime.toSchedulerProContent(document),builder_version:ARGWS_VISUAL_BUILDER_VERSION}
}

export async function createSchedulerProAdapter(_versionOrOptions={},maybeOptions={}){
  const options=typeof _versionOrOptions==='string'?maybeOptions:_versionOrOptions
  const adapter=new runtime.SchedulerProAdapter(options)
  adapter.saveDraft=async document=>{
    const payload=versionedPayload(document)
    const result=await adapter.request(`/landing-pages/${encodeURIComponent(adapter.slug)}/draft`,{method:'POST',body:JSON.stringify(payload)})
    adapter.state={...(adapter.state||{}),draft_version_id:result.version_id}
    return result
  }
  adapter.autosave=async document=>{
    const payload=versionedPayload(document)
    const result=await adapter.request(`/landing-pages/${encodeURIComponent(adapter.slug)}/autosave`,{method:'POST',body:JSON.stringify(payload)})
    adapter.state={...(adapter.state||{}),draft_version_id:result.version_id}
    return result
  }
  adapter.publish=async document=>{
    await adapter.saveDraft(document)
    return adapter.request(`/landing-pages/${encodeURIComponent(adapter.slug)}/publish`,{method:'POST',body:JSON.stringify({version_id:adapter.state?.draft_version_id||null})})
  }
  return {adapter,runtime,version:ARGWS_VISUAL_BUILDER_VERSION}
}
