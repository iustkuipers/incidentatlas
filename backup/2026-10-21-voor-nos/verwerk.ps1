# Incidentatlas - verwerken na beoordeling.
# Neemt goedgekeurde voorstellen over (met controle van link en citaat), valideert daarna
# de dataset en toont per voorstel dat in deze ronde is verwerkt een vinkje of kruisje met reden.

Set-Location -LiteralPath $PSScriptRoot
try { [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false) } catch {}
$env:PYTHONIOENCODING = "utf-8"
$ok  = [char]0x2713
$nok = [char]0x2717

function Read-Verwerkt {
    $map = @{}
    Import-Csv -LiteralPath "data\voorstellen.csv" -Encoding UTF8 | ForEach-Object { $map[$_.voorstel_id] = $_ }
    return $map
}

$voor = Read-Verwerkt

Write-Host "== Verwerken (met controle van link en citaat)" -ForegroundColor Cyan
& python -I -X utf8 "scripts\atlas.py" verwerk --controleer-links | Out-Null
$verwerkCode = $LASTEXITCODE

Write-Host ""
Write-Host "== Resultaat per voorstel" -ForegroundColor Cyan
$na = Read-Verwerkt
$n = 0
foreach ($id in $na.Keys | Sort-Object) {
    $oud = if ($voor.ContainsKey($id)) { $voor[$id].verwerkt } else { "" }
    $nieuw = $na[$id].verwerkt
    if ($oud -eq $nieuw -or -not $nieuw) { continue }
    $n++
    $titel = $na[$id].titel
    if (-not $titel) { $titel = "($($na[$id].soort) $($na[$id].incident_id))" }
    if ($nieuw -like "ja*") {
        Write-Host ("  {0} {1}  {2}" -f $ok, $id, $titel) -ForegroundColor Green
    } else {
        $reden = $nieuw -replace '^fout:\s*', ''
        Write-Host ("  {0} {1}  {2}" -f $nok, $id, $titel) -ForegroundColor Red
        Write-Host ("      reden: {0}" -f $reden) -ForegroundColor Red
    }
}
if ($n -eq 0) { Write-Host "  Geen goedgekeurde, nog niet verwerkte voorstellen gevonden." }

Write-Host ""
Write-Host "== Validatie van data\incidenten.csv" -ForegroundColor Cyan
& python -I -X utf8 "scripts\atlas.py" valideer
$valideerCode = $LASTEXITCODE

if ($verwerkCode -ne 0 -or $valideerCode -ne 0) { exit 1 }
exit 0
