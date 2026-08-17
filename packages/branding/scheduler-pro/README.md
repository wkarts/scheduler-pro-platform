# Scheduler Pro — Identidade Visual Canônica

A identidade padrão da plataforma utiliza o conceito **Time Flow**: um fluxo contínuo em forma de `S`, um ponto central de compromisso/agendamento e dois nós de entrada/saída que representam jornada, confirmação e continuidade.

## Arquivos canônicos

- `brand-symbol.svg` — símbolo principal, fundo escuro e gradiente azul/ciano.
- `brand-symbol-mono.svg` — versão monocromática.
- `brand-logo-horizontal.svg` — assinatura horizontal para fundos claros.
- `brand-logo-light.svg` — assinatura horizontal para fundos escuros.
- `favicon.svg` — favicon simplificado.
- `maskable.svg` — ícone PWA maskable.
- `splash.svg` — splash vertical 1080x1920.
- `brand-tokens.json` — cores, tipografia e tokens visuais.

## Diretrizes

1. O símbolo substitui o antigo quadrado textual `SP` como marca principal.
2. `Scheduler Pro` continua sendo a marca padrão da plataforma.
3. Control Plane pode usar o descritor `Administração da plataforma` ou `Control Plane`, sempre separado da marca principal.
4. Tenants podem substituir nome, logo, cores e assets por branding próprio; os arquivos desta pasta permanecem como fallback da plataforma.
5. Não esticar, inclinar ou alterar proporções do símbolo.
6. Preferir `brand-logo-light.svg` sobre fundos navy e `brand-logo-horizontal.svg` sobre superfícies claras.
7. Em ícones pequenos, usar apenas o símbolo/fav, nunca a assinatura horizontal.

## Paleta

- Navy 950 `#061327`
- Navy 900 `#081A33`
- Navy 800 `#0B1D3A`
- Blue 600 `#2F6BFF`
- Cyan 500 `#1DAAF5`
- Cyan 400 `#22D3EE`
- Violet 500 `#8B5CF6`
- Surface `#F4F7FB`

## Tipografia

Sistema: `Inter, Segoe UI, Arial, sans-serif`.

- Headings: 760
- UI: 600
- Texto: 450

## Tauri

Os builds nativos devem executar `tauri icon` usando `brand-symbol.svg` como fonte. O Tauri 2 aceita SVG quadrado com transparência e gera PNG, ICO, ICNS, Android e iOS conforme o target.
