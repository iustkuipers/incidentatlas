# Incidentatlas - nieuws ophalen naar data\inbox.csv (elk uur via Taakplanner).
# Draait scripts\nos_ophalen.py; het resultaat staat in logs\ophalen.log.
# Stopte de wekelijkse run eerder door de gebruikslimiet van het abonnement (logs\vervolg.flag),
# dan start dit script na minstens 5 uur het vervolg met de resterende stappen.
Set-Location -LiteralPath $PSScriptRoot
New-Item -ItemType Directory -Force -Path "logs" | Out-Null
$env:PYTHONIOENCODING = "utf-8"
$ErrorActionPreference = "Continue"
$out = & python -I -X utf8 "scripts\nos_ophalen.py" 2>&1 | ForEach-Object { "$_" }
$code = $LASTEXITCODE
if ($code -ne 0) {
    Add-Content -LiteralPath "logs\ophalen.log" -Encoding UTF8 -Value ("{0}  FOUT (exitcode {1}): {2}" -f (Get-Date -Format s), $code, ($out -join " | "))
}
$flag = "logs\vervolg.flag"
if ((Test-Path $flag) -and -not (Test-Path "logs\brief.lock") -and ((Get-Date) - (Get-Item $flag).LastWriteTime).TotalHours -ge 5) {
    $stappen = (Get-Content $flag -Raw).Trim()
    Add-Content -LiteralPath "logs\ophalen.log" -Encoding UTF8 -Value ("{0}  vervolg van de weekrun gestart: {1}" -f (Get-Date -Format s), $stappen)
    & powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "run_weekbrief.ps1") -Stappen $stappen
}
exit $code
