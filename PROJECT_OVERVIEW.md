# Dynamic Energy Readiness & Home Assistant Energy Dashboard

## Projectdoel

Dit project bepaalt of de bestaande woninginstallatie technisch, functioneel en financieel geschikt is voor een dynamisch elektriciteitstarief in Vlaanderen. De analyse vertrekt van werkelijk gemeten import, injectie, PV-productie, batterijgedrag, huishoudelijk verbruik en EV-laden. Een dynamisch contract wordt niet als automatisch voordeliger beschouwd.

De voorkeursleverancier is Ecopower indien het actuele aanbod aantoonbaar past bij de installatie en een gevalideerde shadow-billinganalyse een voldoende voordeel toont.

## Kernvragen

1. Is een dynamisch tarief financieel interessant op basis van werkelijke woningdata?
2. Kan de bestaande hardware dynamische prijzen veilig en optimaal benutten?
3. Welke combinatie van PV, batterij, EV, laadpaal, SMA Home Manager, Home Assistant, forecasting en prijsdata verlaagt de totale energiekost zonder comfort, betrouwbaarheid, garantie of levensduur onnodig te schaden?

## Bekende uitgangssituatie

| Onderdeel | Bekend | Status |
|---|---|---|
| PV | Ongeveer 8,5 kWp; productie 2023 circa 8.699 kWh en 2024 circa 7.873 kWh | Te verifiëren |
| Batterij-omvormer | SMA Sunny Boy Storage / SBS5.0 | Exact type en firmware te verifiëren |
| SMA-regeling | SMA Home Manager 2.0 aanwezig | Topologie en actieve functies onbekend |
| EV | Kia EV6 GT-Line facelift RWD, modeljaar 2026 | Connectiviteit en actuele configuratie te verifiëren |
| Laadpaal | Aanwezig verondersteld vanuit de opdracht | Merk, model en aansluiting onbekend |
| Home Assistant | Energie-entiteiten en SMA-batterijsensoren aanwezig | Volledige inventaris vereist |
| Leverancier | Ecopower | Huidig product en tariefkaart vereist |

## Projectfasen

1. Discovery & Research
2. Readiness & Gap Validation
3. Monitoring en shadow billing
4. Ontwerp en gecontroleerde implementatie
5. Validatie van fysieke sturing en eventuele activatie

## Huidige scope

Phase 1 is afgerond. De eigenaar heeft op 2026-09-29 een strikt read-only Phase 2 goedgekeurd volgens `PHASE_1_GO_NO_GO.md`.

P2-001 en P2-004 zijn afgerond. P2-002 heeft Scenario A als offline
shadow-billingbacktest uitgevoerd. Geen van deze read-only werkzaamheden heeft
productieconfiguratie gewijzigd.

P2-003 heeft een apart read-only webdashboard opgeleverd met responsive views
voor overzicht, financiën, prijzen, energie, datakwaliteit, batterij,
meerjarige analyse, scenario's, shadow-sturing en beslissingen. De lokale server bindt op het LAN en is technisch geschikt als
origin voor een latere Cloudflare Tunnel. Er is geen publieke exposure of
Home Assistant-write geactiveerd.

Sinds 2026-10-06 toont de pagina `Prijzen` ook de actuele Belgische
Day-Ahead-kwartieren, omgerekend met de Ecopower Dynamische Burgerstroom-formule.
De prijs wordt per kwartier, dag, ISO-week en maand vergeleken met de door de
eigenaar gekozen indicatieve referentie van `€0,2770/kWh`. De eerste actuele
run bevat `3.456` complete kwartieren vanaf 2026-09-01 en `96` gepubliceerde
kwartieren voor 2026-10-06. Een read-only timer vernieuwt deze feed om `00:10`,
`13:35`, `14:50` en `16:05 Europe/Brussels`; `RandomizedDelaySec=5m` kan elke
nominale start maximaal vijf minuten uitstellen. De twee namiddagmomenten vangen
een latere publicatie van de volgende prijsdag op vóór de capture van `23:45`.
De vergelijking blijft expliciet geen all-in factuurprognose.

Phase 2-resultaten: Home Assistant Grid is over 3.118 overlapuren tegen Fluvius
gereconcilieerd binnen afrondingsprecisie. De exact op het lokale factuurjaar
uitgelijnde ENTSO-E A44/A01-reeks bevat 35.040 complete kwartieren en matcht
20/20 officiële EPEX-samples. Scenario A met ongewijzigd gedrag en
tariefversie `ECOPOWER_DBS_2026-08-01` komt retrospectief uit op `€2.607,12`
inclusief btw tegenover `€2.853,21` historisch, een verschil van `€-246,09`.
Dit is een offline backtest en nog geen contractadvies.

De eigenaar heeft op 2026-10-06 de exacte reconstructie van oudere prijzen
gedeprioriteerd. P2-007 gebruikt voor actuele indicatieve beslissteun daarom
`€0,2770/kWh` inclusief btw als gemiddelde referentie. De bestaande historische
componentanalyse blijft zichtbaar als
`MODELLED_WITH_UNVERIFIED_COMPONENTS` en wordt niet als factuurvalidatie gebruikt.

P2-008 heeft op 2026-10-02 een eerste reproduceerbare read-only
shadow-controller opgeleverd. Een historische dagrun maakt `96/96`
kwartierbeslissingen en vergelijkt piekneutraal, `7 kW`, `8 kW` en `10 kW`.
De eerste dag hield na degradatie een kleine positieve backtestwaarde over,
maar P2-008 blijft open voor representatieve meerdaagse validatie met gemeten
start-SOC en betere componentforecasts. Sinds 2026-10-06 zijn twee lokale
user-systemd-timers actief: om `23:45 Europe/Brussels` wordt de volgende dag
fail-closed vastgelegd en gepland; om `00:45` wordt de voorbije dag uitsluitend
met read-only Home Assistant-statistieken afgerekend en aan één primaire
representativiteitsklasse toegewezen. De eerste geldige capture is gepland voor
doeldag `2026-10-08`: de geplande capture voor `2026-10-07` faalde gesloten op
een te strikte `6 uur`-grens voor de monotone maandpiekstate. De grens vereist nu
de huidige lokale kalendermaand en maximaal `744 uur`. Het cohort blijft `0/12`.
Er zijn geen uitvoercommando's of wijzigingen aan SMA, Smappee of fysieke Home
Assistant-actuators toegevoegd.

P2-009 heeft een gepubliceerde HACS Lovelace-kaart opgeleverd voor live
read-only observatie. De kaart is via de visuele kaarteditor configureerbaar,
leest live grid-, PV-, batterij- en SOC-states en kan een optionele
shadow-planentity vergelijken met werkelijk netvermogen. De officiële HACS-
validatie is geslaagd en de eigenaar bevestigde op 2026-10-05 installatie in de
live Home Assistant-frontend. Read-only inspectie vond nog mappingcorrecties
voor batterijteken, huisvermogen en actuele prijssemantiek. Een fail-closed
planfeed herleest en valideert de lokale bron per request en is via loopback en
de goedgekeurde trusted-LAN-route getest. Aansluiting als Home Assistant-entity
en visuele validatie met een actueel kwartierplan blijven afzonderlijke gates.
De lokale kaartversie van 2026-10-07 toont daarnaast toekomstige ENTSO-E- en
Ecopower-kwartierprijzen, vergelijking met `€0,277/kWh`, uitlijning met
planacties en samenvattingen per dag, ISO-week en maand. De prijsfeed blijft
zichtbaar bij `NO_ACTION`; live HACS-publicatie en REST-sensorkoppeling zijn nog
niet toegepast.

## Buiten scope van de huidige read-only Phase 2

- Productie-automatisaties of fysieke aansturing
- Wijzigingen aan bestaande Home Assistant-configuratie
- Wijzigingen aan SMA-, batterij-, omvormer- of laadpaalinstellingen
- Activering of contractering van een dynamisch tarief
- Live deployment of publicatie
- Aannames over onbekende hardware als bevestigde feiten presenteren

## Werkmethode

Research → Document → Validate → Decide → Ticket → Implement → Test → Document

Belangrijke onderzoeksbevindingen worden gekoppeld aan een ticket, bron en raadpleegdatum. Besluiten met architecturale of veiligheidsimpact worden vastgelegd in `docs/decisions/`.

## Veiligheidsprincipes

- Home Assistant wordt geen single point of failure voor essentiële energiefuncties.
- De lokale veilige werking van SMA, batterij en laadpaal blijft de fallback.
- Monitoring en simulatie gaan vooraf aan fysieke sturing.
- Controls worden pas gebouwd nadat officiële ondersteuning, limieten, fail-safe gedrag en garantie-impact zijn gevalideerd.
- Dubbele of conflicterende sturing door SMA en Home Assistant wordt vermeden.

## Onderzoeksdocumenten

- `docs/research/SMA_BATTERY_HOME_MANAGER.md`
- `docs/research/EV_CHARGER.md`
- `docs/research/HOME_ASSISTANT_ENERGY.md`
- `docs/research/EPEX_DAY_AHEAD_DATA.md`
- `DYNAMIC_TARIFF_RESEARCH.md`
- `ECOPOWER_DYNAMIC_TARIFF.md`
- `PHASE_1_GO_NO_GO.md`

## Fase-1 exitcriteria

Fase 1 is afgerond wanneer:

- alle gevraagde eerste deliverables bestaan en intern consistent zijn;
- bekende feiten, onbevestigde aannames en ontbrekende informatie zichtbaar gescheiden zijn;
- officiële bronnen en raadpleegdatums zijn opgenomen;
- de Kanban-kaarten één-op-één verwijzen naar tickets met prioriteit, afhankelijkheden en acceptance criteria;
- er geen productieconfiguratie is gewijzigd;
- bevindingen en voorgestelde vervolgtickets ter validatie aan de eigenaar zijn voorgelegd.
