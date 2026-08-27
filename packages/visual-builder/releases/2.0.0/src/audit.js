import { getNode, normalizeDocument } from './model.js';
import { materializeProps } from './renderer.js';

export function auditDocument(input) {
  const doc = normalizeDocument(input);
  const issues = [];
  const add = (severity, code, message, nodeId = null) => issues.push({ severity, code, message, node_id: nodeId });
  if (!String(doc.seo?.title || '').trim()) add('warning', 'SEO_TITLE_EMPTY', 'Defina um título SEO.');
  if (!String(doc.seo?.description || '').trim()) add('warning', 'SEO_DESCRIPTION_EMPTY', 'Defina uma descrição SEO.');
  const visit = id => {
    const node = getNode(doc, id); if (!node) return;
    const p = materializeProps(node);
    if (node.type === 'image' && !String(p.alt || '').trim()) add('warning', 'IMAGE_ALT_EMPTY', 'Imagem sem texto alternativo.', node.id);
    if (node.type === 'heading' && p.level === 'h1') add('info', 'H1_FOUND', 'Título H1 encontrado.', node.id);
    if (['button', 'whatsapp_button'].includes(node.type) && !String(p.label || '').trim()) add('error', 'BUTTON_LABEL_EMPTY', 'Botão sem rótulo acessível.', node.id);
    if (node.type === 'form' && !Array.isArray(p.fields)) add('error', 'FORM_FIELDS_INVALID', 'Formulário sem definição de campos.', node.id);
    if (node.style?.position === 'fixed' && !node.style?.zIndex) add('info', 'FIXED_ZINDEX_UNSET', 'Elemento fixo sem z-index explícito.', node.id);
    node.children.forEach(visit);
  };
  doc.builder.root_ids.forEach(visit);
  const h1Count = issues.filter(item => item.code === 'H1_FOUND').length;
  if (h1Count === 0) add('warning', 'H1_MISSING', 'A página não possui título H1.');
  if (h1Count > 1) add('warning', 'H1_MULTIPLE', 'A página possui mais de um H1.');
  const errors = issues.filter(item => item.severity === 'error').length;
  const warnings = issues.filter(item => item.severity === 'warning').length;
  return { score: Math.max(0, 100 - errors * 20 - warnings * 5), errors, warnings, issues };
}
