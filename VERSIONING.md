# Scheduler Pro — Versionamento Canônico

A linha oficial do Scheduler Pro inicia em **1.0.0** e utiliza Semantic Versioning no formato `MAJOR.MINOR.PATCH`.

Exemplos:

- `1.0.0`
- `1.0.1`
- `1.0.2`
- `1.1.0`
- `2.0.0`

## Regra automática por merge

Toda PR mesclada em `main` que altere código/produto passa pelo workflow `Canonical Merge Release`.

A sequência canônica é:

1. resolver a próxima versão;
2. persistir a versão no repositório;
3. construir e publicar todas as imagens GHCR;
4. validar o conjunto completo;
5. criar a Git tag imutável;
6. criar a GitHub Release;
7. gerar os artefatos de distribuição;
8. publicar o pacote independente do ARGWS Visual Builder.

A GitHub Release **não é criada** se a publicação das imagens falhar.

## Cálculo da versão

Sem label, o workflow considera o título/body da PR.

Labels oficiais:

- `version:patch`
- `version:minor`
- `version:major`

Os labels antigos `semver:patch`, `semver:minor` e `semver:major` continuam aceitos para compatibilidade.

Sem label explícito:

- `feat: ...` ou `feat(scope): ...` → MINOR;
- `feat!: ...` → MAJOR;
- `BREAKING CHANGE:` no corpo da PR → MAJOR;
- qualquer outro título → PATCH.

PATCH permanece o fallback, garantindo evolução progressiva:

```text
1.0.0 -> 1.0.1 -> 1.0.2
```

## Persistência da versão

A versão calculada é gravada antes da publicação em:

- `VERSION`;
- `RELEASE-MANIFEST.json`;
- `package.json` e `package-lock.json` da raiz;
- packages do Tenant/Control Plane/Desktop/Mobile;
- Tauri e Cargo correspondentes;
- `@scheduler-pro/api-client`;
- `@scheduler-pro/types`;
- defaults de versão da API/Worker e health/version endpoint.

O **ARGWS Visual Builder não é alterado por essa sincronização**; ele mantém linha independente, atualmente `2.4.x`.

## GHCR

Para uma versão `1.4.3`, cada imagem própria recebe:

```text
:1.4.3
:1.4
:1
:latest
:<git-sha>
```

As imagens são publicadas para:

```text
linux/amd64
linux/arm64
```

O conjunto inclui:

- `python-base`
- `api`
- `worker`
- `web`
- `admin`
- `proxy`
- `acme`
- `cloudpanel-agent`

A promoção é feita em duas etapas: primeiro todas as tags SemVer completas são criadas e verificadas; só depois os aliases móveis `MAJOR.MINOR`, `MAJOR` e `latest` avançam.

## Rollback

O Compose utiliza `APP_IMAGE_TAG`.

Para voltar exatamente a uma versão canônica:

```env
APP_IMAGE_TAG=1.0.0
```

Depois:

```bash
docker compose pull
docker compose up -d
```

Para acompanhar a versão canônica mais recente:

```env
APP_IMAGE_TAG=latest
```

## ARGWS Visual Builder — pacote independente

O ARGWS Visual Builder possui linha própria de versionamento e **não herda a versão do Scheduler Pro**.

Exemplo válido:

- Scheduler Pro `1.0.2`;
- ARGWS Visual Builder `2.4.1`.

Após uma execução bem-sucedida do workflow `Release`, o workflow `ARGWS Visual Builder Package` valida e publica separadamente:

- pacote npm instalável;
- source archive;
- manifest próprio;
- checksums SHA-256;
- artifact separado no GitHub Actions;
- assets anexados à mesma GitHub Release do Scheduler Pro.

## Android e iOS

APK e IPA permanecem pausados até existir uma experiência mobile apta para homologação real. A alteração de versionamento não reativa os jobs nativos.
