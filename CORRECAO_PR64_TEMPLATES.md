# CORREÇÃO PR #64 — CATÁLOGO OFICIAL DE TEMPLATES

## Causa raiz

O projeto contém os 7 pacotes oficiais como arquivos ZIP reais em:

`apps/api/resources/template-packages/*.zip`

Porém `.gitignore` ignorava globalmente `*.zip`. Por isso o GitHub Desktop não incluiu os sete pacotes no commit inicial da PR #64. A tentativa posterior de substituir os ZIPs por uma release Base64 parcial gerou um arquivo truncado (63.634 caracteres / 47.725 bytes decodificados), cujo gzip falha CRC e cujo SHA-256 diverge do catálogo esperado.

## Correção desta entrega

- mantém os sete ZIPs oficiais reais;
- adiciona `!apps/api/resources/template-packages/*.zip` ao `.gitignore`;
- mantém a exceção equivalente no `.dockerignore`;
- `builtin_template_package_service.py` lê diretamente os ZIPs reais e valida cada pacote com `HtmlTemplatePackageService.ensure`;
- não usa `template-catalog/release-b64`;
- não usa `part-*.b64`;
- não usa `repair-*`;
- LANDING e BOOKING continuam páginas independentes;
- não sobrescreve automaticamente páginas existentes de tenants.

## Antes de commitar na PR #64

No checkout da branch `feat/avb-2-3-complete-pages-pwa-navigation`, copie o conteúdo desta entrega por cima do projeto e remova o diretório antigo, se ainda existir:

```text
apps/api/resources/template-catalog/
```

No GitHub Desktop confirme que aparecem como ADDED os sete arquivos em:

```text
apps/api/resources/template-packages/
```

Arquivos esperados:

1. barber-shop-neo-generico.zip
2. clinica-medica-generico.zip
3. clinica-odontologica-generico.zip
4. clinica-veterinaria-generico.zip
5. martelinho-de-ouro-generico.zip
6. studio-unhas-generico.zip
7. tecnologia-generico-simples.zip

Commit sugerido:

`fix(api): versionar os 7 templates oficiais reais e remover catálogo Base64 truncado`
