# Scheduler Pro — PWA First + ARGWS Visual Builder 2.3.0

## Direção canônica

- PWA é a experiência principal.
- Builds nativos ativos: Android/APK e iOS/IPA.
- Código desktop permanece no monorepo para retomada futura, porém não participa de release nem checks ativos.
- ARGWS Visual Builder 2.3.0 é a versão canônica.
- Identidade visual do ARGWS Visual Builder fornecida pelo pacote 2.3.0 foi preservada.

## Arquitetura de páginas

`TEMPLATE = PÁGINA COMPLETA`, nunca componente.

Cada família Scheduler Pro contém duas páginas independentes:

- LANDING — `/pagina`: apresentação, marca, serviços, prova social e CTA.
- BOOKING — `/agendar`: serviço, profissional/recurso, disponibilidade, formulário e confirmação.

Os componentes pertencem às páginas. Aplicar uma família troca os rascunhos das duas superfícies de forma explícita, sem publicar automaticamente e sem transformar uma superfície na outra.

## Navegação

O menu canônico agora é controlado pelo hash/rota. Os antigos bridges/coordenadores DOM deixam de ser instalados. Uma rota ativa possui uma única superfície de conteúdo ativa.

## Scroll

A rolagem continua funcional em documento, menus, modais, tabelas e seletores, com barras discretas e `scrollbar-gutter` para evitar deslocamento de layout.

## ARGWS Visual Builder

TGZ 2.3.0 SHA-256: `d5e63c4a004550c636ddea9dcdf70d1fb0c76d2339bad4b0d4b54f73114472fe`

## Modelos oficiais

```json
{
  "barber-shop-neo-generico": {
    "bytes": 3566086,
    "sha256": "ce6764985a97e3f08f7d766e077ddfd2ccf38a94dbef0c8b6aa6396d81474125"
  },
  "clinica-medica-generico": {
    "bytes": 3466294,
    "sha256": "a8e639cd731fc1fc4e07a19350a679198d87be565e31d77c30337c3f11629d71"
  },
  "clinica-odontologica-generico": {
    "bytes": 2610897,
    "sha256": "ae5dd30355ebf9ac27b5e0ad1088a6037fb71bea75819b5610608a19ed062373"
  },
  "clinica-veterinaria-generico": {
    "bytes": 3582655,
    "sha256": "e363d5a24caf5939352423a604876adc744e3a86cea9f806d85863ffb74afac4"
  },
  "martelinho-de-ouro-generico": {
    "bytes": 331865,
    "sha256": "ce6a31b0a64eff282889327246d3393446b7b369cfad8e6cd3726c7473cc0bb5"
  },
  "studio-unhas-generico": {
    "bytes": 103499,
    "sha256": "b5c076fc9adb604cd321871eabd221593269cda6fe70fe165b4c58d60497c40d"
  },
  "tecnologia-generico-simples": {
    "bytes": 4409890,
    "sha256": "85c32f37db6bcd211eede7c8fa038a1f0fd67d8f02db5426a28d608f853d2444"
  }
}
```
