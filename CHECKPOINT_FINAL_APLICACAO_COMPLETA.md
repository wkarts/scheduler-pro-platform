# CHECKPOINT — AVB 2.3.2 Interaction/Performance Fix — 2026-08-28

Esta é a rodada corretiva posterior à build/release 2.3.2 observada em produção.

## Correções principais

- ShadowRoot usa `addEventListener()` real no lifecycle, em vez de `shadowRoot.onclick`.
- Tema, Importar, Nova página, Fechar, Editar, toggles e Aplicar template voltam a receber eventos.
- Aplicar template exige confirmação interna e executa aplicação atômica no backend.
- Importação ZIP/Project Package persiste LANDING + BOOKING + LOGIN no Scheduler Pro.
- `/settings/tenant/compact` evita transferir HTMLs de ~1,6 MB no bootstrap.
- `/settings/tenant/value/{key}` carrega conteúdo pesado somente ao editar a superfície.
- `/landing-pages/{slug}/document` carrega somente o documento efetivo da Landing.
- `LandingPageService.versions()` não carrega mais o campo `content` completo de até 100 versões.
- Cache PWA: `avb-2.3.2-interactionfix-v3`.

## Validação

- AVB: 85/85 PASS
- `npm run check`: PASS
- 8/8 templates: PASS
- Vue/TypeScript: 45 arquivos / 0 falhas sintáticas
- Python `compileall`: PASS
- pytest completo local: bloqueado apenas pela ausência de `structlog` no runtime local.

---

# Checkpoint — Scheduler Pro + ARGWS Visual Builder 2.3.2

Data: 2026-08-28

## Base

Atualização incremental aplicada sobre a base canônica 2.3.1 Runtime Fix, originada da `main` atual fornecida pelo usuário. Nenhuma publicação remota foi executada.

## Estado canônico

- ARGWS Visual Builder: **2.3.2**;
- PWA: experiência principal;
- Android/APK: ativo;
- iOS/IPA: ativo;
- desktop Windows/Linux/macOS: código preservado, builds fora do fluxo ativo.

## Páginas públicas

- Landing Page `/pagina` — `LANDING`;
- Agenda Pública `/agendar` — `BOOKING`;
- Login `/login` — `LOGIN`.

As três superfícies permanecem páginas completas e independentes.

## Correções centrais 2.3.2

1. **Editor HTML não fica mais vazio**: documento `mode=HTML` não é confundido com uma página visual sem `builder.root_ids`.
2. **Workspace rápido**: Project/Site carrega primeiro settings + contexto e cria as três páginas imediatamente; HTML completo é buscado somente ao editar.
3. **Catálogo progressivo e cacheado**: as 8 famílias oficiais carregam em segundo plano e a validação/descompactação dos ZIPs é memoizada no backend.
4. **Aplicar template persiste antes de abrir**: LANDING, BOOKING ou LOGIN são salvos como rascunho/configuração antes de entrar no editor; a abertura usa `reload:false` para não restaurar o documento anterior.
5. **Salvar/Publicar**: Landing salva versão de rascunho e publica pelo Landing Service; Booking/Login persistem `content`, `key` e `version` nas configurações do tenant usadas pelas páginas públicas.
6. **Inspector 2.3.2**: mostra `ARGWS Visual Builder 2.3.2` e separa explicitamente a versão do editor do contrato Scheduler Pro compatível.
7. **Superfície LOGIN**: disponível também no inspector e no importador de famílias.
8. **Branding 2.3.2**: suporte à logo oficial por tema preservado.

## Templates oficiais

Oito famílias reais estão em `apps/api/resources/template-packages/`:

1. Scheduler Pro — Padrão Genérico;
2. Barber Shop — Neo Genérico;
3. Clínica Médica — Genérico;
4. Clínica Odontológica — Genérico;
5. Clínica Veterinária — Genérico;
6. Martelinho de Ouro — Genérico;
7. Studio de Unhas — Genérico;
8. Tecnologia — Genérico Simples.

Cada ZIP foi validado e importado como:

```text
LANDING /pagina  HTML
BOOKING /agendar HTML
LOGIN   /login   HTML
```

O Template Genérico é fallback; não substitui automaticamente personalizações existentes.

## Validações executadas

- ARGWS Visual Builder: **81/81 testes aprovados**;
- `npm run check` do AVB: **OK**;
- importador AVB: **8/8 famílias**, três páginas por família;
- `HtmlTemplatePackageService`: **8/8 pacotes válidos**;
- `python -m compileall app migrations tests`: **OK**;
- sintaxe de scripts TypeScript/Vue em Web + Admin: **45 arquivos, 0 falhas**;
- sintaxe JavaScript do AVB: **OK**;
- contratos Python executáveis sem fixtures de infraestrutura: **18 passaram**; um contrato de bootstrap não pôde ser importado localmente porque o runtime não possui `asyncpg`.

## Limitação do runtime local

A suíte `pytest` completa não inicia neste ambiente porque faltam dependências de produção/teste como `structlog` e `asyncpg`. Essas dependências não foram removidas do projeto; a suíte completa deve rodar no GitHub Actions/ambiente oficial, onde as dependências são instaladas.

---

## Checkpoint canônico — ARGWS Visual Builder 2.4.0

Direção final: AVB Universal + Scheduler Pro Experience Contract v2. Landing e Agenda Pública permanecem customizáveis; Login é nativo white-label. Templates v1/Base64 são migrados automaticamente para assets. Esta rodada também inclui CRUD de expediente/bloqueios, resiliência para agendamentos legados, correções de menu/calendário mobile e nova identidade padrão Scheduler Pro/PWA.

Validação desta rodada: AVB 70/70 (universal e integrado), npm check PASS, compileall PASS, contratos 2.4.0 5/5, scripts Vue 28/28 sem falhas sintáticas.
