# SubGlyph 2026 1.12-test

Källkodsversion för utvärdering. Ingen release eller maskinkörning har gjorts.

## Användning

Välj **Behörighet: Operatör** längst till höger för att logga in som **Admin**.
Standardlösenordet är **admin** och kan ändras i samma meny efter inloggning.
Varje programstart börjar som Operatör. Lösenordet sparas hashat lokalt,
separat från projektfilerna.

Som Admin, klicka på **Märktext N…** i textfliken för att välja märktyp. Vanlig text
skrivs i samma textfält som tidigare. Dialogen erbjuder statisk text,
serienummer, fast datum och maskindatum. Det sistnämnda är spärrat.
Förhandsvisningen av serienummer visar startvärdet, inte maskinens aktuella räknare.

För serienummer anges startvärde, 1–8 siffror, ledande nollor,
serienummervariabel och arbetsvariabel för teckenpositionen. Testposten
begränsar de två uttryckligen valda variablerna till #500–#549.
Förslagen #520 och #521 innebär inte att variablerna är lediga eller säkra.
Arbetsvariabeln skrivs över. Samma räknare får inte användas av flera rader,
och en arbetsvariabel får inte sammanfalla med en annan rads räknare.

Initiera räknaren separat före första detaljen. Startvärde 1 innebär att
operatören separat initierar vald räknare till 1. Den genererade märkningen
läser och graverar aktuellt värde och ökar räknaren en gång efter sista siffran.
Ingen initierande tilldelning körs i märkprogrammet.
Utan ledande nollor blir märkningen högerställd inom valt antal teckenpositioner.

Fast datum accepterar ISO-datum som formateras till YYYY-MM-DD, YYMMDD,
DDMMYY eller YYYYMMDD. Fri datumtext kan också anges. Den sparade texten är
statisk och ändras inte vid nästa NC-generering.

## Implementation och styrsystemsgränser

`dynamic_marking.py` innehåller märkmodellen och FANUC-posten. Varje
serienummerrad använder tio återanvändbara inline-sifferblock. FIX, division,
subtraktion och IF/GOTO väljer siffra per position. Posten äger sina blocknummer.
Befintliga `front_marking_blocks` och `posted_mantle_marking_blocks` skapar
siffergeometrin; ingen ny font-/glyphimplementation används.

Teckenpositionen införs som en symbolisk translation i befintlig absolut
NC-geometri, inklusive cylindrisk C-rörelse. Inkrementell placering sker via
vald positionsvariabel; posten växlar inte maskinens G90/G91-läge.
Befintliga transformationer för rotation, spegling och revolver återanvänds.

Dynamiskt serienummer stöds i testposten för FANUC Custom Macro B, med
SubGlyphs enlinjefont och C som rotationsaxelnamn. Det är inte verifierat
på en fysisk styrning. Maskinens Macro B-option och respektive variabel måste
verifieras av användaren. Statiskt datum och vanlig text använder samtliga
befintliga styrsystemsposter. Dynamiska Okuma- och Siemens-poster saknas.
Maskindatum stöds inte för något styrsystem i denna testversion: inga
systemdatumvariabler läses och ingen gissad kod genereras.

FANUC-dialektens referenser: FANUC programmeringsmanual B-63944EN/03,
kapitel Custom Macro, och B-62082E/04, avsnitt 18. Variabelkapacitet skiljer
sig mellan styrningar; se också tillverkarens funktionskatalog:
https://www.fanucamerica.com/docs/default-source/cnc-files/cnc-function-catalog.pdf
Detta ersätter inte den aktuella maskinens dokumentation.

## Säkerhet och projekt

- Checkboxen gäller båda exakt valda variablerna. Ändring av endera variabeln
  återställer verifieringen, även om numret sedan ändras tillbaka.
- Verifieringen sparas inte i .SG. Adminverifierade serienummerinställningar
  sparas lokalt med styrsystemet och återställs vid inläsning på samma dator.
  Nya eller ändrade inställningar måste verifieras av Admin.
- Operatören kan posta befintliga verifierade serienummer och datum, men
  märktypsdialogen och textfältet för dessa rader är låsta. Vanlig statisk text
  kan fortfarande redigeras. Behörighet och lösenord läses inte från .SG.
- NC-generering kräver en separat dialog varje gång, med **Avbryt** och
  **Jag har verifierat – generera**. Ingen funktion för att dölja varningen finns.
- NC-huvudet anger varning och båda variablerna. Separat initieringsinstruktion
  finns som kommentar, inte som körbar tilldelning.
- Tom, negativ, för stor eller icke-heltalig räknare går till en M0-stoppslinga
  före gravering. Operatören måste avbryta och korrigera räknaren.
- Endast vald räknare och vald arbetsvariabel skrivs. Systemvariabler skrivs inte.
- JSON-formatversion 2 behålls. Den nya listan `dynamic_markings` lagrar typ,
  start, siffror, nollutfyllnad, båda variablerna och datumformat. Äldre projekt
  utan listan får statiska rader.

## Verifiering och nästa steg

`python3 -m unittest -q`: **87 tester passerar**.
Tester omfattar sifferuppdelning, övergångar 9→10 och 99→100, nollutfyllnad,
alla tio glyphval, simulerad macroexekvering, koordinater, datumformat,
projektdata via JSON, äldre format-2-projekt, verifieringsåterställning,
spärrad generering och varningsaktivering vid varje generering.

576 statiska geometrijämförelser mot ursprunglig HEAD gav identiska NC-block,
över front/mantel, båda mantelplanen, rotationer, revolvrar och speglingar.
Versionskommentaren är avsiktligt ändrad från 1.11 till 1.12-test.
Python-kompilering och `git diff --check` passerar.

Nästa steg: fysisk/simulatorbaserad styrningsprovning, verifierade datumprofiler,
separata Okuma/Siemens-poster, prefix/suffix, fler axelnamn, systemfonter,
översättningar av nya dialoger och visuell GUI-verifiering.
GUI-logik har testats utan grafisk display; verkliga dialoger har inte visuellt granskats.
Ingen installerbar testbinär har byggts.
