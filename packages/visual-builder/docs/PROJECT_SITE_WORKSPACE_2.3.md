# ARGWS Visual Builder 2.3 — Project / Site Workspace

A versão 2.3 corrige o modelo conceitual do produto: o ARGWS Visual Builder deixa de tratar documentos HTML completos como widgets e passa a administrar um **Projeto/Site com múltiplas páginas de primeira classe**.

## Um único produto, dois workspaces internos

```text
ARGWS Visual Builder
├── Project / Site Workspace
│   ├── Pages
│   ├── Templates
│   ├── Components
│   ├── Popups
│   └── Assets / Site Kit
└── Visual Editor Workspace
    └── documento atualmente aberto
```

Não existe uma tela de administração diferente por host. Laravel, FastAPI, PHP, Vue, Scheduler Pro e outros projetos montam o mesmo `<argws-visual-builder-app>`.

## Documento HTML é página, não elemento

Desde 2.3:

```json
{
  "mode": "HTML",
  "surface": "LANDING",
  "html": {
    "document": "<!doctype html>...",
    "contract": "scheduler-pro-html-template/v1"
  },
  "builder": {
    "root_ids": [],
    "nodes": {}
  }
}
```

Portanto não existe `html_surface` na árvore da página importada.

Documentos legados que tinham um único `html_surface` contendo um HTML completo são migrados automaticamente para `mode=HTML`.

## Projeto universal

Schema:

```text
argws-visual-builder-project/v2
```

Cada projeto possui `pages[]`, e cada página contém:

- `id`;
- `title`;
- `slug`;
- `route`;
- `surface`;
- `kind`;
- `status`;
- `document`.

## Scheduler Pro

O importador `scheduler-pro-template-package/v1` lê a família inteira:

```text
template.json
landing.html
agendamento.html
```

Resultado:

```text
Projeto: <nome da família>
├── Landing Page
│   ├── route: /pagina
│   ├── surface: LANDING
│   └── mode: HTML
└── Página de Agendamento
    ├── route: /agendar
    ├── surface: BOOKING
    └── mode: HTML
```

O `SchedulerProProjectAdapter` apenas traduz essas páginas para os endpoints/contratos do Scheduler Pro. O conceito de Projeto/Páginas pertence ao core universal.

## APIs públicas principais

```js
createProject()
createProjectPage()
normalizeProject()
importSchedulerProTemplateFamily()
MemoryProjectAdapter
RestProjectAdapter
SchedulerProProjectAdapter
ProjectPageAdapter
ArgwsVisualBuilderApp
```

## Web Component universal

```html
<argws-visual-builder-app></argws-visual-builder-app>
```

O host fornece somente um Project Adapter.
