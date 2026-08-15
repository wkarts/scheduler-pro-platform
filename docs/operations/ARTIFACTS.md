# Artefatos e distribuição

O Scheduler Pro precisa produzir artefatos testáveis desde os primeiros incrementos, não apenas código-fonte.

## Artefatos gerados

O workflow `Distribution Artifacts` publica, a cada push em `main`, um pacote com:

- `scheduler-pro-web-<sha>.tar.gz`
- `scheduler-pro-admin-<sha>.tar.gz`
- `scheduler-pro-desktop-shell-<sha>.tar.gz`
- `scheduler-pro-mobile-shell-<sha>.tar.gz`
- `scheduler-pro-cloudpanel-<sha>.tar.gz`
- `scheduler-pro-dockge-<sha>.tar.gz`
- `distribution-manifest.json`
- `SHA256SUMS.txt`

Esses artefatos são para teste rápido de entrega, validação de PWA, validação de proxy e smoke de distribuição.

## Artefatos nativos

Os workflows `Desktop Artifacts` e `Mobile Artifacts` são responsáveis pelos builds nativos:

- Windows
- Linux
- macOS
- Android unsigned
- iOS futuro via runner macOS/Xcode

Assinatura Android/iOS/Desktop é uma etapa independente e nunca deve usar certificados commitados.

## Build Manager

A API expõe `/api/v1/platform/builds/*` para registrar perfis, solicitações, jobs, logs e artefatos. O Build Manager é a fonte de verdade da plataforma; GitHub Actions é o executor inicial de CI/CD.

## Script local

```bash
bash scripts/build/package-distribution.sh local
```

O script gera os mesmos pacotes básicos em `artifacts/`.
