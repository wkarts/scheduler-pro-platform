# Scheduler Pro — Matriz de conclusão do produto

Esta matriz consolida o escopo operacional exigido para considerar a plataforma concluída para homologação real.

## Aplicações

| Aplicação | Status esperado | Critério de aceite |
| --- | --- | --- |
| WebApp cliente/PWA | Operacional | login, dashboard, agenda, clientes, serviços, profissionais, WhatsApp, notificações, marca/app e instalação PWA |
| Admin Control Plane/PWA | Operacional | visual no padrão Hub Fiscal, tenants, domínios, builds, logs, integrações, auditoria, configurações e observabilidade |
| Desktop cliente | Instalável | instalador final Windows/macOS/Linux, API absoluta embutida, sem campo de URL para usuário final |
| Desktop admin | Instalável | Control Plane instalado, API absoluta, logs/domínios/builds/provisionamento |
| Mobile cliente | APK debug instalável | app arm64 installable, sessão local, agenda e módulos principais |
| Mobile admin | APK debug instalável | app arm64 installable, Control Plane mobile e logs |

## Motores obrigatórios

| Motor | Critério de aceite |
| --- | --- |
| Agenda | disponibilidade, conflitos, status, histórico e endpoints transacionais |
| Notificações | templates por tenant, lembretes 24h/2h, fila idempotente |
| WhatsApp/Evolution | configuração, envio, webhook idempotente e logs de integração |
| Provisionamento | tenant, banco, usuário DB, storage, domínio, branding, build profile e logs |
| Cloudflare DNS | domínio temporário idempotente e verificação por DNS record |
| Cloudflare Custom Hostnames | domínio próprio do cliente separado do temporário |
| Cache purge | botão operacional com diagnóstico específico para permissão Cloudflare |
| ACME/SSL | wildcard Let's Encrypt via DNS-01 para tenants dinâmicos |
| Observabilidade | logs plataforma + logs tenant + isolamento de banco/storage/artefatos |
| Build Manager | build por tenant/target, artefatos isolados e release pós-merge |

## Isolamento por tenant

Cada tenant deve possuir fronteiras próprias:

- banco próprio;
- usuário de banco próprio;
- bucket/prefixo S3 próprio;
- prefixo de artefatos próprio;
- logs próprios;
- build profiles próprios;
- domínio temporário/custom isolado.

O Control Plane pode visualizar tudo, mas cada tenant só pode acessar o seu próprio espaço.

## Observações operacionais

- APK padrão de homologação é debug assinado e instalável diretamente, sem keystore de produção.
- AAB/Play Store não faz parte do fluxo padrão atual.
- Desktop deve gerar instaladores finais, nunca pacote portável com executáveis internos de build.
- Domínio temporário `*.scheduler.argws.com.br` usa DNS da própria zone.
- Domínio próprio do cliente usa Custom Hostnames/SSL ou validação externa.
