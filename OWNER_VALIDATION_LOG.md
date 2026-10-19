# Owner Validation Log

Ticket: P1-014  
Status: Done  
Startdatum: 2026-09-28  
Besluitdatum: 2026-09-29  
Phase 2: `GO READ-ONLY PHASE 2`; productiecontrol blijft geblokkeerd

## Bewijsstatussen

- `VERIFIED`: technisch bewijs is rechtstreeks gecontroleerd via typeplaat, read-only systeemoutput, officiële configuratie-export of reproduceerbare meting.
- `OWNER CONFIRMED`: door de eigenaar bevestigd, maar nog niet onafhankelijk technisch gecontroleerd.
- `INFERRED`: afgeleid uit indirect bewijs; moet herkenbaar als afleiding blijven.
- `UNKNOWN`: onvoldoende betrouwbare informatie.
- `REQUIRES TESTING`: identificatie is bekend, maar gedrag of compatibiliteit moet nog read-only of gecontroleerd worden getest.

## Correctieregels

Een wijziging van een eerdere aanname krijgt altijd:

1. oorspronkelijk gegeven en eerdere status;
2. nieuw bewijs en nieuwe status;
3. datum;
4. impact op readiness, architectuur, gaps en vervolgtickets.

## Validatiegroepen

| Groep | Status | Resultaat |
|---|---|---|
| SBS + batterij + Home Manager | Done | Hardware, firmware, configuratie en controllergrenzen vastgelegd; runtime controltests doorgeschoven |
| PV-omvormers | Done | Modellen, firmware, vermogen, fasen en interfacegrenzen vastgelegd |
| EV-laadpaal | Done | Model, firmware, limieten, fallback en open runtimegaps vastgelegd |
| Elektrische aansluiting | Done | Fysieke `Driefasig – Delta`, `2 × 40 A` owner-confirmed |
| Ecopower baseline | Done | Volledig factuurjaar, contractcomponenten en injectie gereconcilieerd |
| Home Assistant discovery | Done | Volledige read-only inventaris en bronhiërarchie |
| Historische data | Done | Fluvius-factuurjaar compleet; HA-overlap blijft Phase 2-ticket |
| Readiness update | Done | Gates, gaps en read-only Phase 2-voorstel vastgelegd |
| Phase 2 Go/No-Go | Done | Eigenaar gaf `GO READ-ONLY PHASE 2` op 2026-09-29 |

## Groep 1 - SBS, batterij en Home Manager

### Bekende uitgangspunten

| Gegeven | Status | Bron |
|---|---|---|
| SMA Sunny Boy Storage / SBS5.0 aanwezig | OWNER CONFIRMED | Oorspronkelijke projectopdracht |
| SMA Home Manager 2.0 aanwezig | OWNER CONFIRMED | Oorspronkelijke projectopdracht |
| Batterij charge/discharge total sensors bestaan in Home Assistant | OWNER CONFIRMED | Oorspronkelijke projectopdracht |
| Exact SBS-model en firmware | VERIFIED | SMA-apparaatbeheer: `SBS5.0-10`, firmware `4.07.31.R` |
| Batterijmerk en model | VERIFIED | SBS-parameterexport: LG Chem `RESU16H Prime` |
| Batterijcapaciteit | VERIFIED | `16000 Wh` in SBS-parameterexport |
| Batterij ingebruikname | VERIFIED | SBS-apparaateigenschappen: `10-5-2022` |
| Batterij SoH | OWNER CONFIRMED | 89%; bron, timestamp en berekeningsmethode nog te verifiëren |
| BMS-versie | VERIFIED | `23.11.0.R` |
| Batterij-interfaceversie | VERIFIED | `1.07.3.R` |
| SBS laad-/ontlaadlimiet | VERIFIED | `5000 W` laden; `5300 W` ontladen |
| SHM-firmware | VERIFIED | SMA-apparaatbeheer: Home Manager 2, firmware `2.19.1.R` |
| Portalomgeving | INFERRED | Sunny Portal-velden zijn aanwezig; exacte `powered by ennexOS`-omgeving nog niet bevestigd |
| Home Manager System Manager-modus | VERIFIED | Apparaateigenschappen |
| Forecast-based battery charging | VERIFIED | Momenteel uit |
| Geprioriteerd batterijladen | VERIFIED | Momenteel uit |
| Peak shaving | VERIFIED | Momenteel uit |
| Dynamische PCC-begrenzing | VERIFIED / REQUIRES TESTING | Aan met `0 W`; betekenis en werkelijk injectiegedrag nog valideren |
| Concrete prijsbewuste forecast-based charging | REQUIRES TESTING | Economisch doel en BE Day-Ahead-feed aanwezig; alle drie batterijlaadoptimalisaties staan uit en Ecopower-opslag/injectie is niet gevalideerd |

### Eerste bewijsresultaat - SMA-apparaatbeheer

Bewijs beoordeeld op 2026-09-28 via een door de eigenaar aangeleverde screenshot. De screenshot is niet in Git opgeslagen. Serienummers waren gemaskeerd/onleesbaar.

| Apparaat | Model/product | Firmware | Eerste ingebruikname | Status |
|---|---|---|---|---|
| Home Manager | Home Manager 2 | `2.19.1.R` | `10-5-2022` | VERIFIED |
| PV-omvormer 1 | `SB3.0-1AV-41` | `4.10.10.R` | `10-5-2022` | VERIFIED |
| PV-omvormer 2 | `SB5.0-1AV-41` | `4.10.10.R` | `10-5-2022` | VERIFIED |
| Batterij-omvormer | `SBS5.0-10` | `4.07.31.R` | `10-5-2022` | VERIFIED |
| Smart appliance | `VWL 55/3 A 230V` | Niet getoond | `1-6-2022` | VERIFIED als geregistreerde apparaatnaam; functie UNKNOWN |

De hiërarchie in apparaatbeheer toont deze vier onderliggende apparaten onder de Home Manager. Communicatieprotocol, IP-adres en online-/storingsstatus waren niet zichtbaar; een `-` in die kolommen bewijst niet dat geen netwerkcommunicatie bestaat.

### Tweede bewijsresultaat - batterijidentificatie

De eigenaar bevestigt:

- LG RESU Prime 16H;
- 16 kWh;
- gekoppeld aan de `SBS5.0-10`;
- in dienst sinds `10-5-2022`;
- gerapporteerde SoH 89%.

Status: `OWNER CONFIRMED`. Het fysieke typeplaatje of een batterijdetailpagina is nog nodig om model, serienummerbereik, BMS-versie en bron/timestamp van SoH naar `VERIFIED` te brengen.

Officiële documentatie ondersteunt de technische plausibiliteit: LG specificeert voor de RESU16H Prime 16,0 kWh bruikbare energie en SMA neemt de RESU 16H Prime op in de goedgekeurde SBS-batterijcombinaties.[19][20]

### Derde bewijsresultaat - SBS-parameterexport en apparaateigenschappen

De eigenaar leverde een read-only SBS-parameterexport en screenshot aan. De lokale bewijsbestanden bevatten persoonlijke account-, installatie-, serienummer-, netwerk- en MAC-gegevens en zijn daarom via `.gitignore` uitgesloten van Git.

VERIFIED zonder gevoelige identifiers over te nemen:

- batterij/BMS: LG Chem `RESU16H Prime`;
- nominale capaciteit: `16000 Wh`;
- BMS-firmware: `23.11.0.R`;
- Battery Interface-module software: `1.07.3.R`;
- maximaal laadvermogen volgens configuratie: `5000 W`;
- maximaal ontlaadvermogen volgens configuratie: `5300 W`;
- reservebereik: `0%`;
- diepontladingsbeschermingsparameters: `2%` ondergrens en `3%` minimumbreedte;
- SOC-behoudsbereik: `3%`;
- algemene toestand tijdens export: `Parallel bedrijf van het netwerk`;
- actiefvermogensmodus: `Externe instelling werkelijk vermogen`;
- externe-setpointtimeout: `600 s`, fallback `Waarden behouden`;
- Modbus TCP-server: uit;
- gebruikte teller: `SMA Energy Meter`;
- landnorm: `[BE] C10/11/2012`;
- SBS fase: `L2`;
- automatische firmware-updates: aan;
- Wi-Fi: uit;
- Speedwire-versleuteling: niet actief.

Interpretatie:

- `Externe instelling werkelijk vermogen` maakt centrale SMA-regeling plausibel, maar identificeert de actieve schrijver niet zelfstandig.
- `Waarden behouden` vereist later een gecontroleerde failure-modeanalyse voordat een ander EMS ooit setpoints zou mogen schrijven.
- De raw SOC-bereikparameters worden niet zonder SMA-semantiek herleid tot één minimum-SOC.
- Modbus staat nu uit; Home Assistant heeft daarmee geen actieve lokale Modbus-schrijfroute naar de SBS.

### Vierde bewijsresultaat - Home Manager en PV-parameterexports

VERIFIED voor Sunny Home Manager 2.0:

- firmware `2.19.1.R`, OS `4.05.0.R`;
- bedrijfsmodus `System Manager`;
- meetinterval `1000 ms`;
- zelfverbruikmodus aan;
- geprioriteerd batterijladen uit;
- geprognotiseerd batterijladen uit;
- verkorte prognoseperiode uit;
- vereiste forecast-charge-SOC `0%`;
- peak shaving uit;
- Modbus TCP-server uit en geen Modbus-apparaten geconfigureerd;
- externe lokale actiefvermogensrichtwaarde uit;
- dynamische begrenzing op het netaansluitpunt aan met `0 W`;
- automatische updates aan en Speedwire-codering uit.

VERIFIED voor PV:

- `SB3.0-1AV-41`: 3 kW AC, 3,2 kWp geregistreerde generator, fase L2, Modbus TCP uit;
- `SB5.0-1AV-41`: 5 kW AC, 5,3 kWp geregistreerde generator, fase L1, Modbus TCP aan;
- totaal: 8 kW nominaal AC en 8,5 kWp geregistreerd DC;
- beide firmware `4.10.10.R`, communicatiemodule `4.00.7.R`, externe actiefvermogensmodus, ShadeFix aan en lokale PCC-begrenzing uit.

Architecturale impact:

- Optie A, SMA Home Manager als batterijoptimizer, is technisch de meest native route maar staat nu niet actief voor forecast charging.
- Optie B, Home Assistant als directe batterijcontroller, past niet bij de huidige ownershipconfiguratie en zou interface-, watchdog- en fallbackwijzigingen vereisen.
- Optie C, SMA bestuurt batterij/PV terwijl Home Assistant monitoring, forecasting, EV en orchestration doet, sluit voorlopig het best aan op de actuele System Manager-structuur. Dit is `INFERRED`, geen definitief besluit.
- De `0 W`-PCC-configuratie mag niet stilzwijgend als zero export worden geïnterpreteerd; dit moet worden vergeleken met portalinstellingen en werkelijk gemeten injectie.

### Vijfde bewijsresultaat - energiemanagement en dynamisch tarief

VERIFIED via screenshots:

- optimalisatiedoel `Economisch`;
- dynamisch tarieftype;
- markt `Day-Ahead`, regio `BE`;
- EPEX Spot-bron;
- zichtbare kwartierprijs, onder meer interval `11:00–11:15`;
- marktprijs expliciet zonder toeslag;
- forecast-based batterijladen inactief;
- geprioriteerd batterijladen inactief;
- tijdvenstergestuurd batterijladen inactief;
- peak shaving inactief;
- toeslagmethode `Vereenvoudigd`; geen ingevulde vaste toeslag zichtbaar in de aangeleverde bewerkingsweergave.

Impact:

- SMA Home Manager beschikt in deze installatie over de prijsfeed en het economische optimalisatiedoel, maar voert op het validatiemoment geen prijsbewuste forecast-based battery charging uit.
- De zichtbare SMA-tariefweergave is niet voldoende voor exacte Ecopower-shadow billing: de formule `1,02 × EPEX + €4/MWh`, injectieformule, vaste kosten, nettarieven en belastingen zijn niet aantoonbaar gemodelleerd.
- Optie A is technisch concreet maar niet actief. Optie C blijft voorlopig het best passend bij de huidige controllergrenzen. Optie B blijft het meest risicovol.

### Zesde onderzoeksresultaat - release notes en SMA Premium

Status: `SUPERSEDED` door het zevende resultaat en `COR-009` hieronder.

De eerste interpretatie beschouwde SMA Premium/Energy Maximizer als mogelijk beschikbaar maar nog onbewezen. Nader onderzoek in de actuele SMA-productmatrix toont dat Home Manager 2.0 als hoofdapparaat niet door SMA Premium wordt ondersteund en zijn ingebouwde functionaliteit behoudt.[25][26]

De historische bevinding blijft relevant als correctielog: Energy Maximizer is een afzonderlijke dienst, maar niet de route voor deze concrete installatie.

### Zevende bewijsresultaat - ingebouwde SHM2-optimalisatie

De screenshots `energiebeheer_batterij.png` en `energiebeheer_optimalisatie.png` bevestigen:

- de Home Manager 2.0 biedt de ingebouwde configuratie voor forecast-based battery charging;
- forecast charging gebruikt opbrengst- en verbruiksprognoses met een beschreven horizon van 48 uur;
- forecast-based charging staat momenteel uit;
- priority charging staat momenteel uit;
- time-window charging staat momenteel uit;
- optimalisatiedoelen `Evenwichtig`, `Ecologisch` en `Economisch` zijn beschikbaar;
- `Economisch` is de zichtbare selectie en werd al op de samenvattingspagina als actief getoond;
- voor economisch energiebeheer vereist de interface zowel een stroomtarief als een terugleververgoeding;
- er is geen Premium-, Energy Maximizer- of licentiemelding op deze configuratiepagina's.

De actuele SMA-productmatrix bevestigt dat Home Manager 2.0 zelf dynamische-tariefoptimalisatie en netladen ondersteunt, maar geen netontladen voor marktprijsarbitrage. SMA Premium/Energy Maximizer ondersteunt Home Manager 2.0 als hoofdapparaat niet.[25][26][27]

Status:

- ingebouwde SHM2-functie: `VERIFIED` beschikbaar en configureerbaar;
- huidige forecast charging: `VERIFIED` uit;
- grid charging onder echte dynamische prijzen: `REQUIRES TESTING`;
- grid discharge voor prijsarbitrage: `VERIFIED` niet ondersteund door deze SHM2-route;
- SMA Premium/Energy Maximizer: `NIET VAN TOEPASSING` op de huidige topologie.

### Achtste bewijsresultaat - terugleververgoeding

De screenshot `tarieven_terugleververgoeding.png` bevestigt:

- tariefnaam `Mijn tarief`;
- tarieftype `Vast`;
- terugleververgoeding `€0,02/kWh`;
- geen dynamische formule, index, geldigheidsperiode of afzonderlijke afslag zichtbaar;
- de interface vraagt om de totale vergoeding inclusief kosten, netwerkkosten en belastingen;
- opgeslagen/actief-status is niet zichtbaar in de bewerkingsweergave.

Architecturale impact:

- Het economische SHM2-model gebruikt een vaste injectiewaarde als proxy, niet de dynamische Ecopower-injectieformule.
- SMA adviseert bij dynamische tarieven een lage vaste terugleververgoeding vanwege mogelijk zeer lage of negatieve marktprijzen.[29]
- De officiële SHM2-functiematrix toont geen prijsgebaseerde vermogensreductie bij negatieve tarieven.[26]
- Ingebouwde SHM2-optimalisatie kan dynamische afname/netladen ondersteunen; contractnauwkeurige injectiewaardering en negatieve-prijsoptimalisatie blijven onbewezen.
- De mogelijke `0 W`-PCC-limiet kan deze beperking praktisch verkleinen indien werkelijk zero-export actief is; dat moet met meetdata worden getest.

### Negende bewijsresultaat - herkomst vaste injectievergoeding

De eigenaar bevestigt dat `€0,02/kWh` afkomstig is uit de huidige Ecopower-tariefkaart of factuur.

Status: `OWNER CONFIRMED`.

Nog nodig voor `VERIFIED`:

- exacte Ecopower-productnaam;
- document- of factuurdatum;
- geldigheidsperiode;
- de gesaniteerde regel waarop de injectievergoeding staat;
- bevestiging of het bedrag inclusief alle componenten is zoals SMA verwacht.

### Tiende bewijsresultaat - Home Assistant batterijcapaciteit-entity

Read-only MCP-uitlezing bevestigt voor `sensor.sn_<sbs>_battery_capacity_total`:

- state `89`;
- unit `%`;
- friendly name `Batterij Capaciteit`;
- original name `Battery Capacity Total`;
- platform `sma`;
- entity enabled en niet hidden;
- geen device class en geen state class;
- locatie `Garage`, verdieping `Gelijkvloers`;
- `last_updated` `2026-09-28T11:05:40+02:00`;
- `last_reported` `2026-09-28T11:54:05+02:00`;
- 24-uurs recorderhistoriek aanwezig met state `89`;
- geen long-term statistics in de gecontroleerde 30 dagen.

De PySMA-brondefinitie koppelt register `6100_00696E00` aan `Total battery capacity`. Dat maakt een SoH-interpretatie plausibel, maar niet officieel bewezen. Status wordt daarom:

- waarde/bron/metadata: `VERIFIED`;
- semantiek als exacte SoH: `INFERRED`;
- bruikbare capaciteitstest: `REQUIRES TESTING`.

De Home Assistant MCP is nu ook in het actieve Hermes-profiel geconfigureerd. De oorspronkelijke globale Claude-configuratie faalde door een geërfde `PYTHONPATH`; een wrapper start de MCP nu zonder die conflicterende variabele en bewaart credentials buiten de repository.

### Elfde bewijsresultaat - officiële Ecopower Dynamic-tariefkaart

De eigenaar leverde `docs/information/20260801_dbs_tariefkaart.pdf`. VERIFIED vanaf `1 augustus 2026`:[28]

- product `Dynamische Burgerstroom`;
- digitale laagspanningsmeter in meetregime 3;
- afname per kwartier: `0,00102 × EPEX DA + 0,004` EUR/kWh;
- injectie per kwartier: `0,00098 × EPEX DA - 0,015` EUR/kWh;
- abonnement `€5/maand` exclusief btw;
- GSC `€0,011/kWh` exclusief btw;
- WKK `€0,00392/kWh` exclusief btw;
- particuliere afname 6% btw;
- particuliere terugleververgoeding vrijgesteld van btw;
- injectienettarief alleen bij omvormervermogen boven 10 kVA.

De installatie heeft 8 kW nominaal AC-omvormervermogen. Niet-toepasselijkheid van het injectienettarief is voorlopig `INFERRED`; Fluvius/netgebied moet dit bevestigen.

Belangrijke nuance: de vaste `€0,02/kWh` in Sunny Portal is geen exacte weergave van de dynamische injectieformule. SMA adviseert bij dynamische tarieven juist een lage vaste terugleververgoeding als conservatieve optimalisatieproxy, omdat marktprijzen zeer laag of negatief kunnen zijn.[29]

### Twaalfde bewijsresultaat - SMA-advies voor dynamische injectie

De eigenaar corrigeerde de eerdere veronderstelling dat een dynamisch teruglevertarief rechtstreeks instelbaar was. Officiële SMA-documentatie bevestigt:[29]

- bij een variabele terugleververgoeding moet een gemiddelde vergoeding worden ingevoerd;
- bij een dynamisch stroomtarief adviseert SMA een lage vaste terugleververgoeding wegens mogelijk zeer lage of negatieve marktprijzen;
- SHM2 modelleert dus een vaste economische proxy, niet de volledige Ecopower-kwartierformule.

Status:

- vaste configuratie `€0,02/kWh`: `VERIFIED`;
- dat een lage vaste waarde de bedoelde SMA-methode is: `VERIFIED`;
- dat `€0,02/kWh` voor deze installatie financieel optimaal gekalibreerd is: `REQUIRES TESTING`.

### Dertiende bewijsresultaat - Home Assistant batterij-entitygroep

Read-only MCP-uitlezing bevestigt zes SMA-batterijentities:

- SOC: `0%`, `device_class: battery`, `state_class: measurement`;
- cumulatief laden: `13443.503 kWh`, `energy`, `total_increasing`;
- cumulatief ontladen: `11328.088 kWh`, `energy`, `total_increasing`;
- laadvermogen: `0 W`, `power`, `measurement`;
- ontlaadvermogen: `0 W`, `power`, `measurement`;
- `Battery Capacity Total`: `89%`, zonder device/state class.

Voor SOC, beide vermogens en beide energietotalen zijn recorder en minstens 30 dagen long-term statistics `VERIFIED`. Voor `Battery Capacity Total` is recorderhistoriek aanwezig maar geen long-term statistics. Het exacte pollinginterval is niet uit state-changehistoriek af te leiden.

### Veertiende bewijsresultaat - Smappee EV Wall Home

De eigenaar bevestigt de laadpaal als Smappee EV Wall Home en meldt een Home Assistant-integratie. Status model: `OWNER CONFIRMED`.

Read-only MCP valideert zonder writes:

- HACS custom platform `smappee_ev`, versie `2026.9.1`, is actief; de Home Assistant Core-integratie ondersteunt zelf geen EV-laadstations.[32][33]
- MQTT connected; station beschikbaar; laadstatus `stopped`; EVSE-status `available`.
- Modus `smart`; beschikbare modi `standard`, `smart`, `solar`.
- Connectormaximum `32 A`; regelbaar laadstroombereik `6–32 A`; actuele limiet `6 A`.
- Capacity maximum `5,5 kW`; minimum surplus `100%`; offline failsafe `8 A`; offline laden aan.
- De overload-/hoofdstroomonderbrekerentity rapporteert `40 A`, maar de entitymetadata heeft maximum `32 A`. Dit is `REQUIRES TESTING` en geen bewijs van de fysieke hoofdzekering.
- Actueel vermogen `2 W`; cumulatieve connectorenergie `12722,415 kWh`.
- Per-fasestroom, totaalstroom, status, sessie-energie en controlentities zijn aanwezig.
- Geen 24-uurs recorderhistoriek en geen 30-daagse LTS gevonden voor de directe charger power/current/energy-entities.
- De sessie-entity bevat privacygevoelige RFID-, gebruikers- en billingattributen. Deze waarden zijn niet in projectdocumentatie opgenomen.

Modelniveau:

- Smappee specificeert maximaal `7,4 kW` enkelfasig of `22 kW` driefasig voor EV Wall Home.[34][35]
- `Standard`, `Smart` en `Solar` charging worden officieel ondersteund.[36][37]
- OCPP `1.6J` is modelmatig activeerbaar; actuele activatie op deze installatie blijft `UNKNOWN`.[34]

Controlgrens:

- native Smappee `smart` geldt voorlopig als actieve laadcontroller;
- de aanwezige HA-controls voor start/stop/pause/resume, modus, stroom en availability worden niet gebruikt;
- deze eerste MCP-uitlezing liet componentfirmware, fysieke aansluiting, load-balancingbron, OCPP-status en de precieze `5,5 kW`-/`40 A`-semantiek nog open; de appscreenshots hieronder verfijnen dit in bewijsresultaat 15 en COR-017.

### Vijftiende bewijsresultaat - volledige Smappee-appset

De eigenaar leverde achttien screenshots in `docs/information/smappee/`. Deze map blijft Git-ignored; serienummers, persoons-/installatienamen en telefoonstatusinformatie worden niet overgenomen.

VERIFIED configuratie:

- Grid: `Driefasig – Delta`.
- Maximale stroom/hoofdstroomonderbreker in Smappee: `2 × 40 A`.
- Maximumcapaciteitsdrempel: aan, `5,5 kW`.
- Getoonde gemiddelde 15-minutenverbruikspiek: `7,50 kW`.
- Grid-CT-kanalen zichtbaar op `L1` en `L2`; actuele P/Q/I/power-factorwaarden stonden op `---`.
- Laadstation is geconfigureerd als door het net gemeten toestel, met zichtbare CT-toewijzingen op `L1` en `L2`.
- Charging Controller firmware `2.36`, maximale ondersteunde stroom `32,0 A`.
- Smappee Connect firmware `EC 3.92`; Ethernet en wifi worden als opties genoemd, actieve methode niet zichtbaar.
- Power Box firmware `1.76`.
- CT Hub firmware `1.02`.
- Solid Core 3-phase CT firmware `1.36`.
- RFID-lezer firmware `1.72`.
- Offline laden: aan; automatische overbelastingsbeveiliging tijdens offline laden uit; foutveilige maximumstroom `8 A`.
- Smappee-tarieven toont dynamische-tarieffunctionaliteit, maar geen actieve status of prijswaarden. Heffingen en andere kosten worden expliciet niet meegerekend.
- Smappee-productiecircuits `SMA 1` en `SMA 2`: `Export zonne-energie = Alleen het overschot`; hybride-omvormer uit.

Interpretatie:

- `5,5 kW` is de Grid-maximumcapaciteitsdrempel, niet de fysieke laadpaalrating.
- `40 A` uit Home Assistant komt overeen met de Smappee Grid-instelling; `32 A` is de Charging Controller-limiet. De eerdere schijnbare elektrische inconsistentie is daardoor grotendeels verklaard als custom-integration-semantiek.
- De actieve drempel en `smart`-modus bevestigen een native Smappee-controlbasis, maar werkelijk load-balancinggedrag blijft `REQUIRES TESTING`.
- De appconfiguratie is VERIFIED en de eigenaar bevestigt dat de fysieke aansluiting en hoofdbeveiliging hiermee overeenkomen: `Driefasig – Delta`, `2 × 40 A`.
- Smappee-tarieven kunnen geen contractnauwkeurige Ecopower-shadow billing vervangen.

### Zestiende bewijsresultaat - fysieke netaansluiting eigenaar bevestigd

De eigenaar bevestigt dat de werkelijke netaansluiting en hoofdbeveiliging volledig overeenkomen met de Smappee-configuratie:

- `Driefasig – Delta`;
- `2 × 40 A`.

Status:

- Smappee-configuratie: `VERIFIED` via screenshots;
- overeenkomst met fysieke installatie: `OWNER CONFIRMED`;
- Grid-CT-topologie op alleen L1/L2 en werkelijk meet-/regelgedrag: `REQUIRES TESTING`.

De P0-gap "netaansluitingslimiet onbekend" is daarmee opgelost. De resterende CT-/meetvraag wordt P1.

### Zeventiende bewijsresultaat - huidig Ecopower-product en augustusbaseline

De eigenaar bevestigt dat het huidige product `Groene Burgerstroom` is en leverde `docs/information/202608_gbs_tariefkaart.pdf`. De officiële augustuskaart is ook publiek geverifieerd.[38]

VERIFIED voor augustus 2026, exclusief btw tenzij anders vermeld:

- afname-energiecomponent: `€0,1526/kWh`;
- afnameformule: `50% × €0,17/kWh + 50% × €0,13511/kWh`;
- GSC: `€0,011/kWh`;
- WKK: `€0,00392/kWh`;
- totale injectievergoeding: `€0,0406/kWh`;
- injectieformule: `50% × €0,02/kWh + 50% × (0,9 × €0,07910839/kWh - €0,01/kWh)`;
- particuliere injectievergoeding is vrijgesteld van btw;
- de waarden wijzigen maandelijks.

Belangrijke correctie: de `€0,02/kWh` in Sunny Portal is niet de totale actuele Groene Burgerstroom-injectievergoeding. Het bedrag is de vaste component binnen de maandformule en functioneert in SMA als conservatieve optimalisatieproxy. De contractbaseline moet per maand worden geversioneerd.

### Achttiende bewijsresultaat - netgebied en btw-regime

De eigenaar bevestigt:

- netgebied: `Fluvius West`;
- contracttype: particulier;
- btw op toepasselijke componenten: `6%`.

Status: `OWNER CONFIRMED`.

De augustuskaart vermeldt voor een digitale meter in Fluvius West onder meer `€17,85/jaar` databeheer, `€57,10/kW/jaar` capaciteitstarief en `€0,0631937/kWh` afnametarief, exclusief btw.[38] Deze regels worden pas definitief aan de baseline gekoppeld nadat digitale meter en meetregime expliciet zijn bevestigd.

### Negentiende bewijsresultaat - digitale meter en kwartierwaarden

De eigenaar bevestigt:

- digitale elektriciteitsmeter aanwezig;
- kwartierwaarden in Mijn Fluvius geactiveerd.

Status: `OWNER CONFIRMED`.

Dit bewijst niet automatisch `MR3`. Fluvius maakt onderscheid tussen kwartierwaarden die de gebruiker zelf raadpleegt en kwartierwaarden die met toestemming aan de leverancier worden doorgegeven voor facturatie. Dat laatste is `SMR3`/meetregime 3.[4]

Omdat het huidige product Groene Burgerstroom volgens de tariefkaart bedoeld is voor digitale meters in meetregime 1, werd `MR1` op dit bewijsniveau voorlopig als `INFERRED` geregistreerd.[38] Deze tussenstatus is `SUPERSEDED` door COR-025.

### Twintigste bewijsresultaat - MR1/MR3-verificatie aangevraagd

De eigenaar heeft bij Ecopower bevestiging aangevraagd of het elektriciteitstoegangspunt in SMR1 of SMR3 staat.

Status: `OWNER CONFIRMED - RESPONSE PENDING`.

Dit blokkeert de read-only data-inventaris niet, maar blijft vereist vóór een contractnauwkeurige factuurinterpretatie of contractwissel.

### Eenentwintigste bewijsresultaat - volledige read-only Home Assistant-inventaris

Grid, PV, Battery, EV, Charger, House, Tariffs, Forecast, Costs en SMA zijn via read-only MCP geïnventariseerd.

Belangrijkste VERIFIED-resultaten:

- P1 import/export heeft minstens 263 dagen LTS vanaf `2026-01-09`;
- PV cumulative energy heeft minstens 250 dagen LTS vanaf `2026-01-22`;
- batterij charge/discharge heeft minstens 253 dagen LTS vanaf `2026-01-12`;
- Smappee connectorenergy heeft minstens 62 dagen LTS vanaf `2026-07-29`;
- Solcast is actief met minstens 111 dagen forecastdekking vanaf `2026-06-10`;
- P1, Smappee en SMA Grid-power lagen bij één actieve EV-laadsessie binnen `0,7–1,2%`;
- HA-PV en Smappee-PV kwamen exact overeen op het meetmoment;
- afgeleid HA-huisvermogen en Smappee house consumption verschilden `0,97%`;
- Smappee chargerpower en Kia/Tronity verschilden circa `0,16%`.

Data-qualitybevindingen:

- de bestaande daily house helper mist gridimport en batterijstromen en is geen geldige huisenergiebron;
- daily PV en house helpers gebruiken `total_increasing` ondanks dagelijkse resets, waardoor LTS-sommen ongeschikt zijn;
- bestaande handmatige Ecopower-helpers hebben geen contractversie/geldigheidsinterval en wijken af van de geverifieerde augustusformule;
- geen EPEX-entity is gevonden;
- directe Smappee charger power/energy heeft, anders dan eerder vastgesteld, nu recorder en LTS.

Geen Home Assistant-write is uitgevoerd.

### Tweeëntwintigste bewijsresultaat - Fluvius-kwartierdata en Ecopower-factuur gereconcilieerd

De eigenaar leverde een Fluvius-kwartierexport en de bijbehorende Ecopower-afrekeningsfactuur voor `2025-06-01` tot en met `2026-05-31`. De ruwe bestanden blijven Git-ignored wegens persoonsgegevens en contract-/meteridentifiers.

VERIFIED-resultaten:

- 70.080 datarijen vormen 35.040 kwartierintervallen;
- ieder interval bevat zowel afname als injectie;
- na UTC-canonisatie zijn geen intervallen ontbrekend;
- beide zomer-/wintertijdovergangen zijn correct aanwezig;
- 34.941 intervallen (`99,717466%`) zijn uitgelezen;
- 99 intervallen (`0,282534%`) zijn geschat;
- CSV-afname `9.161,589 kWh` versus factuur `9.161,59 kWh`: verschil `-0,001 kWh`;
- CSV-injectie `1.160,728 kWh` versus factuur `1.160,74 kWh`: verschil `-0,012 kWh`;
- de factuurdetailregels reproduceren exact `€2.690,39` exclusief btw, `€162,82` btw en `€2.853,21` inclusief btw;
- product: Groene Burgerstroom;
- meterlezing: jaarlijks;
- facturatiepiek: `5,26 kW`, met `5,264 kW` in de detailberekening;
- historische injectievergoeding: `€0,0200/kWh` voor deze factuurperiode.

De formele code `SMR1` staat niet op de factuur. Jaarlijkse meterlezing is direct VERIFIED en ondersteunde `SMR1` sterk; de toenmalige `INFERRED`-status is inmiddels `SUPERSEDED` door COR-025.

De privacy-safe analyse staat in `docs/evidence/ECOPOWER_RECONCILIATION_2025-06_TO_2026-05.md`; het afgeleide JSON-resultaat bevat geen EAN-, meter-, adres- of contractwaarden.

### Drieëntwintigste bewijsresultaat - Phase 1 go/no-go-pakket

De Phase 1-exitcriteria zijn opnieuw beoordeeld en het besluitvoorstel staat in `PHASE_1_GO_NO_GO.md`.

Voorstel:

- `CONDITIONAL GO` voor uitsluitend read-only data-export, EPEX-ingestie, shadow billing en offline wireframes;
- `NO-GO` voor contractwijziging, productieautomatisaties en fysieke sturing;
- P2-004 en P2-001 als eerste parallelle tickets;
- P2-002 pas na gevalideerde energie- en prijsdata;
- Phase 3 blijft volledig geblokkeerd.

Status: `SUPERSEDED` door het expliciete besluit in het vierentwintigste bewijsresultaat.

### Vierentwintigste bewijsresultaat - read-only Phase 2 goedgekeurd

De eigenaar gaf op 2026-09-29 expliciet een go voor Phase 2.

Besluit:

- P1-014 is afgerond;
- P2-004 en P2-001 starten parallel;
- P2-002 blijft afhankelijk van gevalideerde prijs- en energiedata;
- de goedkeuring is uitsluitend read-only;
- contractwijziging, productieautomatisatie en fysieke sturing blijven niet geautoriseerd.

Status: `OWNER APPROVED`.

De scope en verboden acties zijn vastgelegd in `docs/decisions/ADR-003-read-only-phase-2-authorization.md`.

### Volgend bewijsverzoek

Een privacy-safe kopie of screenshot van de Ecopower-reactie is optioneel welkom om de mondeling doorgegeven bevestiging als direct correspondentie-evidence te archiveren. Dit blokkeert Phase 2 niet.

### Vijfentwintigste bewijsresultaat - meetregime door Ecopower bevestigd

De eigenaar meldt op 2026-09-30 dat Ecopower het volgende heeft bevestigd:

- het huidige meetregime is `SMR1`;
- bij overschakeling naar Dynamische Burgerstroom wordt het meetregime `SMR3`.

Status: `OWNER CONFIRMED` op basis van doorgegeven Ecopower-reactie. Een privacy-safe kopie van de correspondentie kan dit later versterken tot direct gedocumenteerd leverancierbewijs.

Impact:

- de eerdere `INFERRED`-classificatie van het huidige `SMR1` vervalt;
- de meetregime-overgang is geen open contractgap meer;
- dit bevestigt uitsluitend de datamodus bij een eventuele contractwissel en vormt geen toestemming om het contract te wijzigen.

### Zesentwintigste bewijsresultaat - dynamisch interessant; sturingsonderzoek vrijgegeven

De eigenaar concludeert op 2026-10-01 dat de uitgevoerde factuurbacktest,
meerjarige tariefsensitivity en batterijscenario's voldoende positief zijn om
dynamisch als interessante richting te behandelen en verder te onderzoeken hoe
de installatie goed kan worden gestuurd.

Status: `OWNER APPROVED` voor ontwerp en read-only shadow control.

Geautoriseerd:

- ontwerp van een prijs-, forecast- en piekbewuste strategie;
- offline optimalisatie en dagelijkse shadow-plannen;
- vergelijking van piekneutraal, `7 kW`, `8 kW` en `10 kW`;
- dashboard- en decision-loguitbreidingen voor gepland versus werkelijk gedrag;
- read-only validatie van SMA- en Smappee-gedrag.

Nog niet geautoriseerd:

- Ecopower-contractwijziging;
- activeren van forecast charging, peak shaving of tijdvensterladen in SMA;
- Home Assistant-, SMA- of Smappee-writes;
- wijzigen van EV-laadmodus of stroomlimiet;
- productieautomatisatie of fysieke failure-modeproeven.

De voorkeursrichting blijft hybride orchestration: SMA houdt batterij/PV,
Smappee houdt EV-load-balancing en Home Assistant/data-services berekenen en
observeren eerst uitsluitend shadow-plannen.

## Correctielog

### COR-026 - Van financiële analyse naar read-only sturingsontwerp

- Eerder: dynamisch bleef formeel een sensitivity zonder vrijgegeven vervolg voor
  sturingsontwerp.
- Nieuw: de eigenaar beoordeelt de resultaten als voldoende interessant om de
  sturingsaanpak verder uit te werken.
- Impact: P2-008 start voor een read-only shadow-controller. Contractwijziging en
  fysieke control blijven achter afzonderlijke beslis- en veiligheidsgates.

### COR-025 - Huidig SMR1 en dynamisch SMR3 bevestigd

- Eerder: `SMR1` was met hoge confidence `INFERRED` uit productvoorwaarden en jaarlijkse facturatie; `SMR3` bij dynamisch volgde uit de tariefkaart.
- Nieuw: Ecopower bevestigde volgens de eigenaar rechtstreeks dat het huidige regime `SMR1` is en bij overschakeling naar dynamisch `SMR3` wordt.
- Impact: beide regimecodes worden `OWNER CONFIRMED`. De open meetregimevraag sluit; contractwijziging blijft buiten de huidige read-only Phase 2-scope.

### COR-024 - MR1-aanname versterkt door jaarlijkse facturatie

- Eerder: `MR1` was alleen afgeleid uit het huidige Groene Burgerstroom-product en actieve Mijn Fluvius-kwartierwaarden.
- Nieuw: de afrekeningsfactuur vermeldt rechtstreeks `Meterlezing: Jaarlijks` en zegt dat Ecopower de meterstanden en verbruiksgegevens van Fluvius ontving. De formele code `SMR1` staat niet letterlijk vermeld.
- Impact: jaarlijkse facturatie wordt `VERIFIED`; deze tussenconclusie is nu `SUPERSEDED` door COR-025, waarin `SMR1` rechtstreeks als `OWNER CONFIRMED` is geregistreerd.

### COR-023 - `€0,02/kWh` is tijdgebonden wel de historische factuurvergoeding

- Eerder: na controle van de augustuskaart werd `€0,02/kWh` terecht verworpen als volledige actuele injectievergoeding voor augustus 2026.
- Nieuw: de factuur voor juni 2025 tot en met mei 2026 rekent historische injectie wel af tegen exact `€0,0200/kWh`.
- Impact: beide bevindingen zijn verenigbaar door tariefversionering. De historische factuur gebruikt `€0,0200/kWh`; augustus 2026 gebruikt de dan geldende half-vaste/half-variabele formule en mag niet worden teruggeprojecteerd.

### COR-022 - Bestaande HA-Ecopowerhelpers zijn geen contractmodel

- Eerder: bestaande prijs- en costsensoren waren nog niet inhoudelijk gevalideerd.
- Nieuw: de helpers zijn handmatige inputwaarden en eenvoudige sum/mean-helpers zonder formuleversie, geldigheidsinterval of afname-/injectiescheiding. De injectiehelper `€0,02/kWh` wijkt af van de geverifieerde augustusvergoeding `€0,0406/kWh`.
- Impact: geen bestaande HA-prijshelper wordt gebruikt voor shadow billing. Tariefkaarten en een toekomstige contractpassende EPEX-feed worden de bron.

### COR-021 - Daily house- en PV-helpers ongeschikt voor LTS

- Eerder: daily energyhelpers waren kandidaten voor historische analyse.
- Nieuw: de house-helper gebruikt alleen `PV_daily - export_daily` en mist gridimport/batterijstromen. Zowel house als PV daily declareert `total_increasing` ondanks dagelijkse resets.
- Impact: hun LTS-`sum`/`change` wordt uitgesloten. Huisenergie wordt opnieuw uit intervalstromen afgeleid; cumulative PV-totalen worden gebruikt.

### COR-020 - Directe Smappee chargerentities hebben recorder en LTS

- Eerder: voor directe Smappee power/current/energyentities werd geen 24-uurs recorderhistoriek of 30-daagse LTS gevonden.
- Nieuw: de huidige read-only probe vindt raw history voor power, cumulative energy, session energy en status; numerieke power/energyentities hebben minstens 30 dagen LTS en cumulative connectorenergy 62 dagen.
- Impact: Smappee cumulative connectorenergy wordt de primaire EV-laadenergiebron. Enumstatus blijft zonder numerieke LTS, zoals verwacht.

### COR-019 - `€0,02/kWh` is niet de totale huidige injectievergoeding

- Eerder: `€0,02/kWh` werd op basis van owner evidence als huidige Ecopower-injectievergoeding behandeld.
- Nieuw: de officiële Groene Burgerstroom-kaart van augustus 2026 toont `€0,02/kWh` als vaste component binnen een half-vast/half-variabele formule; de totale augustusvergoeding is `€0,0406/kWh`.[38]
- Impact: historische en huidige baselineberekeningen gebruiken de toepasselijke maandformule. De Sunny Portal-waarde blijft alleen een SMA-optimalisatieproxy en mag niet als contractprijs worden geboekt.

### COR-018 - Fysieke netaansluiting bevestigd

- Eerder: `Driefasig – Delta`, `2 × 40 A` was VERIFIED als Smappee-configuratie; overeenkomst met de fysieke installatie bleef open.
- Nieuw: eigenaar bevestigt dat aansluiting en hoofdbeveiliging volledig overeenkomen.
- Impact: fysieke nettopologie wordt `OWNER CONFIRMED`; de P0-gap voor onbekende aansluitingslimiet sluit. Alleen CT-topologie, meetgedrag en operationele load-balancingtest blijven open.

### COR-017 - Smappee Grid- en chargerlimieten onderscheiden

- Eerder: `5,5 kW` werd als mogelijk charger-/sitelimiet behandeld en `40 A` state versus `32 A` entitymaximum leek intern elektrisch inconsistent.
- Nieuw: de app bevestigt `5,5 kW` als actieve Grid-maximumcapaciteitsdrempel, `2 × 40 A` als Grid-/hoofdstroomonderbrekerconfiguratie en `32,0 A` als maximale Charging Controller-stroom.
- Impact: de drie waarden hebben verschillende semantiek. De custom HA-entitymetadata is onduidelijk, maar er is geen aangetoonde fysieke tegenspraak. Fysieke aansluiting en werkelijk load-balancinggedrag blijven REQUIRES TESTING.

### COR-016 - EV-laadpaal en Home Assistant-controlvlak geïdentificeerd

- Eerder: laadpaalmerk/model, meetwaarden, regelbereik, load balancing en Home Assistant-integratie waren UNKNOWN.
- Nieuw: Smappee EV Wall Home is OWNER CONFIRMED; `smappee_ev`-platform, MQTT-connectie, smart/solar-modi, 6–32 A regelbereik, 5,5 kW capacity, 8 A failsafe en live status/energie zijn VERIFIED.
- Impact: native Smappee `smart` wordt voorlopig als actieve controller behandeld. HA-writecontrols blijven verboden. Op dit bewijsniveau bleven firmware, fysieke fasen, `5,5 kW`-/`40 A`-semantiek, OCPP-status, recorderdekking en fallback open; COR-017 verfijnt firmware en limietsemantiek met de appscreenshots.

### COR-015 - Batterijmetrie live geverifieerd

- Eerder: actuele SOC, laad-/ontlaadvermogen en cumulative battery energy ontbraken.
- Nieuw: zes SMA-batterijentities zijn live read-only uitgelezen; SOC, beide vermogens, beide energietotalen en hun recorder/LTS-status zijn VERIFIED.
- Impact: batterijmonitoring en latere simulatie zijn technisch beter voorbereid. Bruikbare capaciteit, minimum-/reserve-SOC en controlgedrag blijven open.

### COR-014 - Dynamische injectie wordt als lage vaste proxy ingevoerd

- Eerder: de eigenaar dacht dat ook een dynamisch teruglevertarief rechtstreeks instelbaar was; de vaste `€0,02/kWh` werd als uitsluitend huidige-contractbaseline behandeld.
- Nieuw: eigenaar corrigeert dit. Officiële SMA-documentatie adviseert bij dynamische tarieven een lage vaste terugleververgoeding; bij andere variabele vergoedingen moet een gemiddelde worden ingevoerd.[29]
- Impact: `€0,02/kWh` is een ondersteunde conservatieve SHM2-proxy, maar geen exacte Ecopower-kwartierformule. Optimale kalibratie blijft REQUIRES TESTING.

### COR-013 - Dynamische Ecopower-injectieformule geverifieerd

- Eerder: dynamische injectieformule was alleen uit webonderzoek bekend; lokale contractkaart ontbrak.
- Nieuw: officiële tariefkaart vanaf `1 augustus 2026` bevestigt `0,00098 × EPEX DA - 0,015` EUR/kWh per kwartier.[28]
- Impact: shadow billing kan met een geversioneerde contractformule worden opgebouwd. De vaste Sunny Portal-injectiewaarde `€0,02/kWh` kan alleen als conservatieve SMA-optimalisatieproxy dienen, niet als contractnauwkeurige factuurformule.

### COR-012 - Batterijcapaciteitswaarde live geverifieerd

- Eerder: entity en waarde 89% waren OWNER CONFIRMED; live metadata ontbrak.
- Nieuw: state, unit, timestamps, SMA-platform, recorder en ontbreken van state class/LTS zijn VERIFIED via read-only MCP.
- Impact: waarde 89% is betrouwbaar als SMA `Battery Capacity Total`; exacte SoH-betekenis blijft INFERRED en bruikbare capaciteit blijft REQUIRES TESTING.

### COR-011 - Herkomst vaste injectievergoeding

- Eerder: contractmatch van `€0,02/kWh` UNKNOWN.
- Nieuw: eigenaar bevestigt dat het bedrag uit de huidige Ecopower-tariefkaart of factuur komt.
- Impact: bruikbaar als voorlopige huidige-contractbaseline; exact product, documentdatum en geldigheidsperiode blijven nodig voor VERIFIED shadow billing.

### COR-010 - SHM2-injectiewaarde is vast, niet dynamisch

- Eerder: terugleververgoeding en injectiebehandeling door SHM2 waren UNKNOWN.
- Nieuw: vast `€0,02/kWh` is VERIFIED in Sunny Portal; geen dynamische injectieformule zichtbaar.
- Impact: SHM2 kan dynamische afname/netladen uitvoeren, maar volledige Ecopower-injectieoptimalisatie en negatieve-prijsbehandeling ontbreken of zijn onbewezen. Shadow billing en simulatie blijven noodzakelijk.

### COR-009 - SMA Premium niet van toepassing; SHM2-functie ingebouwd

- Eerder: SMA Premium/Energy Maximizer eligibility stond als UNKNOWN.
- Nieuw: actuele SMA-productinformatie sluit Home Manager 2.0 als hoofdapparaat uit van Premium; SHM2 ondersteunt zelf dynamische-tariefoptimalisatie en netladen.[25][26][27]
- Impact: optie A1 is de relevante batterijroute. A2 wordt `NIET VAN TOEPASSING`. De ingebouwde functie is configureerbaar maar momenteel uit; werkelijk netladen blijft REQUIRES TESTING.

### COR-008 - Klassieke Home Manager-functies en Energy Maximizer gescheiden

- Eerder: SMA-native prijsoptimalisatie werd als één route behandeld.
- Nieuw: klassieke Home Manager forecast charging en SMA Premium/Energy Maximizer zijn afzonderlijke mechanismen met verschillende activatie en systeemvereisten.[21][22][23][24]
- Impact: optie A wordt opgesplitst. Klassieke forecast charging is aanwezig maar uit; Maximizer-compatibiliteit/licentie is UNKNOWN en moet in Sunny Portal worden gevalideerd.

### COR-007 - Dynamisch SMA-tarief aanwezig, batterijoptimalisatie uit

- Eerder: optimization target en dynamische tariefconfiguratie UNKNOWN.
- Nieuw: economisch optimalisatiedoel, BE Day-Ahead/EPEX-kwartierfeed en dynamisch tarieftype VERIFIED; forecast-, priority- en time-window charging inactief.
- Impact: native SMA-prijsoptimalisatie is technisch concreet maar niet operationeel actief. De SMA-tariefweergave vervangt geen Ecopower-shadow billing.

### COR-006 - Huidige SMA-optimalisatie- en PV-configuratie

- Eerder: forecast charging, peak shaving, PV-regelmodus, omvormervermogen en PCC-begrenzing UNKNOWN.
- Nieuw: forecast charging uit, peak shaving uit, System Manager actief, PV in externe actiefvermogensmodus, totaal 8 kW AC/8,5 kWp DC en dynamische PCC-begrenzing aan op 0 W, VERIFIED.
- Impact: native dynamische batterijoptimalisatie is momenteel niet actief. SMA blijft de waarschijnlijke controller; exacte tarief- en zero-exportsemantiek blijft REQUIRES TESTING.

### COR-005 - Batterij- en SBS-configuratie technisch geverifieerd

- Eerder: batterijmodel/capaciteit OWNER CONFIRMED; BMS-versie, vermogenslimieten, SOC-bereiken en interfaces UNKNOWN.
- Nieuw: RESU16H Prime, 16 kWh, BMS `23.11.0.R`, laadlimiet 5 kW, ontlaadlimiet 5,3 kW en relevante SBS-parameters VERIFIED via read-only export.
- Impact: batterijsimulatie kan later met concrete limieten worden opgebouwd. Native prijsoptimalisatie en controlownership blijven REQUIRES TESTING; externe control blijft verboden.

### COR-004 - Batterijmodel, capaciteit en SoH

- Eerder: batterij aanwezig, OWNER CONFIRMED; merk/model, capaciteit en BMS UNKNOWN.
- Nieuw: LG RESU Prime 16H, 16 kWh, sinds `10-5-2022`, SoH 89%, OWNER CONFIRMED.
- Impact: SMA's officiële compatibiliteitslijst en LG-specificaties kunnen nu modelgericht worden gebruikt. BMS-versie, SOC-instellingen, bewijsbron van SoH en werkelijk beschikbare capaciteit blijven open.

### COR-001 - SBS-model en firmware

- Eerder: `SMA Sunny Boy Storage / SBS5.0`, OWNER CONFIRMED; exacte variant en firmware UNKNOWN.
- Nieuw: `SBS5.0-10`, firmware `4.07.31.R`, VERIFIED via SMA-apparaatbeheer.
- Impact: de Europese SBS5.0-10-documentatie is nu de relevante productfamilie; exacte batterijcompatibiliteit en control blijven open.

### COR-002 - Home Manager firmware en gekoppelde apparaten

- Eerder: Home Manager 2.0 aanwezig, OWNER CONFIRMED; firmware en gekoppelde apparaten UNKNOWN.
- Nieuw: Home Manager 2 firmware `2.19.1.R` plus twee Sunny Boy-omvormers, SBS en een Smart Appliance zichtbaar, VERIFIED.
- Impact: native prijsbewuste forecast charging is een concreet te controleren scenario. Beschikbaarheid is nog niet bewezen en blijft REQUIRES TESTING.

### COR-003 - PV-omvormers

- Eerder: aantal, modellen en firmware UNKNOWN.
- Nieuw: `SB3.0-1AV-41` en `SB5.0-1AV-41`, beide firmware `4.10.10.R`, VERIFIED.
- Impact: later modelgericht onderzoek naar Modbus, curtailment en SHM-regeling is mogelijk.

## Sources

[4] https://www.fluvius.be/nl/factuur-en-tarieven/kwartierwaarden
[19] https://files.sma.de/downloads/SBS-Batteries-TI-en-28.pdf
[20] https://www.lgessbattery.com/ImageServlet?imageType=PRODUCT&imgPath=20220701171417442%5B20220701171417442%5D.pdf
[21] https://www.sma-benelux.com/producten/apps-digitale-producten/sunny-portal-ennexos
[22] https://www.sma.de/en/products/apps-software/sunny-portal/energy-planner-maximizer
[23] https://www.sma-benelux.com/producten/energiebeheer/sma-premium
[24] https://web.archive.org/web/20260516015747/https://www.sma-benelux.com/producten/energiebeheer/sma-premium
[25] https://www.sma.de/en/products/energy-management/energy-maximizer
[26] https://manuals.sma.de/SMA-Premium/nl-NL/16915921419.html
[27] https://manuals.sma.de/HM-20-ennexOS/en-US/12563269899.html
[28] https://cdn.nimbu.io/s/4tn7vz5/channelentries/ma28q8f/files/1790570062186/20260801_dbs_tariefkaart.pdf?7l4n7vq=
[29] https://manuals.sma.de/HM-20-ennexOS/nl-NL/11412423819.html
[32] https://www.home-assistant.io/integrations/smappee
[33] https://github.com/myny-git/smappee_ev
[34] https://support.smappee.com/hc/en-gb/articles/4402413229844-EV-Wall-Home
[35] https://support.smappee.com/hc/en-gb/articles/5721996814612-Smappee-EV-Line-charging-speeds
[36] https://support.smappee.com/hc/en-gb/articles/4900468508692-How-to-configure-charging-modes-and-schedules-for-Smappee-EV-Line
[37] https://support.smappee.com/hc/en-gb/articles/4406735969940-The-Smappee-Smart-Charging-Functionality
[38] https://cdn.nimbu.io/s/4tn7vz5/channelentries/spiilz4/files/1788271546519/202608_gbs_tariefkaart.pdf?w01uqtn=&dl=1 — Ecopower Groene Burgerstroom - tariefkaart augustus 2026
