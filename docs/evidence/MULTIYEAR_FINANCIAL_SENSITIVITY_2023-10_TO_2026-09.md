# Meerjarige financiële sensitivity 2023-10 tot 2026-09

Status: `VERIFIED_WITH_LIMITATIONS`

Classificatie: `RECONCILED_ALL_IN_RATE_SENSITIVITY`

Verificatiestatus: `RATE_RECONCILED_FIXED_COMPONENTS_HELD_CONSTANT`

Modus: uitsluitend offline en read-only

Analyse uitgevoerd: `2026-10-01`

## Doel

Deze analyse vergelijkt voor drie lokale energiejaren:

1. de maandtarieven uit de door de eigenaar aangeleverde DSMR Reader-export,
   intern gereconcilieerd tegen de weergegeven energiekosten en voor
   januari-september 2026 zonder afwijking gekruist met Home Assistant; en
2. de Ecopower-formule `ECOPOWER_DBS_2026-08-01`, retrospectief toegepast op
   dezelfde Fluvius-kwartierstromen en Belgische Day-Ahead-prijzen.

Er is geen contract gewijzigd en er is geen Home Assistant-, SMA-, Smappee- of
batterijwrite uitgevoerd.

## Tariefledger

De privacy-safe ledger
`config/tariffs/historical-electricity-2023-10_2026-09.json` bevat `36`
maandperioden:

- alle `36` maanden gebruiken de aangeleverde DSMR-export voor afname, injectie
  en vaste dagkosten;
- de `9` historische Home Assistant-maandprijzen van 2026 stemmen exact overeen
  met de export;
- de eerdere vier DSMR/HA-afwijkingen waren afkomstig uit een oudere
  contractrecordextractie en zijn door de schermexport opgelost;
- de weergegeven DSMR-energiekosten sluiten per relevant contractblok binnen
  `€0,10` aan op afname maal tarief minus injectie maal vergoeding;
- de leveranciersovergang van eMobility naar Ecopower in maart 2024 blijft
  zichtbaar.

## Resultaat

| Lokaal jaar | Bruikbare kwartieren | Historisch incl. vaste kost | Dynamisch incl. vaste kost en abonnement | Dynamisch minus historisch |
|---|---:|---:|---:|---:|
| 2023-2024 | `35.130` | `€2.692,59` | `€2.145,37` | `€-547,23` |
| 2024-2025 | `35.040` | `€2.667,02` | `€2.571,42` | `€-95,60` |
| 2025-2026 | `35.040` | `€3.040,54` | `€2.877,36` | `€-163,17` |
| Drie jaar | `105.210` | `€8.400,15` | `€7.594,15` | `€-806,00` |

De sensitivity geeft gemiddeld `€268,67/jaar` voordeel voor het retrospectieve
dynamische scenario. Alle drie jaren geven dezelfde richting, maar de omvang
verschilt sterk. Vooral 2023-2024 is gevoelig voor de toenmalige hogere
eMobility-configuratiewaarden. De eerdere variabele-kostensensitivity bedroeg
`€332,27/jaar`; na toevoeging van het dynamische abonnement van `€5,30/maand`
inclusief geconfigureerde btw resteert `€268,67/jaar`.

## Factuurcross-check van de DSMR-componentverdeling

Voor het gevalideerde factuurjaar juni 2025 tot en met mei 2026 ligt het
DSMR-totaal `€24,37` onder de factuur (`-0,85%`). Dat kleine totaalverschil
maskeert echter een variabele kost die `€102,56` te laag is en een vaste kost die
`€78,19` te hoog is. Daarom blijven de DSMR-vaste dagkosten in beide scenario's
gelijk: ze worden niet als vermijdbare contractbesparing behandeld.

Deze cross-check verhoogt de betrouwbaarheid van de gekozen conservatieve
rekenmethode, maar bewijst niet dat de DSMR-componentverdeling historisch juist
is. Zie
`docs/evidence/DSMR_CONTRACT_INVOICE_RECONCILIATION_2025-06_TO_2026-05.md`.

## Wat wel is opgenomen

- werkelijke Fluvius-afname en -injectie per kwartier;
- exact gekoppelde Belgische Day-Ahead-prijzen;
- uit DSMR geëxporteerde historische afname- en injectietarieven per maand;
- uit DSMR geëxporteerde vaste dagkosten, in beide scenario's ongewijzigd
  voortgezet zolang de componenten niet zijn uitgesplitst;
- Home Assistant-afnameprijzen voor januari-september 2026 als overeenstemmende
  cross-check;
- dynamische afnameformule, injectieformule, GSC, WKK, geselecteerde variabele
  net-/heffingscomponenten en 6% afname-btw volgens de huidige modelconfiguratie;
- het dynamische abonnement van `€5/maand` exclusief en `€5,30/maand` inclusief
  geconfigureerde btw;
- zes onbeschikbare Fluvius-kwartieren als ontbrekend, niet als nul.

## Wat niet component-compleet is

- historische leverancierscomponenten per tariefkaart;
- historische Fluvius West-nettarieven per toepassingsperiode;
- historische heffingen en accijnzen per toepassingsperiode;
- onafhankelijke bevestiging van btw-inclusie via tariefkaart of factuur;
- uitsplitsing van de DSMR-vaste dagkosten in leverancier, databeheer,
  energiebijdrage, Energiefonds en andere vaste netcomponenten;
- capaciteitstarief met de officieel toepasselijke historische maandpieken en
  coëfficiënten;
- energie in de zes onbeschikbare kwartieren van 25 april 2024.

Daarom is dit geen component-complete factuurreconstructie en geen definitief
contractadvies. Het gevalideerde factuurjaar 2025-06 tot 2026-05 blijft de enige
periode met een volledige factuurtegenberekening.

## Reproduceerbaarheid

Bronnen en afgeleide bestanden:

- `config/tariffs/historical-electricity-2023-10_2026-09.json`;
- `docs/evidence/dsmr-contract-price-ledger-2023-10_2026-09.json`;
- `docs/evidence/dsmr-contract-invoice-reconciliation-2025-06_2026-05.json`;
- lokale bronexport `docs/information/energy_contracts_export_dsmr.txt`;
- `data/raw/dsmr-reader-export-2023-10-01_2026-10-01/daily/energy-supplier-prices.json`;
- `config/tariffs/ecopower-monthly-2026-ha.json`;
- `docs/evidence/multiyear-energy-battery-summary-2023-10-01_2026-10-01.json`;
- `data/raw/multiyear-energy-battery-comparison-2023-10-01_2026-10-01.json`.

De read-only dashboardweergave toont de drie jaar afzonderlijk en labelt de
bedragen expliciet als niet component-complete sensitivity.
