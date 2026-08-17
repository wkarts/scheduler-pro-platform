# Fluxos SSL

- Subdomínios temporários da plataforma usam wildcard Let's Encrypt via DNS-01 na zone da plataforma.
- Domínios próprios do cliente seguem o fluxo separado de Custom Hostnames/SSL quando disponível.

O backend não deve tratar um subdomínio temporário como Custom Hostname.
