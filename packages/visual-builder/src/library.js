import { deepClone, exportSubtree, importSubtree } from './model.js';

const STORAGE_KEY = 'argws_visual_builder_library_v2';

export class LocalComponentLibrary {
  constructor({ storage = globalThis.localStorage, key = STORAGE_KEY } = {}) { this.storage = storage; this.key = key; this.memory = []; }
  _read() {
    if (!this.storage?.getItem) return deepClone(this.memory);
    try { const parsed = JSON.parse(this.storage.getItem(this.key) || '[]'); return Array.isArray(parsed) ? parsed : []; } catch { return []; }
  }
  _write(items) {
    this.memory = deepClone(items);
    if (this.storage?.setItem) this.storage.setItem(this.key, JSON.stringify(items));
  }
  list() { return this._read(); }
  saveFromDocument(document, nodeId, { name = 'Componente', category = 'Meus componentes' } = {}) {
    const subtree = exportSubtree(document, nodeId);
    if (!subtree) throw new Error('Elemento não encontrado para salvar na biblioteca.');
    const items = this._read();
    const item = { id: `component-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`, name, category, created_at: new Date().toISOString(), subtree };
    items.unshift(item); this._write(items.slice(0, 200)); return deepClone(item);
  }
  remove(id) { const items = this._read().filter(item => item.id !== id); this._write(items); }
  insert(document, id, parentId = null, index = null) {
    const item = this._read().find(row => row.id === id); if (!item) return null;
    return importSubtree(document, item.subtree, parentId, index);
  }
  export() { return JSON.stringify({ schema: 'argws-visual-builder-library/v1', items: this._read() }, null, 2); }
  import(payload) {
    const parsed = typeof payload === 'string' ? JSON.parse(payload) : payload;
    if (!parsed || !Array.isArray(parsed.items)) throw new Error('Biblioteca inválida.');
    this._write(parsed.items.slice(0, 200)); return this.list();
  }
}
