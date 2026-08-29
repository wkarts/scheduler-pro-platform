# PR — ARGWS Visual Builder 2.4.0 — Mobile, Agenda, PWA e CI

**Branch:** `fix/avb-2-4-0-mobile-agenda-pwa-ci`

**Título:** `fix: estabilizar AVB 2.4.0 no mobile, agenda legada, PWA e CI`

**Commit sugerido:** `fix: corrige mobile, agenda legada, PWA e validação CI do AVB 2.4.0`

## Objetivo

Corrigir regressões identificadas após a integração do ARGWS Visual Builder 2.4.0, com foco em experiência mobile, calendário, compatibilidade com agendamentos legados, edição de expediente/bloqueios, serviços de duração variável, atualização PWA/branding e estabilidade da validação CI.

## Principais correções

- corrige colisão MyPy em `platform_templates.py`;
- adiciona retry controlado para EOF transitório do BuildKit no Integration Tests;
- corrige labels do drawer mobile;
- corrige grid de 7 dias do calendário mobile;
- sincroniza dia selecionado ao navegar entre meses;
- inclui agendamentos legados no calendário pelo `starts_at`;
- tolera `ends_at` legado nulo/inválido;
- permite serviço com duração 0 (variável);
- preserva duração efetiva padrão no motor de conflito;
- confirma CRUD real de expediente e bloqueios;
- permite faixas específicas como 17:30–22:00;
- fortalece propagação de Service Worker, manifest e branding;
- avança cache PWA para `avb-2.4.0-final-mobile-agenda-v5`;
- atualiza contratos de testes antigos ainda presos ao AVB 2.3.2/login.html.

## Validação

- AVB 2.4.0: 70/70 PASS;
- AVB check: PASS;
- Python compileall: PASS;
- Workflow YAML: PASS;
- Vue/TypeScript: 28 scripts, 0 falhas sintáticas.

Ruff, MyPy e pytest completo devem ser reconfirmados pelo GitHub Actions.
