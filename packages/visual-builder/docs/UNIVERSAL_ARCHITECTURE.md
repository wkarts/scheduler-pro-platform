# Arquitetura Universal 2.0

## Princípio

O ARGWS Visual Builder não pertence ao backend. Ele possui um documento canônico e contratos de extensão. Laravel, FastAPI, PHP, Node, Vue ou qualquer outro projeto apenas fornecem persistência, dados e capacidades específicas.

```text
Editor Web Component
       │
       ├── Document/AST V3
       ├── Widget Registry
       ├── Renderer Registry
       ├── Design System / Responsive
       ├── Dynamic Tags
       ├── Query/Data Source Engine
       ├── Form/Action Engine
       ├── SiteKit
       ├── Plugin SDK
       ├── Host Services
       └── Project Package
               │
      ┌────────┴─────────┐
      │                  │
 Renderer Web       Compiler/Exporter
 Component          HTML / Scheduler V2
      │
 Host application
 Laravel / FastAPI / PHP / Node / Vue / React / Svelte / etc.
```

## Separação de autoridade

- Documento: layout, estilo, conteúdo, bindings, conditions e descritores.
- Host: autenticação, tenant, banco, secrets, uploads, email, pagamentos e regras de negócio.
- Data Source: consulta dados do host sem o documento conhecer banco ou framework.
- Host Service: executa ações privilegiadas sem expor secrets ao documento.
- Plugin: reúne widgets/renderers/data sources/actions/services de um domínio.

## Surfaces

O mesmo schema pode representar `PAGE`, `LANDING`, `HEADER`, `FOOTER`, `SINGLE`, `ARCHIVE`, `POPUP`, `OFFCANVAS` e surfaces registradas por projeto.

## Scheduler Pro

O documento V3 é autoridade de edição. Para compatibilidade, `compileSchedulerProV2()` gera `version:2` com os blocos suportados e preserva `builder.schema=argws-visual-builder/v3` como metadata. Assim a adoção continua reversível.
