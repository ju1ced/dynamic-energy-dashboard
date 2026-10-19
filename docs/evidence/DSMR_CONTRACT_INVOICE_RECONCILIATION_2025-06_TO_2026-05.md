# DSMR-contractexport versus Ecopower-factuur

Status: `VERIFIED_WITH_LIMITATIONS`

Classificatie: `READ_ONLY_DSMR_INVOICE_RECONCILIATION`

Periode: `2025-06-01` tot `2026-06-01`

## Resultaat

| Kostgroep | DSMR-export | Factuur | DSMR minus factuur |
|---|---:|---:|---:|
| Variabel, incl. btw | `€2413.88` | `€2516.44` | `€-102.56` |
| Vast, incl. btw | `€414.96` | `€336.77` | `€78.19` |
| Totaal, incl. btw | `€2828.84` | `€2853.21` | `€-24.37` |

Het totaal uit DSMR ligt slechts `0.85%` van de factuur,
maar dat maskeert twee tegengestelde componentverschillen: DSMR is bij de variabele
kosten `€102.56` lager en bij de vaste kosten
`€78.19` hoger. De nabijheid van het totaal bewijst dus
niet dat de componenten of de vaste dagkost correct zijn.

DSMR telt `364` opgeslagen dagen tegenover
`365` kalenderdagen. Dit verschil blijft als
kwaliteitsbeperking zichtbaar.

## Gevolg voor de driejarige sensitivity

De huidige conservatieve aanpak blijft correct: houd de historische DSMR-vaste
kosten gelijk in beide scenario's en voeg alleen het dynamische abonnement apart
toe. Behandel de DSMR-vaste dagkost niet als vermijdbare contractbesparing.

Voor definitief contractadvies moeten de vaste DSMR-kosten nog per jaar worden
uitgesplitst en onafhankelijk worden gekoppeld aan databeheer, capaciteitstarief,
Energiefonds en eventuele leverancierskosten.

## Veiligheidsgrens

Uitsluitend read-only analyse. Geen contractwijziging, productieautomatisatie of
apparaatsturing is uitgevoerd.
