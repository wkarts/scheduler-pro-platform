# Descoberta automática da zone

Quando o Zone ID configurado é inválido ou não pertence ao hostname da plataforma, o backend tenta
as zonas ancestrais do `CLOUDFLARE_CUSTOM_HOSTNAME_ORIGIN` até localizar uma zone ativa acessível ao
token. O resultado é mantido em memória durante a vida do serviço e reutilizado nas chamadas DNS,
Custom Hostnames e purge.
