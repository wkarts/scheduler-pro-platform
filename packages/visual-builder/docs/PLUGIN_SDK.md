# Plugin SDK

Um plugin pode empacotar capacidades de um produto sem forkar o core.

```js
registerBuilderPlugin({
  id: 'argws.scheduler',
  version: '1.0.0',
  widgets: {},
  renderers: {},
  actions: {},
  dataSources: {},
  dynamicTags: {},
  dynamicFilters: {},
  services: {}
});
```

Use plugins por domínio: Scheduler, ERP, Financial, E-commerce, CMS, CRM etc.

## Regras

- widget: somente descrição de UI/defaults;
- renderer: gera visual do nó;
- data source: lê dados;
- action: coordena eventos do runtime;
- service: executa integração do host;
- dynamic tag: expõe valor contextual;
- dynamic filter: transforma valor.

Plugins podem ser removidos por `unregisterBuilderPlugin(id)` sem alterar o documento base.
