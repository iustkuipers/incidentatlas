# Incidentatlas - wekelijkse brief.
# 1. Haalt de bronnen op naar logs\inbox-JJJJ-MM-DD.csv (scripts\haal_bronnen.py).
# 2. Draait Claude Code headless met Tasks\WEEKBRIEF.md als opdracht; de stream gaat naar
#    logs\weekbrief-JJJJ-MM-DD.jsonl.
# 3. Logt het tokenverbruik per zoekactie in logs\tokens.csv en het eindresultaat in
#    logs\weekbrief-JJJJ-MM-DD.json (scripts\tokens_weekbrief.py).
# 4. Controleert de nieuwe rijen in voorstellen.csv en runs.csv. Foute rijen gaan naar
#    logs\afgekeurd-JJJJ-MM-DD.csv, bestaande rijen en de andere bestanden worden zo nodig
#    teruggezet (scripts\controleer_weekbrief.py).

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

# --- stap 1: bronnen ophalen naar logs\inbox-JJJJ-MM-DD.csv (zoekopdrachten doet Claude)
$inbox = Join-Path $logDir "inbox-$datum.csv"
$ErrorActionPreference = "Continue"
$haal = & python -I -X utf8 "scripts\haal_bronnen.py" --uit $inbox 2>&1 | ForEach-Object { "$_" }
$ErrorActionPreference = "Stop"
$haal | ForEach-Object { Log "bronnen: $_" }
$inboxCount = 0
if (Test-Path -LiteralPath $inbox) { $inboxCount = @(Import-Csv -LiteralPath $inbox -Encoding UTF8).Count }
else { Log "WAARSCHUWING: geen inbox aangemaakt; Claude zoekt alleen zelf." }

# --- stap 2: opdracht = inhoud van Tasks\WEEKBRIEF.md, plus waar de inbox van deze run staat.
# PowerShell 5.1 escapet aanhalingstekens niet bij het doorgeven aan een exe, dus dat doen
# we zelf (anders wordt de tekst afgekapt).
$prompt = Get-Content -LiteralPath "Tasks\WEEKBRIEF.md" -Raw -Encoding UTF8
$prompt += "`n`n---`nInbox van deze run: logs/inbox-$datum.csv ($inboxCount berichten). Ophaalresultaat per bron: logs/inbox-$datum-bronnen.csv.`n"
$prompt = $prompt -replace '(\\*)"', '$1$1\"'

$claudeArgs = @(
    "-p", $prompt,
    "--allowedTools", "Read", "Glob", "Grep", "WebSearch", "WebFetch",
                      "Edit(./data/voorstellen.csv)", "Edit(./data/runs.csv)",
    "--disallowedTools", "Bash", "Write", "Edit(./data/incidenten.csv)", "Edit(./data/wijzigingen.csv)",
    "--permission-prompts", "none",
    "--max-budget-usd", "3",
    "--output-format", "stream-json", "--verbose"
)

# stream-json geeft het verbruik per stap; het eindresultaat (zelfde vorm als --output-format json)
# haalt tokens_weekbrief.py eruit en zet het in $jsonLog.
$streamLog = Join-Path $logDir "weekbrief-$datum.jsonl"
$ErrorActionPreference = "Continue"
$all = & $claude @claudeArgs 2>&1
$code = $LASTEXITCODE
$ErrorActionPreference = "Stop"
$stdout = $all | Where-Object { $_ -isnot [System.Management.Automation.ErrorRecord] } | ForEach-Object { "$_" }
$all | Where-Object { $_ -is [System.Management.Automation.ErrorRecord] } | ForEach-Object { Log "stderr: $_" }
[System.IO.File]::WriteAllText($streamLog, ($stdout -join "`n"), [System.Text.UTF8Encoding]::new($false))
Log "claude klaar, exitcode $code, stream in $streamLog"

# --- stap 3: tokenverbruik per zoekactie naar logs\tokens.csv, eindresultaat naar $jsonLog
$ErrorActionPreference = "Continue"
$tok = & python -I -X utf8 "scripts\tokens_weekbrief.py" --stream $streamLog --json $jsonLog --csv (Join-Path $logDir "tokens.csv") --run-datum $datum 2>&1 | ForEach-Object { "$_" }
$ErrorActionPreference = "Stop"
$tok | ForEach-Object { Log $_ }

# --- stap 4: controle: alleen rijen toegevoegd, alles te_beoordelen
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
