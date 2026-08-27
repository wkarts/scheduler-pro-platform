import { addNode, deepClone, getNode, moveNode, normalizeDocument, removeNode } from './model.js';

export function createOperation(type, payload = {}, meta = {}) {
  return { id:globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`, type:String(type), payload:deepClone(payload), actor:meta.actor || null, timestamp:meta.timestamp || new Date().toISOString(), base_revision:meta.base_revision ?? null };
}

export function applyOperation(input, operation) {
  const doc = normalizeDocument(input); const op = operation || {}; const p = op.payload || {};
  switch (op.type) {
    case 'node.add': addNode(doc, p.node, p.parent_id ?? null, p.index ?? null); break;
    case 'node.remove': removeNode(doc, p.id); break;
    case 'node.move': moveNode(doc, p.id, p.parent_id ?? null, p.index ?? null); break;
    case 'node.props.patch': { const node=getNode(doc,p.id); if(node)Object.assign(node.props,p.patch||{}); break; }
    case 'node.style.patch': { const node=getNode(doc,p.id); if(node)Object.assign(node.style,p.patch||{}); break; }
    case 'node.meta.patch': { const node=getNode(doc,p.id); if(node)Object.assign(node.meta,p.patch||{}); break; }
    case 'document.patch': Object.assign(doc, deepClone(p.patch || {})); break;
    case 'settings.patch': Object.assign(doc.settings, deepClone(p.patch || {})); break;
    case 'global_styles.patch': Object.assign(doc.global_styles, deepClone(p.patch || {})); break;
    default: { const error=new Error(`Operação não suportada: ${op.type}`); error.code='UPB_OPERATION_UNSUPPORTED'; throw error; }
  }
  doc.project ||= {}; doc.project.collaboration ||= {}; doc.project.collaboration.revision = Number(doc.project.collaboration.revision || 0) + 1;
  return doc;
}

export function applyOperations(input, operations = []) { let doc=normalizeDocument(input); for(const op of operations)doc=applyOperation(doc,op); return doc; }
