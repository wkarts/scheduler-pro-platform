# API sem expiração e webhooks de entrada/saída

## API Services

`expires_in_days` agora é opcional. Omitir o campo ou enviar `null` cria um token sem expiração. Um inteiro de 1 a 365 define a validade. Valores inválidos não são interpretados como ausência de prazo.

Na view **Integrações → API Services**, a opção **Definir prazo de validade** vem desmarcada. A listagem apresenta **Sem expiração**. O token continua individual, sujeito às permissões atuais, limites definidos na emissão, limite de requisições, revogação e rotação. Não muda o login ou a validade das sessões do navegador.

Tokens anteriores conservam sua data: a migração não remove validade nem reativa credenciais expiradas/revogadas. O próprio titular pode retirar ou redefinir o prazo de um token ainda ativo:

```http
PATCH /api/v1/integrations/services/tokens/{id}/validity
Authorization: Bearer TOKEN_DA_SESSAO_INTERATIVA
Idempotency-Key: IDENTIFICADOR_UNICO
Content-Type: application/json

{"expires_in_days": null}
```

No Control Plane, o prefixo é `/api/v1/platform/integrations/services`. A alteração de validade e a emissão não podem ser delegadas a tokens de máquina.

## Dois sentidos, um menu

**Integrações → Webhook Services → Saída** mantém o envio já implementado. O Scheduler emite eventos assinados para os destinos cadastrados, com histórico e novas tentativas. Esses destinos já não possuíam prazo obrigatório de validade.

**Integrações → Webhook Services → Entrada** adiciona receptores e histórico de eventos recebidos. Cada receptor possui URL e credencial próprias, independentes dos tokens de API e dos destinos de saída. As credenciais de entrada não têm prazo obrigatório; podem ser pausadas, rotacionadas ou revogadas.

URLs geradas para recebimento:

```text
Empresa:       https://DOMINIO-DA-EMPRESA/api/v1/hooks/tenant/{receiver_id}
Control Plane: https://DOMINIO-ADMINISTRATIVO/api/v1/hooks/platform/{receiver_id}
```

A empresa é resolvida pelo hostname. IDs ou nomes de empresas dentro do payload não mudam o banco de destino. Receptores administrativos exigem titular global; o domínio de uma empresa não serve para o receptor do Control Plane. Não coloque segredos na URL.

## O que o recebimento faz

O receptor autentica, valida o contrato, verifica duplicidade e armazena o evento de forma durável antes de responder. O conteúdo fica criptografado com o resolvedor de segredos já existente. Pode ser consultado e marcado **Conferido** ou **Ignorado** na view ou por API autorizada.

**Recebido não significa que uma regra de negócio foi executada.** Esta entrada é uma inbox autenticada; não foi acrescentado um motor de regras/mapeamento de eventos e não há execução de comandos, scripts, SQL ou URLs recebidos no payload. O registro não cria nem cancela agendamentos. Alterações de negócio continuam utilizando os endpoints normais da API Services, com escopos e idempotência. Essa separação impede que um remetente com credencial de webhook ganhe acesso administrativo.

É um contrato JSON próprio, não um adaptador automático de todo provedor existente. Um sistema com formato/assinatura incompatíveis deve usar um adaptador para este contrato. O receptor específico já utilizado pelo WhatsApp permanece separado e inalterado.

## Contrato HTTP

Envie POST, `Content-Type: application/json`, sem compressão nem parâmetros na URL:

```json
{
  "id": "evento-externo-001",
  "type": "pagamento.confirmado",
  "data": {"referencia": "123"}
}
```

`id` é estável em todos os reenvios do mesmo evento, com até 128 caracteres. `type` tem até 100 caracteres. Ambos aceitam letras, números e os separadores `_ . : / -`, iniciando com letra ou número. `data` deve ser objeto JSON. Metadados adicionais são armazenados, não executados. Chaves JSON duplicadas e números não finitos são recusados.

O administrador escolhe um modo de autenticação por receptor:

### Bearer

```http
Authorization: Bearer CREDENCIAL_EXCLUSIVA_DO_RECEPTOR
```

O banco armazena somente seu SHA-256. Esse Bearer não é um token da API nem permite acessar `/customers`, `/appointments` ou demais recursos.

### HMAC-SHA256

Envie:

```text
X-Scheduler-Timestamp: UNIX_EM_SEGUNDOS
X-Scheduler-Delivery-Id: IDENTIFICADOR_DA_ENTREGA
X-Scheduler-Signature: v1=ASSINATURA_HEXADECIMAL
```

Assine com o segredo do receptor os bytes de `timestamp + "." + delivery_id + "." + corpo_JSON_exato`. A comparação é feita em tempo constante. O esquema é compatível com a assinatura dos webhooks de saída do Scheduler.

A tolerância de cinco minutos é para **cada tentativa de entrega**, não é a validade da credencial. Em um retry, mantenha `id` e conteúdo, mas renove timestamp/assinatura. O relógio do remetente deve estar sincronizado. IDs/tipo de evento estão no corpo assinado, não apenas em cabeçalhos soltos.

## Respostas e idempotência

- `202`: evento persistido; `state=received`, não confirmação de execução de uma ação.
- `200`, `duplicate=true`: evento já recebido neste receptor; retorna o mesmo `receipt_id`.
- `409`: mesmo `id` com conteúdo diferente.
- `401/403`: credencial, titular ou escopo não autorizado; `422`: evento/contrato inválido.
- `413`: corpo excede o limite; `429`: limite do receptor, respeitar `Retry-After`.
- `503`: indisponibilidade, capacidade ou recebimento desativado; reenviar o mesmo id/conteúdo, sem inventar novo id.

Unicidade é garantida no PostgreSQL por `(receiver_id, external_id)`. Reenvios concorrentes não criam duas entradas. JSON semanticamente igual com outra ordem de chaves ou espaços continua sendo duplicado. Um mesmo evento pode ser recebido por dois receptores independentes.

A perda da resposta depois do commit é resolvida pelo reenvio com o mesmo id. Marcas de duplicidade não são apagadas automaticamente com o conteúdo: retenção/descartar payload não permite executar uma nova aceitação do mesmo id. Isso não é uma garantia universal de exatamente uma execução; restauração de backup exige reconciliar eventos posteriores ao backup.

## Consulta por API

Com token de API autorizado (escopos `integrations.services.read/write` para a empresa ou `integrations.read/write` no Control Plane e permissões de gestão correspondentes):

```text
GET    {prefixo}/receivers
GET    {prefixo}/inbox?offset=0&receiver_id={uuid_opcional}
GET    {prefixo}/inbox/{receipt_id}
PATCH  {prefixo}/inbox/{receipt_id}/status  {"state":"acknowledged"}
DELETE {prefixo}/inbox/{receipt_id}/payload
```

Gravações administrativas continuam exigindo `Idempotency-Key`. Descartar conteúdo exige recebimento previamente conferido/ignorado. O histórico e a marca idempotente permanecem. Criar/editar/pausar/rotacionar/revogar receptores exige sessão interativa, evitando emissão recursiva de credenciais por máquinas.

## Segurança, retenção e limites

Corpo máximo padrão: **256 KiB**. Máximo padrão de **1.000 conteúdos retidos por banco**. Ao atingir o limite, novos eventos recebem 503 e devem ser reenviados; duplicados existentes continuam reconhecidos. Conteúdos conferidos podem ser descartados sem perder deduplicação. IDs, hashes e estados permanecem como marcas; devem entrar no planejamento de espaço e backup do banco.

Conteúdos expiram segundo `INTEGRATION_RETENTION_DAYS` (padrão 30). O worker de integrações existente remove os conteúdos expirados; a entrada também faz essa limpeza na admissão de novos eventos. A API não apresenta conteúdo vencido. Não são registrados corpos, cabeçalhos de autenticação ou segredos nos logs da entrada. Consultas URL rejeitadas são omitidas dos logs de aplicação dessas rotas; proxies externos devem ter a mesma política.

Não é mantida conexão PostgreSQL durante o recebimento do corpo HTTP. Há prazo e limite de concorrência por processo. Os pools e a infraestrutura existentes são reutilizados: nenhum worker, broker, porta pública ou serviço Compose foi acrescentado.

Permissões e situação do titular são reavaliadas a cada recebimento. Grupos desativados deixam de conceder gestão. Operações sensíveis da identidade do tenant revogam também suas credenciais de entrada; pausar não equivale a revogar.

Configuração opcional, com defaults seguros no código:

```env
INTEGRATION_INCOMING_WEBHOOKS_ENABLED=true
INTEGRATION_INBOX_MAX_BYTES=262144
INTEGRATION_INBOX_MAX_PAYLOADS=1000
INTEGRATION_INBOX_MAX_INFLIGHT=16
```

Habilitar entrada não exige habilitar saídas (`INTEGRATION_WEBHOOKS_ENABLED`). Os quatro modelos Compose e o `.env.example` incluem as novas variáveis no ambiente compartilhado da API/workers. Em uma stack já implantada, incorpore essas linhas ao modelo existente para sobrescrever os defaults, sem substituir credenciais ou volumes. Sem sobrescrita, os defaults acima se aplicam.

## Migrações e publicação

- Plataforma: `platform_0014_webhook_inbox`, após `platform_0013_integrations`.
- Empresas: `tenant_0015_webhook_inbox`, após `tenant_0014_identity` da expansão de usuários.

Aplicar pelos mecanismos existentes a plataforma e a todas as empresas antes de atender com a imagem nova. Preservar chave mestra, credenciais, volumes e configurações; não editar migrations antigas. A atualização não modifica tokens anteriores nem registros de negócios.

**Downgrade apaga a inbox/receptores e revoga tokens sem expiração**, pois o schema/runtime anterior não os representa. Não tratar downgrade como backup/restauração. Para voltar conservando dados, utilizar plano de rollback e backup compatível. Nenhuma implantação é realizada simplesmente ao abrir/atualizar a PR.
