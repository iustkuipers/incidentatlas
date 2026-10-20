# Incidentatlas

Openbare dataset en website van Russische staatsacties buiten Rusland sinds 2000.
Standaard toont de site alleen **bewezen** incidenten: formeel toegeschreven door een rechter,
regering, de EU, de NAVO of de VN. Incidenten die alleen **in het profiel passen** zet je er apart bij.

## Mappen

```
index.html               de website (leest de CSV-bestanden in data/)
data/
  incidenten.csv         de dataset: één rij per incident, nieuwste eerst
  voorstellen.csv        voorstellen van de wekelijkse brief, met kolom 'beoordeling'
  bronnen.csv            de bronnen die de wekelijkse brief afloopt
  wijzigingen.csv        log van alles wat online is gezet (voedt de pagina 'Nieuw')
  runs.csv               tellingen per wekelijkse run
scripts/
  atlas.py               valideren, voorstellen verwerken, links controleren
WEEKBRIEF.md             de opdracht voor de wekelijkse taak van Claude
```

## Zo loopt een week

1. **Maandag 06:00:** de geplande taak van Claude loopt `bronnen.csv` af en zet nieuwe voorstellen
   in `voorstellen.csv` met `beoordeling = te_beoordelen`.
   Zie `WEEKBRIEF.md`.
2. **Jij beoordeelt** elke rij: zet `beoordeling` op `goedgekeurd` of `afgewezen` en vul
   `beoordeeld_door` in. Je mag velden verbeteren voordat je goedkeurt.
3. **Verwerken:**
   ```
   python scripts/atlas.py verwerk --controleer-links
   ```
   - Alleen goedgekeurde, nog niet verwerkte rijen worden overgenomen.
   - Het script controleert opnieuw of de link werkt, het citaat op de pagina staat en
     de bewijsregel klopt.
   - Rijen die falen krijgen in `verwerkt` de reden (`fout: …`) en komen niet online.
4. **Online zetten:** upload of push de map. De site leest de nieuwe CSV direct.

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

## Bewijsregels in het kort

| Status | Wanneer | Minimale bron |
| --- | --- | --- |
| `bewezen` | formele toeschrijving aan de Russische staat of een staatsgestuurde groep | 1× A, of 2× B |
| `past_in_profiel` | vermoed, niet formeel toegeschreven | 1× A of B |
| `afgewezen` | andere dader of ongeluk vastgesteld | blijft in de data, niet op de kaart |

Bronniveaus: **A** de toeschrijver zelf, **B** persbureau of kwaliteitsmedium,
**C** onderzoek of denktank, **D** secundair (nooit de enige bron).

## Openstaand werk in de huidige dataset

93 incidenten zijn officieel toegeschreven, maar worden nu alleen met mediabronnen onderbouwd.
Ze hebben `bron verbeteren` in de kolom `opmerking`. De wekelijkse brief zoekt er een
primaire bron bij. Zodra die is goedgekeurd, verdwijnt de markering vanzelf.
