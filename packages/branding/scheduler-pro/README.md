# Scheduler PRO — Identidade Visual Canônica

Versão oficial de marca: **1.0.0**.

## Conceito

A identidade combina calendário, relógio e confirmação para representar disponibilidade, compromisso e conclusão do agendamento.

## Arquivos canônicos

- `brand-symbol.svg` — ícone oficial para aplicativos e geração Tauri.
- `brand-symbol-mono.svg` — versão monocromática.
- `brand-logo-horizontal.svg` — assinatura para fundos claros.
- `brand-logo-light.svg` — assinatura para fundos escuros.
- `favicon.svg` — favicon simplificado.
- `maskable.svg` — ícone PWA maskable.
- `splash.svg` — splash oficial.
- `brand-tokens.json` — tokens de cor, tipografia e forma.

## Paleta

- Deep Navy `#0B132B`
- Midnight Blue `#0F1E3A`
- Azure Blue `#118AF5`
- Electric Cyan `#00E5FF`
- Teal `#00C2B8`
- Silver Gray `#E6E9EF`
- White `#FFFFFF`

Gradiente de destaque: `#118AF5 → #00E5FF → #00C2B8`.

## Tipografia

- Display: `Inter Display, Inter, Segoe UI, Arial, sans-serif`
- Corpo: `Inter, Segoe UI, Arial, sans-serif`

## Aplicação no produto

A marca canônica é o fallback da plataforma. Tenants continuam podendo personalizar nome, logo e cores. Customizações existentes não devem ser sobrescritas. Desktop cliente/admin usam WebView remoto e herdam a UI Web/Admin; seus instaladores recebem o ícone oficial no build Tauri. Mobile cliente/admin usam a mesma família de assets em seus shells nativos.
