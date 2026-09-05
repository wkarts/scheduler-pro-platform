# Scheduler Pro — Auditoria e correções de resiliência

**Data:** 5 de setembro de 2026. **Base recebida:** `scheduler-pro-platform-main (9).zip`.
**Versão canônica preservada:** Scheduler Pro 2.1.0; ARGWS Visual Builder 2.4.0.
**Identificador desta entrega:** `resilience-20260905`.

## 1. Resultado e limites da entrega

O pacote contém o projeto completo com correções incrementais no gerenciamento de conexões, encerramento de sessões, runtime dos workers, autenticação dos dois painéis, observabilidade e modelos de implantação. Não foram alterados o modelo de negócio, o isolamento por banco de empresa, a identidade visual, o editor, os nomes de imagens ou o fluxo canônico de publicação.

A revisão combinou inventário do repositório, análise estática de caminhos críticos, exame do incidente e testes executáveis das partes compatíveis com este ambiente. **Isso não equivale a executar todas as funcionalidades da aplicação em produção, nem a certificar ausência de falhas.** O ZIP original tem 773 arquivos. O inventário de rotas registra 267 decoradores HTTP e a revisão abrange a estrutura de API, administração, web, workers, editor, superfícies nativas, infraestrutura, CI e testes. Não houve acesso ao banco ou servidor de produção.

Não foram executados reinícios, alteração de senhas, migrações, exclusão de conexões ou mudanças em DNS. Também não foi publicado commit, PR ou imagem no GitHub/GHCR. Os arquivos devem ser incorporados ao repositório e passar pela publicação/homologação descrita no roteiro de implantação.

## 2. O que o incidente comprova — e o que não comprova

O log enviado contém `asyncpg.exceptions.TooManyConnectionsError: sorry, too many clients already`, erros equivalentes do PostgreSQL, HTTP 500 no login/refresh e respostas 200 para arquivos estáticos. Isso comprova recusa de novas conexões naquele intervalo; não quantifica, por si só, quantas conexões cada processo mantinha nem identifica sozinho todo o mecanismo causador.

A análise do código encontrou mecanismos concretos que podiam multiplicar ou prolongar conexões. São corrigidos nesta entrega. Ainda é necessário medir `pg_stat_activity`, recursos do servidor e concorrência real para atribuir precisamente a participação de cada mecanismo no incidente.

**Retificação importante sobre o readiness:** a implementação original já consultava PostgreSQL e outras dependências. O problema não era simplesmente “não consultar o banco”. Uma consulta usando conexão já aberta pode funcionar enquanto novas conexões são rejeitadas; a verificação interna também não representava o estado de todos os bancos de empresas. Agora existe prova de nova conexão e avaliação de capacidade, mantendo a distinção entre processo vivo e serviço pronto.

Os registros de Cloudflare mostravam uma consulta com 403 seguida de descoberta da zona e reconciliação bem-sucedida. Isso merece revisão de configuração, mas não demonstra ser a causa dos erros de login. Não foi modificada a zona a partir de inferências sobre o log.

## 3. Achados e correções efetivamente implementadas

| Área | Achado no código original | Alteração entregue |
|---|---|---|
| Pools | Engines da plataforma e de empresas sem limites explícitos; cache de até 64 engines por processo. | Limites explícitos de pool, overflow, espera e conexão; orçamento validado na inicialização. |
| Identidade do pool | Hostname fazia parte da chave, permitindo pools diferentes para aliases da mesma empresa. | Chave pela identidade da empresa, banco, usuário e referência/versão da credencial. |
| Cache | Expiração/remoção sem proteção explícita de sessões em uso. | Registro limitado com leases; não remove engine emprestado; aguarda com limite em saturação. |
| Sessões | 40 usos de geradores com `async for`, vários encerrados por `break`/`return`. | Fechamento determinístico com `contextlib.aclosing`, preservando fluxo e transações originais. |
| Celery | Relatórios tinham loop próprio e compartilhavam engines com outras tarefas. | Runtime assíncrono unificado; descarte seguro de pools herdados após fork; shutdown dos geradores. |
| Realtime | O stream duradouro mantinha uma sessão durante a conexão, embora já devolvesse a conexão física entre consultas via rollback. | Sessão e lease curtos por leitura, encerrados antes de enviar o evento ou aguardar o próximo ciclo. |
| Logs HTTP | Cada requisição podia gerar uma tarefa assíncrona persistente sem limite global. | Fila best-effort com limite de pendências/concorrência/prazo, contadores e descarte sob pressão. |
| Banco indisponível | Falhas transitórias apareciam como erro genérico de servidor. | Classificação de exaustão/conectividade e HTTP 503 com `Retry-After`, sem tratar como senha incorreta. |
| Admissão HTTP | Requisições podiam continuar acumulando trabalho até pressionar pools e banco. | Limite por processo para requisições em andamento até a resposta inicial; rejeição controlada 503. |
| Readiness | Podia reutilizar conexão saudável e não tinha prazo geral por dependência/capacidade. | Nova conexão PostgreSQL, capacidade efetiva, probes paralelas limitadas e cache compartilhado curto. |
| Sessão da empresa | Erro 500 no refresh apagava tokens e provocava saída/reload. | Falha temporária preserva sessão; refresh compartilhado, cooldown e classificação distinta de 401. |
| Control Plane | Não havia tratamento central equivalente para renovação resiliente. | Wrapper próprio de autenticação, mantendo o formato atual do armazenamento administrativo. |
| Rotação de refresh | Consultas concorrentes não bloqueavam a linha antes de decidir a rotação. | `FOR UPDATE OF rt` na consulta do refresh; proteção entre abas com Web Locks quando disponível. |
| Permissões | Alguns fluxos tratavam 403 como motivo de apagar autenticação. | 401 e 403 separados; stream proibido para sem apagar a sessão ou repetir indefinidamente. |
| Deploy | Concorrência e budgets pouco explícitos; rotação de logs ausente em modelos CloudPanel. | Pools distintos por serviço, concorrência configurável, reciclagem por número de tarefas, grace periods e rotação Docker. |
| Operação | Não havia no pacote um utilitário completo de backup lógico de todas as bases. | Ferramenta de backup com diretório incompleto, dump por base, globals, catálogo, checksums e manifesto. |

### Arquivos centrais

`apps/api/app/db/session.py`, `engine_registry.py`, `connection_budget.py`; `core/config.py`, `background_tasks.py`, `transient_errors.py`, `errors.py`; `main.py`; `workers/tasks.py` e `agenda_report_tasks.py`; rotas de saúde, realtime, observabilidade e dependências; serviços e rotas que consumiam geradores de sessão; `apps/web/src/tenant-auth-fetch.ts`; `apps/admin/src/admin-auth-fetch.ts`; quatro modelos Compose e seus exemplos de ambiente.

A maior parte do volume de diff em tasks/rotas existentes é a indentação necessária para garantir `aclosing`, não uma reescrita das regras de negócio. A relação exata de arquivos, hashes anteriores/novos e inclusões está em `validation/resilience-20260905/CHANGESET.json`.

### O que não foi adotado como “solução automática”

Não foi inserido PgBouncer às cegas: o projeto usa database-per-tenant, asyncpg e tarefas administrativas, exigindo homologação específica de autenticação, prepared statements e modos de pool. Não foi aumentado `max_connections` arbitrariamente. Não foram ativados retries genéricos para POST, exclusão automática de sessões PostgreSQL ou reinícios periódicos como substituto da correção.

Timeouts SQL são opcionais e permanecem desativados por padrão nesta entrega. Aplicar 60 segundos globalmente poderia interromper relatórios, provisionamento ou migrações legítimas. A política deve ser homologada por tipo de operação/role.

## 4. Orçamento padrão de conexões

A fórmula é aplicada **por processo e por engine**:

```text
plataforma: pool_size + max_overflow
empresas:  cache_max × (tenant_pool_size + tenant_max_overflow)
limite por processo: soma das duas parcelas
limite da implantação: soma por processos × réplicas + conexões auxiliares + folga
```

| Serviço no Compose de produção | Processos considerados | Máximo de pools por processo | Total potencial |
|---|---:|---:|---:|
| API | 1 | 4 + 2 + 8 × (1 + 1) = 22 | 22 |
| Worker padrão | 2 filhos | 1 + 4 × 1 = 5 | 10 |
| Worker WhatsApp | 2 filhos | 1 + 4 × 1 = 5 | 10 |
| **Subtotal gerenciado** | | | **42** |

42 é o teto teórico dos pools desses processos com os defaults, **não o número medido em produção nem um limite global de todo PostgreSQL**. Conexões diretas de provisionamento/CLI, readiness, migrations, beat quando aplicável, administração, outras aplicações e sobreposição durante deploy precisam de margem. O orçamento de validação por processo também não é um semáforo global entre containers.

Exemplo de cálculo executado: com `max_connections=100` hipotético e 3 reservadas, a capacidade comum é 97; subtotal 42 mais margem de 15 resulta em 57. O utilitário exige o valor REAL de `SHOW max_connections` e sinaliza revisão acima de 80% da capacidade comum. A reserva de 3 e margem de 15 são argumentos ajustáveis, não fatos sobre o servidor do cliente.

Reduzir cache para 8 não limita a plataforma a 8 empresas cadastradas. Limita engines simultaneamente residentes por processo; empresas ociosas saem do cache e são readmitidas. Em saturação, a aplicação espera de forma limitada ou devolve 503 em vez de criar pools ilimitados. Alta concorrência entre muitas empresas exige capacidade dimensionada, não remover limites.

## 5. Observabilidade entregue

Novo endpoint administrativo: `GET /api/v1/platform/observability/database`, protegido por `observability.read`. Exibe capacidade PostgreSQL, reservas, conexões em uso/ociosas/transações ociosas, métricas do cache por processo e fila best-effort de logs. Não publica senhas, DSNs ou texto de consultas.

As conexões recebem `application_name` por serviço e escopo, facilitando atribuição pelo `pg_stat_activity`. Os contadores de pool são locais ao processo que atende a requisição; não representam todos os workers. Para visão de todo banco, use os contadores PostgreSQL e agrupamento por aplicação.

Liveness permanece simples e independente. Readiness usa conexão nova e verifica migrações/dependências, com aviso de pressão a 75% e estado crítico a 90% da capacidade comum configurada. O cache de saúde é de 5 segundos e as chamadas simultâneas compartilham uma coleta. No hostname de uma empresa, há verificação adicional daquele contexto, não de todas as empresas existentes.

Logs 503 não geram novas gravações HTTP no banco indisponível; health e sucesso de eventos/version também são filtrados. Logs operacionais no stdout continuam disponíveis. O descarte sob pressão é intencional para telemetria HTTP; **não substitui nem remove eventos transacionais de negócio/outbox**.

Não foi criado envio externo automático de alertas. Um monitor deve consumir readiness/métricas, registrar incidentes e notificar o operador. O estado `unhealthy` do Docker Compose não é, sozinho, garantia de reinício ou failover; `restart: unless-stopped` não implementa orquestração de alta disponibilidade.

## 6. Validações realmente executadas

| Grupo | Resultado | Limite da evidência |
|---|---:|---|
| Núcleo de resiliência Python | 32 aprovados | Registro de engines com dublês, tarefas, configuração, classificação e contratos estruturais; não usa PostgreSQL real. |
| Autenticação web/admin compilada e executada | 30 aprovados | Fetch, storage e navegador simulados; não equivale a E2E no Safari/Android. |
| Contratos existentes do backend | 84 aprovados | 24 arquivos de testes de fonte selecionados; não é a suíte inteira. |
| Visual Builder existente | 74 aprovados | Testes Node do pacote, sem redesign do editor. |
| Utilitários de operação | 8 aprovados | Budget e fronteiras do backup; Docker/dump/restore simulados. |
| **Total dessas execuções** | **228 aprovados** | Não inclui testes de integração pendentes. |

Também passaram compilação Python, typecheck TypeScript estrito dos dois wrappers de autenticação, sintaxe do Visual Builder, validador de instalação PWA, sintaxe dos entrypoints shell e leitura YAML dos quatro modelos Compose. A leitura YAML **não substitui** `docker compose config`.

Foi atualizada uma asserção preexistente que fixava a versão 2.0.0 apesar de VERSION/package.json já estarem em 2.1.0. O teste passou a comparar a versão canônica real, sem mudar a versão do produto para satisfazer o teste.

### Validações bloqueadas neste ambiente

A instalação completa Python falhou por indisponibilidade de rede/resolução; faltam dependências do projeto. A tentativa da suíte completa parou ao importar `structlog`. O npm offline não encontrou pacote necessário no cache. Docker não está disponível. Portanto **não foram executados aqui**: suíte completa da API, testes HTTP novos que importam toda a aplicação, Ruff/Mypy completos, build Vue/PWA/nativo, builds Docker, integração PostgreSQL/Redis/RabbitMQ/MinIO/Celery, carga com múltiplos tenants ou restauração real.

Foram adicionados oito testes de fronteira HTTP para execução no CI/homologação normal, incluindo nova conexão recusada, 503, prazo de probe e liberação da sessão SSE. Esses oito NÃO estão incluídos nos 228 aprovados. O CI existente continua obrigatório e recebeu testes de autenticação/operação; não foi executado remotamente nesta entrega.

Evidências e comandos estão em `validation/resilience-20260905/`. Falhas de instalação e tentativa da suíte completa foram preservadas para distinguir bloqueio ambiental de aprovação.

## 7. Riscos residuais e trabalho operacional necessário

**Servidor e banco únicos.** A stack existente não ganha redundância física por um patch. Falha de VPS, disco, rede ou PostgreSQL exige restauração ou arquitetura de HA real. Replicação/failover e contingência de filas/objetos não foram implantados.

**Backup e recuperação.** O novo utilitário produz snapshots lógicos por banco, não um snapshot atômico entre todos os bancos. O catálogo legível e checksum não comprovam restauração. Objetos MinIO/S3, `.env`, `APP_SECRET_KEY`, credenciais, certificados e arquivos de runtime precisam de backup separado, criptografado e fora da VPS. Sem a chave de aplicação original, segredos já selados podem se tornar inutilizáveis. Homologue restauração isolada antes de estabelecer RPO/RTO.

**Privilégios.** O provisionamento original depende de credenciais administrativas e possui fallback compatível com a role inicial do cluster. Não foi rebaixada essa role automaticamente. Separar usuário de runtime, provisionamento e backup requer plano de migração e teste. Docker socket e agente CloudPanel privilegiado permanecem componentes de alto impacto; precisam de acesso restrito e atualização própria. Diretórios permissivos da inicialização original também merecem endurecimento com validação de UID/GID.

**Efeitos externos.** O dispatcher de notificações usa bloqueios de filas, mas há uma janela entre enviar ao provedor e confirmar no banco. Uma interrupção nessa janela pode exigir reconciliação e eventualmente causar reenvio. Não há garantia nova de exactly-once. Não foram alterados acks/retries globalmente, o que poderia produzir duplicidade. Idempotência por provedor, ledger de entregas e reconciliação devem ser homologados separadamente.

**Rotação de refresh.** Promessa compartilhada, lock de linha e Web Locks reduzem concorrência, mas não eliminam toda ambiguidade de resposta perdida após o servidor já ter rotacionado. Não foi relaxada a detecção de reutilização de token. Web Locks tem fallback por aba; clientes nativos e browsers sem o recurso exigem teste real.

**Limites e transações.** Sessões podem ser encerradas corretamente e ainda assim uma operação manter uma transação por muito tempo. O dispatcher e integrações devem ser observados sob atraso de provedores. O limite HTTP atua até o início da resposta, não é um limite global de sockets SSE nem de toda a memória do host. A soma de processos externos e conexões diretas continua responsabilidade do dimensionamento.

**Retenção e confidencialidade.** Rotação de logs Docker não implementa expurgo das tabelas de logs nem rotação de backups. A base original ainda deve receber auditoria específica de retenção, URLs com parâmetros sensíveis e política de acesso aos diagnósticos. Este patch não é certificação de segurança ou LGPD.

**Disponibilidade parcial.** 503 controlado preserva banco e sessão, mas continua significando que aquela operação não foi realizada. Não há promessa de disponibilidade ilimitada. Restante do produto — agenda, cobrança, DNS, desktop/mobile, permissões e editor — mantém contratos existentes e requer a regressão integral antes de produção.

## 8. Critérios para encerrar o incidente

A publicação só pode ser considerada homologada após: CI completo verde; imagens efetivamente construídas deste commit; orçamento recalculado para a topologia real; mounts/segredos preservados; login e refresh aprovados na empresa afetada e no Control Plane; prova de isolamento entre duas empresas; testes de agenda/WhatsApp; falha induzida em homologação devolvendo 503 sem apagar sessão; retorno estável após recuperação; volume de conexões estabilizado após carga; backup restaurado em ambiente isolado.

Os arquivos corrigem causas e ampliam proteção/diagnóstico. O fechamento do incidente em produção depende dessas verificações; ele não foi declarado encerrado apenas por gerar o ZIP.

### Referências técnicas de apoio

A fonte dos achados é o projeto anexado. As referências externas apoiam sem substituir a análise do código: documentação SQLAlchemy 2.0 sobre pooling, descarte após fork e engines assíncronos em loops distintos; documentação PostgreSQL 17 sobre conexões e slots reservados.

- `https://docs.sqlalchemy.org/en/20/core/pooling.html`
- `https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html`
- `https://www.postgresql.org/docs/17/runtime-config-connection.html`
