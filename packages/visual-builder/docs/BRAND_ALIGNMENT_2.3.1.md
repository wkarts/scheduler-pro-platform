# Brand Alignment 2.3.1 — ARGWS Visual Builder Universal

## Objetivo

Alinhar a interface do produto à identidade visual oficial AVB sem alterar arquitetura, schema, documentos, renderer público, adapters ou integrações.

## Paleta oficial

| Token | Valor | Uso principal |
|---|---|---|
| Deep Navy | `#0B1020` | fundo estrutural Dark |
| Charcoal | `#1E2435` | superfície elevada Dark |
| Cyan | `#1AD5E8` | marca/destaque decorativo no Dark |
| Electric Blue | `#2563FF` | ação e foco acessíveis |
| Violet | `#7A4DFF` | marca/destaque secundário |
| Light Gray | `#E9EEF5` | canvas/superfície de separação Light |

Gradiente oficial:

```css
linear-gradient(90deg,#1AD5E8 0%,#2563FF 50%,#7A4DFF 100%)
```

O gradiente continua disponível como token de marca, porém não é usado diretamente atrás de texto branco em ações críticas porque Cyan + branco não atinge contraste AA. Botões primários usam `#2563FF` sólido.

## Tipografia

- **Headings do produto AVB:** `Space Grotesk`, fallback `Inter`, depois system-ui.
- **Interface / Body:** `Inter`, depois system-ui.
- pesos permitidos na UI: 400, 500, 600 e 700.

O pacote não incorpora arquivos de fonte e não adiciona dependência obrigatória de CDN. Se o host não disponibilizar Space Grotesk, Inter/system-ui preservam legibilidade e layout.

## Isolamento do documento editado

A tipografia e o tema do AVB são exclusivos da interface do builder. O renderer público e o canvas da página continuam obedecendo ao Design System do documento.

```text
Tema AVB: Light/Dark
        │
        └── não altera
             │
             └── Tema/Fontes da página do cliente
```

Assim é possível editar uma landing escura no AVB Light, ou uma página clara no AVB Dark, sem contaminar o conteúdo.

## Light Mode

Tokens de legibilidade principais:

```text
background   #F6F8FB
surface      #FFFFFF
canvas       #E9EEF5
text         #0B1020
text-soft    #1E2435
muted        #5B677A
accent       #2563FF
```

## Dark Mode

```text
background   #0B1020
surface      #121827
raised       #1E2435
text         #F7F9FC
text-soft    #D9E1EC
muted        #A6B2C4
accent       #2563FF
accent text  #1AD5E8
```

## Contraste validado

Os testes automatizados verificam contraste WCAG AA (`>= 4.5:1`) nos pares essenciais. Exemplos:

- `#F7F9FC` / `#0B1020`: ~17.95:1
- `#D9E1EC` / `#121827`: ~13.44:1
- `#A6B2C4` / `#121827`: ~8.25:1
- `#0B1020` / `#FFFFFF`: ~18.93:1
- `#5B677A` / `#FFFFFF`: ~5.73:1
- branco / `#2563FF`: ~4.88:1
- branco / `#7A4DFF`: ~4.85:1

## Project/Site Workspace

A partir da 2.3.1, o Project/Site Workspace usa o mesmo tema persistido do Visual Editor. A preferência é compartilhada por `argws_visual_builder_editor_theme`.

## Compatibilidade

Não houve alteração em:

- `argws-visual-builder-project/v2`;
- `argws-visual-builder/v3`;
- `PageDocument`;
- `MemoryProjectAdapter`;
- `RestProjectAdapter`;
- `SchedulerProProjectAdapter`;
- compilador Scheduler Pro V2;
- importação de template families;
- renderer público;
- Plugin SDK;
- Data Sources / Query Engine.

A 2.3.1 é compatível com projetos 2.3.0 sem migração de dados.
