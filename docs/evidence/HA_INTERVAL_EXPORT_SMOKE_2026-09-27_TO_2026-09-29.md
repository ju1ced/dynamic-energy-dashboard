# Home Assistant Interval Export Smoke Test

Ticket: P2-001  
Status: `VERIFIED` smoke test; volledige historische export en Fluvius-reconciliatie blijven open  
Exportperiode: 2026-09-27 00:00 UTC tot 2026-09-29 00:00 UTC  
Uitgevoerd: 2026-09-29

## Scope

De export leest uitsluitend Home Assistant long-term statistics via `ha_get_history`. Er zijn geen entities, helpers, dashboards, automations, recorderinstellingen of apparaatinstellingen gewijzigd.

De private entitymap, ruwe MCP-respons en volledige kwartierreeksen staan uitsluitend in Git-ignored locaties. Het gecommitte evidencebestand bevat alleen aliases, kwaliteitsmetingen en totalen.

## Resultaat

Voor elk van zes cumulative energiestromen zijn 192 kwartieren opgebouwd uit 576 vijfminutenstatistieken:

| Stroom | Totaal | Ontbrekende 5-minutenbuckets | Duplicaten | Counterdalingen | `change`-mismatches |
|---|---:|---:|---:|---:|---:|
| Netafname | 81,989 kWh | 0 | 0 | 0 | 0 |
| Netinjectie | 0,038 kWh | 0 | 0 | 0 | 0 |
| PV-productie | 41,127 kWh | 0 | 0 | 0 | 1 |
| Batterijladen | 12,734 kWh | 0 | 0 | 0 | 0 |
| Batterijontladen | 10,688 kWh | 0 | 0 | 0 | 0 |
| EV-laden | 51,551 kWh | 0 | 0 | 0 | 0 |

## Gevonden data-quality issue

De Home Assistant-statistiek rapporteerde voor één PV-vijfminutenbucket een `change` gelijk aan de volledige cumulatieve teller, terwijl de tellerstate niet reset was. De exporter gebruikt daarom bij beschikbare lookback de delta tussen opeenvolgende cumulative states als primaire intervalwaarde. De afwijkende gerapporteerde `change` blijft zichtbaar als `reported_change_mismatch`; zij wordt niet stilzwijgend overgenomen.

Dit corrigeerde de aanvankelijk onmogelijke PV-uitkomst van 51.655,047 kWh naar 41,127 kWh voor de exportperiode. Een regressietest dekt dit foutpatroon af.

## Reproduceerbaarheid

Script:

`python scripts/export_ha_energy_statistics.py`

De live uitvoering vereist de lokale MCP-runtime en de Git-ignored entitymap. De uitvoer bewaart:

- UTC en `Europe/Brussels` per kwartier;
- bron- en doelresolutie;
- ontbrekende en dubbele vijfminutenbuckets;
- tellerdalingen;
- verschillen tussen state-delta en door Home Assistant gerapporteerde `change`;
- `null` in plaats van een stille schatting wanneer een benodigde bucket ontbreekt.

## Open voor P2-001

1. De volledige gezamenlijke Grid/PV/Battery-periode vanaf 2026-01-22 exporteren.
2. EV vanaf 2026-07-29 als kortere deelreeks meenemen.
3. Kwartierafname en -injectie voor overlappende perioden tegen Fluvius reconciliëren.
4. Chunking, herstartbaarheid en een reproduceerbaar exportmanifest voor de volledige periode valideren.
