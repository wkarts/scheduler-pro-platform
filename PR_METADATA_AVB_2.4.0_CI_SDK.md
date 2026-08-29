# Branch

`fix/avb-2-4-0-ci-sdk-template-studio`

# Título

`fix: estabilizar AVB 2.4.0 CI e disponibilizar SDK no Control Plane`

# Commit sugerido

`fix: corrige CI do AVB 2.4.0 e adiciona SDK Template Studio`

# Descrição

## Objetivo

Corrigir os bloqueios encontrados nos runs de CI 90045954647/90045954648 e disponibilizar permanentemente o kit de desenvolvimento do ARGWS Visual Builder 2.4.0 dentro do Control Plane.

## CI

- corrige Ruff `F821` em `tenant_management.py`;
- remove import não utilizado `F401` de `experience_service.py`;
- corrige nulabilidade TypeScript de `PublicSitePage.vue`;
- corrige handler `openBlockedPeriod()` no Tenant Console;
- corrige inicialização opcional do Meta Pixel;
- atualiza contrato PWA para `/?source=pwa`;
- torna o teste Experience 2.4.0 compatível com a imagem isolada `/app` da API.

## SDK & Template Studio

Novo módulo no Control Plane, com permissão `templates.manage`, permitindo consultar/copiar/baixar:

- padrão mestre para IA;
- Template Runtime SDK v1;
- Experience Contract v2;
- Bindings v1;
- Theme Tokens v1;
- migração v1 → v2;
- Experience Package v2 enriquecido;
- pacote ARGWS Visual Builder 2.4.0.

Os arquivos são embarcados na API e continuam disponíveis remotamente mesmo quando o administrador está longe de sua máquina principal.

## Validação

- AVB Universal: 70/70 PASS;
- AVB integrado: 70/70 PASS;
- npm check: PASS;
- PWA contract: PASS;
- Python compileall: PASS;
- Vue/TS syntax: 28/28;
- Analytics strict TypeScript: PASS;
- contratos AVB 2.4.0: 7/7;
- 11/11 templates migrados para Experience v2.
