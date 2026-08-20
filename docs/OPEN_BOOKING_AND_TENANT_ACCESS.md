# Agenda pública, reaproveitamento de horário e acesso do tenant

Esta evolução mantém a Agenda como núcleo do Scheduler Pro e adiciona:

- liberação imediata do horário quando o agendamento deixa de ocupar agenda;
- conflito por profissional e intervalo, permitindo profissionais diferentes no mesmo horário;
- agenda pública do tenant em `/agendar`, sem exigir Landing Page;
- disponibilidade pública baseada no mesmo motor de expediente, bloqueios e conflitos da agenda interna;
- confirmação posterior por WhatsApp/e-mail usando o fluxo existente;
- personalização de mensagens WhatsApp e corpo/assunto de e-mail;
- reenvio administrativo dos dados de acesso em **Gerenciar tenant → Acesso**;
- opção de gerar nova senha temporária com revogação das sessões anteriores;
- auditoria `tenant_access_credentials_resent` sem persistir senha;
- diagnóstico do tenant com uma única rolagem e carregamento progressivo;
- atualização dos dados ao navegar entre módulos;
- atualização imediata da PWA quando uma nova versão do Service Worker assume.

A senha atual do usuário nunca é recuperada. O Control Plane pode definir uma nova senha ou gerar uma senha temporária; se nenhuma senha for redefinida, o e-mail informa que a senha atual permanece a mesma.
