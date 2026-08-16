# Checkpoint final — Scheduler Pro

Data: 2026-08-16
Branch: `feature/final-hubfiscal-native-checkpoint`

Este checkpoint consolida o estado da aplicação após as entregas incrementais e define o critério objetivo para chamar o Scheduler Pro de concluído.

## Estado real do deploy observado

Os logs de produção mostram que a stack Docker/CloudPanel sobe corretamente:

- `scheduler-api`: saudável e respondendo `/api/v1/health/ready`.
- `scheduler-proxy`: servindo web/admin e proxy `/api/v1`.
- `scheduler-admin`: servindo PWA administrativo.
- `scheduler-web`: servindo PWA cliente.
- `postgres`, `redis`, `rabbitmq`, `minio`: healthy.
- Login administrativo retornou `200 OK` quando a senha correta foi usada.
- Endpoints administrativos retornaram `200 OK` para dashboard, tenants, domains, builds e observability.

## Entregas consolidadas

### Control Plane administrativo

- Login administrativo sem localhost.
- API relativa no PWA e absoluta nos apps nativos.
- Dashboard administrativo.
- Clientes SaaS / tenants.
- Domínios temporários e customizados.
- Verificação de DNS temporário separada de Custom Hostnames.
- Builds e artefatos.
- Logs e observabilidade.
- Diagnóstico Cloudflare separado por DNS, Custom Hostname e Purge Cache.
- Visual atualizado para padrão Hub Fiscal no Admin Desktop.

### Cliente / tenant

- WebApp/PWA cliente.
- Desktop cliente com API absoluta embutida por build.
- Mobile cliente com API absoluta embutida por build.
- Remoção de campo técnico de URL/API para o usuário final.
- Branding por distribuição/build profile.

### Infraestrutura

- Docker Compose CloudPanel/Dockge.
- Porta interna `127.0.0.1:18080`.
- GHCR images para API/worker/web/admin/proxy.
- Release pós-merge.
- Artefatos nativos pós-merge, não em pull request.
- APK debug instalável para homologação direta.
- Desktop instalável por plataforma, sem pacote portátil solto.
- Perfil ACME/Let’s Encrypt DNS-01 via Cloudflare para wildcard.

### Isolamento por tenant

Cada tenant deve manter recursos segregados:

- banco próprio;
- usuário de banco próprio;
- storage/prefixo próprio;
- artefatos próprios;
- logs próprios;
- build profiles próprios;
- domínios próprios.

## Critério para chamar de concluído

A aplicação só pode ser marcada como concluída quando todos os itens abaixo passarem em ambiente real:

1. WebApp cliente abre, autentica e executa agenda/clientes/serviços/profissionais/notificações.
2. Admin PWA abre, autentica, cria tenant, cria domínio temporário, verifica domínio, executa purge, lista logs e cria build.
3. Admin Desktop instala e autentica usando `https://admin.scheduler.argws.com.br/api/v1`.
4. Cliente Desktop instala e autentica usando `https://scheduler.argws.com.br/api/v1` ou endpoint do tenant.
5. Admin Mobile APK instala e autentica.
6. Cliente Mobile APK instala e autentica.
7. Cloudflare DNS cria CNAME/A proxied e o backend marca domínio temporário como `ACTIVE` quando o registro existe.
8. Purge Cloudflare funciona com token que tenha permissão de Cache Purge.
9. Let’s Encrypt wildcard via DNS-01 emite `fullchain.pem` e `privkey.pem` em `scheduler-pro-data/certs`.
10. Build Manager gera artefatos por tenant sem misturar storage/logs/artefatos.
11. Logs do tenant e logs da plataforma aparecem separados no painel.
12. Todas as telas administrativas e cliente seguem o padrão visual aprovado, sem telas vazias ou cards genéricos.

## Pendências que impedem declarar completo sem validação

- Validar token Cloudflare com permissão de purge/cache.
- Rodar o perfil ACME no servidor e confirmar emissão/renovação wildcard.
- Regenerar e reinstalar os binários nativos após a última alteração de UI/API.
- Validar fluxo completo de agenda e WhatsApp em tenant real.
- Validar tela mobile/desktop real no dispositivo após build final.

## Comando de atualização pós-merge

```bash
docker compose pull
docker compose up -d --remove-orphans
```

## Comando ACME/SSL wildcard

```bash
docker compose -f compose.yaml -f compose.acme.yaml --profile ssl up -d scheduler-acme
```

Certificados esperados:

```text
./scheduler-pro-data/certs/fullchain.pem
./scheduler-pro-data/certs/privkey.pem
```

## Decisão final

Este checkpoint não deve ser usado para mascarar pendência. Ele define exatamente o que precisa estar verde antes de declarar a aplicação concluída em produção.
