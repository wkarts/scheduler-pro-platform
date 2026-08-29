# Scheduler Pro 0.1.0-alpha.85 — Recuperação AVB 2.4.0 / Experience Contract v2

## Base canônica

Esta entrega foi construída diretamente sobre o arquivo enviado pelo usuário:

`Scheduler Pro 0.1.0-alpha.85`

Não foi criada PR e nenhum arquivo foi escrito no GitHub durante esta rodada. A entrega é o projeto-fonte completo atualizado em ZIP.

## Fontes analisadas

- `scheduler-pro-platform-0.1.0-alpha.85.zip`;
- `scheduler-pro-diagnostics-20260829-063154Z.zip`;
- 8 Experience Packages v2 enviados para substituir a biblioteca oficial:
  - Scheduler Pro — Padrão Genérico;
  - Barber Shop — Neo Genérico;
  - Clínica Médica — Genérico;
  - Clínica Odontológica — Genérico;
  - Clínica Veterinária — Genérico;
  - Martelinho de Ouro — Genérico;
  - Studio de Unhas — Genérico;
  - Tecnologia — Genérico Simples.

## Diagnóstico confirmado

A análise de `platform/logs.jsonl` encontrou, entre outros registros relevantes:

- 2 ocorrências de `POST /api/v1/experience/pages/LANDING/draft → HTTP 422`;
- 6 `browser_long_task` no contexto `#visual-builder`, entre 1.126 ms e 3.586 ms;
- 9 respostas HTTP 404 históricas para assets do antigo `scheduler-pro-padrao-generico`;
- importação tenant funcionando no backend (`POST /api/v1/experience/import → HTTP 200`), evidenciando que parte do problema percebido era o estado/refresh do host após importar;
- consultas ao catálogo de templates respondendo HTTP 200;
- 2 respostas 404 de `manifest.webmanifest` no hostname raiz da plataforma, sem tenant resolvido; não foram tratadas como falha de template tenant nesta rodada.

## Correções aplicadas

### 1. Importador do Control Plane

O importador deixou de ser exclusivo de `scheduler-pro-template-package/v1` e agora aceita como contrato canônico:

`argws-experience-package/v2`

O suporte ao legado v1 permanece para compatibilidade.

O importador v2 agora:

- aceita `experience.json`;
- valida Landing e Booking;
- preserva HTML/CSS/JS;
- lê `bindings.json` e `theme.json`;
- aceita assets do pacote;
- internaliza assets para a biblioteca global quando necessário;
- internaliza também referências de assets presentes nos defaults dos bindings;
- aceita pacotes de até 50 MB;
- suporta `PLATFORM_DEFAULT` no Control Plane;
- mantém Login fora do pacote, pois o Login é nativo/white-label do Scheduler Pro.

### 2. Biblioteca oficial de templates

Os oito pacotes oficiais foram substituídos por Experience Packages v2.

A biblioteca passa a reconhecer o manifesto v2 e continua reconhecendo v1 quando necessário.

Todos os pacotes oficiais possuem exatamente as superfícies públicas canônicas:

- LANDING → `/pagina`;
- BOOKING → `/agendar`.

Não existe Login HTML dentro dos novos templates.

### 3. Novo Scheduler Pro — Padrão Genérico

O template padrão foi reconstruído como uma experiência simples, clara, profissional e genérica.

Características:

- modo claro como apresentação principal;
- Landing limpa e reutilizável;
- Agenda Pública limpa e funcional;
- integração com `ARGWSRuntime.booking`;
- bindings editáveis;
- Theme Tokens v1;
- sem dependência de assets não utilizados;
- sem Login paralelo;
- adequado como fallback real para tenants sem identidade/template próprio.

### 4. Bindings v1/v2 e assets

O runtime de bindings passou a considerar `defaults` de nível superior do `bindings.json`.

Também foi corrigido o caso de binding de imagem aplicado a `<img data-sp-bind="...">` sem atributo `src`, inserindo o `src` corretamente.

As referências relativas de assets nos defaults v2 são reescritas para o caminho público canônico quando o pacote é importado por tenant.

### 5. Preview de Landing e Agenda

O Centro de Experiência agora carrega a página da superfície selecionada ao abrir e após importar/aplicar um template.

A última superfície usada é persistida localmente:

`scheduler_pro_public_pages_last_surface`

Assim, ao voltar para Páginas Públicas, Landing ou Agenda continua selecionada conforme o último uso.

### 6. Modo Avançado / ARGWS Visual Builder

Foi corrigida a causa da tela `Página vazia` em documentos HTML completos.

Documentos HTML são páginas de primeira classe e não possuem `builder.root_ids`. O editor não substitui mais esse conteúdo pelo placeholder de página vazia.

O host agora executa `el.load()` ao abrir o Modo Avançado e mantém o HTML real da superfície.

### 7. Fechar Studio

O evento `upb-close` do Web Component agora é capturado pelo host Scheduler Pro.

O botão fechar do Studio fecha o Modo Avançado e retorna ao Centro de Páginas Públicas, sem deixar o editor preso.

### 8. Menu mobile do tenant

O drawer mobile foi elevado acima das demais superfícies e overlays, com:

- z-index dedicado alto;
- backdrop próprio;
- logo real do Scheduler Pro;
- versão da aplicação;
- botão fechar explícito;
- acabamento claro e consistente;
- scrollbar discreta/quase imperceptível;
- footer com versão e estado de conexão.

### 9. Root administrativo preservado

Foi preservada a correção já existente na alpha.85:

- `/` → Login/Dashboard administrativo do tenant;
- `/pagina` → Landing pública;
- `/agendar` → Agenda Pública;
- Agenda interna continua por hash/menu da aplicação.

Nenhum endpoint adicional é necessário para entrar na administração.

## Arquivos funcionais alterados

A comparação com o ZIP alpha.85 original resultou em 26 arquivos adicionados/alterados, concentrados em:

- Control Plane / importador;
- Experience Contract e serviços de templates;
- biblioteca oficial de oito packages;
- Centro de Experiência/Páginas Públicas;
- runtime público;
- menu mobile;
- ARGWS Visual Builder;
- testes regressivos.

Não houve refatoração abrupta da aplicação.

## Validação realizada

- `python -m compileall -q app tests`: PASS;
- `node --check` nos JS alterados: PASS;
- parsing TypeScript dos quatro componentes Vue alterados: PASS;
- `npm --workspace packages/visual-builder run check`: PASS;
- `npm --workspace packages/visual-builder test`: **73/73 PASS**;
- 8 pacotes oficiais pelo importador atualizado: PASS;
- 8 ZIPs originais enviados pelo usuário pelo importador do Control Plane: PASS;
- checksum interno dos 8 templates oficiais: PASS;
- bindings defaults texto + imagem sem `src`: PASS;
- Experience v2 somente Landing + Booking: PASS.

### Limitação do ambiente desta sessão

O build completo de `apps/web`/`apps/admin` não pôde ser executado porque o source ZIP não inclui `vue-tsc`/dependências de workspace instaladas neste runtime (`vue-tsc: not found`).

O pytest completo também não é anunciado como executado nesta sessão quando requer dependências ausentes do ambiente. A compilação Python e os testes do pacote AVB foram executados conforme descrito acima.

