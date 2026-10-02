# SubGlyph 2026 — version 1.11

## Ändringar

- Enbart Okuma XYZ+C ändras i denna version. X-värden för instick,
  frigång och rotationsfrigång skrivs som radier för huvudprogrammets
  G138-läge. Inmatade diametermått i programmet behålls.
- G138 och G136 postas inte; huvudprogrammen styr dessa lägen.
- XYZ+C anger G19 för cirkelinterpolering i Y/Z-planet.
- Standardtypsnittets definierade cirkelbågar (O, C och 0) körs med
  G2/G3 utan lyft och återinstick mellan sammanhängande bågdelar.
  Runda former använder bågar på högst 180 grader. Elliptiskt skalade
  former behåller sina cirkelbågsapproximationer.
- Okuma XZ+C och frontgravering samt Fanuc- och Siemens-postning
  behåller tidigare beteende.

## Verifiering

73 automatiska regressionstester godkända, inklusive radiella X-lägen,
rotationsfrigång, sammanhängande små cirkelbågar, spegling och oförändrad
XZ+C-postning. G138/G136 kontrolleras vara frånvarande i NC-utmatningen.
Den nya XYZ+C-postningen har ännu inte verifierats på maskin.

Huvudprogrammet ansvarar för G138/G136, C-axelaktivering, frigång,
absolut programmering och enhetsläge. G19 och G94 ligger kvar efter
retur; huvudprogrammet ansvarar för efterföljande plan- och matningsval.

## Distribution

Linux x86-64 levereras som programfil och tar.gz. Windows x86-64 levereras
som exe och zip. SHA-256-summor levereras separat. Byggena är osignerade.
