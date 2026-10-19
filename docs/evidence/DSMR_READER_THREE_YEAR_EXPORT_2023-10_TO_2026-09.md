# DSMR Reader — read-only driejaarsexport

Status: VERIFIED READ-ONLY EXPORT  
Periode: 2023-10-01 00:00 Europe/Brussels tot 2026-10-01 00:00 Europe/Brussels  
API-methode: uitsluitend gepagineerde `GET`-requests

## Geëxporteerde bronnen

| Bron | Records | Dekking / kwaliteit |
|---|---:|---|
| Elektriciteitsmetingen | 94.891 | Geen dubbele timestamps en geen tellerdalingen |
| Uurstatistieken | 26.104 | 200 van 26.304 uren ontbreken, verdeeld over 24 gaten |
| Kwartierpiekstatistieken | 104.290 | 926 van 105.216 kwartieren ontbreken, verdeeld over 43 gaten |
| Dagstatistieken | 1.095 | Alleen 2025-12-28 ontbreekt |
| Energiecontracten | 32 | Iedere dag in de driejaarsperiode wordt door exact één contract gedekt |

De ruwe gegevens zijn lokaal opgeslagen onder
`data/raw/dsmr-reader-export-2023-10-01_2026-10-01/` en blijven Git-ignored.
De API-key en het private endpoint staan niet in de exportevidence.

## Resolutie

De elektriciteitsmetingen hebben een gemengd retentieregime:

- recente gegevens zijn hoofdzakelijk per minuut aanwezig;
- oudere gegevens bevatten hoofdzakelijk twee opeenvolgende metingen per uur,
  met daarna ongeveer 59 minuten tot het volgende paar;
- daarom mag de ruwe electricity-resource niet zonder kwaliteitslogica als een
  continue minuut- of kwartierreeks worden behandeld.

De kwartierpiekrecords beginnen enkele seconden na de nominale kwartiergrens.
Voor de kwaliteitscontrole zijn ze in UTC naar hun nominale kwartierstart
teruggebracht. Dit leverde geen dubbele kwartieren op.

Het langste historische gat omvat:

- 45 ontbrekende uren van 2025-12-27 20:00 UTC tot en met
  2025-12-29 16:00 UTC;
- 181 ontbrekende kwartierpieken van 2025-12-27 19:45 UTC tot en met
  2025-12-29 16:45 UTC.

Fluvius blijft daardoor de primaire historische factuur- en energiebasis. DSMR
Reader is bruikbaar voor contractprijzen, onafhankelijke reconciliatie,
capaciteitspieken en recentere detaildata.

## Contract- en kostvalidatie

De 32 DSMR-contractrecords dekken alle 1.096 dagen exact eenmaal, zonder gaten
of contractoverlap. Voor alle 1.095 aanwezige dagstatistieken sluiten de door
DSMR opgeslagen elektriciteitskosten exact aan op de geconfigureerde
contractprijzen en de DSMR-rekenwijze.

Dit bewijst interne consistentie van DSMR Reader. Het bewijst niet automatisch
dat iedere ingevoerde maandprijs overeenkomt met de uiteindelijke
leveranciersfactuur.

## Cross-check met Home Assistant 2026

De historische maandwaarden januari tot en met september 2026 zijn tussen de
Home Assistant-prijshelpers en DSMR Reader vergeleken:

| Maand | Home Assistant EUR/kWh | DSMR EUR/kWh | Verschil |
|---|---:|---:|---:|
| Januari | 0,2841 | 0,2841 | 0,0000 |
| Februari | 0,2716 | 0,2716 | 0,0000 |
| Maart | 0,2770 | 0,2716 | +0,0054 |
| April | 0,2702 | 0,2716 | -0,0014 |
| Mei | 0,2773 | 0,2716 | +0,0057 |
| Juni | 0,2894 | 0,2716 | +0,0178 |
| Juli | 0,2859 | 0,2859 | 0,0000 |
| Augustus | 0,2970 | 0,2970 | 0,0000 |
| September | 0,3125 | 0,3125 | 0,0000 |

Vijf maanden zijn exact gelijk. Maart, april, mei en juni verschillen. De
eigenaar heeft beslist dat voor de historische 2026-baseline de maandwaarden
uit Home Assistant leidend zijn. De DSMR-contractrecords blijven als
cross-check zichtbaar, maar overschrijven die vier waarden niet. Er is niets
in DSMR Reader of Home Assistant gewijzigd.

## Reproduceerbaarheid

Export:

`python3 scripts/export_dsmr_reader_data.py ...`

Analyse:

`python3 scripts/analyze_dsmr_reader_export.py --output docs/evidence/dsmr-reader-three-year-export-2023-10-01_2026-10-01.json`
