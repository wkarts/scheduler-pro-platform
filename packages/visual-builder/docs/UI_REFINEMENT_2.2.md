# Refinamento de UX — 2.2.0

## Problemas reproduzidos a partir das capturas

1. As guias do painel esquerdo desapareciam ao rolar Elementos/Modelos/Biblioteca.
2. As guias do Inspector direito eram comprimidas e desapareciam conforme o conteúdo crescia.
3. Configurações da página não dava feedback claro e podia parecer sem efeito.
4. Elementos/Propriedades da toolbar não tinham comportamento útil em desktop.
5. Auditar calculava o relatório, mas não mudava para o painel onde o resultado era exibido.
6. Desktop/Tablet/Mobile consumiam largura desnecessária com texto.
7. Em telas estreitas, ações à direita podiam sair da viewport, principalmente Fechar.
8. HTML grande importado de pacote Scheduler Pro ficava visualmente limitado a um iframe de 760 px.
9. Identidade visual ainda era genérica e não usava a marca AVB fornecida.

## Correções estruturais

### Sidebars

- `.tabs`: `flex: 0 0 40px` e `min-height: 40px`.
- `.inspector-head`: `flex: 0 0 auto`.
- `.panel-scroll`: `height: 0; flex: 1 1 auto; overflow: auto`.

Com isso, somente o conteúdo interno rola. Cabeçalho e guias permanecem visíveis.

### Toolbar

A toolbar foi dividida em três regiões:

- `topbar-start`: marca, página, tema, undo/redo;
- `topbar-center`: viewports e acesso a Elementos/Propriedades;
- `topbar-end`: ações de documento, publicação, recuperação e fechamento.

Todos os comandos visuais principais são icon-only e possuem `title` + `aria-label`.

Em viewport menor, Audit/Import/JSON/HTML/Preview/Save/Tema ficam disponíveis também no menu `…`. Publicar/Recuperação/Fechar permanecem fora do menu.

### Configurações da página

O comando agora:

- remove seleção de elemento;
- força `rightTab=content`;
- abre drawer direito quando necessário;
- reposiciona o painel no topo;
- recebe estado visual ativo.

### Elementos e Propriedades

- Elementos força a guia `elements`, abre drawer em telas pequenas e foca a busca.
- Propriedades força `content` do elemento selecionado; se não houver elemento, mostra página.

### Auditoria

Após executar:

- limpa seleção do elemento;
- muda para `advanced`;
- abre o Inspector direito em viewport pequena;
- posiciona o score de auditoria em área visível;
- exibe notice com o score.

### HTML Surface

No editor, o iframe usa somente:

```text
sandbox="allow-forms allow-same-origin"
```

Scripts continuam desabilitados. `allow-same-origin` existe apenas para o editor conseguir medir `scrollHeight` do `srcdoc`. O iframe é expandido dinamicamente até o conteúdo completo, com teto defensivo de 24.000 px.

No runtime publicado, o sandbox continua separado e não recebe `allow-same-origin` automaticamente.
