# Entrega — Scheduler Pro: correção de resiliência

**Identificador:** resilience-20260905 · **Produto:** 2.1.0 · **Visual Builder:** 2.4.0

Projeto completo atualizado a partir de `scheduler-pro-platform-main (9).zip`. Sem migração de schema nova, sem mudança de identidade visual e sem publicação automática no seu GitHub/servidor.

## Comece por estes arquivos

- `docs/audits/RESILIENCIA_2026-09-05.md`: diagnóstico, alterações, testes e riscos residuais.
- `docs/operations/RESILIENCIA_DEPLOY_2026-09-05.md`: variáveis, backup, publicação de imagens, implantação e rollback.
- `validation/resilience-20260905/SUMMARY.json`: o que passou e o que não foi executado.
- `validation/resilience-20260905/CHANGESET.json`: relação de arquivos e hashes contra o ZIP original.
- `scripts/operations/`: diagnóstico SQL, cálculo de conexões e backup lógico por banco.

## Correções principais

Pools limitados por processo/empresa; aliases sem pools duplicados; fechamento explícito de 40 consumidores de sessão; cache de engines com leases; runtime único dos workers; sessões curtas em realtime; observabilidade HTTP limitada; 503 coerente para banco indisponível; readiness com nova conexão e headroom; refresh resiliente nos dois painéis; configuração de concorrência e rotação de logs.

## Validação

**228 testes aprovados nas execuções disponíveis**, distribuídos entre núcleo, autenticação compilada, contratos existentes, Visual Builder e scripts de operação. Compilação/sintaxe e contrato PWA também passaram.

Não executados: suíte completa da API, oito novos testes HTTP, Ruff/Mypy completos, build Vue/Docker/nativo, integração/carga e restauração real. Dependências ausentes e falta de Docker impediram essas execuções locais. O CI completo permanece requisito antes de produção.

## Atenção para implantação

Não basta copiar fontes ou alterar `.env`: publique novas imagens deste commit. Incorpore variáveis ao ambiente existente sem trocar `APP_SECRET_KEY`, senhas, mounts ou identidade da stack. Não use `down -v`. O roteiro traz atualização direcionada, preservação de dados e rollback.

O subtotal padrão de pools dos serviços API/worker é 42 conexões teóricas; conexões auxiliares, réplicas, outros serviços e folga precisam entrar no cálculo real. Redundância física, backup off-site e restore homologado continuam necessários. Este pacote não é garantia de ausência absoluta de falhas.

**Título sugerido para PR:** `fix(resilience): limitar conexões, corrigir sessões e preservar autenticação durante falhas transitórias`
