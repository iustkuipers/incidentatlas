# Incidentatlas - wekelijkse brief.
# Draait Claude Code headless met WEEKBRIEF.md als opdracht, schrijft de uitvoer naar
# logs\weekbrief-JJJJ-MM-DD.json en controleert daarna de nieuwe rijen in voorstellen.csv en
# runs.csv. Foute rijen gaan naar logs\afgekeurd-JJJJ-MM-DD.csv, bestaande rijen en de andere
# bestanden worden zo nodig teruggezet (zie scripts\controleer_weekbrief.py).

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

$datum   = Get-Date -Format "yyyy-MM-dd"
$logDir  = Join-Path $PSScriptRoot "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$jsonLog = Join-Path $logDir "weekbrief-$datum.json"
$txtLog  = Join-Path $logDir "weekbrief-$datum.log"
$backup  = Join-Path $logDir "backup-$datum"

function Log($msg) {
    $line = "{0}  {1}" -f (Get-Date -Format "HH:mm:ss"), $msg
    Write-Output $line
    Add-Content -LiteralPath $txtLog -Value $line -Encoding UTF8
}

try { [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false) } catch {}
$env:PYTHONIOENCODING = "utf-8"

# --- claude vinden: eerst op PATH, anders de nieuwste uit de VS Code-extensie
$claude = (Get-Command claude -ErrorAction SilentlyContinue).Source
if (-not $claude) {
    $claude = Get-ChildItem "$env:USERPROFILE\.vscode\extensions\anthropic.claude-code-*\resources\native-binary\claude.exe" -ErrorAction SilentlyContinue |
        Sort-Object { [version](($_.FullName -replace '.*anthropic\.claude-code-([\d.]+).*', '$1')) } |
        Select-Object -Last 1 -ExpandProperty FullName
}
if (-not $claude) { Log "FOUT: claude niet gevonden."; exit 2 }
Log "Start weekbrief met $claude"

# --- vorige versie van data\ bewaren
New-Item -ItemType Directory -Force -Path $backup | Out-Null
Copy-Item -Path "data\*.csv" -Destination $backup -Force

# --- opdracht: inhoud van WEEKBRIEF.md. PowerShell 5.1 escapet aanhalingstekens niet
# bij het doorgeven aan een exe, dus dat doen we zelf (anders wordt de tekst afgekapt).
$prompt = Get-Content -LiteralPath "WEEKBRIEF.md" -Raw -Encoding UTF8
$prompt = $prompt -replace '(\\*)"', '$1$1\"'

$claudeArgs = @(
    "-p", $prompt,
    "--allowedTools", "Read", "Glob", "Grep", "WebSearch", "WebFetch",
                      "Edit(./data/voorstellen.csv)", "Edit(./data/runs.csv)",
    "--disallowedTools", "Bash", "Write", "Edit(./data/incidenten.csv)", "Edit(./data/wijzigingen.csv)",
    "--permission-prompts", "none",
    "--max-budget-usd", "3",
    "--output-format", "json"
)

$ErrorActionPreference = "Continue"
$all = & $claude @claudeArgs 2>&1
$code = $LASTEXITCODE
$ErrorActionPreference = "Stop"
$stdout = $all | Where-Object { $_ -isnot [System.Management.Automation.ErrorRecord] } | ForEach-Object { "$_" }
$all | Where-Object { $_ -is [System.Management.Automation.ErrorRecord] } | ForEach-Object { Log "stderr: $_" }
[System.IO.File]::WriteAllText($jsonLog, ($stdout -join "`n"), [System.Text.UTF8Encoding]::new($false))
Log "claude klaar, exitcode $code, uitvoer in $jsonLog"

# --- controle: alleen rijen toegevoegd, alles te_beoordelen
$ErrorActionPreference = "Continue"
$afgekeurd = Join-Path $logDir "afgekeurd-$datum.csv"
$check = & python -I -X utf8 "scripts\controleer_weekbrief.py" --backup $backup --log $jsonLog --afgekeurd $afgekeurd 2>&1 | ForEach-Object { "$_" }
$checkCode = $LASTEXITCODE
$ErrorActionPreference = "Stop"
$check | ForEach-Object { Log $_ }

if ($checkCode -ne 0) { Log "Controle heeft rijen afgekeurd of bestanden teruggezet; zie 'controle' in $jsonLog"; exit 1 }
if ($code -ne 0) { exit $code }
Log "Weekbrief klaar."
exit 0
