# Experience Contract v2

Schema: `argws-experience-package/v2`

Estrutura recomendada:

```text
my-experience/
├── experience.json
├── bindings.json
├── theme.json
├── pages/
│   ├── landing.html
│   └── booking.html
└── assets/
    ├── logo.webp
    ├── hero.webp
    ├── favicon.png
    └── ...
```

## experience.json

```json
{
  "schema": "argws-experience-package/v2",
  "version": 2,
  "package": {
    "key": "studio-beatriz",
    "name": "Studio Beatriz Nails",
    "package_version": "1.0.0",
    "authoring_mode": "runtime-html",
    "capabilities": ["booking", "branding", "analytics"]
  },
  "pages": {
    "landing": {"entry": "pages/landing.html", "route": "/pagina", "surface": "LANDING"},
    "booking": {"entry": "pages/booking.html", "route": "/agendar", "surface": "BOOKING"}
  },
  "files": {"bindings": "bindings.json", "theme": "theme.json"}
}
```

## Regras

1. O pacote não deve conter Login próprio quando o host declara Login nativo.
2. HTML/CSS/JS podem ser sofisticados e futuristas.
3. O contrato não impõe layout.
4. Assets devem preferencialmente ficar em `assets/`, não em Base64 gigante.
5. A aplicação edita somente bindings declarados.
6. Lógica de negócio é chamada pelo Runtime SDK, nunca duplicada no template.
