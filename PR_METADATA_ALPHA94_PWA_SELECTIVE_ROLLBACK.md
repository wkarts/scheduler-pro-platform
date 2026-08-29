# PR — Rollback seletivo do PWA da Alpha 94

**Branch:** `fix/alpha94-pwa-selective-rollback`

**Título:** `fix: reverter seletivamente identidade PWA da alpha.94 sem perder alpha.95`

**Commit sugerido:** `fix: restaura PWA legado dos tenants e preserva sincronização de versão`

## Objetivo

Desfazer somente o bloco de identidade PWA introduzido na Alpha 94 pela PR #80 que passou a proteger/forçar a identidade do aplicativo instalado e criou um override administrativo por tenant, sem reverter a Alpha 94 inteira e sem perder as correções posteriores da Alpha 95.

A base desta correção é o `main`/`v0.1.0-alpha.95` no commit `239a9246a90b3ef0b1f6a95e5160b1a951dc84b0`.

## Rollback aplicado

- remove `AdminPwaIdentityControl.vue` e seu mount no Control Plane;
- remove o router `pwa_identity` e o endpoint paralelo `/api/v1/pwa/manifest.webmanifest`;
- remove o alias de compatibilidade que interceptava `/api/v1/branding/manifest.webmanifest` antes do router de branding;
- restaura a URL canônica do manifest do tenant para `/api/v1/branding/manifest.webmanifest`;
- restaura o título da experiência nativa para `manifest.app.public_name || manifest.app.name`, como antes da Alpha 94;
- mantém o manifest/branding já existente em `branding.py`, sem criar um segundo motor de identidade PWA.

## Preservado propositalmente

- `tenant-version-badge.ts` e a sincronização da versão do tenant introduzida na Alpha 94;
- `installTenantVersionBadge()` no Web;
- todas as correções da Alpha 95;
- `tenant-overlay-layering.css` e a correção do operador sobre o Check-in;
- correções do bridge `postMessage` do Visual Builder;
- workflows, compose, proxy, banco, agenda, templates e demais funcionalidades não relacionadas ao rollback.

## Observação operacional sobre HTTP 502

O rollback remove o comportamento PWA da Alpha 94, porém HTTP 502 gerado antes de a requisição chegar ao `scheduler-proxy` é um problema de reverse proxy e não de manifest PWA. O contrato atual do projeto continua exigindo que o Reverse Proxy do CloudPanel para `scheduler.argws.com.br` aponte para `http://127.0.0.1:18080`, com o wildcard `*.scheduler.argws.com.br` no mesmo VHost.

Não foi feita refatoração de infraestrutura neste hotfix.

## Validação

- base oficial Alpha 95 extraída do artefato do workflow Release: **OK**;
- diferença de runtime limitada ao bloco PWA da Alpha 94: **OK**;
- sincronização de versão do tenant preservada: **OK**;
- correções Alpha 95 preservadas: **OK**;
- Python `compileall` nos arquivos tocados: **PASS**;
- contrato estático do rollback seletivo: **PASS**;
- ARGWS Visual Builder `npm run check`: **PASS**;
- ARGWS Visual Builder `npm test`: **74/74 PASS**.
