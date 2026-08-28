# Migração 1.0 → 2.0

A migração é automática ao chamar `normalizeDocument()`.

- V1: `argws-visual-builder/v1`
- 1.0: `argws-visual-builder/v2`, version 3
- 2.0: `argws-visual-builder/v3`, version 4

Nenhum nó existente é descartado. A 2.0 adiciona `project`, amplia `seo` e normaliza novos estados.

## Scheduler Pro

O conteúdo compilado continua `version:2` apenas como projeção compatível com a API atual; `builder.schema` registra V3. O instalador reconhece V1, V2 e V3 para migração de dados, mas o runtime usa exclusivamente o ARGWS Visual Builder Universal 2.0.

## Backend

Atualize a whitelist de schemas aceitos para incluir `argws-visual-builder/v3` e mantenha V1/V2 durante a janela de migração.
