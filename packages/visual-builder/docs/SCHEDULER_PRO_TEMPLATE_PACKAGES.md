# Scheduler Pro Template Packages no AVB 2.3

## Contrato de entrada

```text
scheduler-pro-template-package/v1
```

Arquivos típicos:

```text
template.json
landing.html
agendamento.html
```

## Importação correta

A 2.3 usa `importSchedulerProTemplateFamily()` e importa **a família inteira**, não apenas uma superfície.

- `landing.html` → página LANDING;
- `agendamento.html` → página BOOKING.

Os HTMLs são preservados integralmente como documentos `mode=HTML`.

## Não existe mais HTML completo como widget

A 2.1/2.2 representava um HTML completo por um nó `html_surface`. Isso foi corrigido.

Na 2.3 uma página HTML tem árvore visual vazia e o HTML fica no payload do próprio documento:

```text
PageDocument.html.document
```

## Compatibilidade

O normalizador detecta automaticamente documentos legados com um único `html_surface` contendo `<!doctype html>` e os migra para o formato de página HTML de primeira classe.
