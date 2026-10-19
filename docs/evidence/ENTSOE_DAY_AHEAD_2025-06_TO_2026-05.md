# ENTSO-E Day-Ahead Live Ingest Evidence

Ticket: P2-004  
Status: `VALIDATED AND INDEPENDENTLY CROSS-CHECKED`  
Periode: 2025-06-01 00:00 Europe/Brussels tot 2026-06-01 00:00 Europe/Brussels  
UTC-venster: 2025-05-31T22:00:00Z tot 2026-05-31T22:00:00Z  
Opgehaald: 2026-09-30T10:36:44Z

## Resultaat

De officiële ENTSO-E Transparency Platform Web API leverde een Belgisch Day-Ahead-prijsdocument voor documenttype `A44`, procestype `A01` en bidding zone `10YBE----------2`.

Na tijdsvensterfiltering en correcte verwerking van zowel vaste als variabele prijsblokken bevat de genormaliseerde dataset:

- 35.040 verwachte kwartieren;
- 35.040 beschikbare kwartieren;
- 0 ontbrekende kwartieren;
- 0 dubbele kwartieren;
- 11.616 kwartieren uit uurresolutie;
- 23.424 kwartieren uit bronresolutie van 15 minuten;
- eerste volledig native kwartierlevering op 2025-10-01 00:00 Europe/Brussels;
- 502 kwartieren gereconstrueerd uit expliciete `A03`-blokken met ongewijzigde prijs;
- 1.861 kwartieren met een negatieve marktprijs;
- minimum -499,29 EUR/MWh;
- maximum 517,57 EUR/MWh.

## Parsercorrectie

De live API-respons gebruikt `curveType: A03`. Bij dit ENTSO-E-curvetype blijft een gerapporteerde waarde gelden tot de positie van het volgende blok; ontbrekende tussenposities zijn daardoor niet automatisch ontbrekende marktdata.[43]

De parser behandelt dit nu als expliciete bloksemantiek en markeert uitgebreide intervallen met `expanded_variable_sized_block`. Dit is geen forward-fill van onbekende data. Een werkelijk ontbrekende positie in een vast `A01`-blok blijft als ontbrekend gerapporteerd.

De API-respons bevatte lokale daggrenzen buiten het aangevraagde UTC-venster. De genormaliseerde dataset wordt daarom expliciet begrensd op het gevraagde halfopen interval.

Een eerdere ingestie gebruikte UTC-middernacht als jaargrens. Die reeks had wel
35.040 complete kwartieren, maar verschoof het lokale Fluvius-factuurvenster met
twee uur. De gecorrigeerde canonieke reeks gebruikt exact de lokale
factuurgrenzen hierboven; geen prijsinterval van Scenario A valt daardoor buiten
de gezamenlijke periode.

## Reproduceerbaarheid en privacy

- Volledige XML en genormaliseerde kwartierreeks staan onder Git-ignored `data/raw/`.
- De XML-responsehash is `cf91e1555dc0d4008d86aa61abaf38299dfe331f874b846b66479451cb92900c`.
- Het ENTSO-E-token wordt uitsluitend uit de lokale omgeving gelezen en komt niet voor in de ruwe of genormaliseerde bestanden.
- `market_issue_time` blijft `null`; `createdDateTime` wordt niet als oorspronkelijke veilingpublicatietijd geïnterpreteerd.

## Onafhankelijke EPEX-validatie

Twintig verspreide Belgische kwartieren voor leveringsdag 2025-10-06 zijn
mechanisch vergeleken met de officiële EPEX SPOT Day-Ahead-resultatentabel.[44]
Alle twintig prijzen komen exact overeen; er zijn nul mismatches en de maximale
absolute afwijking is `0,00 EUR/MWh`.

ADR-004 accepteert dat `market_issue_time` expliciet `null` blijft zolang de
oorspronkelijke auction-publicatietijd niet door de bron is bewezen. De reeks is
geschikt voor historische shadow billing, niet voor as-known-at-time replay.

## Sources

[43] https://transparencyplatform.zendesk.com/hc/en-us/articles/30262342482961-CurveType-A01-vs-CurveType-A03 — ENTSO-E Transparency Platform: CurveType A01 versus A03
[44] https://www.epexspot.com/en/market-results?auction=MRC&data_mode=table&delivery_date=2025-10-06&market_area=BE&modality=Auction&product=15&sub_modality=DayAhead — EPEX SPOT Belgian Day-Ahead market results for 2025-10-06
