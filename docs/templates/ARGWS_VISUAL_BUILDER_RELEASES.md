# ARGWS Visual Builder Editor — releases no Scheduler Pro

O Scheduler Pro trata o **ARGWS Visual Builder Editor** como um produto versionado. Uma atualização do editor não apaga a release anterior: versões homologadas podem coexistir para rollout, teste, compatibilidade e rollback.

## Releases instaladas

| Release | Schema nativo | Canal no Scheduler Pro | Uso |
|---|---|---|---|
| `1.0.0` | `argws-visual-builder/v2` | `legacy-test` | compatibilidade e testes da geração profissional V1 |
| `2.0.0` | `argws-visual-builder/v3` | `stable` | primeira geração Universal 2.0 |
| `2.0.1` | `argws-visual-builder/v3` | `current` | release atual, New-Only e padrão inicial |

Os artefatos originais ficam preservados em `packages/visual-builder/releases/`. O pacote `@argws/visual-builder` funciona como registry/loader e carrega apenas uma release por documento do navegador. Ao trocar de versão, o Scheduler Pro persiste a escolha e recarrega a aplicação antes de registrar o Web Component da outra release, evitando colisão de Custom Elements e mantendo o consumo de memória previsível.

As releases `2.0.0` e `2.0.1` fornecidas para esta implementação possuem o mesmo núcleo JavaScript. A `2.0.1` altera metadados, documentação e a política upstream New-Only. No Scheduler Pro elas permanecem releases distintas porque rollout e homologação são decisões administrativas.

## Política global

O Control Plane expõe um gestor próprio do ARGWS Visual Builder. O administrador pode:

- escolher a release padrão global;
- liberar uma, várias ou nenhuma release para uma empresa;
- escolher a release padrão daquela empresa;
- devolver a empresa para a política herdada global.

A configuração global usa a feature flag `argws_visual_builder_release_policy`. A política específica usa `tenants.settings.argws_visual_builder`, sem alterar migrations históricas.

## Política do tenant

Sem política administrativa específica, o tenant recebe somente a release padrão global. Quando o Control Plane libera várias versões, o próprio tenant pode alternar entre elas dentro do editor. A escolha fica em `tenant_settings.visual_builder_version` e nunca permite uma versão que o Control Plane não tenha liberado.

Cada save/autosave do editor grava também `builder_version` no conteúdo. A página pública usa esse marcador, ou o schema nativo do documento, para ativar o renderer da mesma família que produziu o conteúdo.

## Templates oficiais desta release

Os sete modelos genéricos de blocos antigos deixam de ser oferecidos para novos usos. A biblioteca inicial passa a usar exclusivamente os Template Packages V1 HTML first-class fornecidos para esta evolução:

- Barber Shop — Neo Genérico;
- Clínica Médica — Genérico;
- Clínica Odontológica — Genérico;
- Clínica Veterinária — Genérico;
- Martelinho de Ouro — Genérico;
- Studio de Unhas — Genérico;
- Tecnologia — Genérico Simples.

Os pacotes ficam em `apps/api/resources/template-packages/`, são validados pelo mesmo `HtmlTemplatePackageService` usado pelo importador do Control Plane e são sincronizados de forma idempotente no bootstrap. Na primeira instalação entram como `INTERNAL` + `PUBLISHED`: ficam administráveis no Control Plane, mas não são liberados automaticamente a tenants. O administrador decide posteriormente se cada família será `GLOBAL`, `SELECTED`, `EXCLUSIVE` ou continuará interna.

Imagens Base64 foram reencodadas para WebP somente quando houve redução material do payload. HTML, CSS, JavaScript inline, metadados do Scheduler Pro, rotas `/pagina` e `/agendar` e integração com a Agenda foram preservados.

## Compatibilidade

- páginas HTML já publicadas continuam protegidas contra conversão silenciosa;
- páginas antigas já materializadas no banco continuam funcionando;
- os modelos genéricos antigos deixam apenas de fazer parte do catálogo para novas aplicações;
- troca de release do editor não troca o template publicado;
- o histórico/versionamento da Landing Page continua sendo a proteção para rollback de conteúdo;
- a release `1.0.0` permanece disponível para teste, mas uma troca de uma página 2.x para 1.0.0 exibe aviso porque o schema anterior pode não representar todos os recursos modernos.
