# Historische vaste-kostenreconciliatie 2023-10 tot 2025-09

Status: `MODELLED_WITH_UNVERIFIED_COMPONENTS`

Modus: uitsluitend offline en read-only

## Resultaat

| Lokaal jaar | Maanden | Tariefkaartcomponenten incl. btw | DSMR-vaste kost | DSMR minus reconstructie |
|---|---:|---:|---:|---:|
| 2023-2024 | `12` | `€331.33` | `€372.59` | `€41.26` |
| 2024-2025 | `12` | `€306.57` | `€395.82` | `€89.25` |

De reconstructie modelleert per maand de vaste leverancierskost,
databeheerkost, het capaciteitstarief en het Energiefonds op basis van
tariefkaarten en nog niet volledig bewezen contract-/factuuraannames.
De maandpiek van april 2024 is door de eigenaar gemeld als `5,031 kW`;
direct gearchiveerd Fluvius-bewijs ontbreekt nog.

DSMR-verschillen blijven zichtbaar als onopgeloste modelresiduen en worden
niet als factuurverschil of contractbesparing geïnterpreteerd.

## Open evidencebeperkingen

- Most monthly peaks are interval-derived maxima, not official Fluvius billing peaks.
- The TotalEnergies fixed supplier fee is not yet proven applicable to the 2023-07 contract start.
- The zero Energy Fund assumption still requires domiciliation or invoice evidence.
- April 2024 at 5.031 kW is owner-confirmed and lacks archived direct source evidence.
- No settlement invoice currently proves the reconstructed fixed-component totals.

## Bronnen

- officiële TotalEnergies eMobility-tariefkaart december 2023;
- officiële Ecopower-tariefkaarten januari 2024 en januari 2025;
- Fluvius-kwartiermetingen voor de overige maandpieken;
- eigenaarbevestiging van de officiële aprilpiek op 2026-10-05;
- DSMR-contractexport voor de vergelijking met de ingestelde dagkosten.

## Veiligheidsgrens

Geen contractwijziging, Home Assistant-write of apparaatsturing is uitgevoerd.
