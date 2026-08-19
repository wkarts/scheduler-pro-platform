# Scheduler Pro no CloudPanel

Este diretório documenta o deployment ARGWS com **um único Reverse Proxy**, **um único DNS wildcard** e **um único certificado wildcard** para todos os tenants gerenciados.

A arquitetura canônica é:

```text
Cloudflare DNS
  scheduler.argws.com.br
  *.scheduler.argws.com.br
          |
          v
CloudPanel / NGINX :443
  server_name scheduler.argws.com.br *.scheduler.argws.com.br
          |
          v
http://127.0.0.1:18080
          |
          v
Scheduler Pro Docker
  scheduler-proxy -> API / Web / Admin
          |
          v
TenantResolver pelo header Host
```

Não crie site, Reverse Proxy, DNS ou certificado novo por tenant.

## 1. Preparar o `.env`

```bash
cd /caminho/do/stack/deployments/cloudpanel
cp .env.example .env
```

Configure senhas, SMTP, Cloudflare e os valores do ambiente. Para DNS/TLS wildcard confirme:

```env
PUBLIC_PLATFORM_DOMAIN=scheduler.argws.com.br
TENANT_DEFAULT_DOMAIN_ROOT=scheduler.argws.com.br

CLOUDFLARE_API_TOKEN=TOKEN_COM_ZONE_READ_E_DNS_EDIT
CLOUDFLARE_ZONE_ID=
CLOUDFLARE_ZONE_NAME=argws.com.br
CLOUDFLARE_TEMPORARY_RECORD_TYPE=CNAME
CLOUDFLARE_TEMPORARY_RECORD_TARGET=proxy.scheduler.argws.com.br
CLOUDFLARE_TEMPORARY_RECORD_PROXIED=false
CLOUDFLARE_MANAGED_WILDCARD_DNS=true
CLOUDFLARE_MANAGED_WILDCARD_TARGET=proxy.scheduler.argws.com.br

TLS_PROVISIONING_MODE=local_acme
LOCAL_ACME_DOMAIN=scheduler.argws.com.br
LOCAL_ACME_CERT_DIR=/run/scheduler-pro-certs
ACME_EMAIL=admin@scheduler.argws.com.br
ACME_DOMAIN=scheduler.argws.com.br
ACME_STAGING=false
ACME_DNS_SLEEP=20
```

O token Cloudflare deste fluxo precisa de `Zone:Read` e `DNS:Edit` na zone `argws.com.br`. Cloudflare SSL for SaaS/Custom Hostnames não é necessário para `*.scheduler.argws.com.br`.

## 2. Subir a stack ARGWS

```bash
docker compose --env-file .env -f compose.argws.yaml pull
docker compose --env-file .env -f compose.argws.yaml up -d --remove-orphans
```

O serviço `scheduler-acme` sobe junto com a stack. Ele **não abre 80/443** e não concorre com o CloudPanel.

### O que o `scheduler-acme` faz automaticamente

1. abre um order ACME v2 no Let's Encrypt para:
   - `scheduler.argws.com.br`;
   - `*.scheduler.argws.com.br`;
2. recebe do Let's Encrypt o token/challenge daquele order;
3. usando `CLOUDFLARE_API_TOKEN`, cria temporariamente:

   ```text
   _acme-challenge.scheduler.argws.com.br TXT <challenge>
   ```

4. aguarda a propagação DNS;
5. o Let's Encrypt valida o DNS-01;
6. o TXT temporário é removido pelo plugin `dns_cf`;
7. o bundle é instalado em `${SCHEDULER_PRO_DATA_ROOT}/certs`:
   - `fullchain.pem`;
   - `privkey.pem`;
   - `cert.pem`;
   - `ca.pem`;
8. o cron interno do `acme.sh` verifica as renovações periodicamente.

**Não existe TXT ACME fixo para cadastrar manualmente.** O challenge muda a cada order/renovação e é criado/removido automaticamente.

## 3. DNS wildcard dos tenants

O backend reconcilia automaticamente:

```text
*.scheduler.argws.com.br CNAME proxy.scheduler.argws.com.br
Proxy Cloudflare: OFF / Somente DNS
```

Esse wildcard resolve qualquer tenant novo sem criar um DNS individual:

```text
empresa-a.scheduler.argws.com.br
empresa-b.scheduler.argws.com.br
qualquer-slug.scheduler.argws.com.br
```

Para migração segura, se um tenant antigo ainda tiver um registro específico, o Scheduler Pro detecta esse registro e o reconcilia para `DNS-only`, pois um registro específico tem precedência sobre o wildcard.

## 4. CloudPanel: configuração única

No CloudPanel mantenha **um único site Reverse Proxy**:

```text
Domínio: scheduler.argws.com.br
Reverse Proxy URL: http://127.0.0.1:18080
```

No VHost Editor use como referência:

```text
VHOST_WILDCARD_EXAMPLE.conf
```

O ponto essencial é existir somente:

```nginx
server_name scheduler.argws.com.br *.scheduler.argws.com.br;
```

Não repita blocos `server {}` para `admin`, `api`, `proxy` ou tenants. O wildcard já cobre todos os subdomínios de um nível e o `Host` original é preservado até o Scheduler Pro.

## 5. Instalação e renovação do certificado no CloudPanel

Há uma limitação do CloudPanel atual: o fluxo Let's Encrypt da própria interface/CLI usa o mecanismo nativo de emissão para domínios apontados ao servidor, mas **não oferece DNS-01 wildcard nativo**. Portanto o wildcard é renovado pelo `scheduler-acme`, não pelo emissor nativo do CloudPanel.

O CloudPanel continua sendo o terminador TLS e recebe automaticamente cada bundle renovado pelo CLI oficial `clpctl site:install:certificate`.

Faça **uma única instalação** do sincronizador no host:

```bash
cd /caminho/do/stack/deployments/cloudpanel
sudo bash scripts/install-cloudpanel-cert-sync.sh .env
```

O instalador cria uma tarefa root em `/etc/cron.d/scheduler-pro-cloudpanel-cert-sync` que, a cada 5 minutos:

- verifica se `fullchain.pem + privkey.pem` mudaram;
- se não mudaram, não faz nada;
- se mudaram, executa `clpctl site:install:certificate`;
- valida o VHost/NGINX pelo helper de deploy;
- grava o hash sincronizado;
- deixa log em `/var/log/scheduler-pro-cloudpanel-cert-sync.log`.

Assim a rotina fica:

```text
scheduler-acme Docker
  -> Cloudflare TXT DNS-01
  -> Let's Encrypt wildcard renovado
  -> scheduler-pro-data/certs
  -> sync detecta novo hash
  -> clpctl instala no site scheduler.argws.com.br
  -> CloudPanel/NGINX passa a servir o novo wildcard
```

O trabalho manual fica restrito a:

1. criar/manter o Reverse Proxy principal no CloudPanel;
2. colar uma vez o VHost wildcard;
3. executar uma vez `install-cloudpanel-cert-sync.sh`.

Novos tenants e futuras renovações não exigem novas ações no CloudPanel.

## 6. Diagnóstico

No Control Plane, **Integrações** mostra o estado `local_acme`, incluindo:

- presença do `fullchain.pem`;
- presença da chave privada sem expor seu conteúdo;
- SANs do certificado;
- expiração e dias restantes;
- marcador de instalação no CloudPanel;
- estado `READY`, `INCOMPLETE` ou `MISSING_CERTIFICATE`.

Os logs históricos de `Cloudflare Custom Hostnames` permanecem para auditoria, mas os hostnames gerenciados `*.scheduler.argws.com.br` não devem voltar a chamar `/custom_hostnames` quando `TLS_PROVISIONING_MODE=local_acme`.

## 7. Domínios próprios externos

Um domínio como:

```text
agenda.cliente.com.br
```

não é coberto por `*.scheduler.argws.com.br`. Esse caso continua separado e precisa de provisionamento TLS próprio. O wildcard da plataforma cobre apenas um nível abaixo de `scheduler.argws.com.br`.

## 8. Recuperar provisionamento estagnado

O provisionamento é idempotente por passo. Passos `completed` não são repetidos; somente passos ainda pendentes, em execução ou com falha são reenfileirados.

No Control Plane, use **Provisionamento -> Reprocessar** no job existente. Banco, migrations, storage, DNS, administrador e demais passos já concluídos são preservados.
