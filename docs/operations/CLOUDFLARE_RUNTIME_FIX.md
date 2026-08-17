# Correção Cloudflare no runtime ARGWS

Diagnóstico consolidado:

1. O token Cloudflare estava ativo e conseguia acessar a conta/zone.
2. O valor usado como `CLOUDFLARE_ZONE_ID` podia ser confundido com o Account ID.
3. DNS temporário chegava a ser criado, mas verificações posteriores e purge eram executados contra o identificador incorreto.
4. O perfil ACME também exportava o mesmo valor para `CF_Zone_ID`, fazendo o DNS-01 reutilizar a configuração errada.

Correção aplicada:

- validação da zone configurada antes de DNS, Custom Hostnames e purge;
- autodetecção da zone pelo hostname da plataforma quando o ID configurado é inválido;
- diagnóstico informa Zone ID configurado e efetivamente resolvido;
- erro de Cache Purge permanece específico e não invalida o DNS do tenant;
- ACME/Let's Encrypt deixa `CF_Zone_ID` opcional e remove valores antigos persistidos antes da emissão;
- domínio temporário continua sendo DNS normal; domínio próprio continua separado em Custom Hostnames/SSL.

Permissões mínimas recomendadas no token:

- Zone Read;
- DNS Edit;
- Cache Purge, quando o purge pelo painel for utilizado.

O Zone ID pode ficar vazio no `.env` da stack ARGWS; o backend resolve a zone a partir de
`CLOUDFLARE_CUSTOM_HOSTNAME_ORIGIN` quando o token possui Zone Read.
