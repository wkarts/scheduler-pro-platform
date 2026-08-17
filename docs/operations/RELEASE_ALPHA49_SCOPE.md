# Escopo operacional da próxima release

A próxima release canônica após `v0.1.0-alpha.48` reúne:

- correção definitiva da resolução de Zone ID Cloudflare;
- DNS temporário idempotente usando a zone correta;
- purge de cache com erro específico quando faltar `Cache Purge`;
- ACME/Let's Encrypt DNS-01 sem reutilizar `CF_Zone_ID` incorreto;
- favicon branco do Admin para tema escuro;
- gestão visível de tenant pelo Control Plane;
- edição de nome/fuso horário;
- alteração do usuário principal do tenant;
- rotação de senha com revogação de sessões;
- suspensão, restauração e exclusão lógica preservando recursos isolados.
