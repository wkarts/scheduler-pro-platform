# Scheduler Pro — runtime Tauri/Rust

## Decisão canônica

- `apps/desktop`: aplicação gerencial desktop baseada no template Tauri/Rust.
- `apps/mobile`: aplicação gerencial mobile baseada no mesmo template Tauri/Rust.
- `apps/web`: WebApp PWA instalável pelo navegador, independente de Tauri/Rust.

## Template adotado

O template de referência é `template-app-tauri-desktop-main`, com Tauri 2, Rust, Vue 3, TypeScript, Pinia, Vue Router, splash/startup, providers por runtime e preparação Android/iOS.

## Desativado agora

- Licenciamento.
- Telemetria.
- Headless local.
- Webhook/WebSocket local.
- Serviço Windows/Linux.

Esses pontos ficam documentados e desativados até haver implementação real no Scheduler Pro.

## Próximos artefatos

- Desktop: `npm --workspace apps/desktop run tauri:build`.
- Android init: `npm --workspace apps/mobile run tauri:android:init`.
- APK debug: `npm --workspace apps/mobile run tauri:android:apk`.
- AAB: `npm --workspace apps/mobile run tauri:android:aab`.
