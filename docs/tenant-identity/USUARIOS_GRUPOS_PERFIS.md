# Usuários, grupos, perfis e ajustes de navegação

Base de implementação: main `dc3c0cb6ba41af71246927a771fccb556c5d3a86` (Scheduler Pro 2.1.0, PR #97 incorporada).

## Utilização

No painel da empresa, **Usuários e grupos** permite consultar contas, criar usuários por convite, editar nome/telefone, ativar/desativar e associar grupos existentes. **Grupos e permissões** reutiliza `roles`, `permissions`, `role_permissions` e `user_roles`; não há autorização paralela. Grupos podem ser ativados ou desativados. O histórico exibe ações administrativas e acessos. A exclusão definitiva de contas não faz parte deste fluxo: desativar mantém referências/auditoria.

Cada usuário acessa **Meu perfil**, inclusive sem permissões administrativas. Pode alterar nome e telefone, confirmar/trocar o e-mail, alterar a senha e cadastrar/remover foto. Para administrar usuários, conceder também `users.read`; `users.manage` sozinho não dá acesso à listagem. A consulta de auditoria usa `users.audit` e administração dos grupos usa `groups.manage`.

O novo usuário recebe um convite de uso único, válido por 24 horas, para confirmar o e-mail e definir a própria senha. Nenhuma senha é enviada por e-mail. O SMTP próprio ou compartilhado já configurado na empresa é reutilizado. Se o SMTP falhar, a conta permanece pendente e a tela informa a falha; após corrigir a configuração, reenviar convite (intervalo mínimo de um minuto). Não há fallback silencioso para um remetente diferente.

Trocar e-mail exige senha atual e confirmação na nova caixa postal. O endereço atual é preservado até a confirmação. Alteração/recuperação de senha, desativação e revogação administrativa encerram sessões e revogam tokens de API. Os links são vinculados ao banco da empresa; o token original só vai no e-mail, seu hash fica no banco. O frontend remove o token do fragmento da URL antes de instalar telemetria. Links precisam ser reabertos pelo e-mail após recarregar a página.

O vínculo com profissional é **opcional**, um-para-um, sem criação automática de permissões. Usuário administrativo sem profissional e profissional sem usuário continuam válidos. A exclusão de um profissional limpa o vínculo, não exclui a conta. Um administrador não pode editar seus próprios grupos/estado: usa Meu perfil para seus dados. Não pode conceder permissões fora de seus direitos atuais, atuar em contas superiores, nem remover o último administrador ativo. A autorização é revalidada no backend sob bloqueio transacional por banco.

## Foto

JPEG, PNG ou WebP estático, máximo 2 MiB, 12 milhões de pixels e dimensão máxima 8192. O conteúdo é validado (não só extensão/MIME), imagens animadas são recusadas e a imagem é regravada em PNG até 512x512, sem metadados. O arquivo usa o serviço/cota de armazenamento existente do tenant. O prefixo `_identity/` é privado e bloqueado nos endpoints genéricos de arquivos. Somente o próprio usuário autenticado lê/altera sua foto.

Sob falha ambígua entre upload e commit, um objeto pode ficar órfão: não é removido cegamente, para não apagar foto possivelmente referenciada. A expansão não implementa coleta automática desses órfãos. Os links usados/expirados permanecem registrados: não há limpeza automática nesta entrega.

## Integrações

Um único menu **Integrações** abre uma view normal, no tenant e no Control Plane, sem modal/Teleport ou montagem independente. API Services, Webhook Services, entregas, operações e documentação continuam como abas. Os indicadores operacionais anteriores do Control Plane ficam preservados. Tokens, escopos, assinaturas, idempotência, fila e restrições de saída da PR #97 não são substituídos. A nova área de identidade é interativa e não expõe gestão de credenciais/perfil a tokens de máquina. Permissões de grupos desativados não são aceitas por login, requests, tokens ou webhooks.

## Pesquisa no agendamento

Combobox editável, busca enquanto digita, limite de seis sugestões, teclado e layout mobile. Serviço existente preenche os respectivos valores. Digitar serviço novo e avançar mantém o texto; **o cadastro é feito/reutilizado pelo fluxo existente ao salvar o agendamento**, nunca simplesmente ao perder foco. Campo vazio respeita a configuração opcional/obrigatória da empresa. Não seleciona o primeiro serviço automaticamente. Clientes/profissionais e outros seletores de entidades usam pesquisa; enums fechados de configuração mantêm valores restritos. O catálogo público é pesquisável, mas visitantes não podem criar serviços/profissionais.

## Endpoints

Prefixo `/api/v1/access`:

- `GET /catalog`, `GET/POST /users`, `GET/PUT /users/{id}`, `POST /users/{id}/invite`, `POST /users/{id}/revoke-access`;
- `GET/POST /groups`, `PUT /groups/{id}`, `GET /professionals?q=...`, `GET /audit`;
- `GET/PUT /profile`, `POST /profile/password`, `/profile/email`, `/profile/verify-email`;
- `GET/PUT/DELETE /profile/avatar`, `POST /confirm-email` (público, token de confirmação e hostname da empresa).

Corpos desconhecidos são rejeitados, identificadores usam UUID e consultas de usuários/auditoria são paginadas em 25 itens. O catálogo de profissionais vinculado ao perfil tem pesquisa no servidor com limite de 20. Os campos operacionais pesquisam os dados disponíveis nos lookups existentes; não há promessa de uma busca remota ilimitada em todos os catálogos.

## Migração e implantação

`tenant_0014_identity` sucede `tenant_0013_integrations`. Aplicar a todas as bases de empresas pelo fluxo existente. Não há nova migration da plataforma, serviço, segredo ou variável obrigatória. As imagens Docker permanecem AMD64. O pipeline canônico é responsável por calcular a próxima versão: esta expansão não força nem reaponta uma tag publicada.

A migration adiciona colunas e índices, a tabela de confirmação e quatro permissões. Usuários existentes continuam com `verification_required=false`: não inventa confirmação histórica nem exige vínculo profissional. Grupos existentes ficam ativos e grupos com `tenant.manage` recebem administração de usuários/grupos. Novos tenants recebem os mesmos direitos no provisionamento. Nomes/e-mails existentes não são reescritos; duplicidades históricas não impedem a migration, mas novas alterações de e-mail verificam conflitos sem diferenciar maiúsculas.

Antes da atualização: backup dos bancos/bucket e preservação de `APP_SECRET_KEY`, credenciais e volumes. Publicar as imagens do commit validado, migrar plataforma/empresas como já previsto e testar convite, perfil, permissões e agendamento em homologação. Não executar `docker compose down -v` em produção.

Preferir rollback de aplicação mantendo colunas aditivas. Downgrade remove campos/fotos referenciadas e confirmações da expansão (não remove contas/grupos), por isso exige backup/avaliação antes de execução. Revogação de credenciais é irreversível por intenção: usuário/integração deve renovar acesso.

## Validação e limites

Os testes específicos cobrem delegação, autorizações atuais, vínculos opcionais, conta pendente/confirmada, expiração/uso único, concorrência na confirmação, senha/recuperação/revogação de API, mudança de e-mail, SMTP indisponível, isolamento entre bancos, foto no MinIO e validação de conteúdo. SMTP é capturado em testes, nunca enviado a destinatários externos. Testes de interface com respostas simuladas não substituem autenticação real.

A aprovação do CI não representa implantação em produção, teste de carga prolongada, entrega SMTP real ou restauração de backup. Resultados do commit final e URLs das execuções são registrados na PR.
