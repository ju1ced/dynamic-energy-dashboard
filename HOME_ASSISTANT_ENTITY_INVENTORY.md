# Home Assistant Entity Inventory

Status: volledige fase-1 read-only inventaris uitgevoerd voor Grid, PV, Battery, EV, Charger, House, Tariffs, Forecast, Costs en SMA  
Gerelateerd ticket: P1-007  
Laatst bijgewerkt: 2026-09-28

## Scope en veiligheidsgrens

Deze inventaris is uitsluitend read-only uitgevoerd via Home Assistant MCP. Er zijn geen entities, helpers, templates, dashboards, recorderinstellingen, automations, integraties of apparaatinstellingen gewijzigd.

Entity-ID's met serienummers, station-ID's, accounts of persoonlijke installatienamen worden in Git gemaskeerd. De lokale Home Assistant-registratie blijft de operationele bron voor de exacte ID's.

## Beoordelingsvelden

| Veld | Doel |
|---|---|
| Entity ID | Technische referentie; gevoelige delen worden gemaskeerd |
| Groep | Grid, PV, Battery, EV, Charger, House, Tariffs, Forecast, Costs of SMA |
| Integratie | Herkomst en ownership |
| Unit | W, kW, kWh, %, EUR/kWh enzovoort |
| Device class | Betekenis en Energy Dashboard-compatibiliteit |
| State class | `measurement`, `total` of `total_increasing` |
| Recorder | Recente raw state-history aanwezig of ontbrekend |
| LTS | Long-term statistics aanwezig, ontbrekend of semantisch ongeschikt |
| Datakwaliteit | Tekenconventie, resets, latency, formule en reconciliatie |

## Voorgestelde bronhiërarchie

| Functie | Primaire read-only bron | Reconciliatiebron | Status |
|---|---|---|---|
| Netimport/-export energie | HomeWizard P1 cumulatieve import/export | Fluvius-kwartierexport en factuur | Technisch bruikbaar; contractreconciliatie vereist |
| Netvermogen | HomeWizard P1 signed power | DSMR Reader, Smappee en SMA-meter | Drie onafhankelijke bronnen beschikbaar |
| PV-vermogen en -energie | Som van beide SMA-PV-omvormers | Smappee-productiemeting | Technisch bruikbaar |
| Batterij | SMA SBS cumulatieve laad-/ontlaadenergie, vermogen en SOC | Energiebalans | Technisch bruikbaar; SOC-strategie open |
| EV-laadenergie | Smappee connector cumulative energy | Kia/Tronity charging power en sessiegegevens | Technisch bruikbaar vanaf beperkte historie |
| Huisvermogen | Afgeleide energiebalans-template | Smappee house consumption | Live bruikbaar en cross-validated |
| Huisenergie | Opnieuw afleiden uit intervalstromen | Fluvius/PV/batterij/chargerbalans | Bestaande daily helper is ongeschikt |
| PV-forecast | Solcast | Werkelijke SMA-PV-productie | Beschikbaar; forecastversies nog modelleren |
| Contractprijs | Geversioneerde Ecopower-tariefkaarten | Factuur | Niet uit bestaande HA-prijshelpers overnemen |
| Dynamische prijs | Nog geen HA-entity | Officiële/contractpassende EPEX-feed | Ontbreekt |

## Geverifieerde kernentities

| Groep | Entity | Integratie/type | Unit | State class | Recorder/LTS | Beoordeling |
|---|---|---|---|---|---|---|
| Grid | `grid_import_energy` | HomeWizard | kWh | `total_increasing` | Ja / minstens 263 dagen | Private alias; primaire importteller |
| Grid | `grid_export_energy` | HomeWizard | kWh | `total_increasing` | Ja / minstens 263 dagen | Private alias; primaire exportteller |
| Grid | `grid_power` | HomeWizard | W | `measurement` | Ja / minstens 263 dagen | Private alias; signed net power |
| Grid | `alternate_grid_import_power` | DSMR Reader | W | `measurement` | Ja / minstens 30 dagen | Private alias; onafhankelijke importbron |
| Grid | `alternate_grid_export_power` | DSMR Reader | W | `measurement` | Ja / minstens 30 dagen | Private alias; onafhankelijke exportbron |
| Grid | `month_peak` | Utility Meter | kW | `total` | Ja / minstens 30 dagen | Private alias; gebruik actuele state |
| PV | `pv_power` | Sensor Group | W | `measurement` | Ja / minstens 30 dagen | Private alias; primaire PV-powerbron |
| PV | `pv_generation` | Sensor Group | MWh | `total_increasing` | Ja / minstens 250 dagen | Private alias; cumulatieve PV-energie |
| PV | `pv_daily_helper` | Template | kWh | `total_increasing` | Ja, maar semantisch fout | Private alias; dagreset maakt LTS onbetrouwbaar |
| House | `house_power` | Template | W | `measurement` | Ja / minstens 30 dagen | Private alias; exclusief batterijlaadvermogen |
| House | `house_power_gross` | Sensor Group | W | `measurement` | Ja / minstens 30 dagen | Private alias; inclusief batterijlaadlast |
| House | `house_daily_helper` | Template | kWh | `total_increasing` | Ja, maar semantisch fout | Private alias; geen geldige totale huisenergie |
| Battery | `battery_soc` | SMA | % | `measurement` | Ja / minstens 30 dagen | Private alias; actuele SOC |
| Battery | `battery_charge` | SMA | kWh | `total_increasing` | Ja / minstens 253 dagen | Private alias; cumulatieve laadenergie |
| Battery | `battery_discharge` | SMA | kWh | `total_increasing` | Ja / minstens 253 dagen | Private alias; cumulatieve ontlaadenergie |
| Battery | `battery_charge_power` | SMA | W | `measurement` | Ja / minstens 30 dagen | Private alias; actueel laadvermogen |
| Battery | `battery_discharge_power` | SMA | W | `measurement` | Ja / minstens 30 dagen | Private alias; actueel ontlaadvermogen |
| Battery | `battery_capacity_indicator` | SMA | % | Geen | Recorder ja / LTS nee | Private alias; exacte SoH-semantiek blijft `INFERRED` |
| Charger | `ev_charge_power` | `smappee_ev` | W | `measurement` | Ja / minstens 30 dagen | Private alias; primaire laadvermogensbron |
| Charger | `ev_charge` | `smappee_ev` | kWh | `total_increasing` | Ja / minstens 62 dagen | Private alias; cumulatieve EV-laadenergie |
| Charger | `ev_session_energy` | `smappee_ev` | kWh | `total` | Recorder en LTS aanwezig | Private alias; alleen per sessie gebruiken |
| Charger | `ev_charge_status` | `smappee_ev` | enum | Geen | Recorder ja / LTS nee | Private alias; geen numerieke statistiek verwacht |
| EV | `vehicle_soc_primary` | Kia UVO | % | `measurement` | Ja / minstens 30 dagen | Private alias; voertuig-SOC-kandidaat |
| EV | `vehicle_charge_power_primary` | Kia UVO | kW | `measurement` | Ja / minstens 30 dagen | Private alias; secundair aan charger |
| EV | `vehicle_soc_secondary` | Tronity | % | `measurement` | Ja / minstens 30 dagen | Private alias; SOC-reconciliatie |
| EV | `vehicle_charge_power_secondary` | Tronity | kW | `measurement` | Ja / minstens 30 dagen | Private alias; charge-powerreconciliatie |
| Forecast | `pv_forecast_today` | Solcast | kWh | `total` | Ja / minstens 111 dagen | Private alias; gebruik state per issue time |
| Forecast | `pv_forecast` | Solcast | kWh | `total` | Ja / minstens 30 dagen | Private alias; dagforecast |
| Forecast | `pv_forecast_current_power` | Solcast | W | `measurement` | Ja / minstens 30 dagen | Private alias; updatecadans circa vijf minuten |
| Tariffs | `tariff_reference_import` | Handmatige helper | EUR/kWh | Geen | Recorder ja / LTS nee | Private alias; niet contractnauwkeurig bewezen |
| Tariffs | `tariff_reference_export` | Handmatige helper | EUR/kWh | Geen | Recorder ja / LTS nee | Private alias; niet volledige vergoeding |
| Costs | `tariff_total_helper` | Min/Max sum helper | EUR/kWh | `measurement` | Ja / minstens 30 dagen | Private alias; geen factuurmodel |
| Costs | `tariff_annual_average_helper` | Min/Max mean helper | EUR/kWh | `measurement` | Ja / minstens 30 dagen | Private alias; ongewogen gemiddelde |

## Grid

### VERIFIED

- HomeWizard P1 levert cumulative import/export met `device_class: energy` en `state_class: total_increasing`.
- P1-netvermogen heeft `device_class: power`, `state_class: measurement` en bevat ook negatieve waarden tijdens export.
- DSMR Reader levert afzonderlijk actueel import- en exportvermogen.
- Geobserveerde state-changecadans tijdens belasting:
  - HomeWizard P1 ongeveer vijf seconden;
  - DSMR Reader ongeveer zes seconden.
- Minstens 263 dagelijkse LTS-buckets zijn beschikbaar vanaf 9 januari 2026 voor P1 import en export.
- De maandpiek-helper gebruikt een private bronalias. Voor capaciteitstariefberekening moet de actuele maandpiekstate worden gebruikt; de statistische `sum` van deze helper heeft geen financiële betekenis.

### Live reconciliatie tijdens EV-laden

Een read-only momentopname met circa 4,3 kW EV-laden gaf:

| Vergelijking | Waarden | Absoluut verschil | Relatief verschil |
|---|---:|---:|---:|
| P1 versus Smappee Grid | 4.784 W versus 4.727 W | 57 W | 1,20% |
| P1 versus SMA-meter | 4.784 W versus 4.816 W | 32 W | 0,67% |

Dit is sterk bewijs dat de drie bronnen dezelfde netstroom volgen. Eén momentopname bewijst nog geen structurele kwartiernauwkeurigheid; daarvoor blijft Fluvius-reconciliatie nodig.

## PV

### VERIFIED

- Bronalias `pv_power` is een Sensor Group van de twee SMA-PV-omvormers.
- Bronalias `pv_generation` is de som van beide cumulatieve SMA-yieldtellers.
- De live PV-groepswaarde en Smappee-PV-waarde waren beide exact `1.762 W` op hetzelfde meetmoment.
- Cumulatieve PV-LTS is beschikbaar vanaf 22 januari 2026.

### Data-quality issue

De private bronalias `pv_daily_helper` deelt een dagelijkse yield door 1000, maar declareert `state_class: total_increasing`. De bron reset dagelijks. Daardoor bevatten LTS-`sum` en `change` onbruikbare cumulaties. Gebruik voor intervalanalyse de cumulatieve totaalopbrengst of een correct gemodelleerde utility meter; wijziging gebeurt pas in een apart goedgekeurd ticket.

## House consumption

### VERIFIED live formule

De read-only template is:

`house = PV + grid_import - grid_export - battery_charge + battery_discharge`

Dit is consistent met een huislast exclusief batterijlaadvermogen. Tijdens de live vergelijking:

- afgeleide HA-house power: `6.553 W`;
- Smappee house consumption: `6.490 W`;
- verschil: `63 W`, oftewel `0,97%`.

De onafhankelijke Smappee-meting ondersteunt de templateformule voor live vermogen.

### Data-quality issues

- Bronalias `house_power_gross` is een som van PV, batterijontlading en signed P1-netvermogen. De waarde vertegenwoordigt praktisch huislast plus batterijlaadlast; zij is niet gelijk aan dezelfde semantiek als de netto-template.
- Bronalias `house_daily_helper` gebruikt uitsluitend `PV_daily - grid_export_daily`. Gridimport en batterijstromen ontbreken. Deze helper is daarom geen geldige totale huishoudelijke energiebron.
- De daily helper declareert bovendien `total_increasing` terwijl hij dagelijks reset; de LTS-sommen zijn daardoor ongeschikt.
- Shadow billing moet huisenergie uit dezelfde intervalbalans afleiden en mag deze daily helper niet gebruiken.

## Battery en SMA

- Model, cumulative charge/discharge, SOC en laad-/ontlaadvermogen zijn technisch gevalideerd.
- LTS-dekking:
  - cumulative laad- en ontlaadenergie vanaf 12 januari 2026;
  - minstens 30 dagen voor SOC en power.
- `Battery Capacity Total = 89%` heeft recorderhistoriek maar geen state class of LTS. De waarde is VERIFIED; interpretatie als exacte SoH blijft `INFERRED`.
- Actuele minimum-/reserve-SOC, bruikbare capaciteit en werkelijk controllergedrag blijven open.

## EV charger

### VERIFIED

- Directe Smappee-entities voor charger power, cumulative energy en session energy hebben nu zowel recorderhistoriek als long-term statistics.
- Historische dekking van de cumulative connectorenergie begint op 29 juli 2026 en omvat minstens 62 dagelijkse buckets.
- Tijdens actief laden:
  - Smappee connector: `4.293 W`;
  - Kia/Tronity: `4,3 kW`;
  - verschil: circa `7 W` of `0,16%`.
- De geobserveerde Smappee-state-changecadans tijdens laden is ongeveer vijf seconden.
- Enum/statusentities hebben terecht geen numerieke LTS.

Dit vervangt de eerdere voorlopige conclusie dat de directe chargerentities geen recorder/LTS hadden. Externe writecontrols blijven verboden.

## EV

- Kia UVO en Tronity leveren afzonderlijke SOC- en laadvermogensbronnen.
- Tijdens de validatie rapporteerden zij circa `57,5–58%` SOC en beide `4,3 kW` laadvermogen.
- Beide bronnen hebben minstens 30 dagen LTS.
- De geobserveerde cloud-updatecadans is grofweg één tot vijftien minuten en is daardoor geschikt voor planning/reconciliatie, niet als primaire snelle vermogensbron.
- De Smappee connector blijft primair voor geleverde laadenergie; Kia/Tronity zijn secundair voor voertuig-SOC, plugstatus en cross-checks.

## Forecast

- Solcast is actief en levert forecast today, tomorrow, remaining today, peak power/times en current power.
- Cumulatieve historische dekking voor de today-forecast begint op 10 juni 2026 en omvat minstens 111 dagelijkse buckets.
- De current-power forecast wijzigt ongeveer iedere vijf minuten.
- De dagforecast is een voorspelde state die gedurende de dag wordt herzien. LTS-`sum` of `change` is geen voorspelde energieproductie en mag niet als factuurinput worden gebruikt.
- Voor scenariovalidatie moeten forecast issue time, target interval en werkelijke PV afzonderlijk worden opgeslagen.

## Tariffs en costs

### VERIFIED huidige HA-toestand

- Er is geen entity of configuratiematch voor `EPEX` gevonden.
- Bestaande Ecopower-helpers zijn handmatig en niet geversioneerd:
  - augustushelper `0,2773 EUR/kWh`;
  - terugleververgoeding `0,02 EUR/kWh`;
  - algemene energiekost `0,1542 EUR/kWh`;
  - gecombineerde `Nettarieven GSC WKK` `0,1352 EUR/kWh`;
  - afgeleide totale kost `0,2894 EUR/kWh`.
- Bronalias `tariff_total_helper` is uitsluitend de som van de twee handmatige inputwaarden.
- Bronalias `tariff_annual_average_helper` is een ongewogen gemiddelde van twaalf handmatige maandinputs.

### Beoordeling

Deze helpers hebben geen formuleversie, geldigheidsinterval, bronstatus, btw-componentering of betrouwbare afname-/injectiescheiding. De `0,02 EUR/kWh`-helper is aantoonbaar niet de volledige Groene Burgerstroom-injectievergoeding van augustus 2026. Geen van deze helpers mag als factuurbron voor shadow billing dienen.

## Historische beschikbaarheid

| Datastroom | Eerste aangetroffen dagelijkse LTS-bucket | Aantal aangetroffen dagen | Beoordeling |
|---|---:|---:|---|
| P1 import/export | 2026-01-09 | 263 | Geschikt voor initiële shadow-billingperiode |
| PV cumulative total | 2026-01-22 | 250 | Geschikt vanaf gezamenlijke startdatum |
| Battery charge/discharge | 2026-01-12 | 253 | Geschikt vanaf gezamenlijke startdatum |
| Smappee charger cumulative energy | 2026-07-29 | 62 | EV-scenariohistorie is korter |
| Solcast today forecast | 2026-06-10 | 111 | Forecastevaluatie is korter |

De gemeenschappelijke historische periode voor Grid, PV en Battery start voorlopig op 22 januari 2026. EV-charger- en Solcastscenario's hebben respectievelijk pas vanaf 29 juli en 10 juni 2026 dekking.

## Geschiktheid voor shadow billing

### Direct bruikbaar

- P1 cumulative import/export voor intervaldelta's.
- SMA cumulative PV-energy.
- SMA cumulative battery charge/discharge.
- Smappee cumulative charger energy.
- P1/DSMR/Smappee/SMA live power voor kwaliteitscontrole.
- Solcast voor forecastversus-actual-analyse.

### Niet rechtstreeks gebruiken

- Dagelijkse helpers met `total_increasing` en resets.
- Bronalias `house_daily_helper` wegens onvolledige formule.
- LTS-`sum` van maandpiek- of forecaststates.
- Bestaande handmatige Ecopower-prijs- en costhelpers.
- Vehicle-cloud power als primaire snelle laadmeter.

### Phase 2-voortgang en nog nodig

- Fluvius-kwartierexport en Ecopower-factuur zijn privacy-safe gereconcilieerd.
- Een read-only statistics-export over 48 uur leverde zes volledige kwartierreeksen en valideerde vijf- naar vijftienminutenaggregatie, tijdzones en quality flags.
- Volledige gezamenlijke Grid/PV/Battery-historie en de kortere EV-reeks moeten nog worden geëxporteerd.
- Grid-overlap moet per kwartier tegen Fluvius worden gereconcilieerd.
- Contractpassende EPEX-data moet nog live worden opgehaald en op issue time en volledigheid worden gevalideerd.
- Ecopower bevestigde volgens de eigenaar huidig `SMR1` en `SMR3` bij een eventuele dynamische contractwissel; dit vormt geen contractwijzigingsgoedkeuring.

## Validatiechecks

1. Vermogen en energie worden niet door elkaar gebruikt.
2. Import/export en charge/discharge hebben een eenduidige tekenconventie.
3. Totalen zijn monotonic of resets zijn expliciet gedocumenteerd.
4. Units en schaalfactoren zijn consistent.
5. Sensoruitval produceert geen plausibel ogende nul wanneer de status eigenlijk onbekend is.
6. Afgeleide huisconsumptie sluit energiebalansmatig aan bij Smappee binnen meettolerantie.
7. LTS-`sum` wordt alleen gebruikt waar de state-classsemantiek dat toelaat.
8. Energy Dashboard-bronnen verwijzen naar geschikte cumulative energy-entities.
9. Gevoelige station-, serienummer-, voertuig- en accountidentifiers blijven buiten Git.

## Sources

[32] https://www.home-assistant.io/integrations/smappee
[33] https://github.com/myny-git/smappee_ev
