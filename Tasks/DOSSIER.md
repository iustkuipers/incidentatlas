# Dossier: één zaak vanaf nul opbouwen (protocol C, voor een zaak die nog niet bestaat)

Opdracht om één bekende zaak volledig in de dataset te zetten: de nieuwe zaak plus de hele tijdlijn,
van het eerste bericht tot nu. Het onderwerp staat onderaan deze opdracht. **Lees eerst
`Tasks/ONDERZOEKSPROTOCOL.md` en `Tasks/VERDIEPING.md` helemaal**: alle regels van de verdieping
gelden, met deze afwijkingen.

## Afwijkingen ten opzichte van de verdieping
1. **Controleer eerst of de zaak al bestaat** in `data/incidenten.csv` of als nieuwe zaak in
   `data/voorstellen.csv`. Zo ja: doe een gewone verdieping op die zaak (alleen ontwikkelingen).
2. **Bestaat hij niet:** schrijf **één** voorstel `soort` = `nieuw` voor de zaak, met
   `voorstel_id` = `dossier-JJJJ-MM-DD-01`. De `datum` is de datum van het voorval zelf; `status` is
   de fase **op de dag van het voorval** (meestal `signaal` of `beschuldigd`); de bron is het eerste
   NOS-bericht. De coördinaten zijn de plek van het voorval zelf (bij MH17: de crashplek), 4 decimalen.
3. **Daarna één voorstel `ontwikkeling` per stap**, chronologisch, met
   `incident_id` = `voorstel:dossier-JJJJ-MM-DD-01` en `voorstel_id` = `dossier-JJJJ-MM-DD-02`, `-03`, enz.
4. **De fase loopt mee met de tijd**: `status` is per ontwikkeling de fase **na** die stap. De fase gaat
   alleen omhoog (signaal → beschuldigd → aangeklaagd → bewezen), of naar ontkracht. Een stap die na
   een eerdere hogere fase komt (bijvoorbeeld een aanklacht nadat een regering al formeel had
   toegeschreven) krijgt de huidige, hogere fase: de stap staat in de tijdlijn, de fase blijft gelijk.
5. **Bronnen per stap:** eerst het NOS-bericht van die dag (B); voor de grote stappen (formele
   toeschrijving, aanklacht, vonnis, uitspraak van een internationaal orgaan) daarnaast de
   **primaire bron** (A) uit het bronnenregister, als **eigen ontwikkeling met dezelfde datum** en
   in `samenvatting` "Primaire bron: …". Zo telt een stap als bewezen met A, en blijft het
   NOS-bericht ook in de tijdlijn.
6. **Kies de stappen die het verhaal dragen**: het voorval, de eerste beschuldiging, onderzoeksrapporten,
   formele toeschrijvingen, aanklachten, het vonnis, uitspraken van internationale organen, en
   belangrijke reacties van Rusland (ontkenning) als ontwikkeling zonder fasewissel. Geen dagelijkse
   herhalingen. Richtlijn: 8 tot 20 stappen.

## Budget
Beperkt (zie de opdracht). Besteed het aan het vinden van de juiste NOS-artikelen en de primaire
bronnen van de grote stappen; open geen artikelen die je niet nodig hebt.

## Afsluiting
De tijdlijn zoals je hem hebt opgebouwd (datum · fase · wat · bron · niveau), welke stappen een A-bron
hebben, wat je niet kon vinden, en twijfels over fasen.
