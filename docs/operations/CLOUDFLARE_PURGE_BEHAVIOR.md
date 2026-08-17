# Purge de cache Cloudflare

O purge por hostname é uma operação independente de DNS. Um token pode conseguir ler/criar DNS e
ainda assim não possuir `Cache Purge`. Nesse caso o Scheduler PRO mantém o domínio ativo e retorna
o erro específico `CLOUDFLARE_CACHE_PURGE_PERMISSION_ERROR` apenas para o purge.
