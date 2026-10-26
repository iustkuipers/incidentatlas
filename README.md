# Incidentatlas

Openbare dataset en website van Russische staatsacties buiten Rusland sinds 2000.
Standaard toont de site alleen **bewezen** incidenten: formeel toegeschreven door een rechter,
regering, de EU, de NAVO of de VN. Incidenten die alleen **in het profiel passen** zet je er apart bij.

## Bronnen
Sinds 2026-10-26 (protocol 2.1): de NOS, de publieke omroepen van de prioriteitslanden en de persbureaus als zoekbron; als bewijs alleen nos.nl en de domeinen in `data/bronnenregister.csv`. Tot 2026-10-26 was de NOS de enige bron. De eerdere dataset (202 incidenten uit 27 bronnen),
de oude weekbrief en de testruns staan in `backup/2026-10-21-voor-nos/` (zie `LEESMIJ.txt` daar).

## Mappen

```
index.html                 de website (leest de bestanden in data/)
404.html                   foutpagina
data/
  incidenten.csv           één regel per zaak, met de huidige fase in 'status'
  ontwikkelingen.csv       de tijdlijn: één regel per ontwikkeling van een zaak (datum, fase, wie, bron, citaat)
  voorstellen.csv          voorstellen van de AI (nieuwe zaken en ontwikkelingen), met kolom 'beoordeling'
  beoordelingen.csv        één regel per beoordeeld NOS-bericht (besluit, reden, zaak)
  inbox.csv                alle opgehaalde nieuwsberichten (NOS en omroepen); groeit alleen
  inbox_officieel.csv      berichten van officiële bronnen uit het register (wekelijks); groeit alleen
  dossierstatus.csv        per dossier: wachtrij, bronnen genoeg, laatst bijgewerkt, laatst nagezocht
  bronnen.csv              de nieuwsfeeds die elk uur worden opgehaald (NOS, omroepen, persbureaus)
  bronnenregister.csv      officiële en vertrouwde domeinen (voor verdieping)
  landen.csv               houding per land tegenover Rusland (landinformatie op de kaart)
  landgrenzen.geojson      landsgrenzen voor de klikbare kaart (moet mee online)
  wijzigingen.csv          log van alles wat online is gezet (pagina 'Nieuw')
  runs.csv                 tellingen per wekelijkse run
scripts/
  atlas.py                 valideren, voorstellen verwerken, links controleren, migreren
  nos_ophalen.py           feeds ophalen naar data/inbox.csv (elk uur); --officieel naar inbox_officieel.csv
  dossiers.py              dossierstatus bijwerken, wachtrijen voor volglijst en verrijken, 'nagezocht' vastleggen
  controleer_weekbrief.py  klaarzetten en controleren van de AI-runs
  tokens_weekbrief.py      tokenverbruik per zoekactie naar logs/tokens.csv
  haal_bronnen.py          hulpfuncties voor ophalen en feeds lezen
  beheer.py, beheer.html   het beheerscherm (alleen lokaal, met account)
  landgrenzen.py           eenmalig: haalt de landsgrenzen op (Natural Earth)
Tasks/
  ONDERZOEKSPROTOCOL.md    protocol 2.1: afbakening, fasen, bronnen, werkprocessen 1-6
  WEEKBRIEF.md             opdracht zoeken (wekelijks)
  ARCHIEF.md               opdracht archief (één jaar per run, vanaf 2014)
  VERDIEPING.md            opdracht verdieping van één zaak
  VOLGLIJST.md             opdracht volglijst (open zaken nalopen)
  VERRIJKEN.md             opdracht verrijken (ontbrekende A/B-bronnen zoeken)
  DOSSIER.md               opdracht dossier vanaf nul (bijvoorbeeld MH17)
run_ophalen.ps1            uurlijkse taak: ophalen; start na een gebruikslimiet het vervolg van de weekrun
run_weekbrief.ps1          AI-runs: zonder opties ophalen officieel + zoeken + volglijst + verrijken (maandag 07:00);
                           -Modus volglijst|verrijken | -Modus archief -Jaar 2024 | -Modus verdieping -Zaak <id>
                           -Modus dossier -Onderwerp "..." | -Stappen "volglijst,verrijken" | -Budget 3
beheer.ps1                 beheerscherm starten (http://127.0.0.1:8100)
verwerk.ps1                verwerken vanaf de opdrachtregel (kan ook in het beheerscherm)
design-system/             ontwerpkeuzes van de site (MASTER.md)
backup/                    eerdere datasets en testfasen
```

## Zo werkt het (protocol 2.1)

Een **zaak** doorloopt **fasen**: *signaal* (past in het patroon, niemand wijst Rusland aan) →
*beschuldigd* → *aangeklaagd* → *bewezen*, of *ontkracht*. Elke stap is een **ontwikkeling** met
datum, wie het zegt, bron en citaat; samen vormen ze de tijdlijn op de dossierpagina.

1. **Elk uur:** `run_ophalen.ps1` vult `data/inbox.csv` met nieuwe berichten (NOS en omroepen, gefilterd op trefwoorden).
2. **Maandag 07:00:** `run_weekbrief.ps1` haalt de officiële bronnen op, laat de AI alle nieuwe berichten
   beoordelen (proces 1), de open zaken nalopen (proces 2, langst niet nagezocht eerst) en dossiers met te weinig
   bronnen verrijken (proces 3; genoeg is genoeg: 1 A of 2 B voor bewezen). Raakt de abonnementslimiet op, dan
   gaat de run een paar uur later vanzelf verder (`logs/vervolg.flag`).
3. **Jij beoordeelt** in het beheerscherm (`beheer.ps1`): per voorstel met de tijdlijn ernaast.
   Tabblad *Bronnen nodig* toont wat nog een bron mist; tabblad *Zaken* heeft per zaak *Verdiepen*.
4. **Verwerken** in het beheerscherm; daarna `index.html`, `404.html`, `og-image.png` en `data/` online zetten.

## Commando's

| Commando | Wat het doet |
| --- | --- |
| `python scripts/atlas.py valideer` | Controleert `incidenten.csv` op formaat en bewijsregels |
| `python scripts/atlas.py verwerk` | Neemt goedgekeurde voorstellen over (zonder online controle) |
| `python scripts/atlas.py verwerk --controleer-links` | Idem, met controle van link en citaat |
| `python scripts/atlas.py verwerk --voorstellen <CSV-URL>` | Leest de voorstellen uit een Google Sheet (CSV-export) |
| `python scripts/atlas.py links` | Controleert alle bronlinks en werkt `laatst_gecontroleerd` bij |

Alleen Python 3.9 of hoger is nodig, geen extra pakketten.

## De site lokaal bekijken

De site leest CSV-bestanden, dus open hem via een kleine webserver en niet als los bestand:

```
python -m http.server 8000
```

Ga daarna naar http://localhost:8000.

## Online zetten

Elke statische host werkt: Cloudflare Pages, GitHub Pages of Netlify. Zet de hele map online.
Er is geen database of server nodig.

## Fasen en bewijsregels in het kort

Volledig in `Tasks/ONDERZOEKSPROTOCOL.md`.

| Fase | Wanneer | Minimale bron |
| --- | --- | --- |
| `signaal` | past in het patroon (spionage, sabotage, cyber, inmenging; doelwit Europa/NAVO; vanaf 2014), niemand wijst Rusland aan | 1× A of B |
| `beschuldigd` | een regering, dienst, onderzoekers of de getroffen partij wijzen Rusland met naam aan | 1× A of B |
| `aangeklaagd` | verdachten opgepakt of aangeklaagd, nog geen uitspraak | 1× A of B |
| `bewezen` | veroordeeld, formeel toegeschreven (verklaring, sancties), of openlijk erkend | 1× A, of 2× B |
| `ontkracht` | andere dader of ongeluk vastgesteld; blijft zichtbaar (filter) en telt mee in de statistieken | 1× A of B |

Een zaak gaat alleen omhoog met een bron die de nieuwe fase draagt, en omlaag alleen naar *ontkracht*.
`zekerheid` (hoog/middel/laag) gaat over de feiten, niet over de dader.
Bronniveaus: **A** de toeschrijver zelf, **B** persbureau of publieke omroep (NOS), **C** onderzoek of
denktank, **D** secundair (nooit de enige bron).
