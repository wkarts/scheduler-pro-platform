# Scheduler Pro — Let's Encrypt com Cloudflare DNS-01

Este modo resolve certificados SSL para tenants dinâmicos como:

- `scheduler.argws.com.br`
- `*.scheduler.argws.com.br`
- `cliente-hash.scheduler.argws.com.br`

O desafio HTTP tradicional do Let's Encrypt não escala bem para subdomínios dinâmicos atrás de
CloudPanel/Cloudflare. Por isso o Scheduler Pro usa DNS-01 via Cloudflare.

## Pré-requisitos

No token Cloudflare usado pelo Scheduler Pro, habilite pelo menos:

- Zone Read;
- DNS Edit;
- Cache Purge, se o botão de purge do painel também for utilizado.

Para domínio próprio do cliente via Cloudflare for SaaS/Custom Hostnames, use também as permissões
e recursos de Custom Hostnames/SSL da conta Cloudflare.

## Zone ID x Account ID

Não use o Account ID como `CLOUDFLARE_ZONE_ID`. Eles são identificadores diferentes, embora ambos
possam ter formato semelhante.

O perfil ACME não injeta `CF_Zone_ID` no acme.sh. O plugin oficial `dns_cf` aceita `CF_Zone_ID` como
opcional e consegue descobrir a zone usando `CF_Token` quando o token possui `Zone:Read`. Antes de
emitir/renovar, o script também remove `CF_Zone_ID` antigo persistido nos arquivos do acme.sh para
não reaproveitar uma configuração incorreta.

## Variáveis

No `.env` da stack:

```env
CLOUDFLARE_API_TOKEN=...
# Opcional para o backend; se informado deve ser o Zone ID real, nunca o Account ID.
CLOUDFLARE_ZONE_ID=
ACME_EMAIL=admin@scheduler.argws.com.br
ACME_DOMAIN=scheduler.argws.com.br
ACME_STAGING=false
```

## Emitir/renovar wildcard

```bash
docker compose -f compose.yaml -f compose.acme.yaml --profile ssl up -d scheduler-acme
```

Os certificados ficam em:

```text
./scheduler-pro-data/certs/fullchain.pem
./scheduler-pro-data/certs/privkey.pem
./scheduler-pro-data/certs/cert.pem
./scheduler-pro-data/certs/ca.pem
```

## Uso no CloudPanel

Se o CloudPanel continuar terminando TLS externamente, importe os certificados gerados no
site/reverse proxy correspondente ou copie-os para o local configurado pelo CloudPanel.

Se o TLS for movido para um proxy próprio, monte `./scheduler-pro-data/certs` nesse proxy e configure
`fullchain.pem` + `privkey.pem`.

## Diferença entre domínio temporário e domínio próprio

Domínio temporário da própria plataforma:

```text
cliente-hash.scheduler.argws.com.br -> proxy.scheduler.argws.com.br
```

Este fluxo usa DNS normal da zone `argws.com.br`. Se o CNAME existe, o domínio pode ser marcado
como `ACTIVE`.

Domínio próprio do cliente:

```text
agenda.cliente.com.br -> proxy.scheduler.argws.com.br
```

Este fluxo usa Cloudflare Custom Hostnames/SSL quando disponível ou validação externa/manual do
domínio do cliente.
