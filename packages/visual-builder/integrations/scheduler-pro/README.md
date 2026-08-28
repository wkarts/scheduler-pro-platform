# Integração Scheduler Pro — ARGWS Visual Builder 2.3.1

O Scheduler Pro usa o mesmo **ARGWS Visual Builder Universal** utilizado em qualquer outro projeto. Não existe uma variante do editor para o Scheduler.

## Mudança principal da 2.3

`TenantVisualPageBuilder.vue` passa a montar:

```html
<argws-visual-builder-app>
```

com `SchedulerProProjectAdapter`.

O usuário entra no próprio AVB e vê primeiro o **Project / Site Workspace**, com as páginas públicas disponíveis. Ao abrir uma página, entra no mesmo Visual Editor.

## Template Scheduler Pro com duas páginas

Um pacote:

```text
template.json
landing.html
agendamento.html
```

é importado como:

```text
Projeto / família
├── Landing Page           /pagina   LANDING
└── Página de Agendamento  /agendar  BOOKING
```

Nenhuma das páginas é encapsulada em `html_surface`.

Cada HTML completo é um `PageDocument` com:

```text
mode = HTML
```

## Mapeamento do adapter

- LANDING → `/api/v1/landing-pages/home/*`;
- BOOKING → `booking_page_template_content`, `booking_page_template_key` e `booking_page_template_version` nas configurações do tenant;
- upload/assets → File Service do tenant;
- LANDING mantém histórico e recuperação de emergência do Scheduler Pro.

## New-Only

A integração continua New-Only:

- nenhum editor antigo ativo;
- nenhum `TenantPublicPageEditorV2`;
- nenhum `PublicLandingRenderer` legado;
- não existe feature flag de retorno ao editor anterior.

## Instalação

```bash
python3 integrations/scheduler-pro/install.py /caminho/scheduler-pro-platform
cd /caminho/scheduler-pro-platform
npm install
npm run typecheck --workspace @scheduler-pro/web
npm run build --workspace @scheduler-pro/web
```
