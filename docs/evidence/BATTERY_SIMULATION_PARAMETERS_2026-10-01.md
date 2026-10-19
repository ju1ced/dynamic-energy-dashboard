# Batterijsimulatie — bevestigde invoerparameters

Status: OWNER CONFIRMED / DERIVED  
Datum: 2026-10-01  
Scope: uitsluitend offline simulatie; geen Home Assistant-, SMA- of batterijwrites

## Fysieke batterij

| Parameter | Waarde | Status |
|---|---:|---|
| Bruikbare capaciteit | 14,24 kWh | OWNER CONFIRMED |
| Simulatie-SOC minimum | 0% | OWNER CONFIRMED |
| Simulatie-SOC maximum | 100% | OWNER CONFIRMED |
| Verborgen fysieke buffer onderaan | 3% | OWNER CONFIRMED |
| Verborgen fysieke buffer bovenaan | 3% | OWNER CONFIRMED |
| Maximaal laadvermogen | 5,0 kW | OWNER CONFIRMED |
| Maximaal ontlaadvermogen | 5,0 kW | OWNER CONFIRMED |

De simulatie gebruikt 14,24 kWh als reeds bruikbare capaciteit. De verborgen
buffers worden dus niet nogmaals van deze capaciteit afgetrokken.

## Efficiëntie

De eerste empirische schatting gebruikt de reeds geëxporteerde, onderling
uitgelijnde Home Assistant-uurdata van 2026-01-22 tot 2026-09-30:

- 5.833 uren met zowel een geldige laad- als ontlaadwaarde;
- geladen: 2.654,531 kWh;
- ontladen: 2.266,245 kWh;
- afgeleide round-trip-verhouding: 85,3727%;
- symmetrische modelsplitsing: 92,3974% laden en 92,3974% ontladen.

Status: DERIVED. De lange meetperiode beperkt de invloed van het verschil tussen
begin- en eind-SOC, maar de schatting wordt later nog gecontroleerd met
expliciete SOC-grenzen wanneer voldoende historische SOC-data beschikbaar is.

## Dispatchregels

- Laden vanuit het net is toegestaan.
- Ontladen naar het net is toegestaan.
- PV-productie krijgt voorrang.
- Zelfverbruik maximaliseren heeft voorrang op netexport.
- Netexport blijft toegestaan wanneer die na verliezen en degradatie financieel
  voordelig is.
- Een hogere capaciteitspiek is toegestaan wanneer de totale baten van lagere
  energieprijzen groter zijn dan extra piekkost, conversieverlies en degradatie.

## Economische analyse

De simulatie rapporteert afzonderlijk:

- bruto prijsarbitrage;
- conversieverliezen;
- vermeden of verplaatste injectie;
- extra capaciteitspiekkost;
- batterijthroughput en equivalente volledige cycli;
- degradatiekost;
- netto incrementele besparing bovenop het werkelijk gemeten batterijgedrag.

Zolang geen aanschaf-/vervangingskost en gegarandeerde cycli zijn opgegeven,
wordt degradatie niet verborgen op één geschatte waarde vastgezet. Het model
berekent:

1. de maximale degradatiekost per verwerkte kWh waarbij dispatch nog rendabel is;
2. een gevoeligheidsanalyse voor meerdere degradatiekosten;
3. de marginale jaarlijkse opbrengst van extra batterijcapaciteit;
4. de maximale geïnstalleerde meerprijs waarbij een extra batterij binnen een
   gekozen terugverdientijd rendabel wordt.

Voor een definitieve investeringsbeslissing zijn later nog de offerteprijs,
extra bruikbare capaciteit, garantievoorwaarden en gewenste maximale
terugverdientijd nodig.
