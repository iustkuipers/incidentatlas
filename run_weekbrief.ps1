# Incidentatlas - AI-runs volgens protocol 2.1 (Tasks\ONDERZOEKSPROTOCOL.md, hoofdstuk 5).
#   Wekelijks (geplande taak):  powershell -File run_weekbrief.ps1
#       -> officiele bronnen ophalen, dan zoeken (1), volglijst (2) en verrijken (3)
#   Losse stappen:              -Modus volglijst | verrijken
#   Archief, een jaar compleet: -Modus jaar -Jaar 2024   (ronde 1 zoeken, ronde 2 en 3 gaten dichten; max. $50)
#   Archief, losse ronde:       -Modus archief -Jaar 2024 [-Ronde 2]
#   Verdieping van een zaak:    -Modus verdieping -Zaak <id>
#   Dossier vanaf nul:          -Modus dossier -Onderwerp "<omschrijving>"
#   Vervolg na gebruikslimiet:  -Stappen "volglijst,verrijken"   (doet run_ophalen.ps1 vanzelf)
#   Eenmalig hoger budget:      -Budget 3
#
# Per run: data\ bewaren, Claude Code headless (abonnement) met de opdracht uit Tasks\, tokens naar
# logs\tokens.csv, controle met scripts\controleer_weekbrief.py, goedgekeurd namens de AI en verwerkt
# (scripts\atlas.py, controle 'ai'), en per dossier vastleggen wanneer het is nagezocht
# (scripts\dossiers.py). Zolang een run loopt bestaat logs\brief.lock.
param([ValidateSet("week", "jaar", "archief", "verdieping", "volglijst", "verrijken", "dossier")][string]$Modus = "week",
      [string]$Jaar = "", [string]$Zaak = "", [string]$Budget = "", [string]$Onderwerp = "", [string]$Stappen = "", [int]$Ronde = 1)

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
$datum  = Get-Date -Format "yyyy-MM-dd"
$logDir = Join-Path $PSScriptRoot "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
try { [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false) } catch {}
$env:PYTHONIOENCODING = "utf-8"
$vervolg = Join-Path $logDir "vervolg.flag"

function Py { $ErrorActionPreference = "Continue"; $o = & python -I -X utf8 @args 2>&1 | ForEach-Object { "$_" }; $script:pyCode = $LASTEXITCODE; $o }

$claude = (Get-Command claude -ErrorAction SilentlyContinue).Source
if (-not $claude) {
    $claude = Get-ChildItem "$env:USERPROFILE\.vscode\extensions\anthropic.claude-code-*\resources\native-binary\claude.exe" -ErrorAction SilentlyContinue |
        Sort-Object { [version](($_.FullName -replace '.*anthropic\.claude-code-([\d.]+).*', '$1')) } |
        Select-Object -Last 1 -ExpandProperty FullName
}
$script:limiet = $false

function Run-Mode([string]$m) {
    $slug = ($Onderwerp -replace '[^A-Za-z0-9]', ''); if ($slug.Length -gt 20) { $slug = $slug.Substring(0, 20) }
    $naam = switch ($m) { "archief" { "archief-$Jaar" + $(if ($Ronde -gt 1) { "-r$Ronde" } else { "" }) } "verdieping" { "verdieping-$datum-" + ($Zaak -replace '[^A-Za-z0-9-]', '_') } "dossier" { "dossier-$datum-$slug" } default { "$m-$datum" } }
    $txtLog = Join-Path $logDir "$naam.log"; $jsonLog = Join-Path $logDir "$naam.json"; $streamLog = Join-Path $logDir "$naam.jsonl"
    $backup = Join-Path $logDir "backup-$naam"
    function Log($msg) { $line = "{0}  {1}" -f (Get-Date -Format "HH:mm:ss"), $msg; Write-Host $line; Add-Content -LiteralPath $txtLog -Value $line -Encoding UTF8 }
    if (-not $claude) { Log "FOUT: claude niet gevonden."; return 2 }
    Log "Start $naam met $claude"
    New-Item -ItemType Directory -Force -Path $backup | Out-Null
    Copy-Item -Path "data\*.csv" -Destination $backup -Force

    $lijst = Join-Path $logDir "lijst-$naam.csv"
    $rel = "logs/lijst-$naam.csv"
    $check = @("--modus", $m); $gezocht = $null
    $alles = @("Read", "WebSearch", "WebFetch", "Edit(./data/voorstellen.csv)")
    switch ($m) {
        "week" {
            $n = [int](Py "scripts\controleer_weekbrief.py" klaarzetten --uit $lijst | Select-Object -Last 1)
            Log "Te beoordelen: $n bericht(en)"
            if ($n -eq 0) { Log "Niets nieuw in de inbox."; return 0 }
            [void](Py "scripts\controleer_weekbrief.py" zaken --uit (Join-Path $logDir "zaken-$naam.csv"))
            $prompt = "Lees Tasks/ONDERZOEKSPROTOCOL.md en Tasks/WEEKBRIEF.md en voer de opdracht uit. Datum van vandaag: $datum. Te beoordelen berichten: $rel ($n berichten). Overzicht van zaken: logs/zaken-$naam.csv. Zoekopdrachten voor persbureaus: data/bronnen.csv (type zoekopdracht)."
            $allowed = $alles + @("Edit(./data/beoordelingen.csv)"); $budget = "2.5"
            $check += @("--lijst", $lijst)
        }
        "volglijst" {
            $n = [int](Py "scripts\dossiers.py" wachtrij --soort volglijst --uit $lijst --max 15 | Select-Object -Last 1)
            Log "Dossiers op de volglijst: $n"
            if ($n -eq 0) { Log "Geen open dossiers."; return 0 }
            $prompt = "Lees Tasks/ONDERZOEKSPROTOCOL.md en Tasks/VOLGLIJST.md en voer de opdracht uit. Datum van vandaag: $datum. Open dossiers: $rel ($n dossiers). Inboxen: data/inbox.csv en data/inbox_officieel.csv. Bronnenregister: data/bronnenregister.csv."
            $allowed = $alles; $budget = "1.5"; $gezocht = @("--lijst", $lijst, "--door", "volglijst", "--prefix", "volglijst-$datum")
        }
        "verrijken" {
            $n = [int](Py "scripts\dossiers.py" wachtrij --soort verrijken --uit $lijst --max 10 | Select-Object -Last 1)
            Log "Dossiers om te verrijken: $n"
            if ($n -eq 0) { Log "Alle dossiers hebben genoeg bronnen."; return 0 }
            $prompt = "Lees Tasks/ONDERZOEKSPROTOCOL.md en Tasks/VERRIJKEN.md en voer de opdracht uit. Datum van vandaag: $datum. Dossiers: $rel ($n dossiers). Inbox officiele bronnen: data/inbox_officieel.csv. Bronnenregister: data/bronnenregister.csv."
            $allowed = $alles; $budget = "1.5"; $gezocht = @("--lijst", $lijst, "--door", "verrijken", "--prefix", "verrijken-$datum")
        }
        "archief" {
            if (-not $Jaar) { Log "FOUT: geef -Jaar op."; return 2 }
            [void](Py "scripts\controleer_weekbrief.py" zaken --uit (Join-Path $logDir "zaken-$naam.csv"))
            $prompt = "Lees Tasks/ONDERZOEKSPROTOCOL.md, Tasks/WEEKBRIEF.md en Tasks/ARCHIEF.md en voer de archiefopdracht uit. Jaar voor deze run: $Jaar. Datum van vandaag: $datum. Overzicht van zaken: logs/zaken-$naam.csv. Bronnenregister: data/bronnenregister.csv."
            $gaten = Join-Path $logDir "gaten-archief-$Jaar.md"
            # samen hoogstens $50 per jaar: ronde 1 breed zoeken, ronde 2 en 3 gaten dichten
            $allowed = $alles + @("Edit(./data/beoordelingen.csv)", "Edit(./logs/gaten-archief-$Jaar.md)")
            $budget = switch ($Ronde) { 1 { "25" } 2 { "15" } default { "10" } }
            if ($Ronde -gt 1) {
                if (-not (Test-Path -LiteralPath $gaten)) { Log "FOUT: $gaten ontbreekt; draai eerst ronde 1."; return 2 }
                $prompt += " Dit is ronde $Ronde (gaten dichten): volg de sectie Ronde 2 in Tasks/ARCHIEF.md. De lijst met gaten: logs/gaten-archief-$Jaar.md; werk die aan het eind bij."
            } else {
                # ronde 1 vult zelf de lijst met gaten voor ronde 2
                Set-Content -LiteralPath $gaten -Encoding UTF8 -Value "# Gaten archief $Jaar (na ronde 1)`r`n`r`n(nog in te vullen door ronde 1)"
                $prompt += " Vul aan het eind logs/gaten-archief-$Jaar.md in volgens de sectie Lijst met gaten in Tasks/ARCHIEF.md."
            }
        }
        "verdieping" {
            if (-not $Zaak) { Log "FOUT: geef -Zaak op."; return 2 }
            Set-Content -LiteralPath $lijst -Value "id`r`n$Zaak" -Encoding UTF8
            $prompt = "Lees Tasks/ONDERZOEKSPROTOCOL.md en Tasks/VERDIEPING.md en voer de verdieping uit. Zaak: $Zaak. Datum van vandaag: $datum. De tijdlijn staat in data/ontwikkelingen.csv (regels met incident_id $Zaak); het bronnenregister in data/bronnenregister.csv."
            $allowed = $alles; $budget = "1"; $check += @("--zaak", $Zaak); $gezocht = @("--lijst", $lijst, "--door", "verdieping", "--prefix", "verdieping-$datum")
        }
        "dossier" {
            if (-not $Onderwerp) { Log "FOUT: geef -Onderwerp op."; return 2 }
            [void](Py "scripts\controleer_weekbrief.py" zaken --uit (Join-Path $logDir "zaken-$naam.csv"))
            $prompt = "Lees Tasks/ONDERZOEKSPROTOCOL.md, Tasks/VERDIEPING.md en Tasks/DOSSIER.md en bouw het dossier op. Onderwerp: $Onderwerp. Datum van vandaag: $datum. Overzicht van bestaande zaken: logs/zaken-$naam.csv; het bronnenregister staat in data/bronnenregister.csv."
            $allowed = $alles; $budget = "3"
        }
    }
    if ($Budget -and $m -eq $Modus) { $budget = $Budget }
    $denied = @("Bash", "Write")

    $claudeArgs = @("-p", $prompt, "--allowedTools") + $allowed + @("--disallowedTools") + $denied +
                  @("--permission-prompts", "none", "--max-budget-usd", $budget, "--output-format", "stream-json", "--verbose")
    $ErrorActionPreference = "Continue"
    $all = & $claude @claudeArgs 2>&1
    $code = $LASTEXITCODE
    $ErrorActionPreference = "Stop"
    $stdout = $all | Where-Object { $_ -isnot [System.Management.Automation.ErrorRecord] } | ForEach-Object { "$_" }
    $all | Where-Object { $_ -is [System.Management.Automation.ErrorRecord] } | ForEach-Object { Log "stderr: $_" }
    [System.IO.File]::WriteAllText($streamLog, ($stdout -join "`n"), [System.Text.UTF8Encoding]::new($false))
    Log "claude klaar, exitcode $code"
    # gebruikslimiet van het abonnement bereikt?
    $tail = ($stdout | Select-Object -Last 3) -join " "
    if ($tail -match '"is_error"\s*:\s*true' -and $tail -match '(?i)usage limit|rate limit|limit reached|5-hour') { $script:limiet = $true; Log "Gebruikslimiet van het abonnement bereikt." }
    Py "scripts\tokens_weekbrief.py" --stream $streamLog --json $jsonLog --csv (Join-Path $logDir "tokens.csv") --run-datum $naam | ForEach-Object { Log $_ }
    Py "scripts\controleer_weekbrief.py" controleer --backup $backup --log $jsonLog --afgekeurd (Join-Path $logDir "afgekeurd-$naam.csv") @check | ForEach-Object { Log $_ }
    $checkCode = $script:pyCode
    if ($gezocht -and -not $script:limiet) { Py "scripts\dossiers.py" gezocht @gezocht | ForEach-Object { Log $_ } }
    # wat de controle doorstond gaat met controle 'ai' op de kaart (link, citaat en bewijsregel opnieuw gecontroleerd)
    Py "scripts\atlas.py" autogoedkeuren | ForEach-Object { Log $_ }
    Py "scripts\atlas.py" verwerk --controleer-links | ForEach-Object { Log $_ }
    [void](Py "scripts\dossiers.py" bijwerken)
    if ($checkCode -ne 0) { Log "Controle heeft regels afgekeurd, gemist of teruggezet; zie 'controle' in $jsonLog"; return 1 }
    if ($code -ne 0) { return $code }
    Log "$naam klaar."
    return 0
}

$lock = Join-Path $logDir "brief.lock"
Set-Content -LiteralPath $lock -Value "$Modus $datum" -Encoding ascii
$rc = 0
try {
    if ($Modus -eq "week") {
        $todo = if ($Stappen) { @($Stappen -split "," | ForEach-Object { $_.Trim() } | Where-Object { $_ }) } else { @("ophalen", "week", "volglijst", "verrijken") }
        if (Test-Path -LiteralPath $vervolg) { Remove-Item -LiteralPath $vervolg }
        for ($i = 0; $i -lt $todo.Count; $i++) {
            $stap = $todo[$i]
            if ($stap -eq "ophalen") { Py "scripts\nos_ophalen.py" --officieel | ForEach-Object { Write-Host $_ }; continue }
            $r = [int](Run-Mode $stap | Select-Object -Last 1)
            $rc = [Math]::Max($rc, $r)
            if ($script:limiet) {
                # deze stap en de rest later opnieuw (run_ophalen.ps1 start het vervolg na een paar uur)
                Set-Content -LiteralPath $vervolg -Value (($todo[$i..($todo.Count - 1)]) -join ",") -Encoding ascii
                Write-Host "Vervolg gepland voor: $(Get-Content $vervolg)"
                break
            }
        }
    } else {
        if ($Modus -eq "jaar") {
            # een jaar archief in twee rondes: zoeken, dan de gaten dichten
            $Ronde = 1; $rc = [int](Run-Mode "archief" | Select-Object -Last 1)
            foreach ($r in 2, 3) {
                if ($script:limiet) { Write-Host "Gebruikslimiet: verder later met -Modus archief -Jaar $Jaar -Ronde $r"; break }
                $Ronde = $r; $rc = [Math]::Max($rc, [int](Run-Mode "archief" | Select-Object -Last 1))
            }
        } else {
            $rc = [int](Run-Mode $Modus | Select-Object -Last 1)
        }
    }
} finally {
    if (Test-Path -LiteralPath $lock) { Remove-Item -LiteralPath $lock }
}
exit $rc
