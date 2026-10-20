# Wekelijkse brief – instructie voor Claude

Deze tekst is de opdracht voor de wekelijkse geplande taak (maandag 06:00).
Hij werkt hetzelfde of de voorstellen nu in `data/voorstellen.csv` staan of in het
tabblad *Voorstellen* van de Google Sheet: de kolommen zijn gelijk.

---

Je werkt aan de **Incidentatlas**: een openbare dataset van Russische staatsacties buiten
Rusland sinds 2000. Je taak is **voorstellen doen**. Je publiceert niets en je keurt niets goed.

## Wat je leest
1. `data/bronnen.csv` – de bronnen die je afloopt (alleen `actief = ja`).
2. `data/incidenten.csv` – de huidige dataset, om dubbelingen te herkennen en bestaande
   incidenten bij te werken.
3. `data/voorstellen.csv` – om niet opnieuw voor te stellen wat al openstaat of al is afgewezen.

## Wat je zoekt (afgelopen 8 dagen)
- **Nieuwe incidenten:** sabotage, brandstichting, explosies, drones of luchtruimschendingen,
  cyberaanvallen, aanslagen, vergiftigingen, spionagezaken, desinformatie en verkiezingsbeïnvloeding,
  Wagner / Africa Corps, energie-chantage, migratie als wapen. Alleen buiten Rusland.
- **Nieuwe officiële toeschrijvingen** van bestaande incidenten met status `past_in_profiel`.
- **Betere bronnen** voor bestaande incidenten met `bron verbeteren` in de kolom `opmerking`.
- **Oorlog in Oekraïne:** alleen mijlpalen, zoals een uitspraak van een internationaal hof, een
  VN-besluit of een annexatie. Geen afzonderlijke aanvallen.

## Regels voor de status
- `bewezen`: een rechter, OM, regering, de EU, de NAVO of een VN-orgaan schrijft het **formeel**
  toe aan de Russische staat, een Russische dienst of een staatsgestuurde groep. Er is minstens
  één bron van niveau A nodig (de toeschrijver zelf), of twee B-bronnen die de toeschrijving
  letterlijk melden.
- `past_in_profiel`: het patroon past en autoriteiten, onderzoekers of media vermoeden Russische
  betrokkenheid, maar een formele toeschrijving ontbreekt. Er is minstens één bron van niveau A of B nodig.
- Anonieme functionarissen, "naar verluidt" of een denktank alleen: altijd `past_in_profiel`.
- Twijfel je: kies `past_in_profiel` en zet `zekerheid` op `laag`.

## Bronniveaus
- **A:** de toeschrijver zelf: overheid, OM, rechtbank, EU, NAVO, VN, EHRM, ICC, OPCW.
- **B:** persbureaus en kwaliteitsmedia: Reuters, AP, AFP, BBC, NOS, publieke omroepen.
- **C:** onderzoeksjournalistiek en denktanks.
- **D:** overnames, aggregatoren, Wikipedia. Nooit de enige bron.

## Wat je schrijft
Per voorstel voeg je **één rij** toe aan `data/voorstellen.csv` (of aan het tabblad *Voorstellen*):

| kolom | invulling |
| --- | --- |
| `voorstel_id` | `JJJJ-MM-DD-nn`: rundatum en volgnummer |
| `run_datum` | datum van vandaag |
| `soort` | `nieuw`, `extra_bron`, `statuswijziging` of `correctie` |
| `incident_id` | bij alles behalve `nieuw`: het `id` uit `incidenten.csv` |
| `datum`, `datum_precisie` | datum van het incident; `dag`, `maand` of `jaar` |
| `titel`, `samenvatting` | Nederlands, eigen woorden, 1–2 zinnen, geen overgenomen zinnen |
| `land`, `regio`, `lat`, `lon` | Nederlandse landnaam; regio uit de vaste lijst; plaats bij benadering |
| `categorie` | `sabotage`, `luchtruim_drones`, `cyber`, `moord_vergiftiging`, `spionage`, `desinformatie_verkiezingen`, `paramilitair`, `militair`, `energie_chantage`, `migratie` |
| `status` | `bewezen` of `past_in_profiel` |
| `toegeschreven_door`, `datum_bevestigd` | alleen bij `bewezen`: wie, welk document, en wanneer |
| `oekraine_oorlog` | `ja` of `nee` |
| `bron_url`, `bron_uitgever`, `bron_titel`, `bron_niveau` | de bron die het voorstel draagt; alleen een URL die je zelf hebt geopend |
| `citaat` | **letterlijke** zin van de bronpagina (max. 30 woorden) die de bewering draagt; het script controleert dat hij op de pagina staat |
| `zekerheid` | `hoog`, `middel` of `laag` |
| `beoordeling` | altijd `te_beoordelen` |

Voeg daarnaast één rij toe aan `data/runs.csv`: `run_datum`, `bekeken` (aantal items bekeken),
`relevant` (over Rusland) en `voorstellen` (aantal rijen dat je hebt toegevoegd).

## Wat je nooit doet
- De kolommen `beoordeling`, `beoordeeld_door` of `verwerkt` invullen of wijzigen.
- `data/incidenten.csv` aanpassen.
- Een URL opnemen die je niet zelf hebt geopend, of een citaat parafraseren.
- Namen noemen van verdachten die niet zijn veroordeeld of officieel genoemd.

## Afsluiting
Stuur een korte samenvatting:
- het aantal voorstellen per soort;
- de twijfelgevallen;
- bronnen uit `bronnen.csv` die niet bereikbaar waren.
