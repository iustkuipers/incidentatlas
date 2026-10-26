# Volglijst: open zaken nalopen (protocol D)

Wekelijkse opdracht, na het zoeken. Onderaan staat het pad naar de lijst open zaken (signaal,
beschuldigd, aangeklaagd) met genoeg bronnen, de langst niet nagezochte eerst, met per zaak de
datum van de laatste ontwikkeling en van de laatste zoekronde. **Lees eerst `Tasks/ONDERZOEKSPROTOCOL.md` helemaal.**

## Wat je doet, per zaak
1. Bekijk de zaak en zijn tijdlijn (`data/incidenten.csv` of `data/voorstellen.csv`,
   en `data/ontwikkelingen.csv`).
2. **Kijk eerst in de inboxen van de afgelopen week** (kost niets): `data/inbox.csv` (nieuws) en
   `data/inbox_officieel.csv` (overheden, OM, rechtbanken, EU, NAVO; met `land` en `niveau`).
   Zoek daarna gericht bij de bronnen die bij de zaak passen: de omroep van het land en de officiële
   instanties van dat land uit `data/bronnenregister.csv` (`site:<domein>`). Zoek naar nieuws **na** de
   laatste ontwikkeling: is de dader bekend geworden, is Rusland aangewezen, zijn er verdachten opgepakt of
   aangeklaagd, is er een vonnis, een officiële toeschrijving, of juist een andere verklaring
   (ontkracht)?
3. Gevonden: één voorstel `ontwikkeling` per nieuw feit, precies zoals in `Tasks/VERDIEPING.md`
   beschreven, maar met `voorstel_id` = `volglijst-JJJJ-MM-DD-nn`. Als bron telt alleen een domein uit
   het bronnenregister (lijst `voorkeur` of `vertrouwd`); een officiële bron (A) heeft de voorkeur.
4. Niets gevonden: niets schrijven; noem de zaak in je samenvatting als "niets nieuws".

## Wat je schrijft
Alleen `data/voorstellen.csv`. Geen beoordelingen, geen andere bestanden.

## Wat je nooit doet
Zoals in de weekbrief; daarnaast: geen nieuwe zaken aanmaken.

## Afsluiting
Per zaak één regel: "niets nieuws" of de gevonden ontwikkeling met de fase erna.
