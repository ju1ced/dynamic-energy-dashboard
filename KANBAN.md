# Kanban

Bronrevisie bij aanmaak: `8adaed8`

Scope: Phase 2-validatie en Phase 3 gezamenlijke batterij-/EV-dry-run sturing

Volgorde: A fundament, B parallel onderzoek, C synthese, D validatie, E vervolg na expliciete goedkeuring.

## Backlog

Geen tickets.

## Research

Geen tickets.

## Ready

Geen tickets.

## In Progress

| Ticket | Prioriteit | Volgorde | Epic | Samenvatting |
|---|---:|---:|---|---|
| [P2-008](tickets.md#p2-008---read-only-shadow-controller-voor-dynamische-sturing) | P0 | E | E06 | Cohort `2/12`: doeldagen `2026-10-08` en `2026-10-11` geaccepteerd; capture gebruikt nu read-only EPEX/Ecopower-entities wanneer geen lokaal ENTSO-E-token beschikbaar is |
| [P2-009](tickets.md#p2-009---hacs-installable-live-lovelace-shadow-dashboard) | P0 | E | E05 | HACS `v0.2.1` is gepubliceerd en verwerkt de actuele dubbele EPEX/Ecopower-intervalrijen; live HA-update en visuele validatie blijven open |
| [P3-001](tickets.md#p3-001---ev-laadoptimalisatie-in-simulatie) | P1 | E | E06 | Owner-go voor gezamenlijke dry-run; EV-behoefte en laadvensters worden onder de gedeelde netlimiet gepland |
| [P3-002](tickets.md#p3-002---batterijarbitrage-in-simulatie) | P1 | E | E06 | Actuator-neutrale batterijplanning wordt samen met EV geoptimaliseerd; SMA blijft actieve controller |
| [P3-004](tickets.md#p3-004---gezamenlijke-batterij--en-ev-sturingslogica-in-dry-run) | P0 | E | E06 / E07 | HMAC-manifest en read-only snapshotrefresher zijn actief; rollback, cross-fieldvalidatie, dubbele bronmapping en veilige tijdelijke writes zijn gehard; complete private bronmapping en verse joint evidence blijven open |

## Review / Validation

Geen tickets.

## Blocked

| Ticket | Prioriteit | Volgorde | Epic | Samenvatting |
|---|---:|---:|---|---|
| [P3-003](tickets.md#p3-003---control-authority-en-failure-modes-valideren) | P0 voor activatie | E | E07 | Fysieke tests vereisen apart plan en expliciete goedkeuring |

## Done

| Ticket | Prioriteit | Volgorde | Epic | Resultaat |
|---|---:|---:|---|---|
| [P1-001](tickets.md#p1-001---projectfundament-en-traceerbaarheid) | P0 | A | E01 | Structuur, deliverables, backlog en board aangemaakt |
| [P1-002](tickets.md#p1-002---beschikbare-eigenaarinformatie-en-bewijsmateriaal-inventariseren) | P0 | A | E01 | Bekende data en `INFORMATION_REQUIRED_FROM_OWNER` vastgelegd |
| [P1-003](tickets.md#p1-003---pv-installatie-onderzoeken) | P0 | B | E01 | Modellen, firmware, vermogen, fasen en interfacegrenzen vastgelegd |
| [P1-004](tickets.md#p1-004---sma-batterijsysteem-en-arbitragemogelijkheden-onderzoeken) | P0 | B | E01 | Batterijhardware, limieten, interfaces en arbitragegaps vastgelegd |
| [P1-005](tickets.md#p1-005---sma-home-manager-20-rol-en-controllergrenzen-onderzoeken) | P0 | B | E01 | SHM2-rol, dynamische functies en controllergrens vastgelegd |
| [P1-006](tickets.md#p1-006---ev-en-laadpaal-onderzoeken) | P0 | B | E01 | Smappee-model, limieten, firmware, fallback en open runtimegaps vastgelegd |
| [P1-007](tickets.md#p1-007---home-assistant-entity--en-datakwaliteitsinventaris) | P0 | B | E03 | Volledige read-only inventaris, LTS-dekking, bronhiërarchie en data-qualitygaps vastgelegd |
| [P1-008](tickets.md#p1-008---ecopower-huidig-en-dynamisch-tarief-onderzoeken) | P0 | B | E02 | Contractformules, volledig factuurjaar en 35.040 Fluvius-kwartieren gereconcilieerd |
| [P1-009](tickets.md#p1-009---dynamic-tariff-readiness-matrix-en-gaps-opstellen) | P0 | C | E02 | Readiness-gates en actionable gaps per component vastgelegd |
| [P1-010](tickets.md#p1-010---voorlopige-architectuur-en-control-ownership) | P1 | C | E06 | Monitoring, simulatie en control met één controller per actuator gescheiden |
| [P1-011](tickets.md#p1-011---shadow-billing--en-scenarioplan) | P0 | C | E04 | Bronhiërarchie, scenario's, factuurbaseline en validatieplan vastgelegd |
| [P1-012](tickets.md#p1-012---dashboardvereisten-en-wireframeplan) | P1 | C | E05 | Dashboardeisen en expliciete wireframe-/controlgate vastgelegd |
| [P1-013](tickets.md#p1-013---fase-1-documentatie-valideren) | P0 | D | E07 | Interne structuur-, link-, citation- en Markdownvalidatie uitgevoerd |
| [P1-014](tickets.md#p1-014---eigenaarvalidatie-en-fase-2-gono-go) | P0 | D | E07 | Eigenaar gaf op 2026-09-29 expliciet GO voor read-only Phase 2 |
| [P2-001](tickets.md#p2-001---veilige-home-assistant-data-export-verzamelen) | P0 | E | E03 | Historische retentie vastgesteld en Grid over 3.118 uren tegen Fluvius gereconcilieerd |
| [P2-002](tickets.md#p2-002---shadow-billing-minimum-viable-monitor-bouwen) | P0 | E | E04 | Scenario A over 35.040 kwartieren geeft retrospectief `€-246,09` inclusief btw |
| [P2-003](tickets.md#p2-003---dashboardwireframes-ontwerpen) | P1 | E | E05 | AIHub-geïnspireerde read-only webdashboard-MVP gevalideerd op desktop, mobiel en LAN |
| [P2-004](tickets.md#p2-004---contractpassende-epex-day-ahead-kwartierfeed) | P0 | E | E03 | Compleet prijsjaar en 20/20 officiële EPEX-samples gevalideerd |
| [P2-005](tickets.md#p2-005---forecastkwaliteit-en-issue-time-opslag) | P1 | E | E03 | 75 Solcast-versies met issue time; zeven doeldagen en forecastfouten zichtbaar |
| [P2-006](tickets.md#p2-006---energy-decision-log-datamodel) | P1 | E | E05 | Formeel read-only beslislog met schema, evidence, confidence en dashboardweergave |
| [P2-007](tickets.md#p2-007---meerjarige-financiële-en-batterijgevoeligheidsanalyse) | P0 voor indicatieve beslissteun | E | E04 | Owner-approved gemiddelde referentie `€0,2770/kWh`; exacte historische componentreconstructie blijft niet-advieswaardig gearchiveerd |
