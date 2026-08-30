# Scheduler Pro — Versionamento Canônico

A linha oficial do Scheduler Pro passa a iniciar em **1.0.0**.

A partir desta versão, releases oficiais utilizam **Semantic Versioning (SemVer)** no formato:

`MAJOR.MINOR.PATCH`

Exemplos:

- `1.0.0`
- `1.0.1`
- `1.1.0`
- `1.2.0`
- `2.0.0`

## Regras

- `PATCH`: correções compatíveis e melhorias incrementais sem quebra de contrato. É o incremento padrão para merges canônicos.
- `MINOR`: funcionalidades novas compatíveis. Pode ser solicitado pelo label `semver:minor` na PR.
- `MAJOR`: alterações incompatíveis ou uma nova geração do produto. Pode ser solicitado pelo label `semver:major` na PR.
- O label `semver:patch` pode ser usado explicitamente, mas PATCH já é o comportamento padrão.
- Tags canônicas não usam prefixo `v`: a versão oficial é `1.0.0`, e não `v1.0.0`.
- Uma versão publicada nunca deve ser reapontada para outro commit. O histórico canônico é imutável.

## GitHub Release e artefatos

Cada versão canônica publica uma GitHub Release com a mesma tag SemVer e artefatos contendo a versão no nome.

Exemplo para `1.0.0`:

- `scheduler-pro-web-1.0.0.tar.gz`
- `scheduler-pro-admin-1.0.0.tar.gz`
- `scheduler-pro-cloudpanel-1.0.0.tar.gz`
- `scheduler-pro-dockge-1.0.0.tar.gz`
- `scheduler-pro-source-1.0.0.tar.gz`

APK e IPA permanecem pausados até que as experiências Android e iOS estejam aptas para homologação real.

## GHCR

Cada imagem própria do Scheduler Pro é mantida com três referências:

1. **SemVer imutável**, por exemplo `:1.0.0`;
2. **SHA imutável**, por exemplo `:<git-sha>`;
3. **`latest`**, alias móvel para a versão canônica mais recente.

O conjunto inclui:

- `python-base`
- `api`
- `worker`
- `web`
- `admin`
- `proxy`
- `acme`
- `cloudpanel-agent`

A promoção para `1.0.0` e `latest` só ocorre depois que todas as imagens do mesmo commit tiverem sido construídas e validadas.

## Rollback

O Compose já utiliza `APP_IMAGE_TAG`. Para retornar todo o Scheduler Pro a uma versão canônica específica, fixe a variável no ambiente:

```env
APP_IMAGE_TAG=1.0.0
```

Depois atualize o conjunto normalmente:

```bash
docker compose pull
docker compose up -d
```

Para voltar a acompanhar a versão canônica mais recente:

```env
APP_IMAGE_TAG=latest
```

`latest` é conveniente para atualização contínua; versões SemVer e SHAs são as referências recomendadas para rollback, auditoria e reprodução exata de uma implantação.

## Fonte canônica inicial

O arquivo `VERSION` na raiz registra a versão-base oficial desta nova linha:

```text
1.0.0
```

Os workflows de publicação utilizam essa versão como ponto inicial e passam a calcular as próximas versões estáveis a partir do histórico de releases SemVer.
