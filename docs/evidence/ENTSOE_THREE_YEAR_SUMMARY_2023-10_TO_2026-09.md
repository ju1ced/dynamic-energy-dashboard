# ENTSO-E Day-Ahead-prijzen — driejaarsdekking

Status: VERIFIED  
Periode: 2023-10-01 00:00 Europe/Brussels tot 2026-10-01 00:00 Europe/Brussels (exclusief einde)  
Biedzone: België (`10YBE----------2`)  
Document-/procestype: `A44` / `A01`

## Resultaat

De drie volledige Fluvius-jaren hebben nu een exact uitgelijnde Belgische
Day-Ahead-prijsreeks op kwartierresolutie.

| Lokale periode | Kwartieren | Ontbrekend | Negatieve prijs | Gemiddelde EUR/MWh | Minimum | Maximum |
|---|---:|---:|---:|---:|---:|---:|
| 2023-10-01–2024-10-01 | 35.136 | 0 | 1.836 | 66,575381 | -140,00 | 268,94 |
| 2024-10-01–2025-10-01 | 35.040 | 0 | 2.032 | 86,369879 | -462,33 | 565,46 |
| 2025-10-01–2026-10-01 | 35.040 | 0 | 1.344 | 100,935298 | -499,29 | 1.038,25 |
| **Totaal** | **105.216** | **0** | **5.212** | **84,610382** | **-499,29** | **1.038,25** |

Het eerste jaar bevat 35.136 kwartieren omdat 2024 een schrikkeljaar is.

## Resolutie en kwaliteit

- 2023-10-01–2024-10-01 komt volledig uit ENTSO-E-uurprijzen en is zonder
  prijsinterpolatie naar kwartieren geëxpandeerd.
- 2024-10-01–2025-10-01 bevat 34.944 kwartieren uit uurbronnen en 96 uit een
  native kwartierbron.
- 2025-10-01–2026-10-01 komt volledig uit native kwartierprijzen.
- Alle 105.216 verwachte kwartieren zijn aanwezig; er zijn na validatie geen
  ontbrekende of conflicterende kwartieren.
- De API-response voor 2025-10-01–2026-10-01 bevatte vanaf 2026-08-08 5.088
  overlappende kwartierrecords. De waarden, intervalgrenzen, resolutie en
  kwaliteitsflags waren per overlap exact gelijk. De parser verwijdert nu
  uitsluitend zulke identieke dubbels en rapporteert hun aantal. Niet-identieke
  overlaps blijven zichtbaar als kwaliteitsfout.

## Consistentiecontrole

De volledige bestaande ENTSO-E-reeks voor 2025-06-01–2026-06-01 is opnieuw
vergeleken met de nieuwe jaarbestanden:

- vergeleken kwartieren: 35.040;
- prijsverschillen: 0.

## Bestanden

Lokale bron- en analysebestanden:

- `data/raw/entsoe-day-ahead-2023-10-01_2024-10-01.xml`;
- `data/raw/entsoe-day-ahead-2024-10-01_2025-10-01.xml`;
- `data/raw/entsoe-day-ahead-2025-10-01_2026-10-01.xml`;
- `data/raw/entsoe-day-ahead-quarter-prices-2023-10-01_2024-10-01.json`;
- `data/raw/entsoe-day-ahead-quarter-prices-2024-10-01_2025-10-01.json`;
- `data/raw/entsoe-day-ahead-quarter-prices-2025-10-01_2026-10-01.json`;
- `docs/evidence/entsoe-three-year-summary-2023-10-01_2026-10-01.json`.

De ruwe bestanden blijven Git-ignored. Het beveiligingstoken werd uit de globale
Hermes-`.env` geladen en is niet in opdrachten, output, evidence of Git opgeslagen.

## Interpretatiegrens

Deze evidence valideert de marktprijsdekking. Een correcte historische
contractvergelijking vereist daarnaast de toepasselijke Ecopower-tariefcomponenten
per contractperiode. De tariefkaart van 2026 mag niet zonder gevoeligheidslabel
op eerdere jaren worden toegepast.
