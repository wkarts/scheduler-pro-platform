# Correção — Control Plane Admin

O `apps/admin` não pode ser uma tela placeholder com números fictícios. Ele é a aplicação administrativa da plataforma e precisa operar como PWA instalável, com autenticação própria do Control Plane e shell profissional.

## Correções deste incremento

- Login visual administrativo em `apps/admin`.
- Consumo do endpoint real `/api/v1/auth/platform/login`.
- Armazenamento de sessão em `localStorage` para access/refresh token do Control Plane.
- Dashboard consumindo `/api/v1/platform/dashboard` com token Bearer.
- Backend retornando métricas reais do banco platform em vez de zeros fixos.
- Sidebar responsiva com módulos do Control Plane.
- PWA instalável com manifest, service worker, ícones e tela offline.
- Backend ajustado para permitir login no domínio admin dedicado.

## Regra de UX

A interface administrativa não deve exibir termos técnicos como “Control Plane” para operação cotidiana. O conceito existe no backend; no frontend administrativo aparecem plataforma, tenants/clientes, provisionamento, domínios, builds, integrações, auditoria e configurações.

## Divisão correta dos módulos

- `apps/admin`: administra clientes contratantes/tenants, planos, domínios, provisionamento, builds, releases, white-label, auditoria e integrações da plataforma.
- `apps/web`: administra a operação do cliente contratante: clientes finais, agenda, serviços, profissionais, mensagens, avisos, WhatsApp, aniversários/datas comemorativas e landing page.
- `apps/desktop` e `apps/mobile`: aplicações gerenciais construídas sobre o template Tauri/Rust.

## Próximos incrementos

- CRUD completo de tenants/clientes.
- Tela de provisionamento com logs por etapa.
- Tela de domínios e validação Cloudflare.
- Tela de builds com artefatos e release.
- Auditoria global.
- Usuários administrativos e permissões.
