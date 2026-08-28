# Segurança

- HTML customizado passa por whitelist conservadora.
- CSS passa por sanitização de stylesheet/declarations.
- URLs são validadas por protocolo.
- JavaScript de Custom Code não é emitido por padrão; exige `trusted=true` e `allowTrustedCode=true` no host.
- Data Source descriptors não devem carregar credentials.
- Host Services mantêm integrações privilegiadas fora do documento.
- Capability Policy protege operações sensíveis da UI, mas **não substitui autorização backend**.
- Upload deve ser validado no servidor por MIME, tamanho, extensão e tenant.
- Webhooks/services devem ter allowlist, timeout, retry/idempotência e audit log no host.
- Em SaaS, resolva tenant no backend e nunca aceite tenant authority do documento/frontend.
- CSP é recomendada para páginas publicadas; se Custom Code trusted for habilitado, ajuste nonce/hash de forma controlada.
