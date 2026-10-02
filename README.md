# SubGlyph 2026

**Version 1.11 — nuvarande stabila huvudversion**

SubGlyph 2026 är en kostnadsfri grafisk NC-generator för märkning och gravering.
Programmet skapar underprogram för FANUC, OKUMA OSP och SIEMENS SINUMERIK från en enkelstrecksfont och
visar märkningen på detaljen i en interaktiv 3D-förhandsvisning.

SubGlyph är skapat av **Kristian Simontaival**. Projektet kan stödjas via
[Buy Me a Coffee](https://buymeacoffee.com/FarfarSpelar).

> **Simple should remain simple. Don't overcomplicate things.**

## Viktigt om säkerhet

SubGlyph skapar **underprogram**, inte kompletta huvudprogram. Innan ett
genererat underprogram anropas måste huvudprogrammet ange och verifiera:

- verktygsval och verktygskorrigering;
- spindelvarvtal och rotationsriktning;
- arbets- och interpolationsplan;
- enhetsläge, exempelvis G20 eller G21;
- nollpunkt och koordinatsystem;
- första säkra förpositionering;
- maskinens C-axelfunktioner och övriga maskinspecifika M-/G-koder.

SubGlyph skriver inte G17, G20 eller G21. Okuma XYZ+C anger G19 för
cirkelinterpolering i Y/Z-planet. Huvudprogrammet ansvarar för övriga
planval, enhetsläge och återställning efter underprogrammet.

> **Varning:** Granska och simulera alltid den genererade NC-koden. Torrkör
> därefter med reducerad matning innan programmet används i produktion.
> Kontrollera särskilt axelriktningar, nollpunkter, rotationsfrigång,
> cirkelinterpolering och styrsystemets programspråk.

## Huvudfunktioner

- FANUC (ISO)-, OKUMA OSP (ISO)- och SIEMENS SINUMERIK (ISO)-postning.
- Ett gemensamt program eller individuella programnummer per märkpost.
- Upp till sex märkposter.
- Automatisk sammanslagning av märkposter med samma O-nummer.
- Rund mantelmärkning med `XZ+C`.
- Plan sidmärkning med `XYZ+C` och C-indexering.
- Frontplansmärkning i X/Y med Z som djupaxel och C-indexering.
- Runda, sexkantiga och rektangulära ämnen.
- Individuell position, storlek, rotation, spegling och Z-riktning per märkpost.
- Valbar rotationsaxeladress, exempelvis `C` eller `CS`, för genererad NC-kod.
- Gravyrstöd för dubbelt citattecken (`"`).
- Individuellt, justerbart teckenmellanrum för varje märktext.
- Märkning längs Z-axeln eller runt omkretsen på mantelytor.
- Direkta och tydliga matningsvärden i varje genererat program.
- MM- och INCH-visning med konvertering av inmatade värden.
- Svenska, finska, tyska, franska, engelska, bosniska och polska.
- Interaktiv 3D-preview med orbit, detaljrotation och zoom.
- Projektfiler i `.SG`-format.
- Valfri öppning av genererade program i systemets textredigerare.
- Lokaliserad versions- och tidskommentar i varje NC-program.
- Programikon i distributionerna.

## Systemkrav

Färdiga distributioner kräver ingen separat Pythoninstallation.

- Linuxdistributionen är byggd för x86-64.
- Windowsdistributionen är byggd för 64-bitars Windows.
- macOS-versionen byggs lokalt på en Mac och kan anpassas för aktuell
  Intel- eller Apple Silicon-miljö.

För körning från källkod behövs Python 3.10 eller senare, Tkinter och Pillow.
Runtime-beroenden finns i `requirements.txt`; `requirements-build.txt` lägger
till PyInstaller för paketering. Tester har körts med Python 3.12.

## Snabbstart

1. Starta SubGlyph 2026.
2. Välj språk och `MM` eller `INCH`.
3. Välj FANUC (ISO), OKUMA OSP (ISO) eller SIEMENS SINUMERIK (ISO).
4. Ange projektnamn, programnummer och programkommentar.
5. Välj märkyta, aktiva axlar och ämnestyp.
6. Ange ämnesmått, märkdjup, frigång och matningar.
7. Fyll i en eller flera märkposter.
8. Kontrollera resultatet i 3D-vyn.
9. Klicka på **Generera NC-program**.
10. Granska, simulera och torrkör programmet från ett korrekt förberett
    huvudprogram.

## Gränssnitt

### Program

Här väljs styrsystem och hur programmen ska organiseras.

- **FANUC/OKUMA OSP/SIEMENS SINUMERIK:** väljer ISO-postprocessor.
- **Projektnamn:** används som projektidentitet.
- **Programnummer:** används som O-nummer för ett gemensamt program.
- **Separata program:** aktiverar ett programnummer per märkpost.
- **Kommentar:** skrivs efter O-numret i programhuvudet.
- **Öppna efter generering:** öppnar sparade filer i systemets textredigerare.

Programfliken påminner också om att verktyg, varvtal, arbetsplan och första
förpositionering måste definieras i huvudprogrammet.

### Maskin och yta

Här väljs spindel, märkyta, aktiva axlar, ämnestyp, djup, frigång och
matningsmetod.

- **Märkyta:** `Runt en axel` eller `Frontplan`.
- **Aktiva axlar:** `XZ+C` eller `XYZ+C`, beroende på märkyta och Y-axel.
- **Maskinen har Y-axel:** krävs för `XYZ+C` och frontplansbearbetning.
- **Djupets riktning:** anger positiv eller negativ riktning för djupaxeln.
- **Ämnestyp:** Rund, Sexkant eller Rektangel.
- **Ämneslängd:** styr arbetsstyckets proportioner i 3D-förhandsvisningen men
  påverkar inte NC-koden.
- **Märkdjup:** radiellt eller axiellt ingrepp beroende på vald märkyta.
- **Frigång:** normalt säkerhetsavstånd från den valda ytan.

### Märktext

Fältet **Programnamn** aktiveras för OKUMA OSP (ISO) och bestämmer `.SSB`-filens namn.
Det påverkar inte O-numret inne i programmet.

Upp till sex märkposter kan definieras. Varje post kan ha:

- egen märktext;
- eget programnummer i läget separata program;
- X/Z-position beroende på märkyta;
- Y-position när Y används;
- C-vinkel;
- teckenhöjd och teckenbredd;
- textrotation;
- individuell spegling.

Tomma märkposter hoppas över vid postningen.

## Bearbetningslägen

### XZ+C — rund mantelyta

Detta läge används för gravering runt ett runt ämne.

- X anger graveringsdjup och frigång.
- Z anger position längs detaljens längdaxel. För text längs Z-axeln avser
  ZPos textens vänsterkant, inte dess centrum. `ZPos -20` ger därför Z-20 som
  den innersta koordinaten även när texten roteras 180° med Z-riktning Z-.
- C formar märkningen runt mantelytan.
- Y är låst.
- Rundade former approximeras med G1-segment eftersom Z/C inte utgör ett
  normalt kartesiskt cirkelplan.

Med diameter 50, märkdjup 0,5 och frigång 2 blir gravyrnivån X49.5 och normal
frigång X52.

### XYZ+C — plan sida på rund-, sexkant- eller rektangelämne

Detta läge används när en plan, C-indexerad sida ska märkas.

- C väljer detaljens sida eller vinkel och står sedan stilla under märkningen.
- Z och Y formar gravyrbanan på ytan.
- X anger djup och normal ytfrigång.
- Samma C-värde indexeras inte på nytt mellan märkposter.
- Mellan tecken och separata streck används normal ytfrigång.
- Före indexering till ett nytt C-område används rotationsfrigång.

Rotationsfrigång för sexkant:

```text
2 × NV / √3 + frigång
```

Rotationsfrigång för rektangel:

```text
√(bredd² + höjd²) + frigång
```

Explicit definierade fontbågar postas med G2/G3 och J/K-offset i Y/Z.
Huvudprogrammet måste välja rätt interpolationsplan; SubGlyph skriver inte G19.
Om teckenbredd och teckenhöjd skalar en båge elliptiskt delas formen upp i
flera korta, cirkulära G2/G3-block. Det undviker radietoleransfel utan att
ersätta bågen med G1-segment.

### Frontplan — X/Y-bana med Z-djup

Frontplan används för gravering på detaljens ändyta.

- X och Y formar gravyrbanan.
- Z anger graveringsdjup och frigång.
- C indexerar märkpunkt och text runt detaljens centrum.
- Textrotation roterar texten ytterligare kring dess egen märkpunkt.
- Samma C-värde indexeras inte på nytt mellan märkposter.
- Frontplan kräver en maskin med Y-axel.

Explicit definierade fontbågar postas med G2/G3 och I/J-offset i X/Y.
Huvudprogrammet måste välja rätt interpolationsplan; SubGlyph skriver inte G17.

Böjd text via böjningsradie är ännu inte aktiverad för frontplanspostning.
Fältet ska därför lämnas tomt i version 1.11.

## Ämnestyper

- **Rund:** anges med detaljdiameter.
- **Sexkant:** anges med nyckelvidd, `NV`.
- **Rektangel:** anges med bredd och höjd. Lika värden ger ett kvadratiskt ämne.

För sexkant och rektangel beräknas avståndet till den indexerade ytan från
ämnesmåtten och C-vinkeln. Rotationsfrigången tar hänsyn till ämnets största
radie så att verktyget går fritt innan detaljen vrids.

## Textgeometri och bågar

SubGlyph använder en enkelstrecksfont avsedd för gravering. Tecknen byggs av
linjer och, där explicit bågdata finns, cirkelbågar.

- I `XZ+C` används G1-segment för rundningar.
- I plan `XYZ+C` används G2/G3 med J/K där bågdata finns.
- I Frontplan används G2/G3 med I/J där bågdata finns.
- Tecknen `O`, `0` och `C` har explicita bågdefinitioner i version 1.11.
- Dubbelt citattecken (`"`) graveras som två korta separata streck.
- Små bokstäver normaliseras till motsvarande versaler i gravyrfonten.
- Övriga rundningar representeras av korta G1-segment.

Fältet **Mellanr.** på fliken Märktext anger det fria avståndet i aktuell enhet
mellan två teckenkanter på den aktuella raden. `0,4` ger alltså 0,4 mm mellan
varje tecken när MM är valt. `0` ger inget extra fritt avstånd. Värdet får inte
vara negativt och sparas separat för varje märktext i `.SG`-projektet.

## Rotationsaxelns NC-adress

Fältet **C-axel** på fliken Märktext bestämmer vilken adress som används för
alla rotationsrörelser. Standardvärdet är `C`. Maskiner som använder en annan
adress kan exempelvis ställas till `CS`, vilket gör att vinkeln 60 grader postas
som `CS60` i stället för `C60`. Värdet sparas i `.SG`-projektet; äldre projekt
som saknar inställningen använder automatiskt `C`.

SubGlyph lägger inte till ett extra G1 enbart för att lämna G2/G3-läge.
Frånrörelsen sker med G0. Detta ska verifieras mot den FANUC-, OKUMA OSP-
eller SIEMENS SINUMERIK-variant som används.

## Programnummer och filer

### Gemensamt program

Alla aktiva märkposter skrivs i det programnummer som anges på Programfliken.

### Separata program

Varje märkpost får ett eget programnummerfält. Poster med samma O-nummer slås
automatiskt ihop i samma program och behåller sin ordning.

Exempel:

```text
Märkpost 1: 1200
Märkpost 2: 1200
Märkpost 3: 1201
```

Resultatet blir ett program `O1200` med de två första posterna och ett program
`O1201` med den tredje.

### FANUC (ISO)

- Filnamnet är `O` följt av programnumret, exempelvis `O1000`.
- Filer sparas utan filändelse.
- En fil skapas per unikt O-nummer i läget separata program.
- Underprogram avslutas med `M99`.

### OKUMA OSP (ISO)

- Filen sparas som `Programnamn.SSB`, utifrån fältet Programnamn på fliken Märktext.
- Flera O-program kan ligga i samma `.SSB`-fil.
- Varje underprogram anger `G94` före märkningen så att F-värden tolkas
  som matning per minut även om huvudprogrammet använder `G95`.
- C-rörelser får explicit `M15` (positiv riktning) eller `M16` (negativ
  riktning). C-målen skrivs inom 0–360° och oförändrade C-mål utelämnas.
  Riktningen för gravyrdrag beräknas före vinkelomräkningen, även över noll.
- Första C-positioneringen använder `M15` eftersom ingångsvinkeln är okänd.
  Efterföljande snabbförflyttningar använder kortaste vägen. Huvudprogrammet
  måste säkerställa frigång vid inträdet och absolut programmering.
- En enskild graveringsrörelse på ett helt varv eller mer avvisas.
- För XZ+C korrigeras Okumas textorientering genom att vända C-avvikelsen
  kring märkningens indexläge före M15/M16-beräkningen. Ingen fast
  vinkelförskjutning läggs till. Frontplan behåller sin tidigare postning.
- XYZ+C anger `G19` före rörelserna. X-värden för instick,
  frigång och rotationsfrigång skrivs som radier (hälften av de interna
  diametermåtten). Y/Z och C-indexeringen behåller sina mått.
- I XYZ+C använder enkelstrecksfontens definierade cirkelbågar (O, C och 0) G2/G3.
  Runda former skrivs med bågar på högst 180 grader. Elliptiskt skalade
  former behåller sina cirkelbågsapproximationer. Sammanhängande bågar körs
  utan mellanliggande lyft och återinstick.
- Systemtypsnittens rasterkonturer och XZ+C:s Z/C-rörelser använder fortsatt
  G1. Dessa banor kan inte generellt ersättas med cirkelbågar i G17/G19.
- `G138` och `G136` postas inte. Huvudprogrammet styr dessa lägen och
  ska aktivera `G138` före XYZ+C-gravering. `G19` ligger kvar efter retur;
  huvudprogrammet ansvarar för efterföljande planval.
- Underprogram avslutas med `RTS`.
- `G94` är kvar efter retur. Huvudprogrammet måste ange `G95` och lämpligt
  F-värde innan efterföljande bearbetning som kräver matning per varv.

### SIEMENS SINUMERIK (ISO)

- Filnamnet baseras på programnumret och får filändelsen `.spf`.
- En fil skapas per unikt O-nummer i läget separata program.
- Underprogram avslutas med `M17`.

## Genererade kommentarer

Varje program får en lokaliserad kommentar med produktversion samt datum och
klockslag. Kommentarerna skrivs utan språkspecifika specialtecken för bättre
kompatibilitet med äldre styrsystem.

```text
(CREATED WITH SUBGLYPH VERSION 1.11)
(CREATED 2026-08-12 21:15:30)
```

## Enheter

Knapparna `MM` och `INCH` ändrar visningsenhet och konverterar befintliga
linjära dimensioner och matningar i projektet.

SubGlyph skriver aldrig G20 eller G21. Huvudprogrammet måste ha samma enhetsläge
som valdes när underprogrammet genererades.

## Matningar

Två matningar används:

- **Nedmatning:** rörelsen från frigång till graveringsdjup.
- **Ingreppsmatning:** rörelserna som formar märkningen.

SubGlyph skriver alltid direkta F-värden. Parameterstyrd matning har avsiktligt
tagits bort för att hålla underprogrammen enkla och minska risken att en
maskinparameter ändras eller återanvänds av misstag.

Matningen behandlas som modal och skrivs vid den första relevanta rörelsen i en
sammanhängande gravyrsekvens.

## 3D-förhandsvisning

- **Vänster musknapp + dra:** vrid och luta hela 3D-vyn.
- **Höger musknapp + dra:** rotera detaljen runt sin längdaxel för att se andra
  C-indexerade sidor.
- **Mushjul:** zooma in eller ut.
- **Solid:** visar ett skuggat ämne.
- **Wireframe:** visar ämnets kanter.
- **Av:** döljer ämnet men behåller märkningen.

Förhandsvisningen visar HSP, aktiva axlar och aktuell märkgeometri. Den är ett
visuellt hjälpmedel och ersätter inte maskinsimulering.
Valet Lower/Upper påverkar inte textens läsriktning i förhandsvisningen;
revolverkompenseringen görs endast i den genererade NC-koden.
För Upper + Z- inverterar posten C-indexeringen: ett visat C60-läge skrivs som
C-60 för att hamna på samma synliga sida i maskinen.

## Projektfiler

**Arkiv → Spara projekt** sparar arbetet i `.SG`-format. **Arkiv → Ladda
projekt** återställer det.

Projektfilen innehåller bland annat:

- språk och enhet;
- styrsystem och programupplägg;
- märkyta, aktiva axlar, ämnestyp och ämneslängd;
- dimensioner, djup, frigång och matningar;
- samtliga sex märkposter;
- inställningen för att öppna resultatet i en textredigerare.

Äldre projekt migreras när det är möjligt. Saknade märkposter fylls med tomma
standardvärden.

## Hjälp, felrapporter och önskemål

Menyn **Hjälp** innehåller **Rapportera ett fel**, **Skicka önskemål**,
**Om SubGlyph** och länken **Buy Me a Coffee**. Formulären följer valt språk.

Båda formulären innehåller:

- den fasta mottagaren `subglyph@gmail.com`;
- användarens e-postadress för svar;
- ämnesrad och meddelande;
- möjlighet att lägga till valfria bilagor;
- möjlighet att generera och bifoga en diagnoslogg.

Felrapportformuläret kan dessutom bifoga den senaste automatiskt sparade
crashdumpen. När formuläret slutförs skapar SubGlyph ett oskickat `.eml`-utkast
med mottagare, svarsadress, text och bilagor och öppnar det i systemets
e-postprogram. Användaren granskar själv utkastet och väljer **Skicka**.
SubGlyph lagrar inga SMTP-lösenord och skickar ingenting automatiskt.

### Diagnoslogg

Knappen **Generera logg** skapar en textfil med:

- SubGlyph-, Python- och operativsystemsversion;
- maskinarkitektur och körbar programsökväg;
- aktuella projekt- och maskininställningar;
- de senaste registrerade aktiviteterna, exempelvis försök att ladda, spara
  eller generera ett program.

Loggen kan innehålla projektdata och märktexter. Kontrollera därför innehållet
innan filen skickas.

### Crashdump

Ohanterade programfel skapar automatiskt en tidsstämplad crashdump med
systeminformation och Python-traceback. Fel i Tk-händelser kompletteras även
med aktuella inställningar och aktivitetsloggen. Rapport- och loggfiler sparas
i användarens lokala SubGlyph-katalog:

- Linux: `$XDG_STATE_HOME/SubGlyph`, eller `~/.local/state/SubGlyph`;
- Windows: `%LOCALAPPDATA%\SubGlyph`;
- macOS: `~/Library/Application Support/SubGlyph`.

## Installation och distributioner

Hämta färdiga binärer och kontrollsummor från **Releases** på projektets
GitHub-sida när releasen har publicerats. Binärer ingår inte i källkodsrepot.
Nedanstående filnamn motsvarar lokala byggresultat i `dist/`.

### Linux

Packa upp arkivet och kör programfilen. Arkivet innehåller även
`SubGlyph.desktop`, `SubGlyph.png` och `README.md`.

- `dist/SubGlyph-2026-1.11-linux-x86_64`
- `dist/SubGlyph-2026-1.11-linux-x86_64.tar.gz`

### Windows

Windowsversionen är en fristående `.exe` med inbäddad programikon.
ZIP-distributionen innehåller även `README.md`:

- `dist/SubGlyph-2026-1.11-windows-x86_64.exe`
- `dist/SubGlyph-2026-1.11-windows-x86_64.zip`

Windows SmartScreen kan varna för ett osignerat program. Det innebär inte i sig
att filen är skadlig, men kontrollera alltid SHA-256-summan och distribuera
programmet från en betrodd källa.

### macOS

Ett macOS-bygge måste skapas på macOS eftersom PyInstaller inte kan bygga en
macOS-app från Linux eller Windows. macOS-flödet har inte verifierats
på denna Linuxmiljö och inget färdigt macOS-paket finns för 1.11.
Det medföljande skriptet skapar
`SubGlyph 2026.app` och ett ZIP-arkiv:

```bash
./build_macos.sh
```

För distribution utanför den egna datorn bör appen kodsigneras och notariseras
med ett Apple Developer ID. Skriptet skapar:

- `dist/SubGlyph 2026.app`
- `dist/SubGlyph-2026-1.11-macos.zip`

### Kontrollsummor

SHA-256-summor för färdiga 1.11-filer finns i:

- `dist/SubGlyph-2026-1.11-SHA256SUMS.txt`

## Köra från källkod

Installera Python 3, Tkinter och beroendena:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 subglyph.py
```

På Windows aktiveras miljön med `.venv\Scripts\activate` i stället.
Tkinter installeras via operativsystemets Pythonpaket om det saknas.
Nuvarande version startar direkt i huvudfönstret.

## Automatiska tester

Kör hela regressionssviten med:

```bash
python3 -m unittest -v
```

Testerna täcker bland annat programformat, O-nummergruppering, enhetsansvar,
matningar, parametrar, rotationsfrigång, frontplan samt G2/G3-geometri.

## Bygga distributioner

Installera byggberoenden:

```bash
python3 -m pip install -r requirements-build.txt
```

Linux:

```bash
./build_linux.sh
```

Windows, från en Windows-Pythonmiljö:

```bat
build_windows.bat
```

macOS, på en Mac:

```bash
./build_macos.sh
```

Linux- och Windowsbyggena inkluderar `SubGlyphIcon.png`. macOS-skriptet
inkluderar samma programikon i applikationspaketet.

## Projektstruktur

- `subglyph.py` — gränssnitt, projektformat, preview och postprocessorflöde.
- `nc_geometry.py` — koordinattransformation och G0/G1/G2/G3-block.
- `vector_font.py` — enkelstrecksfont och bågdefinitioner.
- `test_subglyph.py` — automatiska regressionstester.
- `SubGlyphIcon.png` — program- och distributionsikon.
- `build_linux.sh` — Linuxbygge och distributionsarkiv.
- `build_windows.bat` — Windowsbygge.
- `build_macos.sh` — macOS-app och ZIP-arkiv.
- `packaging/linux/SubGlyph.desktop` — Linux-menyintegration.

## Kända begränsningar i version 1.11

- Böjd text med böjningsradie postas ännu inte på frontplan.
- Endast vissa tecken har explicita G2/G3-bågar; övriga kurvor använder G1.
- Okuma XYZ+C anger G19. Övriga lägens interpolationsplan och enhetsläget
  anges i huvudprogrammet.
- Maskinbyggarspecifika C-axelkoder måste hanteras i huvudprogrammet.
- Programmet ersätter inte CAM-verifiering eller maskinsimulering.
- Genererad kod måste anpassas och verifieras för den aktuella maskinen,
  styrsystemsversionen och företagets säkerhetsrutiner.

## Versionsstatus

Version 1.11 är den nuvarande versionen. Fokus är stabilitet, maskinprov,
felrättningar, dokumentation och paketering.


## Publik Git-release

Källkod, bilder, byggskript och aktuell dokumentation hör till Git-repot.
`build/`, `dist/`, virtuella miljöer, genererade `.spec`-filer och lokala
NC-program undantas via `.gitignore`. Färdiga binärer och distributionsarkiv
läggs som bilagor till releasen tillsammans med SHA-256-summorna.

Behåll versionsnumret samstämmigt i `subglyph.py`, byggskripten och
releaseanteckningarna. Kör regressionstesterna före nya byggen. Bygg för
respektive målplattform och kontrollera arkivens innehåll innan publicering.

`RELEASE_NOTES-1.11.md` beskriver aktuell release.
README är ingången för källkodsprojektet och medföljer distributionsarkiven.
Översättningsgranskningar kan återskapas med
`python3 generate_translation_reviews.py`.

## Licens

Copyright (C) 2026 Kristian Simontaival.

SubGlyph distribueras under **GNU General Public License version 3
(GPL-3.0-only)**. Se [LICENSE](LICENSE) för fullständiga villkor.
Programmet levereras utan garanti. Vid distribution av binärer ska även
motsvarande källkod och licensvillkor göras tillgängliga enligt licensen.
