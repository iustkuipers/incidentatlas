# Incidentatlas – ontwerpsysteem (MASTER)

Bron van waarheid voor de vormgeving van `index.html` en `404.html`. Paginaspecifieke afwijkingen
horen in `pages/<pagina>.md`. De tokens staan als CSS-variabelen bovenaan `index.html`; wijzig daar,
niet in losse componenten. Herzien op 2026-10-26: kaart-eerst, licht, één scherm.

## Karakter
De kaart is het canvas, de zijbalk is de krant ernaast. Licht en rustig, zoals een goede kaartapp
met een redactionele kolom: geen dashboard, geen donker "terminal"-thema, geen grijze bijzinnetjes.
Gewone zinnen in plaats van labels in hoofdletters; geen monospace behalve voor code.

## Indeling (één scherm, niets scrollt behalve de zijbalk)
- **Kaart** vult het hele scherm links van de zijbalk.
- **Zijbalk rechts** (`--side`, 360–440px): logo + menu, daaronder de artikelen *in beeld*
  (incidenten in het kaartbeeld én binnen de filters), nieuwste bovenaan.
- **Bovenbalk** zweeft linksboven op de kaart: zoeken, de vijf fasen als schakelaars (tevens legenda),
  knop Filters (periode, soort actie, regio, mijlpalen Oekraïne).
- **Weergavebalk** zweeft onderin het midden: Kaart · Lijst · Grafieken.
- **Kaartknoppen** rechtsboven: in- en uitzoomen, terug naar Europa.
- Methode, Data, Over, Nieuw en het dossier openen als volledige pagina over de kaart heen,
  met "Naar de kaart" linksboven.
- Smal scherm (≤ 900px): kaart boven (68% van de hoogte), zijbalk eronder, weergavebalk vast onderin.

## Lagen in de zijbalk
Wereld (in beeld) → land → incident, met een kruimelpad bovenin. Klik op een land: kaart zoomt in,
zijbalk toont houding tegenover Rusland, één alinea met bron, kerncijfers (incidenten, NAVO, EU,
VN-stem 2022), verdeling per soort actie en de incidenten van dat land. Klik op een incident:
fase, titel, datum en plaats, samenvatting, toeschrijving, verloop en bronnen, knop naar het dossier.
Esc of klik op zee gaat een laag terug.

## Typografie
| Rol | Letter | Gewicht | Maat |
| --- | --- | --- | --- |
| Koppen, artikeltitels, landnaam | Source Serif 4 | 600 | zijbalk 17–30px, pagina's h1 30–44px |
| Tekst en bediening | Source Sans 3 | 400 / 500 / 600 | tekst 15–16px, bediening 14–15px |
| Meta (datum · land) | Source Sans 3 | 600 | 13,5–14,5px, in `--ink-2` (nooit lichter) |
| Cijfers in kolommen | Source Sans 3, `tabular-nums` | | |
| Kaartlabels | Noto Sans (OpenFreeMap-glyphs) | | landnamen in hoofdletters met spatiëring |

Geen tekst onder 12px. Secundaire tekst gebruikt `--ink-2` (#434C56), niet lichter.

## Kleur (alleen licht)
| Token | Waarde | Gebruik |
| --- | --- | --- |
| `--bg` / `--panel` | #F3F4F2 / #FFFFFF | achtergrond lijst en grafieken / zijbalk en kaarten |
| `--ink` / `--ink-2` | #12161B / #434C56 | tekst / meta en toelichting |
| `--accent` | #2459A6 | links, focusring, gekozen artikel |
| `--glass` | wit 64% + blur 18px | alles wat boven de kaart zweeft |

### Fasen (vijf, in deze volgorde)
| Fase | Kaart en symbool | Kleur |
| --- | --- | --- |
| bewezen | vol | #2459A6 |
| aangeklaagd | half (lichte vulling + rand) | #1A8A6E, vulling #A3D0C5 |
| beschuldigd | half | #C07A16, vulling #E6CAA2 |
| signaal (was: past in profiel) | hol (wit + rand) | #C07A16 |
| ontkracht | grijs, schuine streep in het symbool | #7D858F, vulling #E4E7EA |

Hoe voller het symbool, hoe sterker het bewijs; fase nooit alleen met kleur. Standaard staat alleen
*bewezen* aan; *ontkracht* staat standaard uit maar telt mee in "Wat er van signalen terechtkomt".
Blauw/petrol/oranje zijn nagerekend met de dataviz-validator (kleurenblindheid en contrast: geslaagd).
Tekst krijgt nooit de fasekleur: het symbool ernaast draagt de betekenis.

### Kaart
OpenFreeMap-vectortegels (OpenStreetMap) met Natural Earth-reliëf tot zoom 9, eigen stijl in
`mapStyle()`: land #EEEBE4, water #BCD4E7, rivieren, bos, ijs, stedelijk gebied, wegen pas vanaf
zoom 5–12, landsgrenzen paars-grijs met witte gloed. Rusland krijgt een lichte rode waas.
Clusters: donkerblauw rondje (#1C2B3D) met wit getal; klik zoomt in. Incidenten met dezelfde
coördinaten liggen in een kleine kring zodat elk apart klikbaar is. Valt de tegelserver weg, dan
tekent de site zee + landen uit `data/landgrenzen.geojson`.

## Glas
Alleen voor bediening die boven de kaart zweeft (bovenbalk, weergavebalk, kaartknoppen, meldingen).
Panelen met lezenswaardige inhoud (zijbalk, filterpaneel, tooltips) zijn effen wit.

## Vorm en ruimte
- Hoeken: 8px klein, 12–16px kaarten en panelen, pil (999px) voor knoppen, schakelaars en balken.
- Bediening 42px hoog (44px bij touch). Ruimte in stappen van 4px.
- Schaduw alleen voor wat zweeft of gekozen is.

## Beweging
Eén curve: `--ease` = `cubic-bezier(.2,.8,.2,1)`. 150ms voor hover en keuzes, 250ms voor panelen,
600–800ms voor kaartbewegingen. Niets loopt eindeloos. `prefers-reduced-motion`: alles uit,
kaart springt in plaats van vliegt.

## Grafieken
Staven ≤ 24px, afgeronde bovenkant (4px), 2px wit tussen gestapelde delen. Vulling volgt de fasen
(vol/half/hol). Legenda boven elke grafiek; tooltip per staaf; klik op een jaar filtert op dat jaar.

## Toegankelijkheid
Skiplink naar de lijst; de zijbalk is het toetsenbordalternatief voor de kaart. Schakelaars met
`aria-pressed`, sorteerkoppen met `aria-sort`, focusring 2px in `--accent`. Elke pagina één h1.

## Vermijden
Donker thema, monospace als stijlmiddel, labels in hoofdletters in de interface, lichtgrijze
bijzinnetjes, gradiënten en gloed, emoji als iconen, glas op leesvlakken, kerncijfers zonder
context, rood als hoofdkleur (rood betekent op de kaart Rusland), labels van dwergstaten op
overzichtsniveau.
