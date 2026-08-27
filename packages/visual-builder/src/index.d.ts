export * from '../runtime/package/src/index.js'

export type VisualBuilderVersion='2.0.1'
export interface VisualBuilderRelease{version:VisualBuilderVersion;label:string;schema:string;channel:string;recommended:boolean;description:string}
export const ARGWS_VISUAL_BUILDER_VERSION:VisualBuilderVersion
export const ARGWS_VISUAL_BUILDER_RELEASES:readonly VisualBuilderRelease[]
export const ARGWS_VISUAL_BUILDER_DEFAULT_VERSION:VisualBuilderVersion
export const ARGWS_VISUAL_BUILDER_SUPPORTED_VERSIONS:readonly VisualBuilderVersion[]
export function normalizeVisualBuilderVersion(value?:unknown,fallback?:VisualBuilderVersion):VisualBuilderVersion
export function visualBuilderRelease(value?:unknown):VisualBuilderRelease
export function activeVisualBuilderRuntimeVersion():VisualBuilderVersion
export function resolveVisualBuilderVersionFromContent(content?:Record<string,unknown>|null):VisualBuilderVersion
export function loadVisualBuilderRuntime():Promise<Record<string,any>>
export function createSchedulerProAdapter(options?:Record<string,unknown>):Promise<{adapter:Record<string,any>;runtime:Record<string,any>;version:VisualBuilderVersion}>
