# Scheduler Pro — ARGWS Visual Builder 2.3.1 canônico

## Direção

O Scheduler Pro permanece **PWA-first**. Os únicos artefatos nativos ativos são Android/APK e iOS/IPA. O código desktop continua preservado para eventual retomada, mas fora do pipeline ativo.

A versão canônica do editor é:

```text
ARGWS Visual Builder 2.3.1
```

## Páginas de primeira classe

No Scheduler Pro, template não é componente. Cada família oficial contém páginas completas independentes:

- `LANDING` → `/pagina`;
- `BOOKING` → `/agendar`;
- `LOGIN` → `/login`.

Os componentes pertencem às páginas. Aplicar um template em uma superfície não substitui automaticamente as demais páginas.

## Biblioteca oficial

A biblioteca contém oito famílias reais `scheduler-pro-template-package/v1`:

1. Scheduler Pro — Genérico padrão;
2. Barber Shop — Neo Genérico;
3. Clínica Médica — Genérico;
4. Clínica Odontológica — Genérico;
5. Clínica Veterinária — Genérico;
6. Martelinho de Ouro — Genérico;
7. Studio de Unhas — Genérico;
8. Tecnologia — Genérico Simples.

O template `scheduler-pro-padrao-generico` é o fallback da plataforma. Ele não substitui páginas personalizadas existentes.

## Contexto real do tenant

Preview e páginas publicadas usam o contexto canônico `scheduler-pro-public-page-context/v1`, com:

- tenant e timezone;
- capabilities;
- Landing online/offline;
- Agenda Pública online/offline;
- Login público online/offline;
- Login na Landing;
- Agendamento na Landing;
- contato na Landing;
- WhatsApp na Landing.

## Compatibilidade

O adapter 2.3.1 tenta carregar, nessa ordem, a versão editável atual, a publicação existente e, quando nenhuma delas é utilizável, o template genérico padrão. Conteúdo personalizado válido nunca é substituído automaticamente pelo fallback.

## Login

Login é uma página visual editável, porém a autenticação continua sendo a autenticação real do Scheduler Pro. Templates usam `SchedulerProAuth.login` através do bridge do host; não existe sistema de autenticação paralelo.

## Agenda

O calendário consulta o período visível e normaliza data/hora pelo timezone do tenant. Eventos realtime de agendamento atualizam o calendário sem exigir reload completo da página.

## Dialogs

A UI não usa `alert()`, `confirm()` ou `prompt()` do navegador para decisões da aplicação. Confirmações e prompts são internos ao Scheduler Pro/AVB. O `beforeinstallprompt` do PWA é uma API de instalação e não é um dialog de aplicação substituível.
