# Integração Scheduler Pro — ARGWS Visual Builder 2.3.2

O Scheduler Pro utiliza o mesmo **ARGWS Visual Builder Universal 2.3.2**. A integração mantém três páginas públicas completas e independentes:

```text
Projeto / Site
├── Landing Page   /pagina   LANDING
├── Agenda Pública /agendar  BOOKING
└── Login          /login    LOGIN
```

Cada HTML é um `PageDocument` de primeira classe com `mode = HTML`; não é encapsulado como widget `html_surface`.

## Carregamento 2.3.2

O Workspace carrega primeiro apenas configurações e contexto do tenant. Os documentos HTML completos são buscados sob demanda quando a página é aberta para edição. O catálogo oficial carrega em segundo plano.

Uma página HTML pode ter `builder.root_ids=[]` e ainda assim ser uma página válida. O editor 2.3.2 não substitui mais esse conteúdo pelo estado “Página vazia”.

## Aplicação de templates

A ação é por superfície:

```text
Aplicar template · Landing
Aplicar template · Agendamento
Aplicar template · Login
```

O documento selecionado é persistido antes da abertura do editor. A abertura posterior não recarrega o conteúdo anterior sobre o template recém-aplicado.

## Mapeamento do adapter

- LANDING → `/api/v1/landing-pages/home/*` (rascunho, versões, publicação);
- BOOKING → `booking_page_template_content`, `booking_page_template_key`, `booking_page_template_version`;
- LOGIN → `login_page_template_content`, `login_page_template_key`, `login_page_template_version`;
- contexto real → `/api/v1/public/context`;
- catálogo oficial → `/api/v1/landing-pages/template-families`;
- upload/assets → File Service do tenant.

## Compatibilidade

O contrato `scheduler-pro-html-template/v1` e o pacote `scheduler-pro-template-package/v1` são preservados de propósito para compatibilidade. **A versão do editor é 2.3.2 e não deve ser confundida com a versão do contrato de conteúdo.**

## Instalação/validação

```bash
npm install
npm run check --workspace @argws/visual-builder
npm test --workspace @argws/visual-builder
npm run typecheck --workspace @scheduler-pro/web
npm run build --workspace @scheduler-pro/web
```
