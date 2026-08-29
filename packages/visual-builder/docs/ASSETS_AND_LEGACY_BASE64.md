# Assets e migração de Base64 — AVB 2.4.0

## Regra canônica para novos templates

Use arquivos físicos dentro de `assets/` e referências relativas no HTML/CSS.

Formatos recomendados:
- WebP/AVIF para fotografias e hero images;
- PNG quando transparência/raster for necessária;
- SVG para ícones e vetores confiáveis;
- JPEG quando apropriado.

Não existe obrigação de usar somente PNG.

## Templates antigos com Base64

Não precisam ser reconstruídos manualmente.

O adapter Scheduler Pro/Experience Contract v2 aceita pacotes v1 e, durante a migração:
1. detecta imagens Base64 relevantes;
2. calcula SHA-256 e deduplica;
3. extrai para `tenant_template_assets`/storage do tenant;
4. reescreve `src`, `href` e `url(...)` relativos;
5. preserva HTML, CSS e visual;
6. ignora `login.html`, porque Login é nativo/white-label no 2.4.0.

Base64 pequeno pode continuar inline. Base64 grande é tratado como legado e externalizado.

## Modelos oficiais e personalizados

A regra vale para ambos. Pacotes novos devem preferir `assets/`; pacotes v1 existentes continuam compatíveis pela migração.
