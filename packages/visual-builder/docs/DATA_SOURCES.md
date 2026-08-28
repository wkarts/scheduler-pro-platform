# Data Sources e Dynamic Tags

## Data Source

```js
registerDataSource('crm.customers', async ({query, runtime}) => {
  return runtime.api.get('/customers', {params:query});
}, {cacheTtl: 15000});
```

`query_loop` guarda somente `source`, `query_json`, `limit` e filhos. Secrets nunca devem estar em `query_json`.

## Dynamic Tags

```js
registerDynamicTag('auth.user', ctx => ctx.user);
```

Uso:

```text
{{ auth.user.name | upper }}
{{ item.price | currency:BRL:pt-BR }}
{{ article.date | date:pt-BR:long }}
```

## Cache

`QueryCache` é opcional e local ao runtime. O backend continua responsável por cache HTTP, Redis e políticas de autorização.
