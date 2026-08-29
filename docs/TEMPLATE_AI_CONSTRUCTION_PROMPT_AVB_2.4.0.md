# Prompt mestre — construir template compatível com ARGWS Visual Builder 2.4.0

Use este documento como instrução para qualquer IA que for criar um novo template.

---

Construa uma experiência visual profissional e completa compatível com **ARGWS Visual Builder 2.4.0**, **Experience Contract v2**, **Template Runtime SDK v1**, **Bindings v1** e **Theme Tokens v1**.

## Regra máxima

Não simplifique o design para caber no editor. Preserve alta qualidade visual, responsividade, animações, tipografia e identidade. O editor trabalha a favor do HTML; ele não deve reconstruir a página em widgets genéricos.

## Entrega obrigatória

Crie um ZIP contendo exatamente a estrutura base:

```text
experience.json
bindings.json
theme.json
pages/landing.html
pages/booking.html
assets/...
```

## LANDING

- HTML completo e autônomo.
- Responsivo mobile/tablet/desktop.
- Pode usar CSS moderno, SVG, Lottie, Canvas, Web Components e JavaScript seguro.
- CTA de agendamento deve usar `ARGWSRuntime.navigation.openBooking()` ou link `/agendar` com `data-sp-action="booking"`.
- Elementos editáveis devem usar `data-sp-bind`.
- Seções condicionais devem usar `data-sp-show`.
- Não codifique endpoints internos da aplicação.

## AGENDA PÚBLICA

- HTML completo e visualmente coerente com a Landing.
- Não implemente um motor paralelo de agenda.
- Serviços: `ARGWSRuntime.booking.catalog()`.
- Horários: `ARGWSRuntime.booking.availability()`.
- Criação: `ARGWSRuntime.booking.create()`.
- A página deve funcionar mesmo se o backend mudar seus endpoints internos.
- Deve existir caminho claro de volta para `/pagina`.

## LOGIN

Não criar `login.html`. O Login é nativo/white-label do host e usa Theme Tokens/Branding.

## Assets

- Coloque imagens, logos, fontes locais permitidas, SVGs e ícones em `assets/`.
- Evite Base64 para imagens grandes.
- Prefira WebP/AVIF/SVG quando apropriado.
- Nunca dependa de caminhos absolutos específicos de um servidor do desenvolvedor.

## Bindings

Declare em `bindings.json` todos os campos que um usuário poderá editar sem destruir o design, por exemplo:

- business.name
- business.logo
- hero.title
- hero.subtitle
- hero.image
- contact.phone
- contact.whatsapp
- contact.instagram
- cta.label
- show_services
- show_booking

## Theme Tokens

Defina em `theme.json`:

- primary
- secondary
- accent
- background
- surface
- text
- muted
- heading font
- body font
- border radius
- spacing
- branding metadata

## Segurança

- Não armazenar tokens, senhas ou segredos no template.
- Não criar autenticação paralela.
- Não acessar diretamente storage interno do host.
- Não incluir trackers arbitrários; analytics devem usar `ARGWSRuntime.analytics.track()`.
- Não usar `eval`, `new Function` ou código ofuscado.

## Qualidade

O resultado deve ser visualmente final, não mockup. Deve preservar o padrão de qualidade de uma landing premium criada manualmente em HTML/CSS/JS.

Antes de entregar, valide:

1. experience.json segue `argws-experience-package/v2`.
2. Landing e Booking existem.
3. Não existe login.html.
4. Todos os bindings usados no HTML aparecem em bindings.json.
5. Todas as imagens grandes estão em assets/.
6. Agenda usa Runtime SDK.
7. Layout é responsivo.
8. Não há endpoints internos hardcoded.
9. Não há segredos.
10. O ZIP pode ser importado diretamente no ARGWS Visual Builder 2.4.0.
