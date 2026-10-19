# Architecture

Status: gezamenlijke batterij-/EV-logica en dry-run control geautoriseerd; geen live of productiecontrol  
Gerelateerd ticket: P1-010  
Laatst bijgewerkt: 2026-10-12

## Ontwerpprincipes

1. Lokale hardwarecontrollers behouden veilige autonome werking.
2. Monitoring en simulatie zijn logisch en operationeel gescheiden van fysieke control.
3. Ruwe brondata blijft herleidbaar; afgeleide waarden overschrijven geen bronmetingen.
4. Tariefcomponenten, forecasts, strategie en beslissingen hebben versieerbare inputs.
5. Iedere actie is verklaarbaar en heeft een timeout, constraint en fallback.
6. Complexiteit wordt pas toegevoegd wanneer Home Assistant-native mogelijkheden onvoldoende zijn.

## Voorlopige lagen

### 1. Hardware

PV-omvormer(s), SMA Sunny Boy Storage, batterij, SMA Home Manager 2.0, digitale meter, laadpaal en EV.

Verantwoordelijkheid: elektrische veiligheid, apparaatlimieten en lokale basiswerking.

### 2. Device integration

SMA-/DSMR-/charger-/voertuigintegraties via lokaal ondersteunde protocollen waar mogelijk.

Verantwoordelijkheid: genormaliseerde metingen en, pas na goedkeuring, beperkte actuatorcommando's.

### 3. Home Assistant energy data layer

Bronentities, afgeleide energiebalans, statistics, availability en quality flags.

Verantwoordelijkheid: observeerbaarheid en consistente semantiek; niet de enige opslagplaats voor financiële auditdata zonder export/backupstrategie.

### 4. Price layer

Day-ahead marktdata plus afzonderlijke contractformules voor afname en injectie.

Verantwoordelijkheid: intervalprijzen met publicatietijd, geldigheidsperiode, bronversie en stale-detectie.

### 5. Forecast layer

PV-forecast, weer, verwacht basisverbruik en EV-energiebehoefte.

Verantwoordelijkheid: verwachting en onzekerheid leveren; geen directe control.

### 6. Simulation and optimization layer

Shadow billing en scenario's A-D. Kandidaten zijn Home Assistant-native helpers/templates voor eenvoudige berekeningen en een aparte Python-service voor reproduceerbare intervalsimulatie. AppDaemon, pyscript of Node-RED worden pas gekozen na eisenvalidatie.

Verantwoordelijkheid: plannen en kosten berekenen zonder hardware te sturen in MONITOR/SIMULATION.

De eerste P2-008-implementatie gebruikt een aparte Python-optimizer. Deze maakt
een Day-Ahead-kwartierplan, vergelijkt vier gedeelde netpiekgrenzen, voert een
historische planned-versus-actual vergelijking uit en geeft bij onvolledige of
stale input `NO_ACTION`. De privacyveilige dashboardexport bevat geen
kwartierprofiel; het gedetailleerde plan blijft in `data/raw/`.

### 7. Control adapter

Nog niet geautoriseerd. Indien later nodig: kleine apparaat-specifieke adapters met limieten, command acknowledgement, timeout en revert-to-local.

### 8. Dashboard and decision log

Realtime flow, prijs- en forecasttijdlijn, werkelijke versus gesimuleerde kosten, status, planning en verklaarbare beslissingen.

Het dashboardoppervlak bestaat nu uit twee complementaire lagen:

- het standalone webdashboard voor historische evidence, financiële analyse en
  reproduceerbare besluitvorming;
- een HACS-installable Lovelace-kaart voor live Home Assistant-states,
  planvergelijking, piekruimte en data-qualitystatus.

De Lovelace-kaart is uitsluitend een observatie- en uitleglayer. Hij leest
states uit het frontend-`hass`-object, bevat geen servicecalls en ontvangt een
planning optioneel via een read-only planentity. De Python-optimizer blijft in
laag 6 en wordt niet naar browserlogica verplaatst.

## Owner Validation - voorlopige vergelijking controllerarchitectuur

### A. SMA-native optimalisatie

Er zijn nu twee verschillende SMA-routes die niet door elkaar mogen worden gehaald.

#### A1. Klassiek Home Manager forecast-based battery charging

- Past bij de huidige `System Manager`-rol en externe-setpointmodus van PV en SBS.
- Optimalisatiedoel `Economisch` is VERIFIED.
- Een dynamische `Day-Ahead`-marktfeed voor `BE` met EPEX Spot-bron en kwartierprijzen is zichtbaar.
- Forecast-based, geprioriteerd en tijdvenstergestuurd batterijladen staan momenteel uit.
- De zichtbare vereenvoudigde afnametoeslagconfiguratie bewijst niet dat Ecopowers multiplicatieve afnameformule exact wordt verwerkt.
- De terugleververgoeding staat als vast `€0,02/kWh` geconfigureerd. Dit is gelijk aan de vaste helft binnen de Groene Burgerstroom-injectieformule, maar niet aan de totale augustusvergoeding van `€0,0406/kWh`. SMA schrijft voor een variabele vergoeding een gemiddelde voor en adviseert voor dynamische tarieven een lage vaste waarde vanwege mogelijk zeer lage of negatieve marktprijzen.[29][38]
- De officiële functiematrix toont voor SHM2 geen prijsgebaseerde vermogensreductie bij negatieve tarieven.[26]
- De vaste waarde is dus een conservatieve optimalisatieproxy, geen exacte kopie van Groene Burgerstroom of de Ecopower Dynamic-injectieformule. Home Assistant-shadow billing moet alle contractformules apart evalueren.
- Interactie met de dynamische `0 W`-PCC-limiet moet worden gevalideerd: indien werkelijk zero-export actief is, verandert dat de praktische impact van de ontbrekende dynamische injectielogica.

Voorlopige status: A1 is technisch beschikbaar voor dynamische afnameprijzen en netladen, met een lage vaste injectieproxy zoals SMA aanbeveelt. Voor contractnauwkeurige afname-plus-injectieoptimalisatie blijven Home Assistant-simulatie en meetvalidatie nodig.

#### A2. SMA Premium met Energy Maximizer

- SMA's actuele productinformatie sluit installaties met Sunny Home Manager 2.0 als hoofdapparaat expliciet uit van SMA Premium/Energy Maximizer; bestaande Home Manager-functionaliteit blijft ongewijzigd.[25]
- De officiële functiematrix bevestigt voor Sunny Home Manager 2.0 ingebouwde optimalisatie voor dynamische tarieven en netladen, maar geen Energy Maximizer-functies zoals netontladen voor prijsarbitrage.[26]
- SMA beschrijft voor Home Manager 2.0 zelf de ingebouwde route: `Economisch` optimalisatiedoel, dynamisch tarief en activering van forecast-based battery charging; voor de vereiste laad-SOC noemt SMA `0%`.[5][27]
- Energy Maximizer is niet uitsluitend voor hybride omvormers; andere ennexOS System Managers kunnen eveneens worden ondersteund. Voor deze concrete Home Manager 2.0-installatie is de Premium-route echter niet van toepassing tenzij de systeemarchitectuur later bewust naar een ondersteunde System Manager wordt gemigreerd.[25][26]

Voorlopige status: A1 is de relevante SMA-route. A2 is voor de huidige installatie `NIET VAN TOEPASSING`, niet `UNKNOWN`.

### B. Home Assistant bepaalt en schrijft batterijstrategie

- SBS Modbus TCP staat momenteel uit.
- Home Manager is System Manager en SBS/PV staan in externe actiefvermogensmodus.
- Een directe HA-controller zou actuele ownership, watchdog, timeout en fallback moeten wijzigen of vervangen.
- De huidige SBS-fallback `Waarden behouden` vergroot het stale-setpointrisico.

Voorlopige status: niet passend bij de huidige configuratie; geen control toestaan.

### C. Hybride orchestration

- SMA behoudt exclusief de batterij- en PV-actuatorownership.
- Smappee `smart` blijft voorlopig exclusief eigenaar van de EV-laadplanning en lokale overbelastingsbeveiliging. De app bevestigt een actieve Grid-maximumcapaciteitsdrempel van `5,5 kW` bij Grid-configuratie `Driefasig – Delta`, `2 × 40 A`.
- Tijdens offline laden kan Smappee de `5,5 kW`-drempel niet garanderen; automatische overbelastingsbeveiliging is dan uit en een vaste `8 A` failsafe geldt.
- Home Assistant verzorgt read-only monitoring, prijs-/PV-forecast, shadow billing, EV-behoefteplanning en hogere orchestration.
- De HACS-integratie `smappee_ev` exposeert schrijfbare modus-, stroom- en start/stopcontrols via Smappee Dashboard API's en MQTT, maar deze worden in fase 1 niet gebruikt.[33]
- Eventuele strategie-input naar SMA of Smappee mag alleen via een officieel ondersteunde, conflictvrije interface en na expliciete ownershipoverdracht.

Voorlopige status: `INFERRED` als best passende richting, maar nog geen architectuurbesluit. ADR-002 blijft leidend: één actieve controller per actuator.

## Modusmodel

| Modus | Leest data | Simuleert | Stuurt hardware | Fallback |
|---|---|---|---|---|
| OFF | Minimaal | Nee | Nee | Lokale controllers |
| MONITOR | Ja | Nee | Nee | Lokale controllers |
| SIMULATION | Ja | Ja | Nee | Lokale controllers |
| SELF_CONSUMPTION | Ja | Optioneel | Mogelijk later | SMA/lokale standaard |
| DYNAMIC | Ja | Ja | Pas na aparte gates | SMA/lokale standaard |
| MANUAL | Ja | Nee/beperkt | Alleen expliciete tijdelijke opdracht | Timeout + lokale standaard |

Startmodus: MONITOR of SIMULATION.

## Voorlopig controller-ownershipmodel

| Functie | Voorkeurseigenaar fase 1 | Later te beslissen |
|---|---|---|
| Elektrische beveiliging | Hardware/installerconfiguratie | Niet verplaatsen |
| PV- en batterijbasiswerking | SMA | Externe optimalisatie alleen via officiële interface |
| Metering | Digitale meter + SMA meetpunt | Reconciliatie en bronprioriteit |
| EV-laadveiligheid en actieve laadmodus | Smappee EV Wall Home in `smart` | HA alleen read-only; externe planning pas na expliciete ownershipoverdracht |
| EV-stroomlimiet en overload protection | Smappee/installerconfiguratie | App-configuratie: 32 A chargermax, Grid `2 × 40 A`, 5,5 kW-drempel en 8 A offline fallback; fysiek en operationeel valideren |
| Prijs- en forecastanalyse | Home Assistant/data layer | Native versus externe optimizer |
| Shadow billing | Reproduceerbare simulatieservice | Opslag en rapportage |
| Dashboard | Home Assistant | Custom cards pas na wireframes |

## Datacontract per interval

Minimaal gewenst record:

- interval start/einde en timezone;
- grid import/export energy;
- PV energy;
- battery charge/discharge energy en SOC;
- EV charge energy;
- house energy of herleidbare energiebalans;
- actuele contractprijscomponenten;
- forecastwaarden en versies;
- quality flags en ontbrekende-datareden.

## Failure modes

| Fout | Vereist gedrag |
|---|---|
| Internet of marktdata weg | Geen nieuwe dynamische actie; laatste prijs niet stilzwijgend onbeperkt gebruiken |
| Home Assistant weg | SMA en Smappee blijven lokaal veilig functioneren; geen afhankelijkheid van HA-control |
| Smappee Dashboard/API weg | Offline laden blijft toegestaan op vaste `8 A`; automatische overbelastingsbeveiliging is dan uit en de 5,5 kW-drempel wordt niet gegarandeerd; geen HA-retryloop of verhoging |
| Smappee MQTT stale | Chargerdata als unavailable markeren; geen nieuw stroomsetpoint |
| Forecast ontbreekt | Simulatie markeert onzekerheid; conservative/no-control fallback |
| Entity unavailable | Geen nulwaarde veronderstellen; interval als incompleet markeren |
| Control acknowledgement ontbreekt | Commando stoppen, timeout en lokale modus herstellen |
| Conflicterende controller | Control blokkeren en zichtbaar alarm genereren |

## Besluiten die nog niet genomen zijn

- Home Assistant-native versus aparte optimizer.
- Opslagformaat en retentie voor auditdata.
- Exacte prijsintegratie.
- Controlinterface voor SBS, PV en charger.
- Gebruik van AppDaemon, pyscript, Node-RED of externe service.

Deze keuzes blijven open tot de componentinterfaces en simulatie-eisen zijn gevalideerd.

## Owner decision - volgende sturingsfase

Op 2026-10-01 gaf de eigenaar een go om de sturingsaanpak verder uit te werken,
omdat de dynamische contractbacktest en meerjarige gevoeligheden voldoende
interessant zijn. De autorisatie geldt uitsluitend voor ontwerp, offline
optimalisatie en read-only shadow planning.

De implementatievolgorde is:

1. Een aparte, reproduceerbare optimizer maakt een Day-Ahead-kwartierplan.
2. Home Assistant en het webdashboard tonen plan, redenen en afwijkingen maar
   sturen geen apparaten.
3. SMA blijft de enige actieve controller voor PV en batterij.
4. Smappee blijft de enige actieve controller voor EV-laden en load balancing.
5. Na voldoende shadow-resultaten volgt een apart testplan voor één beperkte,
   officieel ondersteunde actuatorroute.
6. Fysieke activatie vereist daarna een nieuwe expliciete eigenaarbeslissing.

## Owner decision - gezamenlijke dry-run sturingsontwikkeling

Op 2026-10-12 gaf de eigenaar expliciet toestemming om de gezamenlijke
batterij- en EV-sturingslogica te ontwikkelen. De goedgekeurde grens omvat:

- één kwartierplanner voor batterij en EV onder een gedeelde netimportlimiet;
- een actuator-neutraal intentcontract;
- een fail-closed safety supervisor met freshness-, ownership-, limiet-,
  acknowledgement-, timeout- en fallbackregels;
- niet-uitvoerbare dry-run adapters voor de SMA- en Smappee-routes;
- replay, fault injection, observability en planned-versus-actual scoring.

Niet geautoriseerd zijn Home Assistant-servicecalls, SMA- of Smappee-commando's,
MQTT-publicaties naar controltopics, setpoints, configuratiewijzigingen,
contractwijzigingen en fysieke actuatorproeven. SMA blijft exclusief eigenaar van
PV en batterij; Smappee blijft exclusief eigenaar van EV-laden en load balancing.

De uitvoeringsvolgorde is:

1. Definieer het gezamenlijke input-, intent- en resultaatcontract.
2. Breid de optimizer uit met EV-behoefte, vertrektijd, minimum-SOC,
   laadvenster en één gedeelde netimportlimiet.
3. Bouw de safety supervisor die ieder intent afzonderlijk accepteert of
   fail-closed omzet naar `NO_ACTION`.
4. Bouw SMA- en Smappee-dry-run adapters die uitsluitend voorgestelde commando's
   serialiseren en technisch niet kunnen uitvoeren.
5. Valideer normale scenario's, DST-dagen, stale/missing data,
   controllerconflicten, limietoverschrijding, timeouts en handmatige overrides.
6. Laat de prospectieve shadowvalidatie en settlement de gezamenlijke planning
   scoren; de bestaande eis van minimaal `12/12` dagen blijft staan.
7. Maak pas daarna een afzonderlijk testdossier voor één beperkte live route.
   Uitvoering daarvan vereist een nieuwe expliciete eigenaarbeslissing.

## Sources

[5] https://www.sma.de/en/products/energy-management/sunny-home-manager
[25] https://www.sma.de/en/products/energy-management/energy-maximizer
[26] https://manuals.sma.de/SMA-Premium/nl-NL/16915921419.html
[27] https://manuals.sma.de/HM-20-ennexOS/en-US/12563269899.html
[29] https://manuals.sma.de/HM-20-ennexOS/nl-NL/11412423819.html
[33] https://github.com/myny-git/smappee_ev
[38] https://cdn.nimbu.io/s/4tn7vz5/channelentries/spiilz4/files/1788271546519/202608_gbs_tariefkaart.pdf?w01uqtn=&dl=1 — Ecopower Groene Burgerstroom - tariefkaart augustus 2026
