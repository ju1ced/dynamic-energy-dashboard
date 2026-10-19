# Phase 1 Go/No-Go

Status: `GO READ-ONLY PHASE 2` - OWNER APPROVED  
Ticket: P1-014  
Beslisdatum: 2026-09-29  
Scopebesluit: alleen read-only monitoring, data-engineering en simulatie

## Besluitvoorstel

Voorstel: `CONDITIONAL GO` voor een strikt read-only Phase 2 en `NO-GO` voor contractwijziging of fysieke sturing.

De eigenaar heeft op 2026-09-29 expliciet goedkeuring gegeven voor Phase 2 binnen de read-only grenzen van dit document.

## Samenvatting Phase 1

Phase 1 heeft de installatie, databronnen, contractcontext en controllergrenzen voldoende geïnventariseerd om read-only data-engineering en shadow billing veilig te ontwerpen.

VERIFIED of OWNER CONFIRMED:

- PV: twee SMA-omvormers, samen `8 kW` nominaal AC en `8,5 kWp` geregistreerd DC;
- batterij: SMA SBS5.0-10 met LG RESU16H Prime, 16 kWh en bekende laad-/ontlaadlimieten;
- energiemanager: Sunny Home Manager 2.0 als System Manager;
- EV-laden: Smappee EV Wall Home, native `smart`-modus en bekende stroom-/fallbacklimieten;
- netaansluiting: driefasige delta, `2 × 40 A`;
- Home Assistant: volledige read-only entity-, metadata- en historie-inventaris;
- huidig contract: Ecopower Groene Burgerstroom, Fluvius West, particulier en 6% btw;
- historische baseline: volledig factuurjaar met 35.040 Fluvius-kwartieren;
- factuurreconciliatie: afname en injectie sluiten binnen maximaal `0,012 kWh` aan;
- officiële formules voor Groene Burgerstroom augustus 2026 en Dynamische Burgerstroom vanaf 1 augustus 2026;
- controllerownership: SMA voor PV/batterij, Smappee voor EV-laden en Home Assistant voorlopig read-only.

Er zijn geen productieautomatisaties gemaakt en geen Home Assistant-, SMA-, batterij- of Smappee-instellingen gewijzigd.

## Readiness-gates

| Gate | Status | Beoordeling |
|---|---|---|
| R1 Observeerbaarheid | Gedeeltelijk behaald | Primaire bronnen en historische dekking zijn bekend; reproduceerbare HA-intervalexport en langdurige kruisreconciliatie ontbreken |
| R2 Financiële reproduceerbaarheid | Gedeeltelijk behaald | Huidige factuur is gereconcilieerd; dynamische EPEX-feed en kostenengine ontbreken |
| R3 Control authority | Ontwerp behaald, runtime niet | Eén controller per actuator is vastgelegd; operationeel fallbackgedrag is niet getest |
| R4 Simulatiebewijs | Niet behaald | Scenario A-D zijn nog niet uitgevoerd |
| R5 Veilige activatie | Niet behaald | Geen failure-mode-, override- of fysieke controltests uitgevoerd |

Alleen R1 en R2 zijn relevant voor de voorgestelde read-only Phase 2. R3-R5 blokkeren iedere productiecontrole, maar hoeven offline data-analyse niet te blokkeren.

## Open punten die read-only Phase 2 niet blokkeren

- exacte Smappee Grid-CT-topologie en OCPP-status;
- fysieke laadpaalgroep en werkelijk fallback-/load-balancinggedrag;
- bruikbare batterijcapaciteit en exacte semantiek van `Battery Capacity Total`;
- werkelijk SMA-grid-charge-, curtailment- en `0 W`-PCC-gedrag;
- formele bevestiging dat geen injectienettarief geldt.

Deze punten blijven verplicht vóór een contractwissel of fysieke sturing waar zij relevant zijn.

## P0-blokkers voor read-only Phase 2

1. Een reproduceerbare, privacy-safe HA-intervalexport voor de beschikbare overlapperiode.
2. Een contractpassende historische en actuele EPEX Day-Ahead-kwartierfeed.
3. Een kostenengine die ontbrekende data zichtbaar afwijst en nooit stilzwijgend invult.
4. Een regressietest die de huidige Groene Burgerstroom-factuur reproduceert.

De eerste regressiebaseline bestaat al als privacy-safe afgeleide dataset; de engine zelf moet nog worden gebouwd.

## Voorgestelde uitvoeringsvolgorde Phase 2

### Stap E1 - P2-004 EPEX-datafundament

- selecteer een betrouwbare contractpassende bron;
- bewaar ruwe marktprijs, marktgebied, interval, UTC/local time, issue time en bronversie;
- verzamel minimaal de historische factuurperiode `2025-06-01` tot `2026-05-31`;
- rapporteer ontbrekende, dubbele, stale en gecorrigeerde waarden;
- pas nog geen contractformule toe in de ingestielaag.

### Stap E2 - P2-001 Home Assistant intervalexport

- exporteer Grid, PV, batterij, EV en relevante kwaliteitsmetadata read-only;
- gebruik cumulatieve totalen met expliciete delta-, reset- en rolloverlogica;
- normaliseer naar UTC en Europe/Brussels;
- vergelijk Grid-overlap met Fluvius-kwartieren;
- schrijf niets terug naar Home Assistant.

P2-004 en P2-001 mogen parallel worden uitgevoerd.

### Stap E3 - P2-002 Shadow-billing MVP

- reproduceer eerst de historische Groene Burgerstroom-factuur;
- bereken daarna Scenario A met exact dezelfde Fluvius-kwartieren en de Dynamische Burgerstroom-formule;
- houd energieprijs, GSC, WKK, injectie, abonnement, netkosten, heffingen, btw en capaciteitstarief afzonderlijk;
- toon maand-, jaar- en cumulatieve verschillen;
- geef geen contractadvies zolang de uitkomst niet onafhankelijk is gevalideerd.

### Stap E4 - P2-003 dashboardwireframes en latere dataschema's

Wireframes mogen pas na stabilisatie van het datamodel beginnen. Ze blijven volledig los van live Home Assistant-configuratie en bevatten geen actieve controls.

P2-005 forecastkwaliteit en P2-006 Energy Decision Log volgen pas wanneer het interval- en shadow-billingschema stabiel is; zij blokkeren Scenario A niet.

## Buiten de goedkeuring

Een Phase 2-go geeft geen toestemming voor:

- overstappen naar Dynamische Burgerstroom;
- wijzigen van Home Assistant-configuratie;
- activeren van SMA-forecast charging, netladen of setpoints;
- wijzigen van Smappee-modus, stroomlimiet of laadstatus;
- activeren van Modbus TCP of OCPP;
- productieautomatisaties;
- fysieke failure-mode- of fallbacktests;
- Phase 3 EV- of batterijoptimalisatie.

Voor iedere latere fysieke controlstap is een afzonderlijk ticket, risicoanalyse en expliciete goedkeuring vereist.

## Go/no-go-keuzes

De eigenaar kan één van deze beslissingen nemen:

1. `GO READ-ONLY PHASE 2` — P2-004 en P2-001 mogen starten binnen bovenstaande grenzen.
2. `GO MET CORRECTIES` — eigenaar noemt aanpassingen aan scope of volgorde vóór uitvoering.
3. `NO-GO` — Phase 2 blijft geblokkeerd.
4. `WACHT OP ECOPOWER` — de gate blijft open tot de SMR1/SMR3-reactie binnen is.

Gekozen besluit: `GO READ-ONLY PHASE 2`.

P2-004 en P2-001 zijn vrijgegeven. Alle overige afhankelijkheids- en veiligheidsgrenzen blijven gelden.
