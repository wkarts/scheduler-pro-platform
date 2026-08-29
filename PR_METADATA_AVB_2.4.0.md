# PR — ARGWS Visual Builder 2.4.0

## Branch
`feat/avb-2-4-0-experience-sdk-branding-agenda-mobile`

## Título
`feat: canonicalizar AVB 2.4.0 com Experience SDK, branding e agenda resiliente`

## Commit sugerido
`feat: integra AVB 2.4.0, Experience Contract v2 e corrige agenda/mobile`

## Descrição

### Objetivo
Canonicalizar o ARGWS Visual Builder 2.4.0 como núcleo universal, integrar o Scheduler Pro através de Experience Contract v2/Template Runtime SDK v1 e corrigir problemas de agenda, branding e mobile sem reconstrução abrupta.

### AVB Universal
- core reutilizável em outros projetos;
- HTML/CSS/JS continuam o runtime canônico;
- Experience Contract v2;
- Template Runtime SDK v1;
- Bindings v1;
- Theme Tokens v1;
- permissões blocked/basic/design/full/developer.

### Scheduler Pro
- Landing e Agenda Pública como experiências personalizáveis;
- Login deixa de ser template e permanece nativo/white-label;
- Runtime SDK delega booking ao motor real da plataforma;
- Control Plane administra experiência e branding independentemente da permissão do tenant.

### Migração v1 → v2
Pacotes antigos continuam aceitos. Base64 grande é extraído automaticamente para assets e o HTML é preservado. Não é necessário reconstruir manualmente os templates antigos.

### Branding/PWA
- nova identidade padrão Scheduler Pro como fallback;
- logo claro/escuro;
- favicon;
- ícones PWA/maskable;
- fundo do Login;
- Theme Tokens;
- manifest por tenant;
- uploads disponíveis no tenant e Control Plane.

### Agenda
- CRUD de faixas de expediente;
- CRUD de bloqueios;
- correção de casts UUID;
- edição/exclusão/cadastro com dialogs internos.

### Agendamentos legados
- LEFT JOIN em cliente/serviço/profissional;
- labels de fallback;
- `ends_at` legado recebe fallback de 60 minutos na consulta;
- registros antigos continuam visíveis no calendário.

### Mobile
- menu do tenant como drawer responsivo com backdrop;
- calendário sem min-width desktop;
- células compactas em telas pequenas.

### Validação
- AVB Universal: 70/70 PASS;
- AVB integrado: 70/70 PASS;
- npm check: PASS;
- Python compileall: PASS;
- testes contratuais 2.4.0: 5/5 PASS;
- Vue/TypeScript: 28 scripts / 0 falhas sintáticas;
- 8 templates oficiais + Studio/Roberto/Gilmar migrados pelo Experience Contract v2.

A suíte pytest completa, Ruff e MyPy precisam ser reconfirmados no GitHub Actions porque as dependências/executáveis não estão disponíveis no runtime local usado para preparar esta entrega.
