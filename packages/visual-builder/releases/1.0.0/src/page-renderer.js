import { normalizeDocument } from './model.js';
import { renderDocument } from './renderer.js';

const HTMLElementBase = globalThis.HTMLElement || class {};
export class ArgwsPageRenderer extends HTMLElementBase {
  constructor(){super();this.attachShadow({mode:'open'});this._document=normalizeDocument(null);this._device=null;this._context={};this._observer=null;}
  set document(value){this._document=normalizeDocument(value);this.render();}get document(){return this._document;}
  set context(value){this._context=value||{};this.render();}
  connectedCallback(){if(this.hasAttribute('document')){try{this._document=normalizeDocument(JSON.parse(this.getAttribute('document')));}catch{}}this._observer=globalThis.ResizeObserver?new ResizeObserver(()=>this.render()):null;this._observer?.observe(this);this.render();}
  disconnectedCallback(){this._observer?.disconnect();this._observer=null;}
  device(){if(this._device)return this._device;const w=this.getBoundingClientRect().width||innerWidth;return w<=680?'mobile':w<=1024?'tablet':'desktop';}
  render(){if(!this.shadowRoot)return;const {html,css}=renderDocument(this._document,{device:this.device(),context:this._context});this.shadowRoot.innerHTML=`<style>:host{display:block}${css}</style>${html}`;this.dispatchEvent(new CustomEvent('upb-rendered',{detail:{root:this.shadowRoot,document:this._document},bubbles:true,composed:true}));}
}
if(globalThis.customElements && !customElements.get('argws-page-renderer'))customElements.define('argws-page-renderer',ArgwsPageRenderer);
