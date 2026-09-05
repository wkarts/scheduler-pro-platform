# Usuários, grupos, perfis e Integrações

## Escopo e compatibilidade

Implementação aditiva sobre a main pós-PR #97 (Scheduler Pro 2.1.0). O versionamento continua sob o pipeline canônico; ARGWS Visual Builder e imagens AMD64 são preservados. Nenhum dado de empresa, segredo, volume ou parâmetro de agenda deve ser substituído.

A página **Integrações** é única por console e segue a navegação normal. Mantém credenciais API, webhooks, entregas, operações e documentação. No Control Plane, os indicadores operacionais anteriores permanecem disponíveis. Não existe mais launcher/modal separado de API e Webhook.

**Usuários e grupos** e **Meu perfil** são páginas do painel da empresa. A primeira lista usuários, situação, grupos, último login, vínculo profissional e permissões; possui edição, ativação/desativação, convite e revogação de acessos. Grupos reutilizam `roles`, `role_permissions` e `user_roles`; não foi criado um segundo mecanismo de autorização. A auditoria utiliza `audit_logs`, filtrada e paginada.

## Autorização

`users.read`, `users.manage`, `groups.manage` e `audit.read` são permissões distintas. A migration concede esses direitos somente aos grupos que já possuíam `tenant.manage`. O provisionamento de novas empresas inclui as mesmas chaves.

Toda operação é validada no backend. O administrador só pode atribuir/remover grupos e modificar contas cujas permissões (inclusive de grupos inativos) estejam dentro da sua autoridade atual. Não há ampliação automática de direitos. Alterações administrativas do próprio grupo/situação da conta exigem outro administrador; o perfil permite somente os dados pessoais autorizados. A última conta ativa e apta a administrar usuários **e** grupos não pode perder essa capacidade. Um bloqueio transacional por banco serializa as mutações IAM, evitando perda de administrador e duplicidade de e-mail concorrentes.

Permissões de grupos desativados são ignoradas em login, requisições e tokens API. Os tokens mantêm também os limites definidos na emissão na PR #97. Desativar uma conta ou revogar seus acessos invalida suas sessões, refresh tokens, credenciais API e links pendentes. Reativar a conta não revalida credenciais revogadas. IAM exige sessão interativa; tokens de máquina não podem administrar identidades.

## Convites, confirmação e senha

Novas contas são cadastradas com senha aleatória não disponibilizada e confirmação obrigatória. O convite por e-mail permite definir a própria senha e verificar a caixa postal. Links são de uso único, armazenados somente por hash e expiram em 24 horas (convite) ou 1 hora (verificação/troca de e-mail). Reenvios têm intervalo mínimo de 60 segundos. O token fica no fragmento da URL; não é enviado no GET nem gravado no histórico da aplicação. A página remove o fragmento antes do envio do formulário.

A mudança de e-mail exige a senha atual e confirmação do novo endereço; até confirmar, o endereço anterior continua válido. Alteração de senha exige senha atual e mínimo configurado em `PASSWORD_RESET_MIN_LENGTH` (padrão 12); espaços são preservados. Alterações de credenciais encerram sessões e revogam tokens API. Os mecanismos existentes de recuperação de senha e MFA são mantidos; confirmar e-mail não remove MFA nem concede grupos.

O envio utiliza os serviços SMTP existentes da empresa/plataforma e libera a transação antes do envio. Falha de SMTP não apaga o usuário criado: a interface informa a falha e permite reenviar após corrigir a configuração. Não há nova fila de e-mails. Contas antigas não têm seu acesso bloqueado por confirmação retroativa: permanecem explicitamente com `verification_required=false`, sem inventar uma data de verificação.

## Foto e vínculo profissional

Fotos JPEG, PNG ou WebP estáticas: até 2 MiB, lado máximo 4096 pixels e até 12 megapixels. O backend decodifica e regrava em JPEG até 512px, removendo metadados. Arquivos SVG, animados, conteúdo inválido e excedentes são rejeitados. O MIME informado pelo navegador não determina se o arquivo é seguro.

Armazenamento reutiliza o bucket e a cota existentes, sob `files/profiles-private/<usuário>/<uuid>.jpg`. A foto é lida pela rota autenticada do próprio perfil com `no-store`. Rotas genéricas de arquivos não permitem ler, sobrescrever, excluir ou obter links desse namespace. Quando a exclusão de um objeto antigo falha, ele permanece privado, sem referência, e uma advertência de limpeza é registrada; não existe coleta automática de órfãos nesta entrega.

Usuário e profissional continuam entidades distintas. O vínculo é opcional e um profissional pode estar ligado a no máximo uma conta no mesmo banco. Desvincular não exclui o profissional. Excluir um profissional remove somente a referência (`ON DELETE SET NULL`). Nenhum vínculo concede permissões, altera horários, capacidade ou regras da agenda.

## Busca e entrada livre

O Operador da Agenda usa campos pesquisáveis de clientes, serviços e responsáveis. A pesquisa é automática, limitada, cancelável e protege contra respostas antigas; há no máximo seis sugestões visíveis. Serviço/responsável podem ser digitados livremente sem escolher uma opção artificial “livre”. Selecionar serviço existente preserva ID, duração e preço. Texto novo é utilizado pelo fluxo de gravação existente; **sair do campo não cria cadastro**, evitando registros por formulários abandonados. Vazio é permitido somente quando os parâmetros da empresa permitem. O primeiro serviço não é selecionado automaticamente.

Catálogos públicos usam busca apenas de seleção: visitantes não ganham direitos de criar serviços/profissionais. Listas fechadas de parâmetros, dias, status e recorrência continuam limitadas aos valores válidos. Conteúdo HTML personalizado já publicado pelo cliente não é reescrito.

## Endpoints

Prefixo `/api/v1/access`: `catalog`, `users`, `users/{id}`, `users/{id}/invite`, `users/{id}/revoke-access`, `groups`, `groups/{id}`, `professionals`, `audit`, `profile`, `profile/password`, `profile/email`, `profile/verify-email`, `profile/avatar`, `confirm-email` e `confirm-page`. O OpenAPI geral descreve os schemas; as rotas interativas não são delegadas à API de máquina.

## Implantação e rollback

Publicar as imagens do commit validado. A migration **`tenant_0014_identity`**, posterior à `tenant_0013_integrations`, precisa ser aplicada a todos os bancos de empresas pelo fluxo já existente. A plataforma permanece em `platform_0013_integrations`. Não são necessários novos containers nem aumento dos pools. A dependência Pillow é instalada nas imagens API/worker pelo mecanismo existente.

Realizar backup dos bancos e objetos antes da atualização; preservar `APP_SECRET_KEY`, referências de segredos, credenciais e volumes. Não usar `docker compose down -v`. Homologar convite com SMTP real, login, recuperação, foto com MinIO/S3, autorização e agendamento. O downgrade remove apenas os novos campos/tabela de confirmação; os dados exclusivos da expansão seriam perdidos, portanto preferir rollback de código que mantenha schema compatível, com decisão e backup prévio. Nenhuma implantação de produção foi executada por esta PR.

## Validação

Testes unitários cobrem delegação, mass assignment, normalização/limites de fotos e a navegação sem modal. Testes integrados exercitam PostgreSQL e MinIO reais com e-mail de saída interceptado, incluindo uso único/expiração de convite, grupos ativos, revogação de sessões/tokens, último administrador, vínculo opcional, isolamento, troca de senha/e-mail e concorrência. CI e resultados por commit devem ser consultados na PR; testes não equivalem a carga prolongada ou homologação do SMTP real de cada cliente.
