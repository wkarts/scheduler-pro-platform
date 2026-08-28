# Performance

- renderer síncrono para páginas sem Data Sources;
- `renderDocumentAsync` somente quando queries precisam ser resolvidas;
- QueryCache evita consultas repetidas no runtime;
- imagens usam lazy loading por padrão, exceto quando o host decide priorizar LCP;
- CSS é gerado por documento e estados/breakpoints necessários;
- Web Components evitam carregar um framework de UI no renderer público;
- plugins podem ser carregados sob demanda;
- Data Sources devem paginar/limitar respostas e evitar transportar datasets grandes ao browser;
- para sites públicos de alto tráfego, o host pode pré-renderizar `renderDocument`/`exportStandaloneHtml` em build/cache/CDN.

A 2.0 não impõe backend, Redis, CDN ou estratégia de cache; isso permanece responsabilidade do projeto integrador.
