# Matriz de Capacidades 2.0

| Área | ARGWS Visual Builder 2.0 | Estratégia universal |
|---|---|---|
| Canvas visual | Sim | Web Component |
| Flex/Grid containers | Sim | AST próprio |
| Nested elements | Sim | filhos arbitrários |
| Responsive | Sim | breakpoints customizados + cascata |
| Hover/Focus/Active | Sim | estados por breakpoint |
| Design System | Sim | tokens, variables, classes |
| Global site parts | Sim | SiteKit |
| Templates / kits | Sim | Local library + Project Package |
| Dynamic content | Sim | bindings + Dynamic Tags |
| Query/Loop | Sim | Data Source Registry + Query Loop |
| Forms | Sim | schema universal + Actions/Services |
| Form multi-step | Sim | steps por campo |
| Submissions | Sim | Store memory/REST + CSV |
| Interactions | Sim | eventos → Action Registry |
| Custom attributes | Sim | whitelist segura |
| Popups / Offcanvas | Sim | overlay runtime |
| Mega menu | Sim | nested menu |
| Tabs / Accordion nested | Sim | structural widgets |
| Motion / Sticky | Sim | renderer/runtime |
| Custom fonts/assets | Sim | Asset Library |
| Custom CSS/HTML | Sim | sanitização |
| Custom JS | Controlado | trusted + host opt-in |
| SEO/Open Graph/JSON-LD | Sim | metadados do documento |
| Role Manager | Sim | capability policy |
| i18n | Sim | locale/translations no documento |
| Commerce | Sim, provider-driven | host components/services/data sources |
| CMS custom content | Sim, provider-driven | data sources + query loop |
| Email | Provider | Host Service |
| CAPTCHA | Provider | Host Service/widget plugin |
| Payment | Provider | Host Service/plugin |
| Image optimization | Provider | upload/media service |
| Analytics | Provider | plugin/service/custom code controlado |
| Collaboration | Foundation | operations + revision; transporte/sync fica no host |
| WordPress/WooCommerce internals | Não necessário | equivalentes genéricos |

“Provider” significa que o builder define o contrato e o projeto injeta a implementação real; isso evita secrets no frontend e mantém o core portátil.
