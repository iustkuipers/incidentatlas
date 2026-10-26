# Verrijken: ontbrekende bronnen zoeken (protocol 2.1, proces 3)

Wekelijkse opdracht, na de volglijst. Onderaan staat het pad naar de lijst dossiers waarvan de
**huidige fase de bronnenregel nog niet haalt** (kolom `bronniveaus` laat zien wat er nu is).
**Lees eerst `Tasks/ONDERZOEKSPROTOCOL.md` helemaal** (vooral 4 en 5e).

## Wat je doet, per dossier
1. Bekijk de zaak en de tijdlijn (`data/incidenten.csv` of `data/voorstellen.csv`, en
   `data/ontwikkelingen.csv`). Bepaal **welke stap de huidige fase draagt** (bijvoorbeeld de formele
   toeschrijving, de aanklacht of het vonnis).
2. **Zoek de bron die ontbreekt**, het liefst de primaire bron (A) van die stap:
   - eerst in `data/inbox_officieel.csv`;
   - daarna bij de officiële instanties uit `data/bronnenregister.csv` die passen bij het land en de
     soort stap: OM of rechtbank bij een aanklacht of vonnis; regering, ministerie, EU of NAVO bij een
     toeschrijving of sancties (`site:<domein>` met de kern van de zaak, ook in de taal van het land);
   - lukt dat niet: een tweede, onafhankelijke B-bron uit het register (een andere omroep of een
     persbureau dat zelf verslag doet).
3. **Genoeg is genoeg:** zodra de fase de bronnenregel haalt, stop je voor dit dossier. Eén goede
   A-bron is genoeg; zoek niet verder.
4. Gevonden: één voorstel `soort` = `extra_bron` met
   - `voorstel_id` = `verrijken-JJJJ-MM-DD-nn`, `run_datum` = vandaag;
   - `incident_id` = het id van het dossier;
   - `datum` = de datum van de stap die de bron draagt; `samenvatting` = "Primaire bron: …" of
     "Tweede bron: …" en wat de bron vaststelt;
   - `status` = de huidige fase van het dossier (verrijken verandert de fase niet; draagt de bron een
     **hogere** fase, gebruik dan `soort` = `ontwikkeling` met die fase);
   - `bron_*`, `bron_niveau` uit het register en een letterlijk `citaat` uit die bron;
   - titel, land, regio, lat, lon, categorie, oekraine_oorlog exact zoals de zaak.
5. Niet gevonden: niets schrijven; noem het dossier in je samenvatting met wat je probeerde.

## Wat je schrijft
Alleen `data/voorstellen.csv`.

## Wat je nooit doet
Zoals in de verdieping; daarnaast: geen nieuwe zaken, en geen bronnen buiten het register.

## Afsluiting
Per dossier één regel: de gevonden bron (instantie, niveau, datum) of "niet gevonden" met de reden.
