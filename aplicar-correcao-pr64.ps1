param(
  [string]$Repo = "."
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path $Repo).Path
Write-Host "Aplicando saneamento da PR #64 em: $root"

$stale = Join-Path $root "apps\api\resources\template-catalog"
if (Test-Path $stale) {
  Remove-Item -Recurse -Force $stale
  Write-Host "Removido catálogo Base64 truncado: apps/api/resources/template-catalog"
}

$gitignore = Join-Path $root ".gitignore"
$content = Get-Content $gitignore -Raw
$exception = "!apps/api/resources/template-packages/*.zip"
if ($content -notmatch [regex]::Escape($exception)) {
  $content = $content -replace "\*\.zip\r?\n", "*.zip`r`n$exception`r`n"
  Set-Content -Path $gitignore -Value $content -Encoding utf8
}

$keys = @(
  "barber-shop-neo-generico",
  "clinica-medica-generico",
  "clinica-odontologica-generico",
  "clinica-veterinaria-generico",
  "martelinho-de-ouro-generico",
  "studio-unhas-generico",
  "tecnologia-generico-simples"
)

$packages = Join-Path $root "apps\api\resources\template-packages"
foreach ($key in $keys) {
  $zip = Join-Path $packages "$key.zip"
  if (-not (Test-Path $zip)) { throw "Pacote oficial ausente: $key.zip" }
}

Write-Host "OK: 7 ZIPs oficiais presentes e liberados pelo .gitignore."
Write-Host "Abra o GitHub Desktop e confirme que os 7 ZIPs aparecem como Added."
Write-Host "Commit sugerido: fix(api): versionar os 7 templates oficiais reais e remover catálogo Base64 truncado"
