# Scheduler Pro — confirmação manual reversível na Central de Check-in

## Objetivo

Estender, sem refatoração abrupta, o mesmo modelo de reversão já adotado pelo Check-in para a confirmação manual feita diretamente na Central de Check-in.

## Comportamento

- `Confirmar` na Central passa a exigir diálogo explícito.
- Somente confirmações realizadas pela própria Central recebem uma marca de origem no histórico.
- Enquanto o atendimento confirmado manualmente ainda não entrou em Check-in/Início, o botão contextual `Cancelar` desfaz essa confirmação e volta exatamente ao status anterior (`PENDING`, `AWAITING_CONFIRMATION` ou `RESCHEDULED`).
- Confirmações feitas por outros fluxos permanecem intactas: nesses casos `Cancelar` continua sendo cancelamento real, preservando o comportamento existente.
- Depois de Check-in/Início, continua valendo a máquina reversível já existente da PR #87.
- Não é criado botão permanente de Undo/Desfazer.

## Notificações

A confirmação manual da Central usa chaves próprias e respeita `checkin_notification_delay_seconds`.

Se a confirmação for desfeita dentro da janela de segurança, mensagens ainda `PENDING` são canceladas. Mensagens já enviadas continuam auditadas e não são recolhidas.

## Operação em lote

- confirmação manual em lote exige diálogo;
- Cancelar em lote consulta se cada item é reversível;
- confirmações manuais ainda não avançadas são desfeitas;
- itens sem etapa reversível seguem para cancelamento real;
- Check-in, início, conclusão, cancelamento e não comparecimento preexistentes permanecem preservados.

## Compatibilidade

- sem migration;
- sem novo botão permanente;
- sem alteração do endpoint genérico `/appointments/{id}/confirm`;
- sem mudança automática nos tenants;
- `FULL` e `SIMPLE` continuam funcionando como antes;
- `RESCHEDULED` foi formalizado no enum backend porque já é um estado usado pelo fluxo atual.

## Arquivos principais

- `apps/api/app/api/v1/routes/checkin.py`
- `apps/api/app/services/notification_dispatcher.py`
- `apps/api/app/core/enums.py`
- `apps/web/src/TenantCheckInCenter.vue`
- testes de contrato da Central de Check-in
