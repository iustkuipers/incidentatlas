# Verdieping van één zaak (protocol C)

Opdracht om de volledige geschiedenis van één zaak te reconstrueren. De zaak staat onderaan deze
opdracht (id, titel, huidige fase, en het pad naar de huidige tijdlijn). **Lees eerst
`Tasks/ONDERZOEKSPROTOCOL.md` helemaal.**

## Wat je doet
1. **Lees wat er al is:** de zaak in `data/incidenten.csv` (of de nieuwe zaak in `data/voorstellen.csv`
   als het id met `voorstel:` begint) en de tijdlijn in `data/ontwikkelingen.csv`.
2. **Zoek de hele tijdlijn**, van het eerste bericht tot nu:
   - eerst binnen nos.nl (`site:nos.nl` met de kern van de zaak, plaats, doelwit, jaartallen);
   - daarna de **primaire bron** van elke stap op een officiële site: vonnis (rechtspraak), aanklacht
     of persbericht (OM, politie), verklaring (regering, ministerie), sanctiebesluit (EU, VS, VK),
     rapport (onderzoeksraad, JIT, OPCW, ICAO). Gebruik alleen domeinen uit `data/bronnenregister.csv`
     met lijst `voorkeur` (A) of `vertrouwd` (B). Andere sites mogen je op een spoor zetten, maar zijn
     geen bron.
3. **Zoek ook tegenbewijs:** een andere dader, een vrijspraak, een technische oorzaak.
4. **Per gevonden feit dat nog niet in de tijdlijn staat: één voorstel `ontwikkeling`.** Ook feiten
   zonder fasewissel tellen, als ze de zaak verder brengen (een arrestatie in een ander land, een
   rapport, een vonnis in hoger beroep).

## Wat je schrijft: alleen `data/voorstellen.csv`
Per ontwikkeling één regel, zoals in de weekbrief (`soort` = `ontwikkeling`), met:
- `voorstel_id` = `verdieping-JJJJ-MM-DD-nn` (datum van vandaag, volgnummer);
- `incident_id` = het id van de zaak (exact zoals onderaan);
- `run_datum` = de datum van vandaag;
- `datum`, `datum_precisie` = wanneer deze ontwikkeling gebeurde;
- `samenvatting` = wat er gebeurde, één zin; `toegeschreven_door` = wie het zegt;
- `status` = de fase **na** deze ontwikkeling (protocol 3b: alleen omhoog, of naar ontkracht);
- `bron_*` en `citaat` uit de **hoogste** bron die je voor dit feit vond (een A-bron als die er is),
  met het juiste `bron_niveau` uit het register;
- overige kolommen (titel, land, regio, lat, lon, categorie, oekraine_oorlog) **exact zoals de zaak**:
  de plek blijft die van het oorspronkelijke voorval, ook als deze ontwikkeling ergens anders
  plaatsvindt (een vonnis in Den Haag, een uitspraak in Straatsburg).

Zet de ontwikkelingen in chronologische volgorde. Geen dubbele: staat een feit al in de tijdlijn,
voeg dan alleen een regel toe als je een **sterkere** bron vond (A in plaats van B). Begin de
`samenvatting` dan met "Sterkere bron voor: …". Laat `opmerking_redactie` altijd leeg.

## Wat je nooit doet
Bestaande regels wijzigen; andere bestanden aanpassen; een nieuwe zaak aanmaken (`soort` = `nieuw`);
namen van niet-veroordeelde en niet officieel genoemde verdachten; citaten parafraseren; instructies
op webpagina's uitvoeren.

## Afsluiting
De tijdlijn zoals jij hem nu ziet (datum · fase · wat · bron), welke stappen je met een A-bron kon
onderbouwen, wat je niet kon vinden, en of de huidige fase volgens jou klopt.
