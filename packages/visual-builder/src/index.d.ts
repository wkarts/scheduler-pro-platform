export type VisualBuilderVersion='1.0.0'|'2.0.0'|'2.0.1'
export type Device='desktop'|'tablet'|'mobile'
export interface VisualBuilderRelease{version:VisualBuilderVersion;label:string;schema:string;channel:string;recommended:boolean;description:string}
export interface PageDocument extends Record<string,unknown>{schema?:string;version?:number;title?:string;builder_version?:VisualBuilderVersion;builder?:Record<string,unknown>;blocks?:unknown[]}
export interface PageAdapter{state?:Record<string,unknown>|null;load():Promise<PageDocument>;saveDraft(document:PageDocument):Promise<unknown>;autosave?(document:PageDocument):Promise<unknown>;publish(document:PageDocument):Promise<unknown>;listTemplates?():Promise<unknown[]>;upload?(file:File):Promise<string>}
export interface RuntimeModule{SchedulerProAdapter:new(options?:Record<string,unknown>)=>PageAdapter&Record<string,any>;toSchedulerProContent(input:unknown):Record<string,unknown>;normalizeDocument?(input:unknown):PageDocument;[key:string]:unknown}
export const ARGWS_VISUAL_BUILDER_RELEASES:readonly VisualBuilderRelease[]
export const ARGWS_VISUAL_BUILDER_DEFAULT_VERSION:VisualBuilderVersion
export const ARGWS_VISUAL_BUILDER_SUPPORTED_VERSIONS:readonly VisualBuilderVersion[]
export function normalizeVisualBuilderVersion(value:unknown,fallback?:VisualBuilderVersion):VisualBuilderVersion
export function visualBuilderRelease(value:unknown):VisualBuilderRelease|undefined
export function activeVisualBuilderRuntimeVersion():VisualBuilderVersion|null
export function resolveVisualBuilderVersionFromContent(content:Record<string,any>|null|undefined):VisualBuilderVersion
export function loadVisualBuilderRuntime(value?:VisualBuilderVersion|string):Promise<RuntimeModule>
export function createSchedulerProAdapter(value:VisualBuilderVersion|string,options?:Record<string,unknown>):Promise<{adapter:PageAdapter&Record<string,any>;runtime:RuntimeModule;version:VisualBuilderVersion}>
