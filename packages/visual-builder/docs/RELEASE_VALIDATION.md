# Release Validation — ARGWS Visual Builder Universal 2.3.2

## Escopo da patch

A 2.3.2 altera somente seleção de logo por tema e versionamento. Toda a base 2.3.1 permanece compatível.

## Validações obrigatórias

- `npm run check`;
- `npm test`;
- Light Mode referencia a logo padrão existente;
- Dark Mode referencia exclusivamente o asset dark fornecido;
- o Editor atualiza o wordmark quando o tema muda sem remontar o documento;
- o Project/Site Workspace usa a mesma regra de seleção;
- o único asset com nomenclatura `dark` adicionado ao branding é a logo fornecida;
- favicon/símbolos/ícones não ganham variantes dark;
- `npm pack`;
- instalação limpa do TGZ;
- importação do pacote pelo nome `@argws/visual-builder`;
- instalador Scheduler Pro continua lendo `PACKAGE_VERSION` do `package.json`.

## Compatibilidade

Não há migração de projeto ou documento entre 2.3.1 e 2.3.2. A alteração é de apresentação da marca do produto e não afeta a página editada.

## Resultado desta build

- `npm run check`: **OK**;
- `npm test`: **65/65 OK**;
- SHA-256 do asset dark fornecido e do arquivo empacotado: `ca95f1addc924bbe7946bd36b94ed901d5916b74bde5f293786c832c327bc709` — **idênticos**.

- instalação limpa do TGZ: **OK** (`@argws/visual-builder@2.3.2`);
- API pública `AVB_BRAND_ASSETS` / `resolveAvbBrandLogo()`: **OK**;
- instalador Scheduler Pro executado duas vezes em fixture: **OK**; dependência e workspace permaneceram em `2.3.2`;
- asset dark copiado para o workspace do host: **OK**.
