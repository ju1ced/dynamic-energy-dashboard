# Dynamic Tariff Research

Status: fase-1-onderzoek  
Gerelateerde tickets: P1-008 en P1-011  
Raadpleegdatum: 2026-09-28

## Onderzoeksvraag

Welke markt-, contract-, meet- en datastructuur is nodig om een dynamisch elektriciteitstarief in Vlaanderen correct te beoordelen en in Home Assistant te simuleren?

## Markt- en contractlaag

Een dynamisch contract koppelt de energiecomponent aan het werkelijk gemeten verbruik en de werkelijke injectie van ieder contractinterval. Voor Ecopower is dit sinds 1 oktober 2025 een kwartierinterval op basis van de Belgische EPEX day-ahead-prijs.[2][3]

De beursprijs is niet de volledige eindprijs. Een betrouwbaar model bewaart minstens deze componenten afzonderlijk:

- day-ahead energieprijs;
- leveranciersfactor en opslag;
- groenestroom- en warmtekrachtcertificaten;
- nettarieven;
- capaciteitstarief;
- accijnzen en andere heffingen;
- btw;
- vaste abonnementen en databeheerkosten;
- injectieformule;
- eventuele kosten bij negatieve injectievergoeding.

## Kwartierwaarden en facturatie

Een dynamisch huishoudcontract vereist een digitale meter met geactiveerde kwartierwaarden en meetregime 3. De leverancier ontvangt gevalideerde kwartierdata; data in Mijn Fluvius kan eerder zichtbaar zijn maar kan nog geschat of later gecorrigeerd worden.[3][4]

Voor shadow billing moeten lokale P1- of Home Assistant-metingen daarom worden gezien als operationele data, terwijl gevalideerde Fluvius-/leveranciersdata de voorkeur krijgt voor factuurreconciliatie.[4]

## Tijdmodel

De simulatie moet:

- `Europe/Brussels` correct behandelen;
- dagen met 92, 96 of 100 kwartieren ondersteunen;
- intervalduur uit timestamps afleiden;
- versie en geldigheidsdatum van iedere tariefformule bewaren;
- publicatie-, meet- en correctietijd van data onderscheiden;
- ontbrekende intervallen niet stilzwijgend forward-fillen.

## Negatieve prijzen

Negatieve marktprijzen betekenen niet automatisch een negatieve totale afnameprijs, omdat opslagen, nettarieven, heffingen en belastingen kunnen blijven gelden.[2]

Ook een positieve beursprijs kan bij de dynamische Ecopower-injectieformule tot een negatieve injectievergoeding leiden door de contractuele afslag en vaste aftrek.[2] Het dashboard moet daarom marktprijs, contractprijs afname en contractprijs injectie afzonderlijk tonen.

## Home Assistant-datapatroon

Home Assistant vereist voor Energy Dashboard-stromen cumulatieve energie-entiteiten met geschikte energy device/state classes. Actuele vermogenssensoren zijn nuttig voor realtime flows, maar vervangen geen cumulatieve kWh-tellers.[9]

De officiële SMA-integratie kan batterij-SOC, charge/discharge power en cumulatieve charge/discharge energy leveren voor ondersteunde WebConnect-apparaten. SMA Energy Meter en Sunny Home Manager worden niet door die integratie ondersteund.[10]

Als een native cumulatieve teller ontbreekt, kan de Integral-helper vermogen naar energie integreren, maar dit blijft een benadering die tegen een fysieke teller moet worden gevalideerd.[12]

Recorder- en long-term-statisticsconfiguratie moeten worden gecontroleerd voordat data als financieel betrouwbaar wordt behandeld.[11]

## Forecasting

Forecast.Solar kan PV-verwachtingen leveren op basis van locatie, oriëntatie, helling en Wattpiek. Dit is een voorspelling, geen meting, en moet samen met forecastfout en issue time worden opgeslagen.[13]

Voor dynamische optimalisatie zijn daarnaast nodig:

- belastingsverwachting;
- EV-energiebehoefte en vertrektijd;
- actuele en verwachte batterij-SOC;
- contractprijzen voor afname en injectie;
- onzekerheidsmarges.

## Minimale shadow-billingdataset

| Veld | Resolutie | Bronprioriteit |
|---|---|---|
| Grid import/export kWh | 15 min | Gevalideerde meterdata, daarna lokale cumulatieve teller |
| PV kWh | 15 min of fijner | Native omvormerteller |
| Batterij charge/discharge kWh | 15 min of fijner | Native SBS-tellers |
| Batterij-SOC | 5-15 min | SBS/BMS |
| EV-laadenergie | 5-15 min | Laadpaalmeter |
| Huidige contractcomponenten | Geldigheidsperiode | Officiële tariefkaart/contract |
| Dynamische prijs | 15 min | Contractueel gebruikte EPEX-data |
| Forecast | 15-60 min | Geselecteerde forecastbron |
| Quality flags | Per interval | Datapipeline |

## Onderzoeksconclusie

De eerste stap is niet automatisering, maar een gevalideerd prijs- en meetmodel. Zonder exacte contractformules, SMR3-data, correcte tijdsintervallen en betrouwbare cumulatieve energiestromen kan een dashboard visueel overtuigend maar financieel fout zijn.

## Sources

[2] https://ecopower.be/groene-stroom/dynamische-burgerstroom
[3] https://ecopower.be/groene-stroom/bijzondere-voorwaarden-dynamische-burgerstroom
[4] https://www.fluvius.be/nl/factuur-en-tarieven/kwartierwaarden
[9] https://www.home-assistant.io/docs/energy/faq
[10] https://www.home-assistant.io/integrations/sma
[11] https://www.home-assistant.io/integrations/recorder
[12] https://www.home-assistant.io/integrations/integration
[13] https://www.home-assistant.io/integrations/forecast_solar
