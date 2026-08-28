# Referência de Paridade Funcional — 2.0

O objetivo do ARGWS Visual Builder não é copiar código ou dependências do Elementor. A referência é a **classe de recursos** esperada de um builder profissional.

A 2.0 cobre editor visual, containers/nested elements, responsive/design system, templates/site parts, dynamic data/query loop, forms/actions, popups/offcanvas, mega menu, custom assets/code, role capabilities e widgets de marketing/site.

Recursos historicamente ligados a WordPress/WooCommerce foram convertidos em contratos universais:

- posts/custom queries → Data Sources + Query Loop;
- WooCommerce → Commerce Provider + Host Components/Services;
- submissions/email → Form Actions + Host Services;
- role manager → Capability Policy;
- Theme Builder → SiteKit;
- custom code → Custom Code controlado;
- fonts/icons → Asset Library;
- plugins/add-ons → Plugin SDK.

Consulte `CAPABILITY_MATRIX_2.0.md` para a matriz detalhada.
