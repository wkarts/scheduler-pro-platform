# Branding, assets e PWA — Scheduler Pro + AVB 2.4.0

## Onde alterar a identidade

O tenant possui área própria de Identidade Visual no módulo de experiência. O Control Plane também pode gerenciar a identidade do tenant mesmo quando o Visual Builder estiver bloqueado para o cliente.

Uploads suportados na experiência:
- Logo claro;
- Logo escuro;
- Ícone PWA;
- Favicon;
- Fundo do Login nativo.

Também são configuráveis cores, tipografia e política de aplicação do tema ao Tenant Console.

## Identidade padrão

Quando o tenant não possui branding próprio, o Scheduler Pro usa a nova identidade oficial fornecida nesta rodada. Ela alimenta Login nativo, favicon, ícones PWA, manifest e fallback de marca.

## Base64 legado

Não é necessário reconstruir manualmente os templates antigos. O migrador v1 → Experience Contract v2:
1. lê o HTML existente;
2. detecta imagens Base64 grandes;
3. decodifica e calcula SHA-256;
4. deduplica;
5. cria assets físicos na experiência;
6. reescreve as referências;
7. preserva o HTML/CSS/layout.

## Novos templates

Para novos modelos, prefira arquivos sob `assets/` em vez de Base64 grande. Não é obrigatório usar PNG:
- WebP/AVIF: fotos e imagens grandes;
- SVG: vetores e ícones;
- PNG: transparência/raster quando necessário;
- JPEG: fotografias quando apropriado.

O HTML continua sendo o runtime canônico.
