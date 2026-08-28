# Identidade visual — ARGWS Visual Builder Universal 2.3.2

A release 2.3.2 preserva o alinhamento do Design System do produto à identidade oficial AVB sem alterar o modelo de documento, adapters, renderer ou integrações.

## Assets

- `argws-visual-builder-symbol-64.png`: toolbar/editor.
- `argws-visual-builder-symbol-128.png`: superfícies HiDPI.
- `argws-visual-builder-symbol-192.png`: PWA/atalhos.
- `argws-visual-builder-symbol-512.png`: splash/branding.
- `argws-visual-builder-logo-640.png`: documentação/telas compactas.
- `argws-visual-builder-logo-1024.png`: telas institucionais.
- `argws-visual-builder-logo-1600.png`: logo oficial padrão para Light Mode e material de alta resolução.
- `argws-visual-builder-logo-dark.png`: **asset dark oficial fornecido**, usado exclusivamente quando o tema do produto está em Dark Mode; não é aplicado a ícones ou favicon.

## Tipografia

- Headings e títulos do **produto AVB**: `Space Grotesk`, com fallback para `Inter` e fontes do sistema.
- Interface, formulários e corpo do **produto AVB**: `Inter`.
- O conteúdo da página editada **não herda** automaticamente estas fontes. Cada projeto/documento mantém seu próprio Design System.

O pacote não embute arquivos de fonte nem depende obrigatoriamente de CDN. O host pode fornecer `Space Grotesk` se desejar fidelidade tipográfica total; caso contrário o fallback mantém a interface legível.

## Seleção por tema

- `light` → `argws-visual-builder-logo-1600.png`
- `dark` → `argws-visual-builder-logo-dark.png`

O arquivo dark é distribuído sem redesenho, recoloração ou geração automática de variantes. O símbolo/ícones existentes permanecem os mesmos nos dois temas.
