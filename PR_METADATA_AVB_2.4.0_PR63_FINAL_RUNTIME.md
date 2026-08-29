# PR — ARGWS Visual Builder 2.4.0 — Runtime Público, Login, Assets, PWA e Branding

**Branch:** `fix/avb-2-4-0-pr63-final-runtime`

**Título:** `fix: estabilizar runtime público, login nativo, assets e PWA do AVB 2.4.0`

**Commit sugerido:** `fix: corrige agenda pública, assets, login nativo, branding e lifecycle do AVB 2.4.0`

## Objetivo

Concluir as correções funcionais identificadas na rodada da PR #63 sem reconstruir o Scheduler Pro e sem introduzir refatoração abrupta, preservando a base canônica do ARGWS Visual Builder 2.4.0 e o comportamento já estabilizado no `main`/`v0.1.0-alpha.83`.

A correção concentra-se nas regressões ainda reproduzíveis no runtime público: Agenda Pública retornando HTTP 422 por validação de template visual, assets migrados de Base64 quebrados entre Landing e Booking, bindings de imagem exibindo URL como texto, Login tratado como template em vez de superfície nativa, lifecycle do Visual Builder podendo resultar em tela branca e propagação incompleta da nova identidade nos ícones/manifests PWA.

## Principais correções

- isola a validação do template visual do motor da Agenda Pública, impedindo que conteúdo visual incompatível derrube `GET /api/v1/public/booking` com HTTP 422;
- aplica fallback canônico de Booking somente quando o template configurado não puder ser utilizado, sem bloquear catálogo, disponibilidade ou criação de agendamentos;
- corrige a migração de imagens Base64 para preservar caminhos lógicos independentes de Landing e Booking mesmo quando o conteúdo possui o mesmo SHA-256;
- adiciona compatibilidade simétrica `landing-*` ↔ `booking-*` para assets de tenants já migrados antes da correção;
- corrige Bindings v1 para reconhecer semanticamente bindings visuais legados, como `brand.logo`, mesmo quando persistidos incorretamente como `text`;
- impede que URLs de logo/imagem sejam renderizadas como texto dentro da página;
- mantém `/login` como rota pública, porém com Login nativo/white-label do Scheduler Pro, sem `login.html` e sem motor paralelo de autenticação no template;
- redireciona autenticação concluída para `/#dashboard` e mantém navegação de templates para o Login nativo do host;
- remove o Login do renderer de páginas públicas do `PublicSitePage`;
- mantém `TenantVisualPageBuilder` montado e deixa o próprio componente sincronizar sua visibilidade pelo hash, eliminando o ciclo que podia produzir tela branca ao abrir o Builder;
- atualiza o Login do tenant para usar símbolo transparente da plataforma quando não houver logo própria do tenant, evitando duplicação visual de marca;
- preserva logo personalizada do tenant quando configurada;
- troca ações primárias do Login e Control Plane por azul sólido, preservando a identidade clara e evitando gradiente multicolorido em botões funcionais;
- atualiza o wordmark do Control Plane para a identidade transparente do Scheduler Pro;
- regenera `icon-192.png`, `icon-512.png`, `maskable-192.png` e `maskable-512.png` de Web e Admin a partir do símbolo transparente canônico;
- atualiza manifests PWA para revisão `avb240-brand-v3`;
- avança o cache dos Service Workers para `avb-2.4.0-pr63-final-runtime-v6`, forçando propagação dos novos assets;
- adiciona testes regressivos específicos para migração Base64 Landing/Booking e bindings de imagem;
- preserva integralmente o workflow canônico `.github/workflows/integration-tests.yml`, sem retry artificial, mudança de concurrency ou alteração de branches.

## Validação

Base utilizada para a atualização completa:

- release: `v0.1.0-alpha.83`;
- commit base: `9f710d6ecdd9420fdaa1d66eb2e79c0074446083`;
- artefato oficial de source da própria release do Scheduler Pro.

Validações executadas após a aplicação:

- verificador estático da correção PR63 Final Runtime: **PASS**;
- Python `compileall` em `apps/api/app` e teste regressivo: **PASS**;
- ARGWS Visual Builder 2.4.0 `npm run check`: **PASS**;
- ARGWS Visual Builder 2.4.0 `npm test`: **72/72 PASS**;
- preservação de assets Landing/Booking com mesmo SHA e caminhos distintos: **PASS**;
- alias legado Landing ↔ Booking: **PASS**;
- bindings de imagem sem URL textual: **PASS**;
- Login removido do renderer público e mantido como superfície nativa: **PASS**;
- lifecycle do Builder com componente persistentemente montado: **PASS**;
- manifests/cache PWA na revisão nova: **PASS**;
- ícones 192/512 e maskable com dimensões corretas e bordas transparentes: **PASS**;
- SHA-256 do `.github/workflows/integration-tests.yml` antes/depois: **idêntico** (`8e7ae47d34275e0e2340c8fbf335fac6af2c34c77ce96bc7465643b35a8fdf72`).

O `pytest` completo da API não foi executado neste runtime porque a dependência `structlog`, carregada pelo `tests/conftest.py`, não está instalada no ambiente local. A validação completa de Ruff, MyPy, pytest, builds Vue/TypeScript e integração deve ser reconfirmada pelo GitHub Actions após a abertura da PR.
