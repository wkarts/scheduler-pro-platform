# Contrato de instalação PWA

- O PWA pertence à WebApp do tenant e não ao pacote nativo.
- A instalação deve estar disponível antes do login, após o login e na área **Aplicativos**.
- Chrome/Edge em Android e Desktop usam `beforeinstallprompt` quando disponível.
- iOS/iPadOS usa o fluxo manual do Safari: **Compartilhar → Adicionar à Tela de Início**.
- Quando `display-mode: standalone` estiver ativo, a UI deve indicar que o PWA já está instalado e não oferecer outro botão de instalação.
- O PWA continua usando `manifest.webmanifest` e `sw.js` do próprio hostname do tenant.
