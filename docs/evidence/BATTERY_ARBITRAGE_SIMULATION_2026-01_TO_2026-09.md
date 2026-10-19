# Offline batterijarbitrage 2026-01 tot 2026-09

Status: `VERIFIED_WITH_LIMITATIONS`  
Modus: uitsluitend offline en read-only  
Periode: `2026-01-22T07:00:00Z` tot `2026-09-30T00:00:00Z`

## Datadekking

De simulatie gebruikt Home Assistant-uurstatistieken voor netafname, netinjectie,
batterijladen, batterijontladen en PV. Van 6.024 bronuren waren 5.814 uren
bruikbaar (`96,513944%`). Er zijn 210 uren uitgesloten: 191 wegens ontbrekende
batterijlaaddata, 15 wegens ontbrekende PV-data en vier wegens ontbrekende
netafnamedata. Er is geen stille forward-fill toegepast.

## Bevestigde en afgeleide parameters

- bruikbare batterijcapaciteit: `14,24 kWh` (`OWNER CONFIRMED`);
- laad- en ontlaadlimiet: elk `5 kW` (`OWNER CONFIRMED`);
- netladen en batterij-export toegestaan (`OWNER CONFIRMED`);
- round-trip-efficiëntie: `85,3727%` (`DERIVED`);
- symmetrische efficiëntie per richting: `92,3974%` (`DERIVED`);
- centrale degradatiekost: `€0,06` per ontladen kWh (`ASSUMPTION`);
- capaciteitstarief: signed maandpiekverschil op uur-gemiddeld vermogen
  (`APPROXIMATION`, niet de officiële kwartierpiekberekening).

## Centrale uitkomst bij €0,06/kWh degradatie

| Scenario | Netto verschil versus werkelijk gedrag | Conversieverlies | Cycli | Batterij-export | Piekeffect |
|---|---:|---:|---:|---:|---:|
| Perfect foresight, export toegestaan | `+€88,96` | `412,62 kWh` | `169,12` | `131,41 kWh` | `-€0,31` |
| Perfect foresight, alleen zelfverbruik | `+€68,46` | `385,25 kWh` | `157,90` | `0,00 kWh` | `-€0,35` |
| Realistische Day-Ahead-heuristiek | `-€107,73` | `287,74 kWh` | `118,57` | `0,00 kWh` | `+€63,57` |

Een positief bedrag betekent dat het scenario goedkoper is dan het werkelijk
waargenomen batterijgedrag over dezelfde vergelijkbare uren. Perfect foresight
is een theoretische bovengrens. De geteste Day-Ahead-heuristiek gebruikt
prijsquartielen, een trailing PV-surplusreserve en realtime zelfverbruik, maar
geen gevalideerd productieforecastmodel. Vijf incomplete dagen zijn voor deze
heuristiek overgeslagen.

## Degradatiegevoeligheid

| Degradatiekost | Perfect + export | Perfect zelfverbruik | Day-Ahead |
|---:|---:|---:|---:|
| `€0,00/kWh` | `+€107,89` | `+€76,10` | `-€154,30` |
| `€0,03/kWh` | `+€95,48` | `+€69,87` | `-€133,24` |
| `€0,06/kWh` | `+€88,96` | `+€68,46` | `-€107,73` |
| `€0,10/kWh` | `+€85,88` | `+€71,17` | `-€83,08` |

De niet-monotone verschillen bij hogere degradatie ontstaan doordat dezelfde
degradatiekost ook op het werkelijk waargenomen baselinegedrag wordt toegepast.
Een strategie met minder ontlading kan daardoor relatief verbeteren wanneer de
aangenomen degradatiekost stijgt.

## Extra batterijcapaciteit

De vermogenslimiet blijft in alle varianten `5 kW`. De perfecte
zelfverbruiksbovengrens geeft de volgende geannualiseerde marginale waarde:

| Extra bruikbaar | Marginale jaarwaarde | Bovengrens 10 jaar | Bovengrens 15 jaar | Realistische case |
|---:|---:|---:|---:|---|
| `5,00 kWh` | `€68,07/jaar` | `€680,66` | `€1.020,99` | niet ondersteund |
| `10,00 kWh` | `€105,64/jaar` | `€1.056,44` | `€1.584,65` | niet ondersteund |
| `14,24 kWh` | `€125,27/jaar` | `€1.252,66` | `€1.878,99` | niet ondersteund |

Dit zijn maximale geïnstalleerde-kostenbovengrenzen zonder discontering,
financiering, onderhoud, capaciteitsveroudering of vervangingsrisico. Zelfs met
extra capaciteit blijft de geteste realistische Day-Ahead-strategie over de
waargenomen periode netto negatief. De analyse ondersteunt daarom geen aankoop
van extra batterijcapaciteit op basis van deze strategie en dataset.

## Interpretatie

1. De bestaande batterij heeft theoretisch nog optimalisatieruimte, maar de
   haalbare waarde is veel kleiner dan de perfecte bovengrens.
2. Batterij-export voegt in de perfecte bovengrens circa `€20,50` toe ten
   opzichte van de zelfverbruiksvariant, maar veroorzaakt `131,41 kWh`
   batterijgedreven netexport.
3. De geteste Day-Ahead-regel verhoogt de benaderde capaciteitspiekkost met
   `€63,57` en is na verliezen en degradatie `€107,73` slechter dan het huidige
   gedrag.
4. Extra opslag is met de huidige `5 kW`-limiet en realistische strategie niet
   economisch onderbouwd.
5. Een volgende iteratie vereist een gevalideerd load-/PV-forecastmodel,
   kwartierdispatch en officiële kwartierpieken voordat investerings- of
   productieadvies mogelijk is.

## Grenzen

- De overlap beslaat geen drie volledige jaren.
- De Ecopower-formule van augustus 2026 wordt retrospectief gebruikt.
- Uurdata maskeert kwartierpieken en intra-uur batterijgedrag.
- De efficiëntie is niet gecorrigeerd voor begin- en eind-SOC.
- Geen contractwijziging, Home Assistant-write, SMA-write, setpoint of fysieke
  batterijactie is uitgevoerd of toegestaan.

Machineleesbare samenvatting:
`docs/evidence/battery-arbitrage-simulation-summary-2026-01-22_2026-09-30.json`.
Volledige lokale output:
`data/raw/battery-arbitrage-simulation-2026-01-22_2026-09-30.json`.
