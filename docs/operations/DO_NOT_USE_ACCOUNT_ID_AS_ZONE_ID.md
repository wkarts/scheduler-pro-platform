# Cloudflare: Account ID não é Zone ID

`CLOUDFLARE_ZONE_ID` deve conter o identificador da zone DNS. O Account ID não deve ser usado nesse
campo. A aplicação agora valida esse vínculo e tenta resolver a zone correta automaticamente.
