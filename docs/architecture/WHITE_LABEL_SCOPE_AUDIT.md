# Auditoria de escopo — White-label, personalização e landing page

## Resultado da reanálise

O projeto segue o núcleo correto do prompt original: FastAPI/Python, tenant por hostname, web/admin PWA e Tauri para desktop/mobile. Porém a camada white-label ainda estava incompleta e não podia ser considerada concluída.

## Já presente

- `tenants.settings` como campo genérico JSONB.
- `domains` para hostnames provisórios/customizados.
- `landing_pages` e `landing_page_versions`.
- Sanitização de `custom_html` na landing page.
- Web/admin PWA com Tailwind.
- Tauri desktop/mobile como apps gerenciais.
- Workflows para imagem base, imagens de serviço, release e artefatos.

## Gaps obrigatórios

- Modelo próprio de branding por tenant.
- Perfil de build white-label por tenant.
- Entidade de assets visuais por tenant.
- Manifesto público de configuração do tenant para web/PWA/Tauri.
- Tokens de tema: cores, logo, favicon, typography, raio, modo, idioma/timezone.
- Aplicação visual por hostname sem depender de `tenant_id` enviado pelo frontend.
- Versionamento/publish de branding, separado da landing page.
- Configuração de bundle/package/app id para desktop/mobile por build profile.
- Endpoints tenant-aware para branding e landing pública.

## Decisão

White-label deve ser tratado como domínio de primeira classe do Scheduler Pro, não apenas como configuração solta em JSON.
