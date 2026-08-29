# ARGWS Visual Builder 2.4.0 — padrão mestre para IA construir templates

Este documento é o padrão a entregar a qualquer IA para criar uma experiência compatível com o ARGWS Visual Builder 2.4.0 e, quando hospedada no Scheduler Pro, com o Scheduler Pro Experience Contract v2.

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

---

# Referência complementar — SDK e construção

# Padrão de construção de templates — AVB 2.4.0

Este documento é o contrato técnico resumido para desenvolvimento manual ou por IA.

## Regra de ouro

O template controla a experiência visual. O host controla autenticação, regras de negócio, dados sensíveis e integrações.

## Estrutura obrigatória

```text
experience.json
bindings.json
theme.json
pages/landing.html
pages/booking.html
assets/
```

Não criar `login.html`.

## HTML

Pode utilizar HTML5, CSS moderno, JavaScript seguro, SVG, Canvas, Web Components, Lottie e animações. Não há obrigação de usar componentes genéricos do AVB.

## Bindings

Tudo que o cliente poderá editar sem alterar estrutura deve ser declarado em `bindings.json` e marcado com `data-sp-bind`, `data-sp-show` ou `data-sp-list`.

## Agenda

A página Booking deve usar `ARGWSRuntime.booking.*`. Nunca codificar endpoints internos do Scheduler Pro.

## Assets

Imagens grandes devem ficar em `assets/`. Evitar Base64 para imagens pesadas.

## Analytics

Eventos devem usar `ARGWSRuntime.analytics.track()`. Pixel/GA/GTM são responsabilidade do host.

## Segurança

Nunca incluir senha, token, secret, credencial, `eval`, `new Function`, script ofuscado ou autenticação paralela.

## Compatibilidade

O visual final deve funcionar sem etapa de build obrigatória. Caso Astro/Svelte/Vue/React sejam usados na autoria, entregar apenas o output compilado final.


# Checklist adicional de homologação

Antes de entregar um template para produção, a IA/desenvolvedor deve confirmar:

- [ ] `experience.json` usa `argws-experience-package/v2`.
- [ ] Não existe `login.html`.
- [ ] Landing degrada com elegância quando a SDK não está disponível.
- [ ] Agenda utiliza `ARGWSRuntime.booking.*`.
- [ ] Nenhuma URL interna `/api/v1/...` está hardcoded no template.
- [ ] Todos os itens editáveis estão declarados em `bindings.json`.
- [ ] `theme.json` contém tokens de cores e tipografia.
- [ ] Imagens grandes estão em `assets/`, não Base64.
- [ ] Layout funciona em 360px, 768px e desktop.
- [ ] Eventos de conversão usam `ARGWSRuntime.analytics.track()`.
- [ ] Não existem segredos, tokens ou credenciais.
- [ ] O design original não depende do editor para funcionar.
- [ ] O pacote pode ser importado sem etapa de compilação no runtime.

## Regra para novos clientes

A IA deve priorizar personalização por **bindings, theme tokens e assets**, preservando a estrutura HTML/CSS. Não transformar o template em widgets genéricos e não simplificar a direção visual para facilitar o editor.
