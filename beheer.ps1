# Incidentatlas - beheerscherm starten (alleen op deze computer: http://127.0.0.1:8100)
Set-Location -LiteralPath $PSScriptRoot
$env:PYTHONIOENCODING = "utf-8"
python -X utf8 "scripts\beheer.py" @args
