import { deviceForWidth, normalizeDocument } from './model.js';
import { renderDocumentAsync } from './renderer.js';
import { hydratePage } from './runtime.js';

const HTMLElementBase = globalThis.HTMLElement || class {};
export class ArgwsPageRenderer extends HTMLElementBase {
  constructor(){super();this.attachShadow({mode:'open'});this._document=normalizeDocument(null);this._device=null;this._context={};this._runtime={};this._observer=null;this._cleanup=null;this._generation=0;this._connected=false;}
  set document(value){this._document=normalizeDocument(value);if(this._connected)void this.render();}get document(){return this._document;}
  set context(value){this._context=value||{};if(this._connected)void this.render();}get context(){return this._context;}
  set runtime(value){this._runtime=value||{};if(this._connected)void this.render();}get runtime(){return this._runtime;}
  set deviceOverride(value){this._device=value||null;if(this._connected)void this.render();}
  connectedCallback(){if(this._connected)return;this._connected=true;if(this.hasAttribute('document')){try{this._document=normalizeDocument(JSON.parse(this.getAttribute('document')));}catch{}}this._observer=globalThis.ResizeObserver?new ResizeObserver(()=>void this.render()):null;this._observer?.observe(this);void this.render();}
  disconnectedCallback(){this._connected=false;this._observer?.disconnect();this._observer=null;this._cleanup?.();this._cleanup=null;this._generation+=1;}
  device(){if(this._device)return this._device;const w=this.getBoundingClientRect().width||globalThis.innerWidth||1180;return deviceForWidth(this._document,w);}
  async render(){
    if(!this.shadowRoot)return;const generation=++this._generation;this._cleanup?.();this._cleanup=null;
    const rendered=await renderDocumentAsync(this._document,{device:this.device(),context:this._context,responsive:true,locale:this._runtime.locale||null,queryCache:this._runtime.queryCache||null,strictData:Boolean(this._runtime.strictData),runtime:this._runtime});
    if(generation!==this._generation||!this.shadowRoot)return;
    this.shadowRoot.innerHTML=`<style>:host{display:block}${rendered.css}</style>${rendered.html}`;
    const page=this.shadowRoot.querySelector('.upb-page');
    this._cleanup=hydratePage(page,{actionRuntime:{...this._runtime,...(this._context?.actionRuntime||{})},onFormSubmit:this._context?.onFormSubmit||this._runtime?.onFormSubmit||null});
    this.dispatchEvent(new CustomEvent('upb-rendered',{detail:{root:this.shadowRoot,document:rendered.document,device:this.device(),dataErrors:rendered.data_errors||[]},bubbles:true,composed:true}));
  }
}
if(globalThis.customElements && !customElements.get('argws-page-renderer'))customElements.define('argws-page-renderer',ArgwsPageRenderer);
