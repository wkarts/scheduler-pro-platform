# Artefatos e distribuição

O Scheduler Pro segue uma estratégia **PWA-first**. A distribuição web é a superfície principal e os únicos artefatos nativos ativos são Android/APK e iOS/IPA.

## Artefatos gerados

O workflow `Distribution Artifacts` publica pacotes para validação e deploy das superfícies ativas:

- `scheduler-pro-web-<sha>.tar.gz`;
- `scheduler-pro-admin-<sha>.tar.gz`;
- artefatos de UI mobile cliente/admin quando previstos pelo fluxo;
- `scheduler-pro-cloudpanel-<sha>.tar.gz`;
- `scheduler-pro-dockge-<sha>.tar.gz`;
- `distribution-manifest.json`;
- `SHA256SUMS.txt`.

Esses artefatos servem para validação de PWA, proxy, deploy e smoke de distribuição.

## Artefatos nativos ativos

O workflow `Mobile Artifacts` é responsável por:

- Android APK;
- iOS IPA.

O runner `macos` permanece necessário para compilar iOS/IPA; isso **não representa uma release desktop para macOS**.

## Desktop legado

Windows, Linux e macOS desktop não fazem parte do pipeline ativo. O código fonte foi preservado para uma eventual retomada futura e o workflow antigo está arquivado em:

```text
docs/legacy-workflows/desktop-artifacts.yml.disabled
```

Nenhuma release atual deve publicar MSI, NSIS, DEB, RPM ou DMG.

## Build Manager

A API expõe `/api/v1/platform/builds/*` para registrar perfis, solicitações, jobs, logs e artefatos. Os targets ativos de build nativo são mobile; targets desktop legados são rejeitados pela API até reativação explícita.

## Script local

```bash
bash scripts/build/package-distribution.sh local
```
