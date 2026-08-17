# ACME Cloudflare

No `dns_cf` do acme.sh, `CF_Zone_ID` é opcional. A stack utiliza `CF_Token` e descoberta da zone para
não propagar um identificador incorreto para a renovação de certificados.
