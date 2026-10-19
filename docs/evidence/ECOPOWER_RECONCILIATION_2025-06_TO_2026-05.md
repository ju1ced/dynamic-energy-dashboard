# Ecopower/Fluvius Reconciliation 2025-06 to 2026-05

Status: VERIFIED owner evidence  
Gerelateerde tickets: P1-008 en P1-011  
Analyse uitgevoerd: 2026-09-28

## Bewijsgrens

De ruwe Fluvius-CSV en Ecopower-afrekeningsfactuur bevatten persoonsgegevens, EAN-, meter-, klant-, contract-, factuur-, adres- en betaalgegevens. Ze blijven daarom onder `docs/information/` en buiten Git.

Dit document, `fluvius-quarter-analysis-2025-06-01_2026-06-01.json` en `ecopower-invoice-baseline-2025-06-01_2026-05-31.json` bevatten uitsluitend gemaskeerde, afgeleide resultaten.

## Periode en contract

De twee bestanden dekken exact dezelfde leveringsperiode:

- begin: `2025-06-01 00:00 Europe/Brussels`;
- einde: `2026-06-01 00:00 Europe/Brussels`;
- factuurperiode: 1 juni 2025 tot en met 31 mei 2026;
- product: Groene Burgerstroom;
- netbeheerder: Fluvius West;
- meterlezing op de factuur: jaarlijks;
- factuur vermeldt dat de meterstanden en verbruiksgegevens van Fluvius afkomstig zijn.

De factuur bewijst jaarlijkse meterafrekening. De formele term `SMR1` staat niet letterlijk in het document, maar Ecopower heeft volgens de eigenaar op 2026-09-30 rechtstreeks bevestigd dat het huidige regime `SMR1` is. De factuurbevinding blijft `VERIFIED`; de regimecode is `OWNER CONFIRMED`.

## Kwartierdata-completeness

De reproduceerbare analyzer rapporteert:

| Controle | Resultaat |
|---|---:|
| CSV-datarijen | 70.080 |
| Canonieke kwartierintervallen | 35.040 |
| Intervallen met zowel afname als injectie | 35.040 / 35.040 |
| Ontbrekende intervallen na tijdzonecanonisatie | 0 |
| Uitgelezen intervallen | 34.941 (`99,717466%`) |
| Geschatte intervallen | 99 (`0,282534%`) |
| Zomer-/wintertijdovergangen | 2 correct verwerkt |

De 99 geschatte intervallen liggen hoofdzakelijk op 18 juni 2025, plus twee intervallen op 31 mei 2026. Geschatte data worden behouden met hun kwaliteitsstatus en mogen niet stilzwijgend als uitgelezen worden voorgesteld.

De lokale CSV sorteert het herhaalde wintertijduur op kloktijd. De analyzer kent ieder interval daarom eerst een unieke UTC-start toe en sorteert daarna chronologisch. Zo worden de dubbele `02:00–03:00`-intervallen behouden en wordt het ontbrekende lente-uur niet foutief als datagat gemeld.

## Volumereconciliatie

| Stroom | Fluvius kwartiersom | Ecopower-factuur | Verschil |
|---|---:|---:|---:|
| Afname | 9.161,589 kWh | 9.161,59 kWh | -0,001 kWh |
| Injectie | 1.160,728 kWh | 1.160,74 kWh | -0,012 kWh |

De verschillen zijn respectievelijk circa `0,000011%` en `0,001034%`. Dit is consistent met afronding van kwartierwaarden op `0,001 kWh` en factuurweergave op `0,01 kWh`. De factuurregisterverschillen bedragen 9.161,587 kWh afname en 1.160,738 kWh injectie; ook daarmee blijft de afwijking maximaal `0,010 kWh`.

De maandelijkse afnamevolumes uit de CSV sluiten eveneens aan op de gefactureerde maandvolumes. Het grootste presentatieverschil is `0,021 kWh` in mei 2026; over de volledige periode compenseren de maandafrondingen elkaar.

## Factuurreconciliatie

De detailregels reproduceren het totaal exclusief btw exact:

| Component | Bedrag excl. btw |
|---|---:|
| Groene Burgerstroom, twaalf maandregels | € 1.192,08 |
| GSC | € 100,78 |
| WKK | € 35,91 |
| Injectievergoeding | € -23,21 |
| Databeheer | € 17,65 |
| Capaciteitstarief | € 300,06 |
| Afnametarief | € 614,48 |
| Bijdrage op de energie | € 17,65 |
| Bijzondere accijns | € 434,99 |
| Energiefonds | € 0,00 |
| Totaal excl. btw | € 2.690,39 |
| Btw | € 162,82 |
| Totaal incl. btw | € 2.853,21 |

De gefactureerde injectievergoeding voor deze historische periode was `€0,0200/kWh` en bedroeg `€23,21`. Dit is tijdgebonden bewijs en mag niet worden toegepast op augustus 2026, wanneer de geverifieerde Groene Burgerstroom-formule een andere totale vergoeding oplevert.

De facturatiepiek op de factuur is `5,26 kW`; de detailberekening gebruikt `5,264 kW` voor het capaciteitstarief.

## DSMR-contractexport als cross-check

De later aangeleverde DSMR Reader-schermexport bevat voor dezelfde twaalf
maanden weergegeven variabele kosten, vaste kosten en totalen. De vergelijking
met deze factuurbaseline geeft:

| Kostgroep | DSMR-export incl. btw | Factuur incl. btw | DSMR minus factuur |
|---|---:|---:|---:|
| Variabel | € 2.413,88 | € 2.516,44 | € -102,56 |
| Vast | € 414,96 | € 336,77 | € +78,19 |
| Totaal | € 2.828,84 | € 2.853,21 | € -24,37 |

Het totale verschil is slechts `-0,85%`, maar dit is geen componentvalidatie:
een te lage variabele kost en een te hoge vaste kost compenseren elkaar voor
`€78,19`. Bovendien telt DSMR `364` opgeslagen dagen tegenover `365`
kalenderdagen. De DSMR-totalen blijven daarom bruikbaar als intern consistente
sensitivitybron, niet als vervanging van een component-complete factuur.

Evidence:
`docs/evidence/DSMR_CONTRACT_INVOICE_RECONCILIATION_2025-06_TO_2026-05.md`.

## Modelgevolgen

1. Deze periode is een geldige factuurreconciliatiebaseline voor Groene Burgerstroom.
2. Het huidige contract werd jaarlijks afgerekend; kwartierdata bepalen de historische Groene Burgerstroom-energieprijs niet rechtstreeks.
3. Dezelfde 35.040 kwartierintervallen zijn wel geschikt voor Scenario A: een dynamisch contract toepassen op ongewijzigd historisch gedrag.
4. Voor exacte historische baselinekosten worden de maandvolumes, maandprijzen en overige factuurcomponenten gebruikt.
5. De dynamische tegenberekening is inmiddels uitgevoerd met volledige
   Day-Ahead-prijsdekking en een geversioneerde kostenengine.
6. Voor EV- en batterijsimulaties ontbreken voor deze volledige periode nog overlappende apparaatstromen; de Fluvius-data alleen kan het contracteffect simuleren, maar niet betrouwbaar toewijzen aan huis, EV, PV en batterij.
7. Een DSMR-totaal dat dicht bij de factuur ligt, mag niet als componentbewijs
   worden gebruikt wanneer vaste en variabele afwijkingen elkaar compenseren.

## Reproduceerbaarheid

De privacy-safe analyse kan opnieuw worden uitgevoerd met:

`python3 scripts/analyze_fluvius_quarter_csv.py <fluvius-export.csv> --output <analysis.json>`

De analyzer:

- gebruikt alleen de Python-standaardbibliotheek;
- ondersteunt Europese decimale komma's en puntkomma-CSV;
- zet lokale kwartieren om naar unieke UTC-intervallen;
- verwerkt beide DST-overgangen;
- rapporteert uitgelezen versus geschatte intervallen;
- neemt geen EAN-, meter- of adreswaarden op in zijn uitvoer.
