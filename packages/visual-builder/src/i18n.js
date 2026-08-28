import { deepClone, normalizeDocument } from './model.js';

export function localeConfig(input) {
  const doc = normalizeDocument(input); const cfg = doc.project?.i18n || {};
  return { default_locale:String(cfg.default_locale || doc.settings?.language || 'pt-BR'), locales:Array.isArray(cfg.locales) && cfg.locales.length ? cfg.locales.map(String) : [String(cfg.default_locale || doc.settings?.language || 'pt-BR')], translations:cfg.translations && typeof cfg.translations === 'object' ? cfg.translations : {} };
}

export function localizeDocument(input, locale) {
  const doc = normalizeDocument(input); const cfg = localeConfig(doc); const target = String(locale || cfg.default_locale); const pack = cfg.translations[target] || {};
  if (pack.title != null) doc.title = String(pack.title);
  if (pack.seo && typeof pack.seo === 'object') Object.assign(doc.seo, deepClone(pack.seo));
  if (pack.nodes && typeof pack.nodes === 'object') {
    for (const [id, nodePatch] of Object.entries(pack.nodes)) {
      const node = doc.builder.nodes[id]; if (!node || !nodePatch) continue;
      if (nodePatch.props && typeof nodePatch.props === 'object') Object.assign(node.props, deepClone(nodePatch.props));
    }
  }
  doc.settings.language = target;
  return doc;
}

export function setNodeTranslation(input, locale, nodeId, props = {}) {
  const doc = normalizeDocument(input); doc.project ||= {}; doc.project.i18n ||= { default_locale:doc.settings.language || 'pt-BR', locales:[doc.settings.language || 'pt-BR'], translations:{} };
  const i18n = doc.project.i18n; i18n.translations ||= {}; i18n.translations[locale] ||= {}; i18n.translations[locale].nodes ||= {}; i18n.translations[locale].nodes[nodeId] ||= { props:{} }; Object.assign(i18n.translations[locale].nodes[nodeId].props, deepClone(props));
  if (!i18n.locales.includes(locale)) i18n.locales.push(locale);
  return doc;
}
