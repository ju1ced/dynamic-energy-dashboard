# Simulation Plan

Status: Scenario A, offline batterijgevoeligheid en driejarige geconfigureerde tariefsensitivity uitgevoerd; componentreconciliatie blijft open

Gerelateerde tickets: P1-011, P2-002 en P2-007

Laatst bijgewerkt: 2026-10-01

## Doel

Bepalen welk financieel effect voortkomt uit:

1. uitsluitend een ander contract;
2. verschoven EV-laden;
3. slim batterijgebruik;
4. gecombineerde optimalisatie met forecasts.

De simulatie wijzigt geen productiehardware.

De Fluvius-basis omvat nu drie volledige lokale jaarvensters van 2023-10-01
tot 2026-10-01. Samen bevatten ze 105.216 kwartieren, waarvan 304 geschat en
zes onbeschikbaar. P2-007 breidt de prijsreeks en scenariovergelijking exact
naar deze periode uit voordat een meerjarige financiële conclusie wordt getrokken.

## Bevestigde batterijconstraints

- bruikbare capaciteit: `14,24 kWh`;
- extern SOC-bereik: `0–100%`, met intern `3%` veiligheidsbuffer aan beide zijden;
- maximaal laden en ontladen: `5 kW`;
- netladen en batterij-export zijn toegestaan;
- PV en zelfverbruik krijgen voorrang op export;
- een hogere capaciteitspiek is toegestaan wanneer de totale netto-opbrengst
  na verlies, piekkost en degradatie positief blijft.

Uit 5.833 gematchte Home Assistant-uren is voorlopig `85,3727%` round-trip-
efficiëntie afgeleid: 2.654,531 kWh geladen en 2.266,245 kWh ontladen. Het
simulatiemodel splitst dit symmetrisch in `92,3974%` laad- en
ontlaadefficiëntie. Dit blijft `DERIVED` tot een SOC-gecorrigeerde controle.

## Batterijresultaat 2026-01-22 tot 2026-09-30

De gevalideerde overlap bevat 5.814 bruikbare uurintervallen van 6.024 bronuren.
Bij de centrale degradatiekost van `€0,06` per ontladen kWh is het netto verschil
ten opzichte van het werkelijk waargenomen batterijgedrag:

- perfect foresight met batterij-export: `+€88,96`;
- perfect foresight met uitsluitend zelfverbruik: `+€68,46`;
- realistische Day-Ahead-heuristiek: `-€107,73`.

De Day-Ahead-heuristiek verhoogt de benaderde capaciteitspiekkost met `€63,57`.
De perfecte zelfverbruiksvariant veroorzaakt geen batterijgedreven netexport;
de exporttoegestane bovengrens veroorzaakt `131,41 kWh` batterij-export.

Extra bruikbare capaciteit van `5`, `10` of `14,24 kWh` blijft in de geteste
realistische strategie netto negatief. De perfecte zelfverbruiksbovengrens
impliceert eenvoudige 10-jaars geïnstalleerde-kostenplafonds van respectievelijk
`€680,66`, `€1.056,44` en `€1.252,66`. Dit zijn bovengrenzen zonder
discontering, onderhoud of capaciteitsveroudering en geen investeringsadvies.

Evidence:
`docs/evidence/BATTERY_ARBITRAGE_SIMULATION_2026-01_TO_2026-09.md`.

## Vergelijkingslijnen

### Baseline - Werkelijk huidig contract

Werkelijke import en export worden afgerekend met Groene Burgerstroom. Voor tariefversie `ECOPOWER_GBS_2026-08` geldt:[38]

- afname-energiecomponent: `0,5 × 0,17 + 0,5 × 0,13511 = 0,1526` EUR/kWh exclusief btw;
- GSC: `0,011` EUR/kWh exclusief btw;
- WKK: `0,00392` EUR/kWh exclusief btw;
- injectie: `0,5 × 0,02 + 0,5 × (0,9 × 0,07910839 - 0,01) = 0,0406` EUR/kWh exclusief btw;
- particuliere injectievergoeding: vrijgesteld van btw;
- netkosten, capaciteitstarief en heffingen: afzonderlijk volgens netgebied en toepasselijkheid.

De eigenaar bevestigt voor deze aansluiting `Fluvius West` en particulier `6%` btw. Voor een digitale meter vermeldt de augustuskaart daarnaast:[38]

- databeheer: `€17,85/jaar` exclusief btw;
- capaciteitstarief: `€57,10/kW/jaar` exclusief btw;
- afnametarief: `€0,0631937/kWh` exclusief btw;
- uitsluitend-nachttarief: `€0,0565360/kWh` exclusief btw;
- maximumtarief: `€0,3276168/kWh` exclusief btw.

Deze netcomponenten zijn toepasbaar op de owner-confirmed digitale meter. Ecopower bevestigde volgens de eigenaar dat het huidige regime `SMR1` is en bij een eventuele dynamische contractwissel `SMR3` wordt. Het model bewaart netkosten, heffingen en btw afzonderlijk van de leveranciersenergieprijs. De bevestiging is geen toestemming om het contract te wijzigen.

Groene Burgerstroom wijzigt maandelijks. Iedere factuurperiode moet daarom de toepasselijke maandversie gebruiken; de augustuskaart mag niet stilzwijgend op andere maanden worden toegepast.

### Scenario A - Dynamisch, huidig gedrag

Dezelfde werkelijke energiestromen worden geprijsd met het dynamische contract. Dit isoleert het tariefeffect zonder gedragswijziging.

### Scenario B - EV verschoven

Alleen flexibele EV-energie wordt binnen gebruikersconstraints naar goedkopere intervallen verschoven. Huis, PV en batterij blijven gelijk aan baseline voor zover energiebalans dit toelaat.

### Scenario C - Batterij slim gestuurd

Batterijacties worden gesimuleerd binnen SOC-, vermogens-, efficiëntie-, reserve- en throughputconstraints. EV blijft volgens baseline tenzij apart gecombineerd.

### Scenario D - EV + batterij + PV forecast

Gezamenlijke planning gebruikt prijs, PV-forecast, verwachte basislast en EV-behoefte. Resultaten moeten aantonen hoeveel extra waarde forecasting toevoegt.

## Minimale inputdata

| Data | Gewenste resolutie | Vereist |
|---|---|---:|
| Grid import/export energy | Contractinterval, bij voorkeur 15 min | Ja |
| PV energy | Zelfde of fijner | Ja |
| Battery charge/discharge energy | Zelfde of fijner | Ja voor C/D |
| Battery SOC | 5-15 min | Ja voor C/D |
| EV charge energy/power | 5-15 min | Ja voor B/D |
| Huidig contract | Formule + geldigheidsperiodes | Ja |
| Dynamisch contract | Afname- en injectieformule per interval | Ja |
| Day-ahead prijzen | Contractueel gebruikte bron | Ja |
| PV forecast | Tijdreeks + issue time | Voor D |
| Vertrektijd/target/minimum SOC | Per laadsessie | Voor B/D |

## Geselecteerde read-only databronnen

| Datastroom | Bron | Historische dekking | Gebruik |
|---|---|---:|---|
| Grid import/export | Fluvius kwartierexport primair voor factuurperiode; HomeWizard P1 voor recente overlap | Fluvius: 2025-06-01 t/m 2026-05-31 volledig; HA vanaf 2026-01-09 | Scenario A en factuurreconciliatie; HA-delta's later met Fluvius vergelijken |
| PV energy | Som van cumulative SMA-PV-yields | Vanaf 2026-01-22 | Intervaldelta's; cross-check met Smappee |
| Battery energy | SMA cumulative charge/discharge | Vanaf 2026-01-12 | Intervaldelta's voor verlies en throughput |
| Battery SOC/power | SMA measurement entities | Minstens 30 dagen LTS | Constraints en operationele validatie |
| EV charge energy | Smappee cumulative connectorenergy | Vanaf 2026-07-29 | Scenario B/D en sessiereconciliatie |
| EV SOC | Kia UVO primair, Tronity cross-check | Minstens 30 dagen LTS | Start-/eind-SOC en plausibiliteitscheck |
| House power | Gevalideerde energiebalans-template | Minstens 30 dagen LTS | Live kwaliteitscontrole |
| House energy | Afleiden uit Grid, PV en Battery | Vanaf gezamenlijke startdatum | Geen bestaande daily helper gebruiken |
| PV forecast | Solcast | Vanaf 2026-06-10 | Forecastversus-actual; issue time bewaren |
| Huidige contractprijs | DSMR-contractrecords, facturen en HA-maandwaarden | DSMR dekt 2023-10-01 t/m 2026-09-30 zonder contractgaten | OWNER CONFIRMED: voor 2026 zijn de HA-maandwaarden leidend; DSMR blijft cross-check |
| Dynamische prijs | ENTSO-E A44/A01-ingestielaag | Drie lokale jaren; 105.216 kwartieren zonder gaten | Scenario A en P2-007; bestaande jaaroverlap heeft nul prijsverschillen |

De Fluvius-export bevat 35.040 volledige kwartierintervallen voor één factuurjaar, met zowel afname als injectie en zonder gaten na Europe/Brussels-naar-UTC-canonisatie. Daarvan zijn 99 intervallen (`0,282534%`) als `Geschat` gemarkeerd. Dit is de primaire dataset voor Scenario A over 2025-06-01 tot 2026-05-31.

De gemeenschappelijke HA-analyseperiode voor Grid, PV en Battery begint op 22 januari 2026. EV-scenario's beginnen pas op 29 juli 2026; Solcast-evaluatie begint op 10 juni 2026. Daardoor kan het contracteffect over het volledige Fluvius-jaar worden berekend, maar EV-/batterijoptimalisatie alleen over latere overlapperioden.

Een eerste read-only smoke-export over 48 uur leverde voor Grid, PV, Battery en EV telkens 192 kwartieren zonder ontbrekende vijfminutenbuckets, duplicaten of tellerdalingen. Eén foutieve door Home Assistant gerapporteerde PV-`change` werd zichtbaar gemarkeerd; de kwartierwaarde is reproduceerbaar uit opeenvolgende cumulative states afgeleid. Dit valideert de exportmethode, niet de volledige historische reconciliatie.

## Scenario A-resultaat

De offline kostenengine heeft alle 35.040 Fluvius-kwartieren gekoppeld aan een
prijsinterval in het exact uitgelijnde lokale factuurvenster. Tariefversie
`ECOPOWER_DBS_2026-08-01` is bewust retrospectief toegepast op ongewijzigd
historisch gedrag:

- dynamische leverancierscomponent: `€1.074,57` exclusief btw;
- historische leverancierscomponent: `€1.305,56` exclusief btw;
- verschil leverancierscomponent: `€-230,99` exclusief btw;
- volledige tegenberekening: `€2.607,12` versus `€2.853,21` inclusief btw;
- verschil volledige tegenberekening: `€-246,09` inclusief btw;
- 99 geschatte Fluvius-kwartieren blijven zichtbaar en dragen `€+0,20`
  exclusief btw bij aan het verschil;
- 582,356 kWh injectie viel in kwartieren met een negatieve dynamische
  injectieformule.

Dit is geen contractadvies. De tariefkaart geldt vanaf 1 augustus 2026 en wordt
als scenarioformule over een ouder prijs- en verbruiksjaar gebruikt. Een tweede
prijsjaar en actuele voorwaarden blijven nodig voor robuust advies.

Read-only validatie toont dat P1, Smappee en SMA bij een actieve EV-laadsessie binnen circa `0,7–1,2%` dezelfde netbelasting rapporteerden. PV kwam exact overeen en de afgeleide huislast week circa `1,0%` af van Smappee. Deze momentopname ondersteunt de bronselectie, maar vervangt geen kwartierreconciliatie.

Niet gebruiken als simulatiebron:

- `sensor.huis_verbruik_daily`: onvolledige formule en foutieve reset-/state-classsemantiek;
- dagelijkse PV-helper met `total_increasing`: LTS-sommen zijn door resets onbruikbaar;
- bestaande Ecopower-prijshelpers zonder expliciete maand- en bronreconciliatie;
- LTS-`sum` van forecast- of maandpiekstates;
- voertuigcloudvermogen als primaire snelle energiemeter.

## Gevalideerde factuurbaseline 2025-06 tot 2026-05

De bijbehorende Ecopower-factuur is volledig gereconcilieerd met de Fluvius-export:

- afname: `9.161,589 kWh` in CSV versus `9.161,59 kWh` gefactureerd;
- injectie: `1.160,728 kWh` in CSV versus `1.160,74 kWh` gefactureerd;
- totaal exclusief btw: `€2.690,39`;
- btw: `€162,82`;
- totaal inclusief btw: `€2.853,21`;
- facturatiepiek: `5,264 kW` in de detailberekening;
- historische injectievergoeding: `€0,0200/kWh`.

De factuur vermeldt jaarlijkse meterlezing. De baseline wordt daarom gereproduceerd met de twaalf gefactureerde maandvolumes/-prijzen en afzonderlijke factuurcomponenten. De kwartierdata wordt gebruikt voor de dynamische tegenberekening, niet om de historische Groene Burgerstroom-maandprijs achteraf per kwartier te wijzigen.

Privacy-safe detailrapport: `docs/evidence/ECOPOWER_RECONCILIATION_2025-06_TO_2026-05.md`.

## Geversioneerde Ecopower-formule

Voor tariefversie `ECOPOWER_DBS_2026-08-01` geldt per kwartier:[28]

- afname-energiecomponent: `0,00102 × EPEX_DA_EUR_per_MWh + 0,004` EUR/kWh;
- injectie-energiecomponent: `0,00098 × EPEX_DA_EUR_per_MWh - 0,015` EUR/kWh;
- abonnement: `5,00` EUR/maand exclusief btw;
- GSC: `0,011` EUR/kWh exclusief btw;
- WKK: `0,00392` EUR/kWh exclusief btw;
- particuliere terugleververgoeding: vrijgesteld van btw.

Het model bewaart de ruwe EPEX-prijs, afnameformule, injectieformule, GSC, WKK, btw en netcomponenten afzonderlijk. De vaste Sunny Portal-injectiewaarde van `€0,02/kWh` mag niet als proxy voor dit dynamische scenario worden gebruikt.

## Kostmodel

Per interval worden minimaal apart berekend:

- energiecomponent afname;
- leveranciersopslag of formulecomponent;
- energiecomponent injectie;
- nettarieven voor zover volume-/tijdafhankelijk;
- belastingen, heffingen en btw volgens gevalideerde toepasselijkheid;
- vaste kosten pro rata voor rapportage, zonder ze foutief aan optimalisatie toe te schrijven;
- batterijconversieverlies;
- optionele transparante degradatiekost in gevoeligheidsanalyse.

## Energiebalans

Voor ieder interval moet een consistente balans worden nagestreefd:

`PV + grid_import + battery_discharge = house + EV + battery_charge + grid_export + losses`

Meetlocaties en tekenconventies bepalen de exacte formule. Onverklaarde residuen worden opgeslagen als quality metric en niet automatisch weggepoetst.

## Tijd en datakwaliteit

- Canonieke opslag gebruikt tijdzonebewuste timestamps.
- Lokale rapportage gebruikt Europe/Brussels en behandelt zomer-/wintertijd expliciet.
- Ontbrekende markt- of energiedata wordt gemarkeerd; geen stille forward-fill voor facturatie.
- Iedere tariefformule en forecast heeft een versie en geldigheidsdatum.
- Incomplete dagen worden apart gerapporteerd.

## Validatie

Afgerond:

1. Eén volledige Groene Burgerstroom-factuurperiode is binnen afrondingstolerantie gereproduceerd.
2. Geaggregeerde Fluvius-import/-export sluit aan op factuur- en registertotalen.
3. Zomer- en wintertijd zijn in de analyzer getest; 99 geschatte intervallen blijven expliciet gemarkeerd.
4. Nul-/negatieve prijzen, ontbrekende marktdata, cumulatieve dag-/maandverschillen en de 2026-08-tariefformule zijn in de kostenengine getest.
5. Scenario A is over het volledige factuurjaar uitgevoerd zonder ontbrekende prijs- of energie-intervallen.

Nog uit te voeren:

1. Controleer dat scenario B geen energie creëert of verwijdert.
2. Bouw een gevalideerd load-/PV-forecastmodel voor een volgende Day-Ahead-iteratie.
3. Herhaal batterijdispatch op kwartierresolutie met officiële kwartierpieken.
4. Gebruik voor ieder optimalisatiescenario een representatieve overlapperiode met seizoensvariatie.
5. Herhaal Scenario A over alle drie prijsjaren met de DSMR-schermexport en de
   overeenstemmende HA-maandwaarden als historische prijsbron voor 2026.
   `UITGEVOERD ALS RECONCILED_ALL_IN_RATE_SENSITIVITY`; all-in tarieven, vaste
   dagkosten en dynamisch abonnement zijn opgenomen, maar component-complete
   historische billing blijft open.

## Rapportage

Minimaal per dag en maand:

- totale import/export;
- afnamekost en injectieopbrengst;
- netto kost;
- gemiddelde aankoop-/verkoopprijs;
- baseline versus scenario delta;
- cumulatieve delta;
- datadekking;
- aantal verschoven EV-kWh;
- batterijthroughput en verlies;
- forecastfout voor scenario D.

## Go/no-go voor contractwissel

Een contractadvies volgt pas wanneer:

- formules en factuurreconciliatie gevalideerd zijn;
- voldoende representatieve data is geanalyseerd;
- gevoeligheid voor prijsjaar, gedrag en ontbrekende data is getoond;
- voordeel zonder optimalisatie en voordeel door optimalisatie afzonderlijk zijn;
- operationele risico's en eventuele investeringen zijn meegerekend.

## Sources

[4] https://www.fluvius.be/nl/factuur-en-tarieven/kwartierwaarden
[28] https://cdn.nimbu.io/s/4tn7vz5/channelentries/ma28q8f/files/1790570062186/20260801_dbs_tariefkaart.pdf?7l4n7vq=
[38] https://cdn.nimbu.io/s/4tn7vz5/channelentries/spiilz4/files/1788271546519/202608_gbs_tariefkaart.pdf?w01uqtn=&dl=1 — Ecopower Groene Burgerstroom - tariefkaart augustus 2026
