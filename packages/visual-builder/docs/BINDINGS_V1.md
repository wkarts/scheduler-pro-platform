# Bindings v1

Schema: `argws-bindings/v1`

Bindings tornam um HTML sofisticado editável sem reconstruí-lo.

## HTML

```html
<h1 data-sp-bind="hero.title">Título original</h1>
<img data-sp-bind="hero.image" src="assets/hero.webp">
<a data-sp-show="show_booking" href="/agendar">Agendar</a>
```

## bindings.json

```json
{
  "schema": "argws-bindings/v1",
  "version": 1,
  "bindings": {
    "hero.title": {"type": "text", "label": "Título principal", "group": "Hero"},
    "hero.image": {"type": "image", "label": "Imagem principal", "group": "Hero"},
    "show_booking": {"type": "boolean", "label": "Exibir agendamento", "group": "Seções"}
  }
}
```

Tipos canônicos: text, richtext, image, color, phone, url, boolean, section, list, number, select.
