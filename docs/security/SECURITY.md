# Segurança

Obrigatório desde a fundação:

- HTTPS.
- CORS restritivo.
- CSP/HSTS na borda/origin.
- Rate limiting.
- Refresh token rotativo.
- Senhas com Argon2.
- Tenant por hostname.
- Usuário PostgreSQL por tenant.
- Segredos fora do código.
- Sanitização de HTML no Landing Builder.
- Deduplicação de webhooks.
- Auditoria em eventos sensíveis.
- URLs assinadas para arquivos privados.

Nunca commit nessa base:

- `.env` real.
- Token Cloudflare.
- Token WhatsApp.
- Senhas PostgreSQL reais.
- Certificados Apple/Android.
