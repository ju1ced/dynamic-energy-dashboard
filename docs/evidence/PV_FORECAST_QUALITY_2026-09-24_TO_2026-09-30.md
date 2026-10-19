# PV-forecastkwaliteit 2026-09-24 tot 2026-09-30

Status: `VERIFIED_WITH_LIMITATIONS`

Ticket: `P2-005`

Modus: uitsluitend offline en read-only

Analyse uitgevoerd: `2026-10-01`

## Doel

Solcast-dagforecasts geversioneerd bewaren en per issue time vergelijken met de
werkelijke PV-dagenergie. Load- en EV-behoefteforecast blijven afzonderlijke,
nog niet geïmplementeerde datastromen en worden niet uit PV afgeleid.

## Bronnen en methode

- `today`- en `tomorrow`-states uit de recente Home Assistant-recorderhistorie;
- issue time uit de oorspronkelijke state change timestamp;
- doeldag als lokaal halfopen interval in `Europe/Brussels`;
- werkelijke PV-dagenergie uit opeenvolgende dagelijkse cumulative states;
- geen gebruik van foutieve LTS-`sum` of incidenteel geresette provider-`change`;
- geen forward-fill voor ontbrekende forecastversies.

De privacy-safe snapshot bewaart alle `75` aangetroffen forecastversies voor
zeven voltooide doeldagen. Iedere doeldag heeft meerdere revisies; oudere
voorspellingen worden niet door de nieuwste waarde overschreven.

## Resultaat

| Horizon | Geëvalueerde dagen | Ontbrekend | Gemiddelde fout | MAE | RMSE | MAPE |
|---|---:|---:|---:|---:|---:|---:|
| Laatste Day-Ahead-versie | `6` | `1` | `+6,936 kWh` | `6,936 kWh` | `8,354 kWh` | `28,69%` |
| Middernachtversie | `6` | `1` | `+6,936 kWh` | `6,936 kWh` | `8,354 kWh` | `28,69%` |
| Laatste versie vóór 08:00 | `7` | `0` | `+9,154 kWh` | `9,154 kWh` | `10,397 kWh` | `38,43%` |

In dit korte venster overschat de Day-Ahead-reeks de gerealiseerde PV-productie.
De ochtendupdates verbeteren de gemiddelde absolute fout niet. Dit is een
observatie over zeven dagen, geen algemene beoordeling van Solcast.

De eerste doeldag heeft geen bewaarde vorige-dagforecast omdat deze vóór de
beschikbare recorderhistorie ligt. Het ontbrekende punt blijft `MISSING` en is
niet gereconstrueerd.

## Datacontract

Iedere forecastversie bewaart:

- `forecast_kind` (`today` of `tomorrow`);
- `issue_time` met UTC-offset;
- `target_date` en lokaal doelinterval;
- voorspelde kWh;
- horizon tot het einde van het doelinterval;
- fout, absolute fout en procentuele fout na realisatie.

Per doeldag worden revision count, forecastbereik en alle oudere versies
bewaard. Samenvattingen rapporteren ontbrekende dagen apart.

## Grenzen

- De raw recorderhistorie dekt slechts zeven voltooide doeldagen, terwijl de
  dagelijkse LTS-reeks langer is maar geen bruikbare issue-timeversies bewaart.
- De evaluatie gebruikt dagenergie, nog geen kwartierforecastcurve.
- Loadforecast en EV-energiebehoefteforecast zijn expliciet
  `NOT_IMPLEMENTED_SEPARATE_STREAM`.
- Deze korte reeks is onvoldoende om een productiestrategie of fysieke
  batterijbesturing te activeren.

## Reproduceerbaarheid

Bron:
`docs/evidence/solcast-pv-forecast-snapshots-2026-09-24_2026-09-30.json`

Analyse:
`python3 scripts/analyze_pv_forecast_quality.py`

Uitvoer:
`docs/evidence/pv-forecast-quality-2026-09-24_2026-09-30.json`
