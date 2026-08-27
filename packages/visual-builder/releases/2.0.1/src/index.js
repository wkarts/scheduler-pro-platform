export * from './model.js';
export * from './history.js';
export * from './registry.js';
export * from './sanitize.js';
export * from './dynamic.js';
export * from './dynamic-tags.js';
export * from './data-sources.js';
export * from './forms.js';
export * from './assets.js';
export * from './permissions.js';
export * from './i18n.js';
export * from './operations.js';
export * from './project-package.js';
export * from './custom-code.js';
export * from './embeds.js';
export * from './services.js';
export * from './submissions.js';
export * from './plugins.js';
export * from './actions.js';
export * from './library.js';
export * from './audit.js';
export * from './site-kit.js';
export * from './renderer.js';
export * from './runtime.js';
export * from './adapters.js';
export * from './templates.js';
export * from './editor.js';
export * from './page-renderer.js';

// Aliases públicos explícitos para integrações externas e SDKs.
export { createDocument as createPageDocument } from './model.js';
export { toSchedulerProContent as compileSchedulerProV2 } from './renderer.js';
import { renderDocument as _renderDocument } from './renderer.js';
export function renderPage(input, options = {}) {
  return _renderDocument(input, options).html;
}


import { renderDocumentAsync as _renderDocumentAsync } from './renderer.js';
export async function renderPageAsync(input, options = {}) { return (await _renderDocumentAsync(input, options)).html; }
