# Energy Decision Log v1

Status: `VERIFIED`

Ticket: `P2-006`

Modus: uitsluitend offline en read-only

Analyse uitgevoerd: `2026-10-01`

## Resultaat

Het project heeft nu een formeel, privacy-safe Energy Decision Log met zeven
reproduceerbare entries. Iedere entry bevat:

- tijd en stabiel entry-ID;
- scenario en expliciet entrytype;
- privacy-safe evidence-referenties;
- actieve read-only constraints;
- reden en voorgestelde vervolgstap;
- confidence-niveau, score en onderbouwing;
- uitkomst en machineleesbare metrics;
- script en argumenten voor offline herberekening.

Werkelijke meetconclusies gebruiken `MEASUREMENT_CONCLUSION`.
Simulatiebesluiten gebruiken `SIMULATION_DECISION`. Daardoor kan de
read-only dashboardweergave beide soorten bewijs niet stilzwijgend mengen.

## Safety boundary

Alle entries leggen dezelfde harde grenzen vast:

- `read_only = true`;
- `physical_writes_allowed = false`;
- `contract_change_allowed = false`;
- `production_automation_allowed = false`;
- `production_command = null`;
- `setpoint = null`.

Het log registreert dus beslissteun en voorgestelde offline analyses, geen
commando's voor Home Assistant, SMA, Smappee, batterij of laadpaal.

## Artefacten

- schema: `config/decision-log/energy-decision-log-v1.schema.json`;
- generator: `scripts/build_energy_decision_log.py`;
- machineleesbaar log:
  `docs/evidence/energy-decision-log-2026-10-01.json`;
- regressietests: `tests/test_build_energy_decision_log.py`;
- dashboard: pagina `Beslissingen` gebruikt rechtstreeks het formele log.

## Huidige entries

1. gevalideerde jaarbacktest Scenario A;
2. gemeten driejarige netafhankelijkheidstrend;
3. voorgestelde winterse piekneutrale shadow-test;
4. voorgestelde offline test van de gezamenlijke `7 kW`-guardrail;
5. uitgestelde extra batterij-investering;
6. gemeten Solcast-forecastkwaliteit met issue-timeversies;
7. gemeten DSMR/factuur-componentmismatch ondanks een bijna gelijk jaartotaal.

## Reproduceerbaarheid

`python3 scripts/build_energy_decision_log.py`

De generator leest uitsluitend bestaande privacy-safe evidence en schrijft een
deterministisch log met zeven entries. Dashboarddata wordt daarna opnieuw gebouwd
met `python3 scripts/build_dashboard_data.py`.
