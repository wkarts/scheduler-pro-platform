# Extensões

## Widget

```js
registerWidget('my_widget', {
  label: 'Meu widget',
  group: 'Meu projeto',
  icon: '◇',
  acceptsChildren: false,
  defaults: { title: 'Título' },
  fields: [
    { key: 'title', label: 'Título', control: 'text', default: 'Título' }
  ]
});
```

Controles suportados pelo inspector base:

```text
text
textarea
number
select
toggle
```

Um projeto pode ampliar o editor para novos controles sem alterar o documento canônico.

## Renderer

```js
registerRenderer('my_widget', ({ props, wrap, escapeHtml, safeUrl, context }) => {
  return wrap(`<h2>${escapeHtml(props.title)}</h2>`);
});
```

O renderer recebe:

```text
document
node
props
device
context
wrap()
escapeHtml()
safeUrl()
renderChildren()
```

## Dados dinâmicos

Não grave segredos ou tokens no documento. Para dados dinâmicos, o host deve passar valores pelo `context` do renderer ou montar componentes do sistema sobre os placeholders de integração.

O Scheduler Pro usa esse padrão para manter o `PublicBookingWidget` responsável pela agenda real.
