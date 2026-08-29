# Host Adapter SDK Guide — ARGWS Visual Builder 2.4.0

O núcleo do AVB não conhece o backend da aplicação hospedeira. Integrações são feitas através de um adapter.

```js
const adapter = {
  async getContext() { return { tenant: { id:'...', name:'...' } }; },
  async getBranding() { return { logo_url:'...', colors:{ primary:'#2563eb' } }; },
  async getFeatures() { return { public_booking:true }; },
  async bookingCatalog() { return []; },
  async bookingAvailability(input) { return []; },
  async bookingCreate(input) { return { id:'...' }; },
  async navigate({to}) { location.href = to; },
  async track({event,properties}) { return { accepted:true }; },
};
```

Instalação:

```js
import { installTemplateRuntimeGlobal } from '@argws/visual-builder';
installTemplateRuntimeGlobal(adapter, 'ARGWSRuntime');
```

Assim o mesmo template pode rodar em FastAPI, Laravel, Node, PHP, uma SPA, um CMS ou qualquer outra aplicação que implemente o adapter.
