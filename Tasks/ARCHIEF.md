# Archief: één jaar volledig in kaart brengen (protocol 2.1, eenmalig per jaar vanaf 2014)

Opdracht om de dataset jaar voor jaar te vullen, van oud naar nieuw. Het jaar staat onderaan deze
opdracht. **Lees eerst `Tasks/ONDERZOEKSPROTOCOL.md` en `Tasks/WEEKBRIEF.md` helemaal.** Alle regels uit
de weekbrief gelden (afbakening, besluiten, kolommen, coördinaten, talen, wat je nooit doet), met de
afwijkingen hieronder. Doel: **geen zaak uit dit jaar missen** die binnen de afbakening valt.

## Bronnen
| rol | welke | gebruik |
| --- | --- | --- |
| zoeken én bewijs | `nos.nl` en de domeinen in `data/bronnenregister.csv` met lijst `voorkeur` (A, officieel) of `vertrouwd` (B, omroepen en persbureaus) | als `bron_url` in een voorstel |
| alleen zoeken | domeinen met lijst `toegestaan` (C, onderzoek, denktanks) en overzichten elders (tijdlijnen, lijsten, Wikipedia) | om zaken te **vinden**; daarna zoek je de zaak op bij een bron uit de eerste rij. **Nooit** als `bron_url` |
| nooit | lijst `niet_gebruiken` | niet openen |

Per zaak heeft een officiële bron (A) de voorkeur: zoek bij een aanklacht, vonnis of toeschrijving
gericht bij de instantie zelf (`site:<domein>` uit het register, ook in de taal van het land). Lukt dat
niet, dan een omroep of persbureau (B). De NOS is één van de B-bronnen, niet de enige.

## Werkwijze
1. **Per categorie zoeken**, in deze volgorde: `sabotage`, `cyber`, `spionage`,
   `desinformatie_verkiezingen`, daarna de overige categorieën (die pas vanaf `beschuldigd`). Per
   categorie zoek je in het Engels én in de talen van de landen waar in dat jaar iets gebeurde (zie de
   trefwoorden in `scripts/nos_ophalen.py`), steeds met het jaartal.
   **Minimum, niet onderhandelbaar:** minstens **8 zoekopdrachten** per signaalcategorie (`sabotage`,
   `cyber`, `spionage`, `desinformatie_verkiezingen`) en minstens **4** per overige categorie, verdeeld
   over landen en talen (zeker de Baltische staten, Polen, Duitsland, Scandinavië, Tsjechië, Nederland,
   België, Frankrijk, het VK). Pas daarna mag je een categorie stoppen, en alleen als de laatste drie
   zoekopdrachten niets nieuws opleverden. Een zoekopdracht die mislukt (domein onbereikbaar) telt niet:
   probeer dan een andere bron of formulering.
2. **Alleen zaken uit het opgegeven jaar** als `nieuwe_zaak` (de datum van het oorspronkelijke voorval
   ligt in dat jaar). Latere stappen van zo'n zaak (aanklacht, vonnis in een later jaar) mag je meteen als
   `ontwikkeling` toevoegen, met hun eigen datum en bron: dan is het dossier in één keer compleet.
3. **Bestaat de zaak al** (zakenoverzicht, pad onderaan; ook `voorstel:` uit een eerdere run): geen
   nieuwe zaak, alleen ontbrekende `ontwikkeling`en of een `extra_bron`.
4. **Volledigheidscheck aan het eind:** zoek twee of drie overzichten van Russische hybride acties in
   Europa die dit jaar dekken (rij "alleen zoeken"), loop ze na en zoek elke zaak die nog ontbreekt alsnog
   op bij een bewijsbron. Wat je niet kunt onderbouwen, noem je in de afsluiting.

## Vastleggen
- `run_datum` = `archief`, in beoordelingen én voorstellen; `voorstel_id` = `archief-JAAR-nn`
  (doorlopend over alle soorten).
- **Elk geopend artikel** krijgt één regel in `data/beoordelingen.csv` (ook van omroepen en officiële
  sites); staat de url er al, sla hem over. Artikelen die op grond van titel en fragment duidelijk niet
  relevant zijn, open je niet en noteer je niet.
- **Per zaak één `nieuwe_zaak`**; andere artikelen over dezelfde zaak worden `ontwikkeling` (met
  `incident_id` = `voorstel:<voorstel_id>`) of `extra_bron`.
- Het `citaat` is letterlijk, in de taal van de bron, en hoogstens 30 woorden. Het wordt automatisch op de
  pagina gecontroleerd; een pagina die je niet kon openen, gebruik je niet als bron.
- Wat de controle doorstaat, gaat automatisch op de kaart met het teken "AI-gecontroleerd". Wees dus
  streng: liever een zaak als `signaal` met een goede bron dan een te hoge fase.

## Budget
**Gebruik het.** Stop niet zolang het minimum niet gehaald is of er nog zaken op je lijst staan; een run
die klaar is met budget over en een mager resultaat is mislukt. Schrijf wel steeds in blokken van
ongeveer 30 regels, zodat er niets verloren gaat als het budget op is, en begin met de categorieën met
de meeste zaken. Noem in de afsluiting per categorie het aantal zoekopdrachten.

## Lijst met gaten (laatste stap van ronde 1)
Vervang de inhoud van `logs/gaten-archief-JAAR.md` (alleen dat bestand, met Edit) door een genummerde
lijst voor ronde 2. Zet daarin:
- elke zaak die je in een overzicht of zoekresultaat zag, maar niet kon onderbouwen met een bewijsbron
  (met datum, land, categorie en waarom het niet lukte);
- elke zaak waarvan het voorstel misschien afvalt (pagina gaf een fout, citaat twijfelachtig);
- per signaalcategorie de landen waar je nog niet in de eigen taal zocht, als gerichte zoekopdracht;
- onderaan: sites die onbereikbaar waren en sites die goed werkten.
Ronde 2 krijgt alleen deze lijst mee; schrijf hem dus zo dat iemand anders ermee verder kan.

## Ronde 2 en 3: gaten dichten
Na ronde 1 volgt per jaar een tweede ronde met de lijst `logs/gaten-archief-JAAR.md` (pad onderaan).
- Werk de lijst zaak voor zaak af. Per zaak **minstens drie** zoekopdrachten bij verschillende bronnen
  uit het register (omroep van het land, persbureau, officiële instantie, in de taal van het land) voordat
  je hem opgeeft; hoogstens zes. Noem wat niet lukte in de afsluiting, met wat je probeerde.
- Kom je onderweg zaken uit dit jaar tegen die nog niet in de dataset staan, neem ze ook op.
- **Werk aan het eind de lijst met gaten bij** (Edit): haal weg wat gelukt is, laat staan wat nog open is
  met wat je probeerde, en voeg nieuwe gaten toe. Ronde 3 werkt op dezelfde manier met die lijst; is de
  lijst leeg, zoek dan breed verder naar zaken die nog ontbreken.
- Zaken die bij een ander jaar horen: zet ze onderaan onder "Voor andere jaren" met jaar en kern.
- Sla sites over die in de lijst als onbereikbaar staan; kies een andere bewijsbron uit het register.
- `voorstel_id` loopt door na het hoogste `archief-JAAR-nn` dat al in `data/voorstellen.csv` staat.
- Bestaat een zaak al (zakenoverzicht), dan alleen een ontbrekende stap of bron.

## Afsluiting
Zoekopdrachten per categorie; aantal zaken per categorie en fase; de zaken in één regel elk; zaken uit
de volledigheidscheck die je niet kon onderbouwen; zaken die vervolg hebben in latere jaren.
