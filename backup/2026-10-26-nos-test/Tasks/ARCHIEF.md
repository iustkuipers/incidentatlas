# Archiefbrief – instructie voor Claude (bron: NOS, één jaar per run)

Eenmalige opdracht om de dataset te vullen met NOS-artikelen uit het verleden. Het jaar staat
onderaan deze opdracht. De regels voor beoordelen, status, citaat en voorstellen zijn **precies
dezelfde als in `Tasks/WEEKBRIEF.md`**: lees dat bestand eerst helemaal en volg het, met de
afwijkingen hieronder.

## Afwijkingen ten opzichte van de weekbrief
1. **Er is geen lijst.** Je zoekt zelf, met de zoekmachine, **uitsluitend binnen nos.nl**: zet
   in elke zoekopdracht `site:nos.nl`. Open alleen artikelen op nos.nl.
2. **Alleen artikelen uit het opgegeven jaar.** Een artikel van een ander jaar neem je niet op.
3. **`run_datum` is altijd `archief`** (in `data/beoordelingen.csv` én in `data/voorstellen.csv`;
   `voorstel_id` wordt dan `archief-JAAR-nn`, bijvoorbeeld `archief-2024-01`).
4. **Elk gevonden artikel krijgt één regel** in `data/beoordelingen.csv`, ook als het niet
   relevant blijkt. Staat de url al in `data/beoordelingen.csv`, dan sla je hem over.
5. **Eén voorstel per incident.** Gaan meerdere artikelen over hetzelfde incident, kies dan het
   artikel met de duidelijkste toeschrijving voor het voorstel; de andere krijgen besluit
   `volglijst` met reden "zelfde incident als <url>".

## Zoektermen
Combineer `site:nos.nl` en het jaar met de termen hieronder. Begin met de bovenste; stop een
categorie zodra nieuwe zoekopdrachten geen nieuwe artikelen meer opleveren.

| categorie | termen |
| --- | --- |
| `sabotage` | Rusland sabotage · brandstichting Rusland · Russische sabotage spoor · kabel Oostzee Rusland |
| `luchtruim_drones` | Russische drone luchtruim · Russisch gevechtsvliegtuig luchtruim · drones boven kazerne |
| `cyber` | Russische hackers · cyberaanval Rusland · GRU hackers |
| `moord_vergiftiging` | vergiftiging Rusland · aanslag Russische geheime dienst |
| `spionage` | Russische spion opgepakt · spionage Rusland · Russische diplomaten uitgezet |
| `desinformatie_verkiezingen` | Russische desinformatie · verkiezingen beïnvloeding Rusland |
| `energie_chantage` | Rusland gas chantage · gaskraan Rusland |
| `migratie` | migranten Belarus grens Rusland · migratie als wapen |
| `paramilitair` | Wagner · Africa Corps |
| mijlpalen Oekraïne | Internationaal Strafhof Rusland · VN-resolutie Rusland · annexatie |

## Budget
Je budget is beperkt. Besteed het aan zoeken en aan het openen van artikelen die relevant
lijken. Artikelen die op grond van titel en zoekfragment duidelijk niet relevant zijn, mag je
zonder openen als `niet_relevant` noteren.

## Afsluiting
Stuur een korte samenvatting: zoekopdrachten die je hebt gedaan, aantal artikelen per besluit,
de voorstellen in één regel elk, en categorieën waar je vermoedelijk iets hebt gemist.
