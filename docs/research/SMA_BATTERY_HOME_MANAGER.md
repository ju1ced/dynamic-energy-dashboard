# SMA Battery and Home Manager Research

Status: fase-1-onderzoek; concrete installatie nog te verifiëren  
Gerelateerde tickets: P1-004 en P1-005  
Raadpleegdatum: 2026-09-28

## Sunny Boy Storage

De Sunny Boy Storage 3.7/5.0/6.0-familie ondersteunt volgens SMA Ethernet/WLAN, Speedwire/Webconnect, SMA Modbus en SunSpec Modbus. De Modbus-interface kan meetwaarden, ondersteunde parameters, setpoints en batterijregeling ontsluiten, maar de exacte registers en schrijfrechten zijn model- en firmwareafhankelijk.[7]

Modbus is standaard uitgeschakeld. Activering creëert schrijfrisico's; SMA adviseert netwerksegmentatie, firewalling, VPN voor externe toegang en geen internet-port-forwarding.[8]

Daarom geldt voor dit project:

- eerst exact Europees model en firmware bevestigen;
- alleen de officiële passende registerlijst gebruiken;
- read-only telemetrie vóór iedere schrijfproef;
- geen batterijcontrol op basis van alleen cumulatieve Home Assistant-sensoren;
- externe schrijfbesturing alleen na één-controllerbesluit, timeout en fallback.

## Sunny Home Manager 2.0

SMA positioneert de Sunny Home Manager 2.0 als energiemanager en meetpuntcontroller. Recente productinformatie noemt voor België ondersteuning voor dynamische tarieven en forecast-based battery charging; prijzen worden per kwartier verwerkt in Sunny Portal powered by ennexOS.[5]

SMA documenteert daarnaast vaste batterijlaadvensters van 15 minuten voor Sunny Boy Storage. Daarbij kan netenergie worden gebruikt, maar deze tijdsturing concurreert met de normale batterijregeling en kan zelfverbruik-/autarkiestatistieken beïnvloeden.[6]

## Concrete installatie - Owner Validation 2026-09-28

Een read-only screenshot van SMA-apparaatbeheer bevestigt:

- `SBS5.0-10`, firmware `4.07.31.R`;
- Home Manager 2, firmware `2.19.1.R`;
- `SB3.0-1AV-41` en `SB5.0-1AV-41`, beide firmware `4.10.10.R`;
- een gekoppeld `Smart Appliance` met apparaatnaam `VWL 55/3 A 230V`.

De screenshot bevestigt niet welk portalproduct wordt gebruikt, welke batterij gekoppeld is, of dynamische prijsoptimalisatie actief/geconfigureerd is. De concrete beoordeling verandert daardoor van algemeen `UNKNOWN` naar:

- model- en firmware-identificatie: `VERIFIED`;
- native dynamische batterijoptimalisatie: `REQUIRES TESTING`;
- externe Home Assistant-control: nog niet toegestaan.

## Concrete batterijcombinatie

De eigenaar bevestigt een LG RESU Prime 16H van 16 kWh, gekoppeld aan de `SBS5.0-10`, in dienst sinds `10-5-2022`, met gerapporteerde SoH 89%. Dit blijft `OWNER CONFIRMED` totdat typeplaat of portaalbewijs beschikbaar is.

LG specificeert voor de RESU16H Prime 16,0 kWh bruikbare energie en 7 kW maximaal laad-/ontlaadvermogen.[20] SMA vermeldt de LG RESU 16H Prime als goedgekeurde batterij voor de Sunny Boy Storage 3.7/5.0/6.0, onder model- en firmwarevoorwaarden.[19]

Daaruit volgt niet automatisch dat 16 kWh × 89% de werkelijk beschikbare energie is. SoH-definitie, SOC-venster, BMS-reserves, temperatuur en omvormerlimieten vereisen meting en configuratiebewijs.

## Concrete parameterconfiguratie - Owner Validation

Een read-only SBS-parameterexport bevestigt:

- LG Chem RESU16H Prime, `16000 Wh`;
- BMS-firmware `23.11.0.R` en Battery Interface software `1.07.3.R`;
- geconfigureerd maximaal laden `5000 W` en ontladen `5300 W`;
- actiefvermogensmodus `Externe instelling werkelijk vermogen`;
- externe-setpointtimeout `600 s` met fallback `Waarden behouden`;
- Modbus TCP-server uitgeschakeld;
- SMA Energy Meter als gebruikte teller;
- fase `L2`, Belgische landnorm en netparallel bedrijf.

Deze configuratie ondersteunt architectuuroptie A of C — SMA als actieve batterijcontroller — maar bewijst nog niet dat prijsbewuste forecast charging actief staat. Architectuuroptie B, Home Assistant als directe batterijcontroller, zou wijziging van de huidige interface- en ownershipsituatie vereisen en blijft niet toegestaan.

De fallback `Waarden behouden` is een expliciet risico voor een toekomstig extern EMS: zonder gevalideerde watchdog kan een eerder setpoint tijdens communicatieverlies blijven gelden. Dit moet vóór iedere schrijfproef worden opgelost of aantoonbaar begrensd.

### Correctie op basis van actuele SMA-productmatrix

De eigenaar merkte terecht op dat Sunny Home Manager 2.0 de relevante dynamische optimalisatie zelf bevat. De actuele SMA-productpagina sluit Home Manager 2.0 als hoofdapparaat expliciet uit van SMA Premium/Energy Maximizer en zegt dat de bestaande functionaliteit behouden blijft.[25]

De officiële functiematrix onderscheidt voor Home Manager 2.0:[26]

- optimalisatie op dynamische tarieven: ondersteund;
- netladen van de batterij: ondersteund;
- netontladen van de batterij voor prijsarbitrage: niet ondersteund;
- SMA Premium/Energy Maximizer: niet van toepassing op de huidige SHM2-topologie.

SMA's Home Manager-documentatie beschrijft de ingebouwde configuratie met `Economisch` als optimalisatiedoel, een dynamisch tarief en forecast-based battery charging. SMA noemt daarbij een vereiste laad-SOC van `0%`.[5][27]

Energy Maximizer is niet uitsluitend voor hybride omvormers; ook andere ennexOS System Managers worden ondersteund. Dit verandert de installatie-specifieke conclusie niet: voor deze concrete Home Manager 2.0-installatie is de klassieke ingebouwde SHM2-route de relevante route.

De eerder gedocumenteerde Premium-eligibility als `UNKNOWN` wordt gecorrigeerd naar `NIET VAN TOEPASSING`. Alleen een toekomstige bewuste migratie naar een andere ondersteunde System Manager zou die beoordeling heropenen.

## Gevalideerde energiebeheer- en tariefconfiguratie

Owner-validation screenshots bevestigen:

- optimalisatiedoel `Economisch`;
- dynamisch tarieftype;
- `Day-Ahead`, regio `BE`;
- EPEX Spot-bron en zichtbare 15-minutenprijs;
- marktprijs weergegeven zonder toeslag;
- forecast-based, geprioriteerd en tijdvenstergestuurd batterijladen inactief;
- peak shaving inactief;
- vereenvoudigde toeslagmethode geselecteerd, zonder zichtbare ingevulde vaste toeslag in de bewerkingsweergave.

Owner-validation bevestigt daarnaast een vaste terugleververgoeding van `€0,02/kWh`. De Groene Burgerstroom-kaart voor augustus 2026 toont dat dit alleen de vaste helft van de contractformule is; de totale augustusvergoeding bedraagt `€0,0406/kWh` exclusief btw en is voor particulieren vrijgesteld van btw.[38] SMA schrijft bij variabele terugleververgoedingen een gemiddelde waarde voor en adviseert bij dynamische stroomtarieven een lage vaste terugleververgoeding wegens mogelijk zeer lage of negatieve marktprijzen.[29] De officiële SHM2-functiematrix toont tegelijk geen prijsgebaseerde vermogensreductie bij negatieve tarieven.[26]

Conclusie: `€0,02/kWh` is geen contractnauwkeurige huidige injectieprijs, maar kan wel als door SMA ondersteunde conservatieve proxy dienen. De installatie voert op het validatiemoment nog geen prijsbewuste forecast-based battery charging uit. Wanneer die functie later wordt getest, kan SHM2 dynamische afnameprijzen en netladen gebruiken, maar de vaste injectieproxy modelleert noch Groene Burgerstroom noch Ecopower Dynamic contractnauwkeurig. Shadow billing moet daarom de echte formules afzonderlijk toepassen.

## Arbitragebeoordeling

### Officieel aangetoond op productfamilieniveau

- Monitoring via ondersteunde SMA/SunSpec Modbus.[7]
- Mogelijkheid tot batterijsetpoints via ondersteunde registers.[7]
- SHM-laadvensters voor Sunny Boy Storage, mogelijk met netenergie.[6]
- Dynamische prijsoptimalisatie op recente SHM-functionaliteit voor ondersteunde configuraties.[5]

### Nog niet aangetoond voor deze installatie

- Exact model `SBS5.0-10` versus andere regionale variant.
- Firmwarecompatibiliteit van SBS, SHM en batterij-BMS.
- Beschikbaarheid van dynamische prijsoptimalisatie in de eigen ennexOS-installatie.
- Exacte schrijfregisters, prioriteit en fallback.
- Garantie- en installateursgoedkeuring voor extern EMS-control.

### Voorlopige conclusie

Actieve energy arbitrage is technisch plausibel en SMA biedt native bouwstenen, maar deze installatie is nog niet vrijgegeven voor externe Home Assistant-control. De veiligste eerste validatie is de native SMA-functionaliteit observeren in MONITOR/SIMULATION, zonder concurrerende schrijver.

## Controllergrens

Voor fase 1 blijft SMA eigenaar van batterij- en PV-basisregeling. Home Assistant leest, normaliseert, simuleert en adviseert. Een toekomstige keuze moet expliciet zijn:

1. SHM master; Home Assistant observeert en levert hoogstens planning/context via officieel ondersteunde route, of
2. extern EMS master; conflicterende SHM-regelfuncties worden bewust uitgeschakeld en alle safety/fallbacktaken zijn aantoonbaar overgenomen.

Een hybride schrijfmodus zonder expliciete prioriteit is niet toegestaan.

## Owner evidence required

- SBS-typeplaatje en firmware;
- batterijmerk/model/BMS-versie/capaciteit;
- SHM-firmware en portaltype;
- screenshots van optimization target, forecast charging, laadvensters, peak shaving en exportlimiet;
- PV-omvormermodellen en firmware;
- actuele actieve-vermogensmodus en Modbusstatus;
- installateurs-/garantiebevestiging vóór schrijfproeven.

## Sources

[5] https://www.sma.de/en/products/energy-management/sunny-home-manager
[6] https://manuals.sma.de/HM-20/en-US/7415011979.html
[7] https://manuals.sma.de/SBSxx-10/en-US/391139595.html
[8] https://manuals.sma.de/SBSxx-10/en-US/1129302539.html
[19] https://files.sma.de/downloads/SBS-Batteries-TI-en-28.pdf
[20] https://www.lgessbattery.com/ImageServlet?imageType=PRODUCT&imgPath=20220701171417442%5B20220701171417442%5D.pdf
[25] https://www.sma.de/en/products/energy-management/energy-maximizer
[26] https://manuals.sma.de/SMA-Premium/nl-NL/16915921419.html
[27] https://manuals.sma.de/HM-20-ennexOS/en-US/12563269899.html
[29] https://manuals.sma.de/HM-20-ennexOS/nl-NL/11412423819.html
[38] https://cdn.nimbu.io/s/4tn7vz5/channelentries/spiilz4/files/1788271546519/202608_gbs_tariefkaart.pdf?w01uqtn=&dl=1 — Ecopower Groene Burgerstroom - tariefkaart augustus 2026
