# Meerjarige energie- en batterijvergelijking 2023-10 tot 2026-09

Status: `VERIFIED_WITH_LIMITATIONS`

Modus: uitsluitend offline en read-only

Periode: `2023-10-01T00:00:00+02:00` tot `2026-10-01T00:00:00+02:00`

Analyse uitgevoerd: `2026-10-01`

## Hoofdconclusie

De woning werd over de drie vergelijkbare jaren duidelijk meer afhankelijk van
netafname, terwijl de injectie daalde en de gewogen marktprijs steeg:

- netafname steeg van `7.820,473 kWh` naar `9.510,180 kWh`: `+21,61%`;
- netinjectie daalde van `1.471,811 kWh` naar `989,269 kWh`: `-32,79%`;
- de afnamegewogen Day-Ahead-prijs steeg van `€72,05/MWh` naar
  `€103,12/MWh`: `+43,14%`;
- de retrospectieve dynamische variabele sensitivity steeg daardoor van
  `€1.709,17` naar `€2.396,60`: `+40,22%`.

De bestaande batterij werkte consistent: de verhouding ontladen/laden ligt in
de drie lokale jaren tussen `84,59%` en `85,07%`. De beschikbare detaildata van
mei tot december 2025 wijst erop dat slechts circa `22,44 kWh`, of `1,26%` van
de waargenomen laadenergie, mogelijk uit het net kwam. Dit is een afleiding uit
gelijktijdige vermogensstromen en geen bewezen controllerlog.

Een extra virtuele batterij op het resterende netprofiel heeft wel positieve,
maar beperkte waarde. Voor `14,24 kWh` extra bruikbare capaciteit bedraagt de
gemiddelde perfecte bovengrens `€84,21/jaar`; expliciete prijsbewuste netlading
voegt gemiddeld slechts `€5,99/jaar` toe boven laden uit resterend PV-overschot.
Dit ondersteunt geen investeringsbeslissing zonder installatieprijs,
levensduur, forecastfouten en een realistische regelstrategie.

## Datakwaliteit

| Controle | Resultaat |
|---|---:|
| Fluvius-kwartieren | `105.216` |
| Bruikbare kwartieren | `105.210` |
| Geschatte kwartieren | `304` |
| Onbeschikbare kwartieren | `6` |
| Ontbrekende ENTSO-E-prijzen | `0` |
| Sunny Portal-dagdelen 2023-2025 | `1.096` |
| Ontbrekende Sunny Portal-dagen | `0` |
| Dubbele lokale Sunny-tijden bij wintertijd | `12`, behouden als fysieke intervallen |

Het eerste lokale jaar bevat een schrikkeldag en daarom `35.136`
kwartieren. De twee normale lokale jaren bevatten elk `35.040` kwartieren. De
zes lege Fluvius-volumes zijn niet naar nul omgezet en zijn uitgesloten uit de
optimalisatie.

## Jaarvergelijking energie en prijs

| Lokaal jaar | Netafname | Netinjectie | Netto-afname | Winterafname | Gewogen afnameprijs | Negatieve kwartieren | Retrospectieve variabele kost |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2023-2024 | `7.820,473 kWh` | `1.471,811 kWh` | `6.348,662 kWh` | `6.925,057 kWh` | `€72,05/MWh` | `1.836` | `€1.709,17` |
| 2024-2025 | `8.411,868 kWh` | `1.268,425 kWh` | `7.143,443 kWh` | `6.706,811 kWh` | `€101,97/MWh` | `2.032` | `€2.111,99` |
| 2025-2026 | `9.510,180 kWh` | `989,269 kWh` | `8.520,911 kWh` | `7.521,922 kWh` | `€103,12/MWh` | `1.344` | `€2.396,60` |

De winter vertegenwoordigt respectievelijk `88,55%`, `79,73%` en `79,09%`
van de jaarlijkse afname. Goedkope of negatieve kwartieren bestaan dus wel,
maar het grootste financiële risico blijft het hoge wintervolume tijdens een
periode met gemiddeld hogere marktprijzen.

Over de volledige drie jaar:

- netafname: `25.742,521 kWh`;
- netinjectie: `3.729,505 kWh`;
- netto-afname: `22.013,016 kWh`;
- negatieve marktprijskwartieren: `5.212`;
- retrospectieve dynamische variabele sensitivity: `€6.217,77`.

Deze kost is een constante-tariefgevoeligheid met formuleversie
`ECOPOWER_DBS_2026-08-01`. Ze reconstrueert niet de historische contracten en
bevat niet alle vaste factuurcomponenten.

## Driejarige gereconcilieerde tariefsensitivity

Een privacy-safe maandledger bevat `36` perioden uit de aangeleverde DSMR-
schermexport. De negen Home Assistant-afnameprijzen voor januari tot en met
september 2026 stemmen ermee overeen. De DSMR-vaste dagkosten worden in beide
scenario's gelijk gehouden; het dynamische abonnement wordt apart toegevoegd.

| Lokaal jaar | Geconfigureerd historisch | Dynamische sensitivity | Dynamisch minus historisch | Classificatie |
|---|---:|---:|---:|---|
| 2023-2024 | `€2.692,59` | `€2.145,37` | `€-547,23` | `RATE_RECONCILED` |
| 2024-2025 | `€2.667,02` | `€2.571,42` | `€-95,60` | `RATE_RECONCILED` |
| 2025-2026 | `€3.040,54` | `€2.877,36` | `€-163,17` | `RATE_RECONCILED` |
| Drie jaar | `€8.400,15` | `€7.594,15` | `€-806,00` | `RATE_RECONCILED` |

Het gemiddelde gereconcilieerde voordeel is `€268,67/jaar`. Dit is nog geen
component-complete factuurvergelijking: de vaste dagkosten zijn wel opgenomen,
maar niet uitgesplitst naar leverancier, capaciteit, netbeheer, heffingen en
btw. Het eerste jaar omvat bovendien een leveranciersovergang van eMobility
naar Ecopower.

## Werkelijk batterijgedrag

| Lokaal jaar | Bron en dekking | Geladen | Ontladen | Ontladen/laden | Equivalent volledige cycli |
|---|---|---:|---:|---:|---:|
| 2023-2024 | Sunny Portal, `366` volledige dagen | `2.936,040 kWh` | `2.483,740 kWh` | `84,59%` | `174,42` |
| 2024-2025 | Sunny Portal, `365` volledige dagen | `3.194,110 kWh` | `2.717,110 kWh` | `85,07%` | `190,81` |
| 2025-2026 | Sunny `92` dagen + HA `5.833` uren | `2.849,651 kWh` | `2.422,675 kWh` | `85,02%` | `170,13` |

De verhouding ontladen/laden is een lange-termijn-cross-check en geen
laboratoriumrendement: begin- en eind-SOC zijn niet gecorrigeerd. De drie jaren
liggen wel dicht bij de eerder afgeleide centrale round-tripwaarde van
`85,3727%`.

De Sunny Portal-vermogensdata van `2025-05-29` tot en met `2025-12-31` bevat
`1.784,108 kWh` laadenergie en `1.516,393 kWh` ontlaadenergie. De afgeleide
mogelijke netlading is `22,438 kWh`. In oktober-december samen is dat circa
`5,368 kWh`; de bestaande installatie vertoont dus geen sterke winterse
prijsarbitrage in deze detailperiode.

## Virtuele extra batterij op het resterende netprofiel

De onderstaande resultaten voegen een extra batterij toe na het reeds gemeten
historische batterijgedrag. Ze zijn dus geen heroptimalisatie van de bestaande
batterij en tellen de bestaande zelfconsumptiewinst niet opnieuw mee.

Vaste modelparameters:

- extra bruikbare capaciteit: `5`, `10` of `14,24 kWh`;
- laad- en ontlaadvermogen: maximaal `5 kW`;
- round-trip-efficiëntie: `85,3727%`, symmetrisch verdeeld;
- degradatiekost: `€0,06` per ontladen kWh;
- batterij-export: verboden in deze residuele vergelijking;
- SOC-stap: `0,25 kWh`;
- perfecte kennis van prijzen en resterende netvraag;
- netladen begrensd op de historische maandpiek plus `1 kW`.

### Netto jaarwaarde per extra capaciteit

| Extra bruikbaar | 2023-2024 | 2024-2025 | 2025-2026 | Gemiddeld per jaar |
|---|---:|---:|---:|---:|
| `5,00 kWh` | `€33,06` | `€52,20` | `€52,40` | `€45,89` |
| `10,00 kWh` | `€53,37` | `€73,77` | `€77,46` | `€68,20` |
| `14,24 kWh` | `€65,98` | `€90,45` | `€96,19` | `€84,21` |

De optimizer mag bij de prijsbewuste variant terugvallen op de PV-only
planning wanneer netladen na piek- en degradatiekosten slechter is. Daardoor is
de gerapporteerde beste variant nooit slechter dan uitsluitend PV-overschot.

### Specifiek effect van prijsbewuste netlading

| Extra bruikbaar | 2023-2024 | 2024-2025 | 2025-2026 | Gemiddeld per jaar |
|---|---:|---:|---:|---:|
| `5,00 kWh` | `€0,00` | `€0,00` | `€0,00` | `€0,00` |
| `10,00 kWh` | `€0,00` | `€0,00` | `€4,14` | `€1,38` |
| `14,24 kWh` | `€2,80` | `€3,33` | `€11,84` | `€5,99` |

Er zijn dus winters waarin goedkoop laden en later duur verbruiken technisch
waarde toevoegt. Na efficiëntieverlies, degradatie en piekeffect is die
marginale jaarwaarde in deze perfecte bovengrens echter klein. Voor
`14,24 kWh` extra opslag bedroeg de netlading `307,57`, `584,81` en
`751,00 kWh`, maar de bijkomende financiële waarde bleef beperkt tot maximaal
`€11,84` in één jaar.

## Interpretatie voor beslissingen

1. `VERIFIED`: de netafname stijgt, de injectie daalt en het meest recente jaar
   heeft zowel het hoogste volume als de hoogste dynamische kost.
2. `VERIFIED_WITH_LIMITATIONS`: de bestaande batterij werkt over de drie jaren
   consistent rond `85%` ontladen/laden.
3. `INFERRED`: de beschikbare Sunny-detailperiode toont nauwelijks netlading;
   de bestaande SMA-regeling lijkt vooral op PV-zelfconsumptie gericht.
4. `UPPER BOUND`: goedkope winterse netlading kan waarde toevoegen, maar
   gemiddeld slechts circa `€5,99/jaar` voor `14,24 kWh` extra capaciteit boven
   de PV-only-bovengrens.
5. `NO INVESTMENT CASE`: de gemiddelde totale perfecte waarde van
   `14,24 kWh` extra opslag is `€84,21/jaar`, nog vóór aanschaf, financiering,
   onderhoud, capaciteitsveroudering en forecastfouten.
6. `NO CONTROL`: er is geen contract gewijzigd en er is geen Home Assistant-,
   SMA-, Smappee- of batterijwrite uitgevoerd.
7. `SENSITIVITY ONLY`: de driejarige contractwaarde is richtinggevend en blijft
   ongeschikt als definitief contractadvies tot de historische componenten zijn
   gereconcilieerd.

## Grenzen

- Fluvius toont alleen de resterende netstroom na historische batterijwerking.
- Volledige bestaande-batterijdispatch is voor 2023 en 2024 alleen op dagbasis
  beschikbaar.
- De periode `2026-01-01` tot `2026-01-21` mist gedetailleerde batterijstromen.
- Perfect foresight overschat een werkelijk uitvoerbare Day-Ahead-strategie.
- De capaciteitspiek wordt wel op kwartierdata berekend, maar de gebruikte
  tariefcoëfficiënt blijft een modelparameter en geen factuurreconstructie.
- De huidige dynamische formule wordt retrospectief constant toegepast.

Machineleesbare samenvatting:
`docs/evidence/multiyear-energy-battery-summary-2023-10-01_2026-10-01.json`.

Beslisgericht scenario-overzicht met piekgrenzen van `7`, `8` en `10 kW`:
`docs/evidence/SCENARIO_OPTIONS_OVERVIEW_2023-10_TO_2026-09.md`.

Volledige lokale output:
`data/raw/multiyear-energy-battery-comparison-2023-10-01_2026-10-01.json`.
