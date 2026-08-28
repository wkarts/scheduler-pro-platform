# Scheduler Pro — ARGWS Visual Builder 2.3.2 canônico

## Problemas corrigidos

### 1. Template aparece no Preview, mas o editor mostra “Página vazia”

A causa era a regra do canvas que interpretava `builder.root_ids.length === 0` como página vazia mesmo quando o documento era `mode=HTML`. Páginas HTML completas, por definição, não precisam possuir nós do builder visual.

A condição agora só exibe o estado vazio para documentos visuais sem nós. Em HTML, o iframe/document frame permanece visível.

### 2. Project/Site demorava 1–2 minutos

O adapter antigo esperava settings, contexto, Landing completa, Booking completa, Login completa e validação das oito famílias de ZIP antes de mostrar o Workspace.

A 2.3.2 usa carregamento progressivo:

1. settings + contexto;
2. três cards de página imediatamente;
3. catálogo oficial em background;
4. HTML completo apenas ao clicar em Editar.

No backend, o catálogo lê apenas `template.json` e usa cache em processo; a validação completa fica no bootstrap e na aplicação da superfície. Em validação local, a leitura fria dos oito manifestos levou cerca de 43 ms e chamadas seguintes ficaram abaixo de 1 ms.

### 3. “Aplicar template” não persistia

A ação agora:

1. obtém a superfície selecionada do pacote oficial;
2. substitui somente a página correspondente;
3. grava o rascunho/configuração no backend;
4. somente depois abre o editor;
5. abre com `reload:false`, impedindo que o documento anterior/fallback seja carregado por cima.

### 4. Salvar e publicar

- Landing: versão de rascunho + publicação pelo Landing Service;
- Booking: conteúdo/chave/versão do template no tenant;
- Login: conteúdo/chave/versão do template no tenant.

Booking e Login são consumidos diretamente pelas páginas públicas a partir dessas configurações, portanto o botão Publicar confirma/persiste o documento ativo sem criar uma autenticação ou agenda paralela.

## Contrato

O contrato Scheduler Pro continua compatível (`scheduler-pro-html-template/v1` e `scheduler-pro-template-package/v1`). O número **2.3.2** é a versão do ARGWS Visual Builder, não uma quebra de schema do template.

## Validação

- 81/81 testes do AVB;
- 8/8 famílias importadas pelo AVB;
- 8/8 pacotes aceitos pelo backend;
- LANDING + BOOKING + LOGIN em todos os pacotes.
