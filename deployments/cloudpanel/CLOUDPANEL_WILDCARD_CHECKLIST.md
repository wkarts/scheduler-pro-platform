# Checklist — Scheduler Pro wildcard no CloudPanel

## Cloudflare

- `proxy.scheduler.argws.com.br` aponta para o IP público do servidor.
- `*.scheduler.argws.com.br` é criado/reconciliado pelo Scheduler Pro como CNAME para `proxy.scheduler.argws.com.br`.
- Proxy Cloudflare desligado (`DNS only`) para os hostnames gerenciados.
- API Token restrito à zone `argws.com.br` com `Zone:Read` + `DNS:Edit`.

## CloudPanel

Crie/mantenha somente um Reverse Proxy:

- Domínio: `scheduler.argws.com.br`
- URL: `http://127.0.0.1:18080`

No VHost use um único `server_name`:

```nginx
server_name scheduler.argws.com.br *.scheduler.argws.com.br;
```

Use `VHOST_WILDCARD_EXAMPLE.conf` como referência. Não crie um bloco por tenant.

## ACME

O container `scheduler-acme` sobe com `compose.argws.yaml` e emite:

- `scheduler.argws.com.br`
- `*.scheduler.argws.com.br`

O TXT `_acme-challenge.scheduler.argws.com.br` é temporário e criado/removido automaticamente pelo plugin Cloudflare do acme.sh.

## Sincronização CloudPanel

Uma vez no host:

```bash
sudo bash scripts/install-cloudpanel-cert-sync.sh .env
```

Depois disso a renovação é automática: o ACME Docker renova e o sync instala no CloudPanel somente quando o hash do bundle muda.

## Verificação

```bash
docker compose --env-file .env -f compose.argws.yaml ps scheduler-acme
ls -l scheduler-pro-data/certs/
sudo tail -n 100 /var/log/scheduler-pro-cloudpanel-cert-sync.log
```

No navegador teste um hostname de tenant, por exemplo:

```text
https://tenant.scheduler.argws.com.br
```
