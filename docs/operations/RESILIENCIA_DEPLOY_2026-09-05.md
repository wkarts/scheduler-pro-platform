# Scheduler Pro — Implantação e rollback da correção de resiliência

**Entrega:** resilience-20260905. **Versões preservadas:** produto 2.1.0 / Visual Builder 2.4.0.

Este roteiro não foi executado no servidor do cliente. Todos os caminhos, tags e valores reais precisam ser verificados no ambiente. Não há migração de schema nova nesta correção.

## 1. Preservar identidade da stack e dados

Trabalhe com o MESMO projeto Compose, diretório da stack, `.env` de produção e mounts atualmente usados. Antes de substituir arquivos, registre de forma privada as imagens/digests atuais e os caminhos de dados. Conserve uma cópia protegida do Compose e do `.env` anteriores.

Não substitua `.env` por `.env.example`; copie apenas as novas opções de resiliência. NÃO altere `APP_SECRET_KEY`, senhas já provisionadas, `COMPOSE_PROJECT_NAME`, `SCHEDULER_PRO_DATA_ROOT`, certificados ou credenciais durante esse hotfix. Um caminho relativo em outro diretório pode fazer o Docker criar uma pasta vazia e parecer que os dados desapareceram. Use o caminho absoluto ORIGINAL dos dados quando normalizar configurações.

Não use `docker compose down -v`, `docker volume prune`, exclusão de dados, encerramento em massa de sessões ou reinício do PostgreSQL como primeira resposta. Nunca exponha a saída completa de `docker compose config`, pois contém segredos resolvidos.

Os nomes abaixo correspondem ao modelo ARGWS do log. Outros modelos têm variações; confirme com `config --services`.

```bash
# Defina caminhos REAIS da stack já existente, não de uma stack nova.
COMPOSE_FILE="/caminho/real/da-stack/compose.yaml"
ENV_FILE="/caminho/real/da-stack/.env"
SOURCE_DIR="/caminho/do/codigo/scheduler-pro-platform-main"

docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" config --services
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps
```

## 2. Diagnóstico somente leitura e orçamento

```bash
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T scheduler-postgres   sh -c 'export PGPASSWORD="$POSTGRES_PASSWORD"; exec psql --no-password -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"'   < "$SOURCE_DIR/scripts/operations/database-diagnostics.sql"
```

O relatório não encerra sessões nem imprime o texto das consultas. Guarde a saída com acesso restrito. Verifique limites, total por banco/serviço e transações ociosas. Se o banco recusar até o diagnóstico, reduza primeiro os consumidores de forma controlada, começando por pausar novas tarefas; não aumente limites cegamente.

Depois de atualizar o Compose, mas ANTES de subir as imagens novas, valide o orçamento com valores REAIS:

```bash
MAX_CONNECTIONS=100  # EXEMPLO: substitua pelo SHOW max_connections real.
RESERVED_CONNECTIONS=3  # EXEMPLO: soma real das reservas do cluster.

docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" config --quiet

docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" config --format json   | python3 "$SOURCE_DIR/scripts/operations/check-connection-budget.py"       --max-connections "$MAX_CONNECTIONS" --reserved "$RESERVED_CONNECTIONS"       --operational-margin 15
```

A saída mostra apenas metadados de capacidade; não grave o JSON intermediário de Compose. Retorno 2 exige revisão, não ignorar a proteção. Some manualmente réplicas externas, outras aplicações e sobreposição de deploy. Recalcule quando aumentar API workers, Celery concurrency ou cache.

## 3. Novas variáveis para incorporar ao ambiente atual

```dotenv
DB_SERVICE_NAME=scheduler-api
DB_PLATFORM_POOL_SIZE=4
DB_PLATFORM_MAX_OVERFLOW=2
DB_TENANT_POOL_SIZE=1
DB_TENANT_MAX_OVERFLOW=1
DB_POOL_TIMEOUT_SECONDS=3
DB_CONNECT_TIMEOUT_SECONDS=3
DB_POOL_RECYCLE_SECONDS=600
DB_CONNECTION_BUDGET_PER_PROCESS=24
TENANT_ENGINE_CACHE_MAX=8
TENANT_ENGINE_CACHE_TTL_SECONDS=120

DB_WORKER_PLATFORM_POOL_SIZE=1
DB_WORKER_PLATFORM_MAX_OVERFLOW=0
DB_WORKER_TENANT_POOL_SIZE=1
DB_WORKER_TENANT_MAX_OVERFLOW=0
DB_WORKER_TENANT_ENGINE_CACHE_MAX=4
DB_WORKER_CONNECTION_BUDGET_PER_PROCESS=8
CELERY_DEFAULT_CONCURRENCY=2
CELERY_WHATSAPP_CONCURRENCY=2
CELERY_MAX_TASKS_PER_CHILD=500

HEALTH_PROBE_TIMEOUT_SECONDS=3
HEALTH_CACHE_SECONDS=5
DB_CAPACITY_WARNING_PERCENT=75
DB_CAPACITY_CRITICAL_PERCENT=90
HTTP_LOG_MAX_PENDING=64
HTTP_LOG_CONCURRENCY=2
HTTP_LOG_TIMEOUT_SECONDS=3
API_MAX_INFLIGHT_REQUESTS=64

DB_STATEMENT_TIMEOUT_MS=0
DB_LOCK_TIMEOUT_MS=0
DB_IDLE_TRANSACTION_TIMEOUT_MS=0
LOG_MAX_SIZE=20m
LOG_MAX_FILES=5
```

O Compose aplica as opções `DB_WORKER_*` aos nomes `DB_*` de cada worker. Não basta adicionar variáveis sem atualizar o modelo Compose correspondente. Não mantenha inadvertidamente `TENANT_ENGINE_CACHE_MAX=64`: a nova validação recusará uma combinação que ultrapasse o budget. Isso é uma proteção deliberada.

Os valores acima são ponto inicial conservador, não dimensionamento universal. Não habilite timeouts SQL agressivos globalmente sem testar relatórios/provisionamento. Não foi necessário alterar `max_connections` nem adicionar PgBouncer para esse patch.

## 4. Backup antes da publicação

O utilitário abaixo não derruba serviços. Em ambiente com muita escrita, cada base tem snapshot próprio; pause operações que exigem consistência transversal ou use uma estratégia de backup físico/PITR homologada.

```bash
python3 "$SOURCE_DIR/scripts/operations/backup-postgres.py"   --compose "$COMPOSE_FILE" --env-file "$ENV_FILE"   --service scheduler-postgres   --output "/caminho/seguro/fora-dos-dados-ativos/backups"
```

Só trate como concluído o diretório `postgres-...` com manifesto e checksums. `.incomplete-...` é falha/parcial. O utilitário usa as credenciais do container sem imprimi-las, cria `globals.sql` e um dump custom por base, e verifica leitura do catálogo. Não confunda isso com restauração testada.

Faça também backup consistente de MinIO/S3, `.env`, chave de aplicação original, certificados e configurações. Não copie cegamente arquivos vivos do PostgreSQL como se fossem backup físico válido. Envie cópias criptografadas para outro servidor e teste restore em ambiente separado. Dumps/globals contêm dados sensíveis e hashes de roles. O rollback abaixo não depende de restaurar banco porque o patch não muda schema; backup protege contra incidentes adicionais.

## 5. Publicar código e imagens corretas

Extraia o pacote, revise `CHANGESET.json`/diff e incorpore pelo GitHub Desktop ao repositório existente, sem copiar `.git`, caches ou credenciais locais. O pacote não inclui histórico Git novo. Preserve o fluxo canônico de merge/release do projeto.

Execute o CI completo: API, Ruff, Mypy, unitários, integrações, autenticação, PWA, typecheck/build, Docker e testes nativos pertinentes. **Os testes locais parciais não dispensam o CI.** Os oito testes HTTP novos ainda precisam dessa execução.

O servidor usa imagens GHCR. Copiar o ZIP para a VPS ou mudar `.env` NÃO altera o código de uma imagem já publicada. É necessário construir/publicar API, worker, web e admin deste commit e confirmar que a tag/digest corresponde a ele. Use a tag imutável/SHA realmente produzida pelo pipeline existente; não invente uma tag ainda não publicada. Guarde a tag antiga para rollback. Não altere versões internas do Visual Builder para esse hotfix.

Atualize `APP_IMAGE_TAG` no ambiente para a tag disponível. Faça pull dos serviços afetados antes de iniciar a janela de manutenção:

```bash
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" pull   scheduler-api scheduler-worker-default scheduler-worker-whatsapp scheduler-beat   scheduler-web scheduler-admin
```

## 6. Atualização controlada sem recriar o banco

A instalação atual tem uma API; recriá-la pode produzir breve indisponibilidade. Não prometa deploy zero-downtime nessa topologia. Avise a operação e drene tarefas existentes. A parada usa grace period, mas tarefas mais longas que esse limite precisam de tratamento antes de continuar; não force kill sem entender efeitos externos pendentes.

```bash
# Impede agendamento de novas tarefas periódicas e encerra workers graciosamente.
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" stop -t 120   scheduler-beat scheduler-worker-default scheduler-worker-whatsapp

# Recria somente a API, usando as imagens publicadas e os novos limites.
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --no-deps --force-recreate scheduler-api
```

Antes de continuar, confirme readiness real da API e ausência de erro de configuração no log. Se falhar, faça rollback; não comece a alterar senhas ou recriar banco para contornar.

```bash
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T scheduler-api   sh -c 'curl --fail --silent --show-error -H "Host: $PUBLIC_PLATFORM_DOMAIN" http://127.0.0.1:8000/api/v1/health/ready'

docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --no-deps --force-recreate   scheduler-worker-default scheduler-worker-whatsapp scheduler-beat scheduler-web scheduler-admin
```

`--no-deps` aqui evita recriar dependências como PostgreSQL/MinIO e não é desculpa para ignorar sua saúde; elas devem estar verificadas. Uma atualização geral da stack aplicaria também alterações de logging e pode recriar mais containers; programe isso separadamente. O proxy não recebeu novo código neste hotfix.

## 7. Aceite em homologação e verificação pós-publicação

Verifique login, refresh e 2FA no Control Plane e na empresa afetada; navegação administrativa; listagem/criação/reagendamento/cancelamento; confirmação e envio de WhatsApp; relatórios; editor/preview/publicação; PWA instalado e acesso web. Abra duas empresas distintas e dois aliases da mesma empresa: confirme isolamento e ausência de pools duplicados por alias.

Acesse o endpoint administrativo `/api/v1/platform/observability/database` com permissão `observability.read`. Compare com `database-diagnostics.sql`. Observe estabilização após ciclos de uso/ociosidade, nenhuma transação ociosa longa e ausência de crescimento contínuo por tarefa Celery.

Somente em homologação, provoque indisponibilidade transitória do banco e atraso de dependências. Esperado: readiness 503, liveness do processo ainda funcional, erro temporário sem apagar tokens, nenhum retry automático de gravação 5xx, retomada após restauração da dependência. Teste muitas chamadas 401 simultâneas: uma renovação por aba/grupo suportado, sem tempestade de refresh.

Faça carga compatível com a utilização real e observe CPU/RAM/disco, fila, taxa 5xx, latência e conexões. O subtotal padrão 42 não prova suportar qualquer quantidade de usuários. Valide também duplicidade/reconciliação de notificações após interrupção de worker; este patch não promete exactly-once.

O Service Worker tem geração nova para distribuição do frontend. Não mande clientes apagar todo armazenamento como correção primária. Confirme que o bundle servido corresponde ao commit publicado e permita atualização normal da PWA.

## 8. Rollback

Conserve Compose, ambiente e imagens/digests anteriores. Em falha de validação, interrompa o beat e drene workers; restaure a combinação compatível de Compose/variáveis/tag anterior e recrie APENAS os serviços de aplicação afetados. Não apague volumes nem restaure dumps sobre a produção como rotina desse rollback, pois não houve alteração de schema.

Após rollback, valide novamente autenticação/agenda. A versão antiga continua contendo os riscos de conexão identificados; trate rollback como contenção, acompanhe pressão e não aumente workers. Caso uma implantação tenha apontado para mount incorreto, pare e reconcilie os caminhos antes de qualquer escrita/restauração.

## 9. Monitoramento e recuperação contínua

Configure monitor externo com readiness e teste sintético de acesso, alertas de conexões/idade de transações, disco, fila, backups e certificado. Healthcheck Compose sem notificação não atende operação. Estabeleça RPO/RTO somente depois de restauração cronometrada em ambiente isolado. Planeje redundância de infraestrutura separadamente: o código entregue não torna uma VPS única tolerante à perda do host.
