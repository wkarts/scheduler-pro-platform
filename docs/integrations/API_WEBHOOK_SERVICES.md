# Scheduler Pro — API Services e Webhook Services

## O que muda

Esta evolução preserva os endpoints e serviços de negócio existentes. Acrescenta autenticação de máquina, administração de credenciais, registro durável de idempotência e webhooks opcionais. Há uma entrada **API Services** e outra **Webhook Services** no menu da empresa e no Control Plane, utilizando o layout existente e diálogos internos em modo claro.

A publicação Docker passa a construir exclusivamente `linux/amd64`. Foram removidos a emulação QEMU e os requisitos ARM64 dos workflows de imagens. Os aplicativos nativos Android/iOS/macOS não foram alterados. Imagens antigas não são apagadas; servidores ARM64 não devem migrar para estas novas imagens AMD64.

## Por que os webhooks são úteis

A API executa operações e consulta informações. Webhooks avisam que algo mudou, sem exigir que um ERP, CRM ou automação fique consultando toda a agenda continuamente. Exemplos: sincronizar um novo agendamento, liberar uma ordem de serviço após confirmação, atualizar atendimento após check-in, refletir cancelamentos e avisar sobre provisionamento de uma empresa.

Webhooks não são obrigatórios para usar o Scheduler Pro ou sua API. Sem destinos cadastrados, os gatilhos não criam eventos nem entregas. A integração de WhatsApp existente permanece independente. Não foi criado um receptor genérico que aceite comandos arbitrários: sistemas externos executam comandos pela API autenticada; os receptores específicos existentes permanecem com seus próprios contratos.

## Separação entre ambientes

| Ambiente | Base para administração de integrações | Credencial de máquina |
|---|---|---|
| Empresa | `/api/v1/integrations/services` no hostname da empresa | `sp_t_<id>.<segredo>` |
| Control Plane | `/api/v1/platform/integrations/services` no hostname administrativo autorizado | `sp_p_<id>.<segredo>` |

Credenciais, idempotência, auditoria, destinos e entregas da empresa ficam no banco daquela empresa; o Control Plane usa o banco da plataforma. O token não escolhe livremente um banco por cabeçalho. O hostname é resolvido pela implementação existente, inclusive status da empresa e do domínio.

A emissão exige sessão interativa válida: `tenant.manage` na empresa e `integrations.manage` no Control Plane. O MFA administrativo existente é preservado. Um token de máquina não cria, lista, rotaciona ou revoga outros tokens.

Os tokens possuem nome, escopos de leitura/escrita, validade de 1 a 365 dias, limite individual de requisições e revogação. O segredo é aleatório e o banco armazena seu SHA-256, não o token em texto claro. A resposta inicial e a de rotação exibem a credencial; as listagens não a revelam. A rotação invalida imediatamente a credencial anterior, preservando a identidade do token e suas chaves de idempotência.

A cada chamada, o proprietário precisa continuar ativo. As permissões são a interseção entre as concedidas na emissão e as atuais. No Control Plane, as empresas permitidas também são congeladas na emissão e intersectadas com as autorizações atuais: concessões posteriores não expandem silenciosamente um token antigo. Uma empresa explicitamente provisionada pelo próprio token é incorporada ao seu alcance. O token nunca recebe a marca de superadministrador para contornar verificações dos endpoints.

**Webhooks globais** exigem um administrador global ou um token emitido por ele, com escopo de integração e permissão correspondente. Administradores restritos a algumas empresas não recebem o fluxo global da plataforma. A remoção da autorização ou a desativação do criador pausa novos envios quando o worker confere o destino; uma entrega já iniciada pode terminar. Na empresa, a mesma verificação exige proprietário ativo com `tenant.manage`.

## Contrato consultável

`GET <base>/catalog` lista escopos, operações, eventos, limites e exclusões. `GET <base>/openapi` exporta o OpenAPI derivado dos endpoints reais do projeto, com autenticação Bearer, escopo requerido e `Idempotency-Key` nas gravações. O painel Documentação permite pesquisar operações e baixar o contrato.

No código desta entrega, o catálogo contempla 144 operações da empresa e 105 do Control Plane. Ele inclui agendamentos, confirmação, agenda/relatórios, check-in, clientes, serviços, profissionais, horários, notificações, arquivos, páginas/editor, configurações, recursos administrativos, domínios, provisionamento e observabilidade. As permissões e capacidades já existentes continuam sendo verificadas.

Exclusões deliberadas: login/refresh/logout/MFA e demais rotas de autenticação, administração de tokens por máquinas, confirmação manual de resultado incerto por máquinas, telemetria privativa do navegador, handlers públicos sem autenticação e operações que exigem superadministrador interativo. O canal SSE interativo não é substituído por um token. Não há uma API paralela com regras de negócio duplicadas.

Exemplo de consulta, usando uma variável de ambiente local em vez de fixar a credencial no código:

```bash
curl --fail-with-body 'https://EMPRESA.scheduler.argws.com.br/api/v1/customers' \
  -H "Authorization: Bearer ${SCHEDULER_SERVICE_TOKEN}"
```

Exemplo de criação:

```bash
curl --fail-with-body 'https://EMPRESA.scheduler.argws.com.br/api/v1/customers' \
  -H "Authorization: Bearer ${SCHEDULER_SERVICE_TOKEN}" \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: crm-cliente-000123-v1' \
  --data '{"name":"Cliente de exemplo"}'
```

Atribua `customers.read` e/ou `customers.write` ao token conforme necessário. Escopos de serviço complementam, não substituem, as permissões do proprietário.

## Idempotência e resultados incertos

Em requisições de máquina e nas gravações de administração de integrações, `POST`, `PUT`, `PATCH` e `DELETE` exigem `Idempotency-Key`, com 8 a 128 caracteres de `A-Z`, `a-z`, `0-9`, `_`, `.`, `:` ou `-`.

O banco reserva a combinação ambiente + ator + chave antes de chamar o serviço de negócio. A impressão digital inclui método, caminho, query string, Content-Type e os bytes exatos do corpo. Portanto, não altere a serialização de um corpo ao repetir a mesma operação. A mesma chave com requisição diferente retorna `409`. Chaves diferentes, tokens diferentes ou bancos diferentes identificam operações diferentes; isso não substitui as regras de unicidade de negócio.

Uma resposta concluída e de tamanho permitido pode ser reproduzida por 24 horas, com `Idempotency-Replayed: true` e `X-Idempotency-Request-Id`. O conteúdo armazenado para replay é criptografado com a chave da aplicação. O replay volta a verificar autenticação, escopo e a redução de permissões/capacidades, inclusive administração global.

**Não há promessa de exatamente uma execução diante de qualquer falha.** Os serviços atuais têm seus próprios commits. Se o processo cair após uma gravação e antes de registrar a resposta, o estado fica `processing`/`unknown`: a mesma chave NÃO executa o serviço novamente. Consulte `GET <base>/requests/<id>`, confira o recurso e só então decida uma nova operação. Um administrador pode registrar a conferência em `POST <base>/requests/<id>/resolve-outcome`; isso não libera a chave original.

Depois de expirar o replay, o corpo é eliminado. A marca de idempotência permanece no banco para impedir reutilização da chave, inclusive depois da limpeza de histórico. Registros pendentes não são removidos automaticamente. Monitore o crescimento desta tabela e inclua-a nos backups. Restaurar um backup antigo pode perder marcas posteriores; a reconciliação após restauração é obrigatória.

Respostas maiores que o limite configurado são entregues sem guardar o corpo para replay. Falhas 5xx já registradas também não disparam uma repetição automática. Nunca troque a chave aleatoriamente para contornar um resultado incerto.

## Webhook Services

O painel permite cadastrar, editar, pausar, excluir, testar e rotacionar a assinatura de cada destino, consultar entregas/tentativas e reenviar falhas. Cada destino possui seu próprio segredo HMAC e pode ter um Bearer adicional do receptor. Credenciais são criptografadas; histórico não grava cabeçalhos sensíveis, corpo de resposta do receptor ou mensagens de exceção que possam incluir segredos.

Eventos disponíveis: mudanças de agendamentos, clientes, serviços, profissionais, páginas, horários, bloqueios e notificações; no Control Plane, empresas, domínios, provisionamento, builds e modelos. Para agendamentos, alterações também geram eventos específicos de status e remarcação. Um assinante de `appointment.updated` continua recebendo mudanças de status; quem assina `*` pode receber o evento genérico e o específico, cada qual com ID próprio.

Os eventos são gravados por gatilhos PostgreSQL na mesma transação da alteração. Um rollback elimina evento e entrega. Isso cobre mudanças feitas pelo painel, API e workers, sem depender de código de frontend. Os payloads usam uma lista restrita de identificadores, estado e horários; não enviam nomes, telefones, notas clínicas, HTML ou senhas. Consulte detalhes pela API quando autorizado.

O worker usa reivindicações com prazo, `SKIP LOCKED` e identificador de tentativa. Ele libera a sessão antes do HTTP e não permite que uma tentativa antiga sobrescreva o resultado de uma tentativa mais recente. Entregas podem se repetir se o receptor aceitar o evento e a confirmação se perder: o receptor deve deduplicar persistentemente pelo ID de entrega ou de evento.

São aceitos apenas destinos HTTPS públicos na porta 443. A validação rejeita IPs locais, privados, reservados, metadados, transições IPv6 perigosas, credenciais na URL e redirecionamentos. O DNS é verificado no cadastro e novamente no envio; a conexão é fixada ao IP validado, mantendo hostname/SNI e verificação TLS. Configure também uma política de saída no firewall da produção; a validação da aplicação não substitui controle de rede.

### Assinatura e recebimento

Cabeçalhos relevantes:

```text
X-Scheduler-Event: appointment.confirmed
X-Scheduler-Event-Id: <UUID do evento>
X-Scheduler-Delivery-Id: <UUID da entrega, estável nos retries>
X-Scheduler-Timestamp: <Unix timestamp em segundos>
X-Scheduler-Signature: v1=<HMAC-SHA256 hexadecimal>
Authorization: Bearer <opcional, configurado por destino>
```

A assinatura usa o segredo `whsec_...` completo, como texto UTF-8. A mensagem assinada é:

```text
<timestamp>.<delivery_id>.<bytes exatos do corpo JSON>
```

O envelope contém `specversion`, `source`, `id`, `type`, `time`, `scope`, `tenant_id` e `data`. Valide a assinatura em tempo constante, a janela de timestamp e o identificador; persista a deduplicação antes de confirmar. Há um receptor de exemplo com inbox SQLite durável em `examples/integrations/webhook_receiver.py`. Ele valida e armazena o evento, mas não implementa regras do ERP/CRM.

2xx confirma a entrega. Erros de rede, 408, 425, 429 e 5xx têm novas tentativas com espera crescente, dispersão e `Retry-After` numérico limitado. Outros 4xx e redirecionamentos terminam em falha. O padrão é de 8 tentativas por ciclo. Reenvio manual preserva os IDs e reinicia somente o ciclo de tentativas. O histórico de entregas terminais tem retenção padrão de 30 dias; entregas pendentes/pausadas não são apagadas automaticamente.

## Implantação e operação

Publique as imagens AMD64 do commit aprovado, preserve `APP_SECRET_KEY`, credenciais e volumes e execute a migração da plataforma **e de todas as empresas** pelo fluxo atual (`python -m app.cli migrate-platform` e `python -m app.cli migrate-all-tenants`, conforme o comando de bootstrap existente). As novas revisões são `platform_0013_integrations` e `tenant_0013_integrations`. Os modelos de implantação mantêm a sequência existente de migrations.

Os modelos de produção incluem `scheduler-worker-webhooks`, usando a imagem de worker existente e consumindo a fila `webhooks`. O worker de WhatsApp deixa de consumir essa fila. O Celery Beat já existente agenda as varreduras. Não crie uma segunda instância de Beat na mesma stack.

No modelo de desenvolvimento, apenas os serviços novos de processamento são opt-in:

```bash
docker compose -f deployments/development/docker-compose.yml --profile integration-services up --build -d
```

Padrões: 1 processo de webhooks, 1 conexão de plataforma e cache de até 2 engines de empresa com 1 conexão cada. São **3 conexões potenciais adicionais**, elevando a topologia padrão de produção de 42 para 45, antes de administração, probes, provisionamento, réplicas e atualizações sobrepostas. Use `scripts/operations/check-connection-budget.py` com o Compose resolvido e o `max_connections` real. Não aumente a concorrência sem recalcular.

As variáveis `INTEGRATION_*` estão no `.env.example` e nos quatro modelos Compose. Há limites de requisições simultâneas, tamanho/tempo do corpo, quantidade de tokens e destinos, replay, pendências e tentativas. `INTEGRATION_API_ENABLED=false` bloqueia autenticação por tokens sem impedir a gestão interativa para revogação. `INTEGRATION_WEBHOOKS_ENABLED=false` pausa os envios: eventos já capturados permanecem pendentes. Para parar a captura de novos eventos, pause os destinos.

A varredura é paginada e não carrega toda a frota em memória. Mensagens redundantes do broker expiram, mas os registros duráveis de entrega permanecem. Não há prazo fixo de entrega: ele depende do número de empresas, tamanho da fila, latência dos receptores e capacidade dos workers. Monitore filas, idade das entregas, falhas terminais, crescimento do ledger, conexões e espaço em disco.

Faça homologação com dois bancos de empresas, tokens sem permissão, revogação, queda temporária do banco, receptor lento, erro 500, timeout após aceite, repetição de chave e restauração de backup. Os testes de integração existentes passam a incluir regressões específicas deste módulo; testes HTTP externos usam receptor simulado para não disparar eventos reais.
