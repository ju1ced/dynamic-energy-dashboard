# Gap Analysis

Status: read-only Phase 2 actief; P2-007 componentreconciliatie in uitvoering

Gerelateerd ticket: P1-009
Laatst bijgewerkt: 2026-10-01

## Prioriteitsdefinitie

- P0: blokkeert betrouwbare conclusie of veilige vervolgstap.
- P1: noodzakelijk voor bruikbare simulatie of ontwerpkeuze.
- P2: optimalisatie of kwaliteitsverbetering na de basis.

## Geïdentificeerde gaps

| Gap | Prioriteit | Huidige toestand | Benodigd bewijs/resultaat | Ticket |
|---|---:|---|---|---|
| PV-topologie en centrale begrenzing nog niet volledig gevalideerd | P1 | `8,5 kWp` DC, `8 kW` AC, modellen, firmware, fasen en Modbusstatus zijn VERIFIED | Panelen/strings, Home Manager-setpointgedrag, curtailment en injectietest | P3-003 |
| Werkelijke batterijcapaciteit en `Battery Capacity Total`-semantiek nog niet gevalideerd | P1 | RESU16H Prime, 16 kWh, BMS `23.11.0.R`, HA-waarde 89%, SOC/power en cumulative energy zijn VERIFIED | Officiële betekenis van capacity-register, bruikbare-capaciteitstest en langere datadekking | P3-003 |
| Arbitrageondersteuning installatie-specifiek onbewezen | P0 voor activatie | Native externe-setpointmodus staat geconfigureerd; Modbus TCP is uit | SHM-prijsconfiguratie, setpointownership, grid-chargegedrag, failure mode en garantie-impact | P3-003 |
| Ingebouwde SHM2-dynamische optimalisatie nog niet operationeel gevalideerd | P0 voor activatie | Economisch doel, BE Day-Ahead/EPEX-feed en configureerbare forecast charging zijn VERIFIED; SHM2 ondersteunt dynamische afnameoptimalisatie en netladen | Activering, werkelijk laadgedrag, afnametoeslag en 0 W-PCC-semantiek | P3-003 |
| Lage vaste SHM2-injectieproxy moet worden gekalibreerd | P1 | Terugleververgoeding is VERIFIED als €0,02/kWh; SMA adviseert bij dynamische tarieven een lage vaste waarde wegens lage/negatieve marktprijzen | Vergelijk proxy met Ecopower-kwartierformule, test negatieve prijsimpact en valideer mogelijke zero-export | P2-002 / P3-003 |
| Laadpaalinstallatie en controlownership niet volledig gevalideerd | P0 voor activatie | EV Wall Home-componentfirmware, 32 A chargermax, smart/solar, Grid `Driefasig – Delta`, `2 × 40 A`, 5,5 kW-capaciteitsdrempel en 8 A offline fallback zijn VERIFIED | Fysieke aansluiting/groep, CT-topologie, OCPP-status, werkelijk load-balancinggedrag en fallbacktest | P3-003 |
| Historische vijfminutenretentie is beperkt | P1 | Recente 5-minutenreeks is bruikbaar; hourly Grid levert 3.118 volledig gereconcilieerde Fluvius-overlapuren | Voor toekomstige kwartiermonitoring periodiek exporteren; oude kwartieren niet reconstrueren | P2-001 / P2-005 |
| Meerjarige energie- en prijsdekking zijn compleet, vaste tariefcomponenten niet uitgesplitst | P0 voor contractadvies | Fluvius en Belgische ENTSO-E Day-Ahead-prijzen dekken exact 105.216 kwartieren; de DSMR-export levert 36 maanden all-in tarieven en vaste dagkosten. Na toevoeging van het dynamische abonnement bedraagt de sensitivity gemiddeld `€268,67/jaar` voordeel. In het gevalideerde factuurjaar maskeert een totaalverschil van `€-24,37` een variabele afwijking van `€-102,56` en vaste afwijking van `€+78,19` | DSMR-vaste dagkosten voor de twee overige jaren uitsplitsen en onafhankelijk toetsen aan tariefkaarten/facturen, Fluvius West-netcomponenten, heffingen en btw | P2-007 |
| Oudere DSMR-contractrecordextractie week vier maanden af van HA | Opgelost voor prijsledger | De aangeleverde DSMR-schermexport bevat de actuele maandprijzen; alle negen historische HA-maandwaarden van 2026 stemmen nu exact overeen | Alleen onafhankelijke factuur-/tariefkaartvalidatie blijft open | P2-007 |
| DSMR-historie bevat meetgaten | P1 | Read-only export bevat 200 ontbrekende uren, 926 ontbrekende kwartierpieken en één ontbrekende dag | Fluvius primair houden; DSMR alleen gebruiken waar dekking per interval aantoonbaar is | P2-007 |
| Grid-CT-topologie en meetgedrag niet volledig verklaard | P1 | P1, Smappee en SMA Grid-power liggen live binnen 1,2%; fysieke aansluiting OWNER CONFIRMED | Langdurige kwartierreconciliatie en verklaring van Smappee tweekanaals-/deltaweergave | P2-001 / P3-003 |
| PV/Battery/EV hebben geen volledig historisch kwartierjaar | P1 | Fluvius Grid is volledig; HA-hourly Grid is gereconcilieerd; apparaatstromen hebben kortere of grovere dekking | Scenario's B-D beperken tot aantoonbare overlap en energiebalans valideren | P2-005 / P3-001 / P3-002 |
| Energiebalans alleen live gevalideerd | P1 | HA-house template verschilt bij live test 0,97% van Smappee; bestaande daily house helper heeft onvolledige formule | Intervalreconciliatie en vervangend berekeningsmodel buiten productie-HA | P1-007 / P2-002 |
| Forecastlaag voor PV operationeel geëvalueerd; load/EV nog open | P1 | `75` Solcast-versies over zeven voltooide doeldagen bewaren issue time en revisies; Day-Ahead MAE is `6,936 kWh`, met één zichtbaar retentiegat | Langere automatische issue-timeopslag, kwartierforecastcurve en afzonderlijke load-/EV-forecast bouwen | P2-005 / vervolg shadow-controller |
| Scenario A is één component-complete contractbacktest | P0 voor contractadvies | Het gevalideerde factuurjaar toont `€-246,09` inclusief btw; daarnaast zijn drie afzonderlijke jaren als geconfigureerde tariefsensitivity berekend | De driejarige sensitivity pas als contractadvies behandelen na component-complete historische reconciliatie | P2-007 |
| Dashboarduitbreiding voor meerjarige scenario's | P1 | Het read-only webdashboard toont nu drie afzonderlijke financiële sensitiviteitsjaren, batterijscenario's en kwaliteitsstatus | Component-complete bedragen later naast de sensitivity plaatsen zonder de classificatie te verbergen | P2-003 / P2-007 |
| Decision-logdatamodel operationeel | P1 | Zeven formele entries onderscheiden metingen en simulatiebesluiten en leggen read-only constraints vast | Log bij iedere nieuwe gevalideerde analyse deterministisch regenereren | P2-006 |
| Control-fallback niet getest | P0 voor activatie | Lokale werking verondersteld, niet vastgelegd | Failure-modeplan en gecontroleerde tests | P3-003 |

## Verplicht vóór financiële conclusie

1. Exact huidig contract en dynamische formule.
2. Werkelijke import en export op contractueel relevante intervalresolutie.
3. Correcte behandeling van vaste kosten, netkosten, heffingen, btw en injectie.
4. Ten minste één factuur- of portaalperiode voor reconciliatie.
5. Transparante omgang met ontbrekende intervallen en tijdzones.

## Verplicht vóór fysieke sturing

1. Officieel ondersteunde interface per apparaat.
2. Bevestigde setpointlimieten, rate limits en veilige defaults.
3. Eén controller per actuator.
4. Handmatige override en automatische timeout.
5. Terugval naar lokale SMA-/laadpaalwerking zonder Home Assistant.
6. Monitoring van commando, bevestigde status en werkelijk effect.
7. Goedkeuring van eigenaar na simulatie en risicoanalyse.

## Optionele investeringen

Nog niet te adviseren. Eventuele hardware- of software-investeringen worden pas beoordeeld nadat charger, PV-omvormers, batterij en datafeeds exact zijn geïdentificeerd. Mogelijke categorieën zijn een lokale meetinterface, een regelbare laadpaal, extra submeting of een ondersteunde EMS-koppeling; dit zijn geen huidige aanbevelingen.

## Sources

[38] https://cdn.nimbu.io/s/4tn7vz5/channelentries/spiilz4/files/1788271546519/202608_gbs_tariefkaart.pdf?w01uqtn=&dl=1 — Ecopower Groene Burgerstroom - tariefkaart augustus 2026
