# Integração por Stack

## HTML puro

Use `<argws-page-renderer>` e atribua `element.document`. Para editar, use `<argws-visual-builder>` com `RestAdapter` ou `MemoryAdapter`.

## PHP puro

O frontend é idêntico ao HTML. PHP fornece endpoints JSON para load/draft/autosave/publish. Veja `examples/php/index.php`.

## Laravel / Blade

- publique/copiei o pacote para assets ou use Vite/NPM;
- exponha endpoints autenticados;
- o Blade monta o Web Component;
- persista JSON em PostgreSQL/MySQL/S3 ou no storage escolhido;
- valide tenant e permissões no backend.

Veja `examples/laravel/` e `examples/blade/`.

## Python / FastAPI

O frontend continua independente. FastAPI expõe os contratos REST e pode servir os ES Modules. Para páginas server-side, Jinja2 apenas hospeda `<argws-page-renderer>`.

Veja `examples/python-fastapi/` e `examples/jinja2/`.

## Vue

Importe o pacote uma única vez e use o Web Component. O documento pode vir de Pinia/API ou do adapter do próprio builder. Veja `examples/vue/VisualBuilderHost.vue`.

## React / Svelte

Web Components evitam adapter específico de framework. Os exemplos atribuem a propriedade DOM `document` após carregar a API.

## Node/Express

Pode servir o bundle e os endpoints REST. Veja `examples/node-express/server.mjs`.

## Twig / Symfony

Use o template de `examples/twig/` e os mesmos endpoints REST.

## Outras stacks

Java/Spring, ASP.NET, Rails, Go, Delphi WebView/Tauri etc. precisam apenas de:

1. servir o JS/CSS;
2. fornecer o documento JSON;
3. opcionalmente fornecer draft/autosave/publish/upload;
4. registrar data sources/services no frontend ou em um BFF seguro.
