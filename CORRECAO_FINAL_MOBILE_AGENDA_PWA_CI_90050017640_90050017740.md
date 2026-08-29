# Correção final — Mobile, Agenda, PWA e CI — ARGWS Visual Builder 2.4.0

Data: 2026-08-28

## Logs analisados

- `logs_90050017640.zip`
- `logs_90050017740.zip`

## 1. API / MyPy

Falha observada:

```text
app/api/v1/routes/platform_templates.py:214:
Incompatible types in assignment (expression has type "str", variable has type "AuthPrincipal")
```

Causa: o parâmetro `_` da rota já era tipado como `AuthPrincipal`, mas o mesmo nome era reutilizado no desempacotamento de `DEVELOPER_KIT_ARTIFACTS`.

Correção:

```python
filename, _label, media_type = DEVELOPER_KIT_ARTIFACTS[artifact]
```

Nenhuma regra do MyPy foi desativada.

## 2. Multitenant Integration Stack

O run falhou antes da API iniciar. O BuildKit retornou:

```text
failed to solve: Unavailable: error reading from server: EOF
```

Todos os passos posteriores falharam por consequência com `service "api" is not running`.

Correção do workflow:

1. build separado de `api` e `bootstrap`;
2. até 3 tentativas;
3. prune do builder entre tentativas;
4. backoff progressivo;
5. somente após build válido: `up --no-build -d`;
6. testes continuam falhando normalmente se a aplicação realmente não subir.

## 3. Menu mobile

Causa raiz: os labels eram removidos do DOM por:

```vue
v-if="!collapsed"
```

No mobile o drawer podia estar aberto com `collapsed=true`, por isso somente os ícones existiam.

Correção:

```vue
v-if="!collapsed || mobileOpen"
```

Aplicado ao branding, itens do menu, instalação, sair e informações da versão.

O drawer mobile possui backdrop, largura responsiva e bloqueio de scroll da página enquanto aberto.

## 4. Calendário mobile

Correções:

- sete colunas reais com `repeat(7,minmax(0,1fr))`;
- `min-width:0` em grid, cards e células;
- largura máxima de 100%;
- redução de padding/gap em telas pequenas;
- mês selecionado também atualiza o dia selecionado;
- elimina o cenário "Setembro" com painel ainda apontando para data de agosto.

## 5. Agendamentos legados

Consultas de calendário agora usam `starts_at` como critério de pertencimento ao período:

```sql
a.starts_at >= :range_start and a.starts_at < :range_end
```

Assim registros antigos não desaparecem porque `ends_at` está nulo ou inconsistente.

Para leitura, `ends_at` inválido recebe fallback seguro de 60 minutos.

Relacionamentos continuam com `LEFT JOIN`, com labels de compatibilidade:

- Cliente legado;
- Atendimento;
- Agenda geral.

## 6. Serviço sem duração fixa

`duration_minutes = 0` agora é válido no cadastro de serviço e significa **duração variável**.

A interface exibe "Duração variável".

No momento de criar um agendamento real, como o motor precisa de uma janela para disponibilidade/conflitos, um serviço variável utiliza a duração padrão configurada no tenant, salvo quando uma duração efetiva for informada no atendimento.

## 7. Expediente e bloqueios

CRUD completo confirmado para:

- criar faixa de expediente;
- editar faixa;
- excluir faixa;
- criar bloqueio;
- editar bloqueio;
- excluir bloqueio;
- Geral ou profissional específico.

Faixas como `17:30–22:00` são válidas.

A interface também valida horários antes de enviar à API e apresenta erro legível quando o fim é anterior ao início.

## 8. PWA e identidade

Fortalecimento da atualização:

- `serviceWorker.register('/sw.js', { updateViaCache: 'none' })`;
- `registration.update()` no carregamento;
- update periódico enquanto a aplicação está visível e online;
- update ao voltar para foreground/focus/online/pageshow;
- reload quando um novo Service Worker assume o controle;
- cache canônico avançado para `avb-2.4.0-final-mobile-agenda-v5`;
- manifest dinâmico com `Cache-Control: no-store`;
- assets de branding revalidados;
- URLs de ícones personalizados versionadas por `branding_version`;
- identidade Scheduler Pro nova usada como fallback;
- white-label do tenant continua prevalecendo.

Observação: a aplicação força revalidação do SW/manifest/assets. O instante em que Android/iOS atualiza visualmente o ícone já instalado na tela inicial continua sujeito ao navegador/SO.

## 9. Contratos de teste atualizados

Foram eliminadas expectativas obsoletas que ainda exigiam:

- AVB 2.3.2;
- `login.html` como terceira página de template;
- adapter antigo de Project Workspace;
- versão anterior do cache PWA.

Os contratos agora refletem AVB 2.4.0:

- Experience Contract v2;
- Landing + Booking em HTML;
- Login nativo white-label;
- ExperiencePageAdapter;
- PWA v5.

## Validações locais executadas

- ARGWS Visual Builder 2.4.0: 70/70 testes PASS;
- `npm run check`: PASS;
- Python `compileall`: PASS;
- Workflow Integration Tests: YAML válido;
- scripts Vue/TypeScript: 28 verificados, 0 falhas sintáticas;
- `pwa.ts`, Admin PWA, branding e analytics: transpile TypeScript PASS.

Não foram executados localmente Ruff/MyPy/pytest completo porque esses executáveis/dependências não estão presentes neste runtime. O erro MyPy fornecido no log foi corrigido diretamente e deve ser reconfirmado no GitHub Actions.
