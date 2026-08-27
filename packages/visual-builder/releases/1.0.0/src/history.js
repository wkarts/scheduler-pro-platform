import { deepClone } from './model.js';

export class HistoryStack {
  constructor(limit = 80) { this.limit = limit; this.past = []; this.future = []; this.current = null; }
  reset(value) { this.current = deepClone(value); this.past = []; this.future = []; }
  checkpoint(value) {
    if (this.current != null) this.past.push(deepClone(this.current));
    if (this.past.length > this.limit) this.past.shift();
    this.current = deepClone(value); this.future = [];
  }
  canUndo() { return this.past.length > 0; }
  canRedo() { return this.future.length > 0; }
  undo() { if (!this.canUndo()) return deepClone(this.current); this.future.push(deepClone(this.current)); this.current = this.past.pop(); return deepClone(this.current); }
  redo() { if (!this.canRedo()) return deepClone(this.current); this.past.push(deepClone(this.current)); this.current = this.future.pop(); return deepClone(this.current); }
}
