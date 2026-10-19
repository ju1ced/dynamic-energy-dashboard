# Dynamic Tariff Readiness Matrix

Status: read-only Phase 2 actief; datafundament in uitvoering  
Gerelateerde tickets: P1-009 en componenttickets P1-003 t/m P1-008  
Laatst bijgewerkt: 2026-09-29

## Schaal

- `Ja`: bevestigd bruikbaar.
- `Gedeeltelijk`: relevante basis bestaat, maar kwaliteit of dekking is niet gevalideerd.
- `Onbekend`: bewijs ontbreekt.
- `Nee`: aantoonbaar niet beschikbaar.
- `Niet activeren`: control bestaat mogelijk, maar is niet veilig/geautoriseerd voor gebruik.

| Component | Monitoring | Control | Automation | Dynamic-ready | Gap / bewijsbehoefte |
|---|---|---|---|---|---|
| Grid | Goed | N.v.t. | Smappee-capaciteitsbewaking aanwezig | Gedeeltelijk | Volledig Fluvius-factuurjaar: 35.040 kwartieren, import/export compleet, 99 geschat, DST verwerkt en factuurvolumes gereconcilieerd; huidig `SMR1` en dynamisch `SMR3` zijn OWNER CONFIRMED; volledige HA-overlap blijft open |
| PV | Goed | Centrale SMA-setpointmodus aanwezig; niet extern activeren | Home Manager-regeling aanwezig | Voorwaardelijk | SMA power/totalen hebben 250 dagen LTS en live match met Smappee; daily helper heeft foutieve reset-/LTS-semantiek; curtailment en injectiegedrag vereisen testing |
| Battery | Goed | Native SMA-control aanwezig; extern niet activeren | Native SHM2 mogelijk; configuratie te valideren | Voorwaardelijk | SBS/RESU/BMS, SOC, laad/ontlaadvermogen en cumulative energy zijn VERIFIED; 253 dagen energy-LTS; bruikbare capaciteit en control/failure behavior vereisen testing |
| EV charger | Goed | Native Smappee-control aanwezig; HA niet activeren | Smappee `smart` actief; `solar` beschikbaar | Voorwaardelijk | Directe power/energyentities hebben recorder en 62 dagen energy-LTS; live match met Kia/Tronity; chargerfasegedrag, OCPP en fallbacktest blijven open |
| SMA Home Manager 2.0 | Goed | System Manager en ingebouwde SMA-regeling actief | Dynamische afnameoptimalisatie en netladen ondersteund; lage vaste injectieproxy | Voorwaardelijk | SMA adviseert bij dynamische tarieven een lage vaste terugleververgoeding; forecast charging staat uit; kalibratie van €0,02/kWh, werkelijk laadgedrag en 0 W-PCC-semantiek vereisen simulatie/testing |
| Home Assistant | Goed voor read-only monitoring | Niet activeren | Monitoring/simulatie geschikt | Goed voor Grid-validatie | Grid-hourly is over 3.118 uren tegen Fluvius gereconcilieerd; historische vijfminutenretentie blijft beperkt |
| Price data | Volledig prijsjaar en officiële cross-check | N.v.t. | Nee | Goed voor historische backtest | 35.040 ENTSO-E-kwartieren zonder gaps; 20/20 EPEX-samples exact; issue time blijft volgens ADR-004 `null`[28][38][39][40][41][42] |
| Forecasting | PV-dagforecast met issue-timeversies beschikbaar | N.v.t. | Solcast actief | Gedeeltelijk | 75 recente forecastversies over zeven voltooide doeldagen bewaard; Day-Ahead MAE 6,936 kWh en MAPE 28,69%; één retentiegat zichtbaar; kwartierforecast, langere evaluatie, load- en EV-forecast ontbreken |
| Financial model | Factuurbaseline en Scenario A reproduceerbaar | N.v.t. | Nee | Goed voor eerste backtest | Scenario A geeft retrospectief `€-246,09` inclusief btw; tweede prijsjaar en actuele contractversie vereist voor advies |
| Decision logging | Formeel read-only log actief | N.v.t. | Nee | Goed | Zeven auditbare entries met evidence, constraints, confidence, outcome en reproductiemetadata; metingen en simulatiebesluiten zijn gescheiden |

## Voorlopige conclusie

De installatie heeft aantoonbare monitoringbouwstenen, maar is nog niet bewezen klaar voor veilige, actieve dynamische optimalisatie. De grootste onzekerheid zit niet in dashboardvisualisatie, maar in:

1. exacte hardware- en firmware-identificatie;
2. officiële en conflictvrije controlinterfaces;
3. betrouwbare intervaldata en tariefformules;
4. validatie dat lokale SMA-regeling de veilige fallback blijft;
5. financiële simulatie vóór contract- of controlwijzigingen.

## Readiness-gates

### Gate R1 - Observeerbaarheid

Alle energiestromen hebben betrouwbare momentane én cumulatieve meetwaarden met bekende units, locaties en tekenconventies.

### Gate R2 - Financiële reproduceerbaarheid

De huidige factuur en dynamische shadow bill zijn met dezelfde intervaldata en expliciete kostcomponenten reproduceerbaar.

### Gate R3 - Control authority

Per actuator is exact één controller eigenaar van het setpoint. Officiële ondersteuning, limieten en fallback zijn bevestigd.

### Gate R4 - Simulatiebewijs

Scenario's A-D tonen voordeel, risico en gevoeligheid over een representatieve periode zonder fysieke sturing.

### Gate R5 - Veilige activatie

Failure modes, overrides, observability, rate limits en herstel naar lokale werking zijn getest en goedgekeurd.

## Sources

[28] https://cdn.nimbu.io/s/4tn7vz5/channelentries/ma28q8f/files/1790570062186/20260801_dbs_tariefkaart.pdf?7l4n7vq=
[38] https://cdn.nimbu.io/s/4tn7vz5/channelentries/spiilz4/files/1788271546519/202608_gbs_tariefkaart.pdf?w01uqtn=&dl=1 — Ecopower Groene Burgerstroom - tariefkaart augustus 2026
[39] https://transparencyplatform.zendesk.com/hc/en-us/articles/15692855254548-Sitemap-for-RESTful-API-integration — ENTSO-E Transparency Platform RESTful API sitemap
[40] https://transparencyplatform.zendesk.com/hc/en-us/articles/12845911031188-Web-API-Documentation — ENTSO-E Web API documentation
[41] https://www.entsoe.eu/news/2025/09/30/entso-e-welcomes-the-go-live-of-the-15-minute-market-time-unit-mtu-in-the-single-day-ahead-coupling-sdac — ENTSO-E welcomes 15-minute MTU in SDAC
[42] https://www.nemo-committee.eu/assets/files/250930-nemo-committee-press-release-15-minute-mtu-sdac-go-live.pdf — NEMO Committee 15-minute MTU SDAC go-live press release
