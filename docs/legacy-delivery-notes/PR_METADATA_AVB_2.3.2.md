# PR — ARGWS Visual Builder 2.3.2

**Branch:** `fix/avb-2-3-2-editor-template-persistence`

**Título:** `fix: atualizar AVB 2.3.2 e corrigir carregamento, templates e publicação`

**Commit sugerido:** `fix: estabiliza AVB 2.3.2 no editor e persistência de templates`

## Descrição

Atualiza o ARGWS Visual Builder canônico para 2.3.2 e corrige falhas de runtime/integração que faziam páginas HTML completas aparecerem no Preview mas permanecerem vazias no editor. O Workspace passa a carregar progressivamente, o catálogo oficial é cacheado, e a aplicação de templates persiste a superfície antes de abrir o editor.

- corrige canvas HTML de primeira classe;
- reduz carregamento inicial do Project/Site;
- cacheia 8 famílias oficiais no backend;
- aplica templates separadamente em LANDING, BOOKING e LOGIN;
- salva antes de abrir e evita reload que restaurava documento anterior;
- preserva contratos Scheduler Pro compatíveis;
- mantém fallback genérico sem sobrescrever personalizações;
- AVB 2.3.2: 81/81 testes;
- 8/8 famílias válidas e importáveis.
