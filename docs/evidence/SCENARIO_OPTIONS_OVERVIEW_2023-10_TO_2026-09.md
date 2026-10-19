# Overzicht interessante energiescenario's 2023-10 tot 2026-09

Status: `VERIFIED_WITH_LIMITATIONS`

Modus: uitsluitend offline en read-only

Analyseperiode: `2023-10-01` tot `2026-10-01`

Analyse uitgevoerd: `2026-10-01`

## Doel

Dit overzicht scheidt scenario's die met de huidige gegevens berekend kunnen
worden van opties waarvoor nog EV-, warmtepomp-, SOC- of comfortdata nodig is.
Er is geen productieconfiguratie gewijzigd en geen enkel apparaat aangestuurd.

Alle batterijsimulaties gebruiken:

- `14,24 kWh` virtuele bruikbare capaciteit;
- maximaal `5 kW` laden en ontladen;
- `85,3727%` round-trip-efficiëntie;
- `€0,06/kWh` degradatie per ontladen kWh;
- Belgische ENTSO-E Day-Ahead-prijzen;
- het resterende Fluvius-netprofiel na de historische batterijwerking;
- perfecte prijs- en verbruikskennis.

De resultaten zijn daarom technische en financiële bovengrenzen. Ze zijn geen
exacte redispatch van de bestaande batterij.

## Beknopte besliskaart

| Scenario | Status | Indicatieve waarde | Waarom interessant | Belangrijkste grens |
|---|---|---:|---|---|
| Dynamisch contract zonder sturing | `OPTION` | gemiddeld `€268,67/jaar` lager in de driejarige gereconcilieerde sensitivity | Vereist geen fysieke optimalisatie | All-in tarieven en vaste kosten zijn DSMR-gereconcilieerd, maar vaste/net-/belastingcomponenten zijn niet uitgesplitst of onafhankelijk gefactureerd |
| Winterse netlading zonder hogere maandpiek | `OPTION` | `€36,86/jaar` extra, waarvan `€19,69/jaar` in oktober-maart | Benut de 's winters vaak lege batterij | Perfect foresight op residueel profiel |
| Batterij-export tijdens dure kwartieren | `REQUIRES_TESTING` | `€35,19/jaar` extra boven piekneutraal netladen | Kan zeldzame prijspieken benutten | Controller, garantie, leverancier en regelgeving valideren |
| Extra `14,24 kWh` batterijcapaciteit | `INVESTMENT_CASE_REQUIRED` | `€84,21/jaar` perfecte bovengrens | Meer PV-opslag en arbitrage | Te weinig voor hardwarebesluit zonder kost en levensduur |
| EV slim laden | `DATA_GATED` | Nog niet betrouwbaar | Grote verschuifbare last | Vertrektijd, doelenergie en beschikbaarheidsvenster ontbreken |
| Warmtepomp voorverwarmen | `DATA_GATED` | Nog niet betrouwbaar | Thermische opslag kan goedkope uren benutten | Vermogen, COP, temperatuur en comfortgrenzen ontbreken |
| Gecombineerd energiemanagement | `DATA_GATED` | Nog niet betrouwbaar | Kan batterij, EV en warmte gezamenlijk plannen | Volledige gedesaggregeerde kwartierdata ontbreekt |

## Winterse netlading

De piekneutrale variant mag uit het net laden, maar de gesimuleerde maandpiek
niet verhogen boven de historisch waargenomen maandpiek.

| Lokaal jaar | PV-only waarde | Met prijsbewust netladen | Extra waarde netladen |
|---|---:|---:|---:|
| 2023-2024 | `€63,18` | `€84,73` | `€21,56` |
| 2024-2025 | `€87,13` | `€128,04` | `€40,91` |
| 2025-2026 | `€84,35` | `€132,46` | `€48,11` |
| Gemiddeld | `€78,22` | `€115,08` | `€36,86` |

Van de gemiddelde extra waarde door netladen ontstaat `€19,69/jaar` in de
wintermaanden oktober tot en met maart. De rest ontstaat in goedkope kwartieren
buiten die maanden.

Dit ondersteunt een softwarematig shadow-scenario voor de bestaande batterij,
maar nog geen productieautomatisatie. De Fluvius-basis bevat de bestaande
batterijwerking al; vooral in de winter, wanneer die werking beperkt is, is de
residuele benadering het meest informatief.

## Absolute gezamenlijke kwartierpieken

De grenzen van `7`, `8` en `10 kW` gelden voor de totale gemiddelde
kwartierafname aan het aansluitpunt. Huisverbruik, warmtepomp, EV en
batterijladen delen dus dezelfde grens.

| Grens | Historische overschrijdingen | Grootste overschrijding | Beste perfecte modelwaarde | Prijsbewust netladen gekozen |
|---|---:|---:|---:|---:|
| `7 kW` | `125` kwartieren | `3,012 kW` | `€98,12/jaar` | `1/3` jaren |
| `8 kW` | `19` kwartieren | `2,012 kW` | `€89,95/jaar` | `0/3` jaren |
| `10 kW` | `1` kwartier | `0,012 kW` | `€74,95/jaar` | `0/3` jaren |

Interpretatie:

1. `7 kW` is een strakke gezamenlijke limiet. In 2023-2024 is vooraf netladen
   nodig om voldoende SOC voor peak shaving beschikbaar te hebben. In de andere
   jaren is laden uit PV-overschot meestal financieel beter.
2. `8 kW` is een middenvariant met meer gelijktijdige ruimte, maar de gemeten
   profielen overschrijden deze grens slechts `19` kwartieren in drie jaar.
3. `10 kW` is vooral een guardrail tegen uitzonderlijke gelijktijdigheid. De
   historische maximale overschrijding was slechts `0,012 kW`.
4. Een hoger plafond maakt goedkoop batterijladen technisch eenvoudiger, maar
   betekent niet automatisch meer nettowinst. De optimizer kiest onder `8` en
   `10 kW` in geen enkel jaar voor de netlaadvariant, omdat verliezen en
   degradatie groter zijn dan de extra prijswaarde.
5. De berekende waarde bevat peak shaving en PV-opslag. Ze mag niet volledig aan
   winterse prijsarbitrage worden toegeschreven.

## Aanbevolen volgorde

1. De reeds gebouwde 36-maands tariefledger aanvullen met historische
   tariefkaarten/facturen en de componenten per toepassingsperiode reconciliëren.
2. Een read-only shadow-controller voor winterse, piekneutrale batterijlading
   bouwen en vergelijken met de perfecte bovengrens.
3. `7`, `8` en `10 kW` als gezamenlijke guardrails evalueren met expliciete
   headroom voor huis, warmtepomp en EV.
4. EV-optimalisatie toevoegen zodra beschikbaarheidsvensters en doelenergie
   bekend zijn.
5. Warmtepompflexibiliteit pas toevoegen met comfort-, temperatuur- en COP-data.
6. Batterij-export en extra hardware pas onderzoeken nadat de softwarematige
   scenario's realistisch zijn gevalideerd.

## Grenzen

- De historische batterij kan over drie jaar niet exact uit het Fluvius-profiel
  verwijderd worden.
- EV, warmtepomp en huis zijn in de driejaarsbasis niet afzonderlijk
  gereconstrueerd.
- De scenario's kennen toekomstige prijzen en belasting perfect.
- SOC wordt per kalendermaand op `50%` gestart en beëindigd.
- Het capaciteitstarief wordt na de dispatch berekend; de optimizer optimaliseert
  niet gelijktijdig een continue afweging tussen energieprijs en maandpiek.
- De Ecopower-formule van augustus 2026 wordt retrospectief gebruikt.
- De driejarige contractvergelijking is een geconfigureerde all-in-rate-
  sensitivity. Ze is niet component-compleet en geen factuurreconstructie.

Machineleesbare bron:
`docs/evidence/multiyear-energy-battery-summary-2023-10-01_2026-10-01.json`.
