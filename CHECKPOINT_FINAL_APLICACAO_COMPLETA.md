# Checkpoint — Scheduler Pro + ARGWS Visual Builder 2.3.1

Data: 2026-08-28

## Base

Atualização aplicada sobre a `main` atual fornecida nesta rodada.

## Estado canônico

- ARGWS Visual Builder: **2.3.1**;
- PWA: experiência principal;
- Android/APK: ativo;
- iOS/IPA: ativo;
- desktop Windows/Linux/macOS: código preservado, builds fora do fluxo ativo.

## Páginas públicas

- Landing Page `/pagina`;
- Agenda Pública `/agendar`;
- Login `/login`.

As três superfícies são páginas independentes e editáveis.

## Biblioteca de templates

Oito famílias oficiais estão versionadas como ZIPs reais em `apps/api/resources/template-packages/`. O modelo `scheduler-pro-padrao-generico` é fallback e padrão para ausência de personalização.

O bootstrap sincroniza somente a biblioteca global. Ele não substitui automaticamente páginas já personalizadas de tenants.

## Correções 2.3.1

- página publicada pode ser recuperada para edição quando o rascunho estiver ausente/inválido;
- Preview real abre a rota pública da superfície e respeita parâmetros do tenant;
- canvas HTML do editor respeita flags condicionais sem executar scripts importados;
- Agenda Pública offline não renderiza como online;
- Login público pode ser ativado/desativado;
- Login na Landing, Agendamento na Landing, Contato e WhatsApp usam flags centrais;
- Login personalizado usa a autenticação real através de `SchedulerProAuth.login`;
- dialogs, confirmações e prompts de Web/Admin/AVB usam UI interna;
- calendário consulta intervalo visível, usa timezone do tenant e reage a eventos realtime e às mutações do Operador da Agenda;
- aplicar template afeta somente a superfície selecionada;
- modelos internos antigos do AVB foram removidos da lista, permanecendo apenas “Em branco”.

## Validações executadas neste ambiente

- 8/8 pacotes oficiais validados pelo `HtmlTemplatePackageService`;
- LANDING + BOOKING + LOGIN presentes nas oito famílias;
- `python -m compileall`: OK;
- testes do ARGWS Visual Builder: 60/60 aprovados;
- scripts Vue/TypeScript verificados sintaticamente com TypeScript;
- nenhum `alert()`, `confirm()` ou `prompt()` nativo de aplicação encontrado no AVB/Web/Admin; chamadas `.prompt()` restantes são exclusivamente o contrato `beforeinstallprompt` do PWA.

## Limitação do ambiente de validação

A suíte Python completa e o build Vue completo não puderam ser executados aqui porque este runtime não possui todas as dependências do projeto e não tem acesso de rede para instalá-las. A validação completa deve ser repetida no GitHub Actions/ambiente de desenvolvimento com as dependências oficiais.
