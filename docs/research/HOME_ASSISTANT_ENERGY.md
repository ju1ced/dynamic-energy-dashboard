# Home Assistant Energy Research

Status: fase-1-onderzoek zonder live toegang  
Gerelateerd ticket: P1-007  
Raadpleegdatum: 2026-09-28

## Energy Dashboard en statistics

Home Assistant verwacht voor energiestromen cumulatieve energy-sensoren met geschikte units en `total`/`total_increasing` state classes. Actuele power-sensoren gebruiken `measurement` en zijn aanvullend voor realtime flows.[9]

Recorder is de bron voor historie en statistics. Een uitgesloten entity of foutieve unit/state class kan daardoor onbruikbaar zijn voor Energy Dashboard en long-term statistics.[11]

De huidige inventaris moet daarom per entity minstens vastleggen:

- fysieke bron en integratie;
- momentaan vermogen versus cumulatieve energie;
- unit, device class en state class;
- tekenconventie en resetgedrag;
- updatecadans en stale-drempel;
- Recorder- en statisticsstatus;
- formule en dependencies voor templates.

## Bekende entities

De drie genoemde realtime entities lijken op basis van hun namen vermogenssensoren, maar dit is niet voldoende bewijs. Zij moeten live worden gecontroleerd op unit en metadata.

`Netto Huisverbruik` vereist extra validatie op formule, batterijrichting, gelijktijdige import/exportupdates en availability. Bronuitval mag niet met `float(0)` als werkelijk nulverbruik worden opgeslagen.

De officiële SMA-integratie kan voor ondersteunde apparaten SOC, charge/discharge power en cumulatieve batterij-energie leveren. Sunny Home Manager en SMA Energy Meter zijn volgens de integratiedocumentatie zelf niet ondersteund.[10]

## Helpers

De Integral-helper kan sampled vermogen omzetten in energie wanneer geen native cumulatieve teller bestaat. Dit blijft een benadering en moet over meerdere dagen tegen een fysieke teller worden vergeleken.[12]

Native cumulatieve tellers hebben voorkeur voor financiële toepassingen.

## Forecasting

Forecast.Solar levert PV-verwachtingen op basis van installatieparameters en weerdata. De output moet als forecast worden opgeslagen, niet als werkelijke productie, en voorzien zijn van issue time en forecastfout.[13]

## Fase-1-boundary

Toegestaan:

- read-only sensors;
- statisticsaudit;
- prijs- en forecastingestie;
- templates en helpers als ontwerpvoorstel;
- simulatie en advies;
- datakwaliteitsdashboard.

Niet toegestaan:

- service calls naar batterij, PV of laadpaal;
- schrijfregisters of REST commands;
- productiewijzigingen aan recorder/templates;
- automatische statistics-repair;
- controls zonder apart gevalideerd ticket.

## Sources

[9] https://www.home-assistant.io/docs/energy/faq
[10] https://www.home-assistant.io/integrations/sma
[11] https://www.home-assistant.io/integrations/recorder
[12] https://www.home-assistant.io/integrations/integration
[13] https://www.home-assistant.io/integrations/forecast_solar
