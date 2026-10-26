# Archiefbrief: zoeken in het verleden (protocol A, één jaar per run)

Eenmalige opdracht om de dataset vanaf 2014 te vullen. Het jaar staat onderaan deze opdracht.
**Lees eerst `Tasks/ONDERZOEKSPROTOCOL.md` en `Tasks/WEEKBRIEF.md` helemaal.** Alle regels uit de
weekbrief gelden (besluiten, kolommen, coördinaten, wat je nooit doet), met deze afwijkingen:

1. **Er is geen lijst.** Je zoekt zelf, **uitsluitend binnen nos.nl**: zet `site:nos.nl` en het jaar
   in elke zoekopdracht. Open alleen artikelen op nos.nl.
2. **Alleen artikelen uit het opgegeven jaar.** Een artikel uit een ander jaar neem je niet op (wel
   mag je het noemen in de samenvatting, als het een ontwikkeling van een zaak lijkt).
3. **`run_datum` is `archief`**, in beoordelingen én voorstellen; `voorstel_id` = `archief-JAAR-nn`.
4. **Elk gevonden artikel krijgt één regel** in `data/beoordelingen.csv`. Staat de url er al, sla hem over.
5. **Zaken over meerdere jaren:** kijk in het zakenoverzicht (pad onderaan) of de zaak al bestaat,
   ook als `voorstel:` uit een eerdere archiefrun. Zo ja: `ontwikkeling` bij die zaak. Zo bouwt een zaak
   als MH17 zich jaar voor jaar op.
6. **Per zaak één `nieuwe_zaak`**; andere artikelen over dezelfde zaak in dit jaar worden `ontwikkeling`
   (met `incident_id` = `voorstel:<voorstel_id>`), ook als ze niets nieuws toevoegen aan de fase.

## Zoektermen
Combineer `site:nos.nl`, het jaar en de termen hieronder. Eerst de signaalcategorieën; stop een
categorie zodra nieuwe zoekopdrachten geen nieuwe artikelen opleveren.

| categorie | termen |
| --- | --- |
| `sabotage` | sabotage Rusland · brandstichting · explosie wapendepot · kabel Oostzee beschadigd · spoor sabotage |
| `cyber` | hack · cyberaanval · Russische hackers · ddos · gelekte mails |
| `spionage` | spion opgepakt · spionage · diplomaten uitgezet · inlichtingendienst Rusland |
| `desinformatie_verkiezingen` | desinformatie · nepnieuws · verkiezingen beïnvloeding · trollenfabriek |
| overige (alleen vanaf beschuldigd) | Russische drone luchtruim · vergiftiging · aanslag Russische geheime dienst · gas chantage · migranten grens Belarus · Wagner · MH17 |

Neem bij `sabotage` en `cyber` ook voorvallen mee die zelf nog geen Russische link hebben maar wel
een signaal zijn (protocol 3a), bijvoorbeeld een grote storing of een hack bij vitale infrastructuur.

## Budget
Beperkt. Besteed het aan zoeken en aan het openen van artikelen die relevant lijken. Artikelen die op
grond van titel en zoekfragment duidelijk niet relevant zijn, noteer je zonder openen als
`niet_relevant`.

## Afsluiting
Zoekopdrachten die je deed; aantal artikelen per besluit; de zaken in één regel elk met hun fase;
categorieën waar je vermoedelijk iets mist; zaken die waarschijnlijk vervolg hebben in andere jaren.
