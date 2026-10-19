# Energy System Inventory

Status: voorlopige fase-1-inventaris  
Gerelateerde tickets: P1-002 t/m P1-006  
Laatst bijgewerkt: 2026-09-28

## Bewijsniveaus

- `VERIFIED`: rechtstreeks gecontroleerd via typeplaat, read-only systeemoutput, officiële configuratie-export of reproduceerbare meting.
- `OWNER CONFIRMED`: expliciet bevestigd door de eigenaar, maar nog niet onafhankelijk technisch gecontroleerd.
- `INFERRED`: afgeleid uit indirect bewijs; de afleiding blijft expliciet vermeld.
- `UNKNOWN`: onvoldoende betrouwbare informatie beschikbaar.
- `REQUIRES TESTING`: identificatie is bekend, maar gedrag of compatibiliteit moet nog worden getest.

## Systeemoverzicht

| Component | Huidige informatie | Bewijsniveau | Belangrijkste open punt |
|---|---|---|---|
| PV-array | `8,5 kWp` geregistreerd: 3,2 kWp + 5,3 kWp | VERIFIED | Panelen, strings, oriëntatie en schaduw |
| PV-omvormers | SMA `SB3.0-1AV-41` 3 kW AC en `SB5.0-1AV-41` 5 kW AC, beide firmware `4.10.10.R` | VERIFIED | Modbusverschil, curtailmentgedrag en Home Manager-setpoints testen |
| PV-productie | 2023 circa 8.699 kWh; 2024 circa 7.873 kWh | OWNER CONFIRMED | Bron, meetpunt en kalenderjaarvolledigheid |
| Batterij-omvormer | SMA `SBS5.0-10`, firmware `4.07.31.R` | VERIFIED | Batterij, actieve modus, interfaces en setpointconfiguratie |
| Batterij | LG RESU16H Prime, nominale capaciteit 16 kWh, BMS firmware `23.11.0.R`; HA `Battery Capacity Total` 89% | VERIFIED voor model/capaciteit/BMS/entitywaarde; INFERRED als SoH | Werkelijke bruikbare capaciteit, actuele SOC en betekenis van `Battery Capacity Total` |
| Energiemanager | SMA Home Manager 2, firmware `2.19.1.R` | VERIFIED | Portalomgeving, actieve optimalisaties en dynamische prijsconfiguratie |
| Digitale meter | Aanwezig; kwartierwaarden in Mijn Fluvius actief; huidig regime `SMR1`; bij dynamisch `SMR3` | OWNER CONFIRMED, inclusief Ecopower-regimebevestiging via eigenaar | Metermerk/model en firmware blijven onbekend |
| EV | Kia EV6 GT-Line facelift RWD, MY26 | OWNER CONFIRMED | Batterijvariant, AC-laadconfiguratie en connectiviteit |
| Laadpaal | Smappee EV Wall Home; `smart`; Charging Controller max `32 A`; Grid-drempel `5,5 kW`; offline fallback `8 A` | VERIFIED | Chargerfasegedrag, CT-topologie, OCPP en load-balancingtest |
| Home Assistant | SMA- en Smappee-entities live read-only gevalideerd | VERIFIED voor onderzochte entities | Volledige grid-, PV-, house-, prijs- en voertuig-inventaris |
| Leverancier | Ecopower Groene Burgerstroom; particulier `6%` btw; Fluvius West; augustus 2026 afname-energiecomponent `€0,1526/kWh` en injectie `€0,0406/kWh`[38] | Tariefkaart VERIFIED; product/netgebied/btw OWNER CONFIRMED | Contractstartdatum, meterregime, tariefversies buiten augustus en factuurreconciliatie |
| Netaansluiting | `Driefasig – Delta`, `2 × 40 A` | OWNER CONFIRMED; Smappee-configuratie VERIFIED | CT-topologie en live meet-/regelgedrag |

## PV

### VERIFIED via SMA-apparaatbeheer en parameterexports

- SMA `SB3.0-1AV-41`:
  - firmware `4.10.10.R`;
  - communicatiemodule `4.00.7.R`;
  - nominaal AC-vermogen `3 kW`;
  - geregistreerd PV-generatorvermogen `3,2 kWp`;
  - fase `L2`;
  - Modbus TCP uit;
  - actiefvermogensmodus `Externe instelling werkelijk vermogen`.
- SMA `SB5.0-1AV-41`:
  - firmware `4.10.10.R`;
  - communicatiemodule `4.00.7.R`;
  - nominaal AC-vermogen `5 kW`;
  - geregistreerd PV-generatorvermogen `5,3 kWp`;
  - fase `L1`;
  - Modbus TCP aan op poort 502, Unit ID 3;
  - actiefvermogensmodus `Externe instelling werkelijk vermogen`.
- Totaal geregistreerd PV-generatorvermogen: `8,5 kWp`; totaal nominaal AC-vermogen: `8 kW`.
- Beide omvormers tonen eerste ingebruikname `10-5-2022`, SMA ShadeFix aan, automatische updates aan, Wi-Fi uit en ongecodeerde Speedwire-communicatie.
- Inverter-lokale begrenzing aan het netaansluitpunt staat bij beide uit; centrale regeling door de Home Manager is daarmee architecturaal plausibel maar nog te testen.

### OWNER CONFIRMED

- Ongeveer 8,5 kWp geïnstalleerd vermogen.
- Referentieproductie: circa 8.699 kWh in 2023 en circa 7.873 kWh in 2024.
- Home Assistant-bronalias `pv_power` is genoemd; het live entity-ID blijft privé.

### Nog te valideren

- Merk, model, aantal en nominaal vermogen van panelen.
- Aangesloten DC-vermogen per omvormer en stringtopologie.
- AC/DC-topologie, strings, oriëntaties, hellingshoeken en eventuele schaduw.
- Of bronalias `pv_power` omvormeroutput, totale installatieoutput of een afgeleide waarde meet.
- Lokale Webconnect/API-, Modbus TCP/RTU- of Speedwire-configuratie.
- Regelbaar actief vermogen, zero-export en curtailment.
- Relatie met SMA Home Manager 2.0.

### Validatiebewijs

- Foto of gesaniteerde tekst van ieder omvormertypeplaatje.
- Firmwareversie en schermafbeelding/export van lokale netwerk- of portalconfiguratie.
- Single-line diagram of eenvoudige beschrijving van strings en AC-aansluiting.
- Energy Dashboard- of portalexport die jaarproductie bevestigt.

## Batterij en SMA Sunny Boy Storage

### VERIFIED

- Exact model: SMA `SBS5.0-10`.
- Geïnstalleerde firmware: `4.07.31.R`.
- Datum eerste ingebruikname in apparaatbeheer: `10-5-2022`.
- De SBS staat in het getoonde apparaatbeheer onder de Home Manager geregistreerd.
- Batterijmanagementsysteem: LG Chem `RESU16H Prime`.
- Nominale batterijcapaciteit in SBS-parameterexport: `16000 Wh`.
- BMS-firmware: `23.11.0.R`.
- Battery Interface-module software: `1.07.3.R`.
- Geconfigureerd maximaal laadvermogen: `5000 W`.
- Geconfigureerd maximaal ontlaadvermogen: `5300 W`.
- Minimale breedte reservestroombereik: `0%`.
- Ondergrens diepontladingsbeschermingsbereik vóór uitschakeling: `2%`.
- Minimale breedte diepontladingsbeschermingsbereik: `3%`.
- Breedte bereik voor behoud van acculaadtoestand: `3%`.
- Algemene bedrijfstoestand tijdens export: `Parallel bedrijf van het netwerk`.
- Bedrijfsmodus actief vermogen: `Externe instelling werkelijk vermogen`.
- Timeout externe actiefvermogensinstelling: `600 s`; fallbackmodus: `Waarden behouden`.
- Modbus TCP-server: uitgeschakeld; geregistreerde poort `502`, Unit ID `3`.
- Gebruikte energieteller: `SMA Energy Meter` via Speedwire.
- Landnorm: `[BE] C10/11/2012`; SBS toegewezen aan fase `L2`.

### OWNER CONFIRMED

- In dienst sinds `10-5-2022`.
- Gerapporteerde State of Health: 89%; bron en meetmoment nog te verifiëren.
- Home Assistant heeft totalen voor laden en ontladen.

### INFERRED / REQUIRES TESTING

- De modus `Externe instelling werkelijk vermogen` is consistent met centrale regeling door de SMA-installatie, maar de parameterexport bewijst nog niet welk apparaat op ieder moment de setpoints schrijft.
- `Waarden behouden` bij ontbrekende externe setpoints kan relevant zijn voor stale-commandrisico; gedrag bij communicatieverlies moet vóór externe control worden getest.
- De raw SOC-bereikparameters mogen niet zonder SMA-semantiek worden samengevoegd tot één veronderstelde minimum-SOC.

### UNKNOWN / REQUIRES TESTING

- Actuele SOC tijdens validatie en bron van de gerapporteerde SoH.
- Werkelijk beschikbare energie bij de huidige SoH; 89% wordt niet zonder capaciteitsmeting rechtstreeks als bruikbare kWh geïnterpreteerd.
- Round-trip efficiency op basis van fabrikantdata én werkelijke metingen.
- Garantievoorwaarden en throughput/cyclingbeperkingen.

### Centrale onderzoeksvraag

Actieve arbitrage heeft nu een `VERIFIED` SBS-, batterij- en BMS-basis. Native regeling blijft `REQUIRES TESTING` totdat Home Manager-portalconfiguratie, dynamische prijsfunctie, actuele SOC-strategie en setpointownership zijn bevestigd. Externe Home Assistant-control blijft niet toegestaan; Modbus TCP staat momenteel uit.

## SMA Home Manager 2.0

### VERIFIED

- Product: SMA Sunny Home Manager 2.0.
- Firmware: `2.19.1.R`; besturingssysteem `4.05.0.R`.
- Bedrijfsmodus: `System Manager`.
- Meetinterval: `1000 ms`.
- Datum eerste ingebruikname: `10-5-2022`.
- Zelfverbruikmodus: aan.
- Geprioriteerd batterijladen: uit.
- Geprognotiseerd batterijladen: uit.
- Verkorte prognoseperiode: uit.
- Vereiste batterij-SOC voor forecast charging: `0%`.
- Peak shaving: uit.
- EEBUS-begrenzing van verbruik en productie: uit.
- Modbus TCP-server: uit; geen Modbus-apparaten geconfigureerd.
- Externe richtwaarde werkelijk vermogen via lokale interface: uit.
- Dynamische begrenzing op het netaansluitpunt: aan; geconfigureerde waarde `0 W`; semantiek/werkelijk gedrag vereist validatie.
- Automatische updates: aan; Speedwire-codering: uit.
- Zichtbaar geregistreerde onderliggende apparaten:
  - `SB3.0-1AV-41`;
  - `SB5.0-1AV-41`;
  - `SBS5.0-10`;
  - `VWL 55/3 A 230V`, producttype `Smart Appliance`.

### VERIFIED - energy management en tarief

- Optimization target: `Economisch`.
- Dynamisch stroomtariefpagina aanwezig met:
  - tarieftype `Dynamisch`;
  - markt `Day-Ahead`;
  - regio `BE`;
  - bronvermelding `Epex-Spot SE`;
  - zichtbare kwartierprijs, bijvoorbeeld interval `11:00–11:15`;
  - prijs expliciet weergegeven zonder toeslag.
- De terugleververgoeding-configuratie toont tarieftype `Vast` en `€0,02/kWh`.
- De interface vraagt een totale terugleververgoeding inclusief kosten, netwerkkosten en belastingen.
- Forecast-based, geprioriteerd en tijdvenstergestuurd batterijladen: inactief.
- Peak shaving: inactief.
- De toeslagconfiguratie staat op `Vereenvoudigd`; in de aangeleverde bewerkingsweergave was geen vaste toeslagwaarde zichtbaar.

### INFERRED / REQUIRES TESTING

- De Home Manager is aantoonbaar de System Manager en de PV-/batterijomvormers staan in externe actiefvermogensmodus. Dit ondersteunt SMA als huidige actieve controller, maar commando-ownership moet nog operationeel worden bevestigd.
- De dynamische marktfeed en economische optimalisatiedoelstelling zijn aanwezig, maar de ingebouwde SHM2-batterijfuncties gebruiken ze momenteel niet omdat forecast-, priority- en time-window charging inactief zijn.
- SMA Premium/Energy Maximizer is voor de huidige Home Manager 2.0-topologie `NIET VAN TOEPASSING`; de relevante route is de ingebouwde SHM2-optimalisatie.[25][26][27]
- De portalpagina toont actuele kwartierdata, maar geen expliciete opgeslagen/actief-status; operationeel gebruik moet via gedrag of portalstatus worden bevestigd.
- De eenvoudige toeslagweergave bewijst niet dat de Ecopower-formule `1,02 × EPEX + €4/MWh` exact wordt gemodelleerd.
- De terugleververgoeding staat als vast `€0,02/kWh` geconfigureerd. SMA schrijft voor een variabele vergoeding een gemiddelde voor en adviseert bij dynamische stroomtarieven een lage vaste terugleververgoeding vanwege zeer lage of negatieve marktprijzen.[29]
- Deze vaste proxy is dus een ondersteunde SHM2-ontwerpkeuze, maar modelleert de Ecopower-kwartierformule niet exact en vervangt geen shadow billing.
- SMA's functiematrix toont voor SHM2 geen prijsgebaseerde vermogensreductie bij negatieve tarieven; dit blijft een relevante beperking voor fysieke injectiesturing.[26]
- De combinatie `dynamische begrenzing aan`, `0 W` en externe setpointmodus kan op zero-export of een centrale limiet duiden. Dit wordt niet als bewezen zero-export geregistreerd zolang werkelijk injectiegedrag niet is gecontroleerd.

### UNKNOWN

- Exacte portal-/tenantnaam en of dit Sunny Portal powered by ennexOS is.
- Of beide tariefconfiguraties definitief opgeslagen en actief gekoppeld zijn.
- Of `€0,02/kWh` overeenkomt met het huidige Ecopower-contract en vanaf welke datum.
- Reden waarom forecast-based battery charging momenteel inactief is.

## Net en meter

### VERIFIED via Smappee-configuratiescreenshots

- Grid-configuratie: `Driefasig – Delta`.
- Geconfigureerde maximale stroom/hoofdstroomonderbreker: `2 × 40 A`.
- Maximumcapaciteitsdrempel: actief op `5,5 kW`.
- Getoonde gemiddelde 15-minutenverbruikspiek: `7,50 kW`.
- Grid-CT-kanalen zichtbaar op `L1` en `L2`; meetvelden stonden tijdens de screenshots op `---`.
- Een geregistreerde `Solid Core 3-phase CT` is aanwezig, firmware `1.36`.
- De app waarschuwt dat de `5,5 kW`-drempel tijdens offline EV-laden niet gegarandeerd wordt.

### Beschikbaar in Home Assistant

- Private bronalias `grid_import_power` voor actueel importvermogen.
- Private bronalias `grid_export_power` voor actueel exportvermogen.
- Smappee-gridentities voor vermogen, energie, stroom en spanning zijn live aanwezig; volledige semantiek en historie worden nog gevalideerd.

### OWNER CONFIRMED

- De eigenaar bevestigt dat de fysieke netaansluiting en hoofdbeveiliging volledig overeenkomen met de Smappee-configuratie: `Driefasig – Delta`, `2 × 40 A`.

### INFERRED / REQUIRES TESTING

- Het is UNKNOWN waarom slechts twee Grid-CT-kanalen zichtbaar zijn en waarom de actuele waarden `---` waren.
- Metermerk/model en firmware blijven onbekend; langdurige bronreconciliatie blijft open.
- Kwaliteit bij uitval/herstart, cumulatieve energietellers en reconciliatie tussen DSMR, Smappee en SMA blijven REQUIRES TESTING.

## EV en laadpaal

### Voertuig

- Kia EV6 GT-Line facelift RWD, modeljaar 2026.
- Exacte batterijvariant, VIN-afhankelijke opties en connected-servicesstatus zijn niet vastgelegd.

### Laadpaal - OWNER CONFIRMED

- Merk/model: Smappee EV Wall Home.
- Home Assistant-integratie aanwezig.

### Laadpaal - VERIFIED via read-only MCP

- Actieve integratie: HACS custom platform `smappee_ev`, versie `2026.9.1`; serienummers en locatie-ID's zijn gemaskeerd.[33]
- MQTT-connected; station beschikbaar; laadstatus bij validatie `stopped` en EVSE-status `available`.
- Modus `smart`; selecteerbare modi `standard`, `smart`, `solar`.
- Connectormaximum `32 A`; regelbaar bereik `6–32 A`; actuele laadstroomlimiet `6 A`.
- Capacity-instelling `5,5 kW`; offline failsafe `8 A`; offline laden aan; minimum surplus `100%`.
- Overload-/hoofdstroomonderbrekerstate `40 A`; de Smappee-app bevestigt dat dit de Grid-configuratie `2 × 40 A` vertegenwoordigt. De custom entitymetadata met maximum `32 A` vermengt dit onduidelijk met de Charging Controller-limiet.
- Actueel vermogen `2 W` en cumulative connector energy `12722,415 kWh` op het validatiemoment.
- Per-fasestroom, totaalstroom, laadvermogen, sessie-energie, cumulatieve energie, laadstatus en controlentities zijn beschikbaar.
- De directe charger power/current/energy-entities hebben in de gecontroleerde vensters geen 24-uurs recorderhistoriek of 30-daagse LTS.
- De sessie-entity exposeert privacygevoelige RFID-, gebruikers- en billingattributen; deze worden niet in Git vastgelegd.

### Laadpaal - VERIFIED via Smappee-appscreenshots

- Grid staat geconfigureerd als `Driefasig – Delta` met `2 × 40 A`.
- De actieve Grid-maximumcapaciteitsdrempel is `5,5 kW`; dit is geen charger-rating. De app toont een gemiddelde 15-minutenpiek van `7,50 kW`.
- Charging Controller firmware `2.36`; maximale ondersteunde laadstroom `32,0 A`.
- Smappee Connect firmware `EC 3.92`; Ethernet en wifi worden als opties genoemd, actieve methode UNKNOWN.
- Power Box firmware `1.76`; CT Hub `1.02`; Solid Core 3-phase CT `1.36`; RFID-lezer `1.72`.
- Laadstation is als door het net gemeten toestel geconfigureerd; zichtbare CT-kanalen op `L1` en `L2`.
- Offline laden staat aan met vaste failsafe `8 A`; automatische overbelastingsbeveiliging is tijdens offline laden expliciet uitgeschakeld.
- Smappee ondersteunt in de app dynamische tarieven, maar concrete activering/waarden zijn niet zichtbaar en heffingen/andere kosten worden niet meegerekend.

### INFERRED / REQUIRES TESTING

- Smappee specificeert voor EV Wall Home maximaal `7,4 kW` enkelfasig of `22 kW` driefasig; de fysieke Grid-aansluiting `Driefasig – Delta`, `2 × 40 A` is OWNER CONFIRMED. Het werkelijke fasegebruik van de charger tijdens een laadsessie vereist nog een meettest.[34][35]
- Native Smappee `smart` plus de actieve maximumcapaciteitsdrempel wijzen op Smappee als actieve laad- en overbelastingscontroller. Home Assistant-control blijft verboden totdat ownership en fallback apart zijn goedgekeurd.
- De HA-state `40 A` correspondeert met de Grid-configuratie, terwijl de entitymetadata `32 A` als maximum toont; dit is een custom-integration-semantiekprobleem, geen aangetoonde elektrische inconsistentie.
- OCPP `1.6J` is modelmatig beschikbaar, maar activatie op deze installatie is UNKNOWN.[34]
- Lokale API/Modbus, werkelijk regelgedrag, exacte CT-topologie en eventuele SMA-koppeling blijven UNKNOWN.

## Home Assistant

### Genoemde entities

| Domein | Entity | Waarschijnlijk doel | Validatiestatus |
|---|---|---|---|
| PV | `pv_power` (private alias) | Actueel PV-vermogen | Te verifiëren |
| Grid | `grid_import_power` (private alias) | Actueel importvermogen | Te verifiëren |
| Grid | `grid_export_power` (private alias) | Actueel exportvermogen | Te verifiëren |
| House | Template `Netto Huisverbruik` | Afgeleid huisvermogen | Definitie vereist |
| Battery | Charge/discharge total sensors | Cumulatieve batterij-energie | Entity-ID's en semantiek vereist |

## Contract en marktdata

- Leverancier: Ecopower.
- Exact huidig product, startdatum, actuele tariefkaart en factuurstructuur ontbreken.
- Digitale-meter- en meetregimegegevens moeten worden bevestigd voordat kwartier- of uurprijzen op werkelijk verbruik worden toegepast.

## INFORMATION_REQUIRED_FROM_OWNER

### P0 - nodig voor betrouwbare fase-1-conclusies

1. Verklaring of installateurdocumentatie voor de Grid-CT-topologie op L1/L2 beschikbaar is.
2. Exact huidig Ecopower-product plus actuele tariefkaart of gesaniteerde factuur.
3. Digitale-meter-/meetregimebevestiging en beschikbaarheid van gevalideerde Fluvius-kwartierwaarden.
4. Aanvullende read-only Home Assistant-inventaris voor grid, PV, house, tarieven en voertuig.
5. Actuele batterij minimum-/reserve-SOC en portalstrategie.
6. Smappee OCPP-activeringsstatus en bevestiging van de actieve internetverbinding indien relevant.

### P1 - nodig voor simulatie en ontwerp

1. Minstens twaalf maanden import/export op de fijnst beschikbare resolutie.
2. PV-, batterij- en EV-laadhistoriek op 5- of 15-minutenresolutie indien beschikbaar.
3. Bestaande `Netto Huisverbruik`-template en gebruikte bronentities.
4. Voorbeelden van bestaande custom dashboards en gewenste mobiele/desktopweergave.
5. Gewenst normaal EV-target-SOC, typische vertrektijden en minimale noodreserve.
6. Comfort- en levensduurrandvoorwaarden voor batterijcycli.

### Veilige verzamelregels

- Deel geen wachtwoorden, API-tokens, herstelcodes of volledige back-ups.
- Masker klant-, meter-, contract-, serienummer- en VIN-gegevens wanneer ze niet functioneel nodig zijn.
- Gebruik waar mogelijk tekstexports met entity-ID, state, attributen en statisticsmetadata.

## Sources

[25] https://www.sma.de/en/products/energy-management/energy-maximizer
[26] https://manuals.sma.de/SMA-Premium/nl-NL/16915921419.html
[27] https://manuals.sma.de/HM-20-ennexOS/en-US/12563269899.html
[29] https://manuals.sma.de/HM-20-ennexOS/nl-NL/11412423819.html
[33] https://github.com/myny-git/smappee_ev
[34] https://support.smappee.com/hc/en-gb/articles/4402413229844-EV-Wall-Home
[35] https://support.smappee.com/hc/en-gb/articles/5721996814612-Smappee-EV-Line-charging-speeds
[38] https://cdn.nimbu.io/s/4tn7vz5/channelentries/spiilz4/files/1788271546519/202608_gbs_tariefkaart.pdf?w01uqtn=&dl=1 — Ecopower Groene Burgerstroom - tariefkaart augustus 2026
