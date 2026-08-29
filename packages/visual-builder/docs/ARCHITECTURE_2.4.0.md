# ARGWS Visual Builder 2.4.0 — Arquitetura canônica

## Princípio central

O ARGWS Visual Builder 2.4.0 é **universal**. Ele não pertence ao Scheduler Pro.
O núcleo trabalha com HTML/CSS/JS final, bindings, theme tokens, assets, permissões e um Runtime SDK baseado em adapter.

Aplicações específicas integram o Builder implementando um **Host Adapter**.

```text
ARGWS Visual Builder 2.4.0
        │
        ├── Experience Contract v2
        ├── Template Runtime SDK v1
        ├── Bindings v1
        ├── Theme Tokens v1
        ├── Assets
        └── Editor Permissions
                 │
                 ├── Scheduler Pro Adapter
                 ├── ARGWS ERP Adapter
                 ├── ARGWS Financial Adapter
                 └── qualquer outro host
```

## Runtime canônico

HTML continua sendo o formato canônico de execução.

O autor pode produzir o HTML diretamente ou usar Astro, Svelte, Vue, React ou outra tecnologia e fornecer o **resultado compilado final**. O host nunca precisa compilar o template em produção.

## Superfícies

O Experience Contract v2 é propositalmente pequeno:

- `LANDING`
- `BOOKING`

Login **não é uma superfície de template** do contrato universal. Hosts podem possuir Login nativo/white-label.

## Regra de ouro

Template é uma página completa. O Builder não reconstrói HTML sofisticado em uma árvore de widgets. O HTML original é preservado e somente os bindings explicitamente declarados são alterados.
