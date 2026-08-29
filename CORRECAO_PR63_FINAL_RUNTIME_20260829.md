# Scheduler Pro — Fechamento da rodada PR #63 / AVB 2.4.0

Este pacote é o **projeto-fonte completo** do Scheduler Pro atualizado sobre a base oficial `v0.1.0-alpha.83` (`9f710d6ecdd9420fdaa1d66eb2e79c0074446083`).

Ele não é um patch isolado. A árvore contém a aplicação completa — API, Web, Admin, mobile/desktop, infraestrutura, deployments, documentação, packages, Visual Builder, testes e scripts — já com as correções finais incorporadas.

## Escopo incorporado

1. Agenda Pública sem bloqueio HTTP 422 causado por template visual incompatível.
2. Migração Base64 com assets independentes para Landing e Booking.
3. Compatibilidade para tenants já migrados com alias Landing/Booking.
4. Bindings de imagem tratados como imagem, nunca URL textual.
5. Login nativo/white-label do Scheduler Pro preservado como rota `/login`.
6. ARGWS Visual Builder 2.4.0 sem ciclo de montagem que produzia tela branca.
7. Branding Tenant e Control Plane refinado sem gradientes funcionais multicoloridos.
8. Ícones PWA transparentes e manifests/cache revisados.
9. Workflow canônico de integração preservado sem alteração.

Consulte `PR_METADATA_AVB_2.4.0_PR63_FINAL_RUNTIME.md` para o texto completo da PR e `VALIDACAO_PR63_FINAL_RUNTIME_20260829.txt` para os resultados da validação local.
