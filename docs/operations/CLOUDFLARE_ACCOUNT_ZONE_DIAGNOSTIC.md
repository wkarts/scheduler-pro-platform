# Diagnóstico Account ID x Zone ID

Sintoma típico: `/user/tokens/verify` retorna token ativo, mas chamadas em `/zones/{id}` retornam
401/403 ou erro 10000. Isso pode acontecer quando o valor usado em `{id}` é o Account ID em vez do
Zone ID. A resolução automática adicionada nesta versão corrige esse caso sem tratar o token válido
como inválido.
