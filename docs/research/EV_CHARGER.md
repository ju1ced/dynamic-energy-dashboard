# EV and Charger Research

Status: owner-validation actief; Smappee EV Wall Home en Home Assistant-integratie geïdentificeerd  
Gerelateerd ticket: P1-006  
Raadpleegdatum: 2026-09-28

## Kia EV6

De actuele Nederlandse Kia-prijslijst voor de EV6 GT-Line RWD noemt een 84 kWh-accu, maximaal 11 kW AC-laden en een indicatieve AC-laadtijd van circa 8,5 uur bij drie fasen en 16 A.[14]

Kia Connect ondersteunt voertuigafhankelijk laadstatus, resterende laadtijd, doelpercentage, gepland laden en remote start/stop.[15] De bruikbaarheid voor deze auto moet in de actuele app en voertuigsoftware worden bevestigd.

Voertuigclouddata is geschikt voor langzame planning, niet als enige realtime veiligheidsinput. SOC moet altijd een timestamp en stale-status hebben; actuele stroom en vermogen komen bij voorkeur lokaal uit de laadpaal.

Kia Smart Charge ondersteunt volgens Kia de EV6 facelift als afzonderlijke laadoptimalisatiedienst.[16] Als die actief is, moet worden voorkomen dat Kia Smart Charge, het voertuigschema, de laadpaalcloud en Home Assistant tegelijk dezelfde laadsessie plannen.

## Laadpaal

### OWNER CONFIRMED

- Merk/model: Smappee EV Wall Home.
- De laadpaal is in Home Assistant geïntegreerd.

### Modelcapaciteiten uit officiële Smappee-documentatie

- De EV Wall Home-productfamilie ondersteunt maximaal `7,4 kW` enkelfasig of `22 kW` driefasig; de werkelijke installatieconfiguratie moet afzonderlijk worden bevestigd.[34][35]
- Smappee onderscheidt `Standard`, `Smart` en `Solar` charging. Smart charging gebruikt overbelastingsbeveiliging; Solar laadt op basis van zonne-overschot en kan netondersteuning configureren.[36][37]
- Smappee vermeldt OCPP `1.6J` als activeerbare optie voor EV Wall Home. Dit bewijst niet dat OCPP op deze installatie geactiveerd is.[34]

### VERIFIED via read-only Home Assistant MCP

De actieve integratie is niet de beperkte Home Assistant Core-integratie `smappee`, die EV-laadstations niet ondersteunt.[32] Het betreft de HACS custom integratie `smappee_ev`, versie `2026.9.1`; die gebruikt Smappee Dashboard REST API's voor configuratie/control en MQTT voor live meetdata.[33]

Privacygevoelige serienummers, locatie-ID's, persoonsnamen en sessieattributen zijn niet in Git vastgelegd. Hieronder staan alleen gemaskeerde entitypatronen en functionele waarden:

- platform: `smappee_ev`; MQTT-verbinding actief;
- laadmodus: `smart`; beschikbare modi: `standard`, `smart`, `solar`;
- connector-maximale stroom: `32 A`;
- regelbaar laadstroombereik: `6–32 A`; actuele limiet `6 A`;
- maximum-capacity instelling: `5,5 kW`; semantiek als site-/capaciteitslimiet, niet als fysieke charger-rating;
- minimale solar-surpluswaarde: `100%`;
- offline laden: aan; offline failsafe-stroom `8 A`;
- overload-/hoofdstroomonderbrekerinstelling rapporteert `40 A`;
- station beschikbaar; laadstatus `stopped`; EVSE-status `available`;
- live laadvermogen bij validatie: `2 W`;
- cumulatieve connectorenergie: `12722,415 kWh`;
- stroomentities per fase en totaal zijn aanwezig;
- de integratie exposeert start/stop/pause/resume, modus, stroomlimiet en beschikbaarheid als schrijfbare controls, maar geen control is uitgevoerd.

De hoofdbeveiligingsentity rapporteert `40 A` terwijl de entitymetadata een maximum van `32 A` vermeldt. De Smappee-app verduidelijkt dit: het Grid-circuit staat op `2 × 40 A`, terwijl de Charging Controller zelf maximaal `32,0 A` ondersteunt. De custom HA-entitymetadata modelleert deze twee verschillende limieten dus onduidelijk; ze mag niet als primaire elektrische configuratiebron worden gebruikt.

Voor de directe `smappee_ev`-entities voor vermogen, stroom en cumulatieve energie werd geen recorderhistoriek over 24 uur en geen long-term statistics over 30 dagen gevonden. Er bestaan wel oudere laadpaalhelpers/utility meters; hun bron en continuïteit worden later afzonderlijk gevalideerd.

De sessie-energie-entity bevat privacygevoelige sessie-, gebruiker-, RFID- en vergoedingsattributen. Deze attributen mogen niet naar Git, brede dashboards of diagnostische exports worden gekopieerd.

### VERIFIED via Smappee-appscreenshots

- Grid-configuratie: `Driefasig – Delta` en maximale stroom `2 × 40 A`.
- Maximumcapaciteitsdrempel: actief op `5,5 kW`; de app toont een gemiddelde 15-minutenverbruikspiek van `7,50 kW`.
- De app waarschuwt dat de maximumcapaciteitsdrempel tijdens offline laden niet gegarandeerd kan worden.
- Grid-CT-configuratie: zichtbare CT-kanalen op `L1` en `L2`; actuele meetvelden stonden op `---`.
- Laadstationcircuit: type `Laadstation`, `Gemeten door het net = Ja`, met zichtbare CT-toewijzingen op `L1` en `L2`.
- Charging Controller: firmware `2.36`; maximale ondersteunde stroom `32,0 A`.
- Smappee Connect: firmware `EC 3.92`; Ethernet en wifi zijn beschikbare verbindingsmethoden, maar de actieve methode is niet zichtbaar.
- Power Box: firmware `1.76`.
- CT Hub: firmware `1.02`.
- Solid Core 3-phase CT: firmware `1.36`.
- RFID-lezer: firmware `1.72`.
- Offline laden staat aan. Automatische overbelastingsbeveiliging is volgens het scherm tijdens offline laden uitgeschakeld; vaste foutveilige maximumstroom `8 A`.
- Smappee-tarieven ondersteunt een dynamische-tarieffunctie, maar activering en concrete prijswaarden zijn niet zichtbaar. Het scherm vermeldt expliciet dat heffingen en andere kosten niet worden meegerekend.
- De Smappee-productiecircuits `SMA 1` en `SMA 2` staan op `Export zonne-energie = Alleen het overschot`; hybride-omvormer staat voor beide uit. Dit is meet-/classificatieconfiguratie, geen bewijs dat EV Solar charging actief is.

Alle zichtbare serienummers en persoons-/installatienamen blijven gemaskeerd en buiten Git.

### OWNER CONFIRMED - fysieke aansluiting

De eigenaar bevestigt dat de werkelijke netaansluiting en hoofdbeveiliging volledig overeenkomen met de Smappee-configuratie: `Driefasig – Delta`, `2 × 40 A`.

Dit bevestigt de fysieke Grid-topologie op owner-evidence-niveau. Chargerfasegebruik tijdens werkelijk laden, CT-topologie en Smappee-regelgedrag blijven `REQUIRES TESTING`.

### INFERRED / REQUIRES TESTING

- `5,5 kW` is nu VERIFIED als actieve Grid-maximumcapaciteitsdrempel, niet als fysieke charger-rating.
- `2 × 40 A` is VERIFIED als Smappee Grid-configuratie; bevestiging dat dit exact overeenkomt met de fysieke netaansluiting en hoofdbeveiliging blijft nodig.
- De zichtbare CT-configuratie en het driefasige CT-moduletype bewijzen niet zelfstandig dat alle fysieke fasen correct aangesloten en gemeten worden; actuele velden stonden op `---`.
- Native Smappee `smart` en de maximumcapaciteitsdrempel vormen sterke aanwijzingen dat Smappee de actieve laad- en overbelastingscontroller is. Werkelijk regelgedrag moet nog worden getest.
- Offline laden heeft een expliciete `8 A` fallback zonder automatische overbelastingsbeveiliging; de fysieke veiligheid van die waarde hangt af van de bevestigde aansluiting.
- OCPP-activatie, Modbusondersteuning, lokale API en eventuele SMA-koppeling zijn nog niet bevestigd.
- De HACS-integratie is cloud-/MQTT-afhankelijk en expliciet een communityproject; ze is bruikbaar voor observatie maar wordt niet zonder aparte failure-mode- en controlownershiptest als veiligheidskritische controller ingezet.[33]

OCPP is een protocol tussen laadpaal en een managementsysteem; protocolondersteuning alleen bewijst niet dat een eigenaar een eigen backend mag configureren of dat alle smart-chargingfuncties aanwezig zijn.[17]

Home Assistant kan Modbus TCP/RTU gebruiken, maar alleen met een officiële, firmwarepassende registermap en bekende schaal/datatype-/schrijfsemantiek.[18]

## Veilige toekomstige controlgrens

- Laadpaal en elektrische installatie blijven leidend voor veiligheid.
- Home Assistant mag later alleen gedocumenteerde start/stop- of stroomsetpoints sturen.
- Na ieder commando worden setpoint, status en werkelijk vermogen teruggelezen.
- Load balancing gebruikt lokale voldoende snelle netmeting, niet Kia-cloud-SOC.
- Stale data verhoogt nooit automatisch de laadstroom.
- Minimum-SOC en vertrektijd hebben voorrang op prijsoptimalisatie.
- Er is één primaire scheduler en een zichtbare `Charge now`-override.
- Geen hard schakelen van een actieve laadgroep met een externe slimme schakelaar.

## Owner evidence required

1. Bevestiging door eigenaar/installateur dat de Smappee-configuratie `Driefasig – Delta`, `2 × 40 A` overeenkomt met de fysieke netaansluiting en hoofdbeveiliging.
2. Verklaring waarom alleen Grid-CT's op `L1` en `L2` zichtbaar zijn en waarom actuele CT-waarden `---` tonen.
3. Type dynamische load balancing en exacte lokale meetbron operationeel testen.
4. OCPP-activeringsstatus en mogelijkheid tot eigen backend.
5. Eventuele officiële Modbus-registermap of lokale API-documentatie.
6. Kia Connect-status en zichtbare voertuigfuncties.
7. Normale target-SOC, minimale vertreks-SOC en typische vertrektijden.

## Sources

[14] https://www.kia.com/content/dam/kwcms/kme/nl/nl/assets/contents/utility/price-list/Kia-Netherlands-EV6-prijslijst.pdf?2025=
[15] https://connect.kia.com/nl/customer-support/feature-guides
[16] https://connect.kia.com/nl/customer-support/smart-charge-faq
[17] https://openchargealliance.org/protocols/open-charge-point-protocol
[18] https://www.home-assistant.io/integrations/modbus
[32] https://www.home-assistant.io/integrations/smappee
[33] https://github.com/myny-git/smappee_ev
[34] https://support.smappee.com/hc/en-gb/articles/4402413229844-EV-Wall-Home
[35] https://support.smappee.com/hc/en-gb/articles/5721996814612-Smappee-EV-Line-charging-speeds
[36] https://support.smappee.com/hc/en-gb/articles/4900468508692-How-to-configure-charging-modes-and-schedules-for-Smappee-EV-Line
[37] https://support.smappee.com/hc/en-gb/articles/4406735969940-The-Smappee-Smart-Charging-Functionality
