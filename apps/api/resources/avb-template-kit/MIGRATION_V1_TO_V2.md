# Migração de templates legados para Experience Contract v2

O v2 não exige refazer o visual.

Estratégia:

1. Ler `template.json`, `landing.html`, `agendamento.html` e opcional `login.html` antigos.
2. Preservar Landing e Agenda visualmente.
3. Ignorar `login.html` como superfície de runtime; extrair somente branding útil.
4. Extrair imagens Base64 grandes para `assets/`.
5. Criar `experience.json`.
6. Criar `bindings.json` para campos que devem ser editáveis.
7. Criar `theme.json` a partir da identidade existente.
8. Substituir chamadas diretas à Agenda por Template Runtime SDK.
9. Validar e comparar screenshots antes/depois.

O pacote v1 continua podendo ser mantido pelo host como compatibilidade, mas novos templates devem preferir v2.
