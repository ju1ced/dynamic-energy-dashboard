# EPEX / ENTSO-E Day-Ahead Data Foundation

Ticket: P2-004  
Status: `DONE`  
Laatst bijgewerkt: 2026-09-30

## Bronkeuze

De primaire kandidaat voor reproduceerbare Belgische Day-Ahead-prijzen is de officiële ENTSO-E Transparency Platform Web API. De API-documentatie beschrijft de REST-integratie en de document-/procesparameters voor marktdata.[39][40]

Technische configuratie:

- document type: `A44` - Day-ahead Prices;
- process type: `A01` - Day ahead;
- marktgebied: Belgische bidding zone, EIC `10YBE----------2`;
- bronwaarde: EUR/MWh;
- output: genormaliseerde kwartieren met UTC en `Europe/Brussels`;
- geen Ecopower-formule in de ingestielaag.

## Marktresolutie

De Single Day-Ahead Coupling ging op 30 september 2025 over naar een market time unit van 15 minuten, met eerste levering op 1 oktober 2025.[41][42]

Gevolg voor Scenario A:

- 2025-06-01 tot en met 2025-09-30: native uurprijzen verwachten;
- vanaf 2025-10-01: native kwartierprijzen verwachten;
- een uurprijs wordt voor normalisatie exact over vier kwartieren herhaald;
- de ruwe prijs verandert daarbij niet;
- ieder uitgebreid kwartier krijgt `source_resolution_minutes: 60` en de kwaliteitsflag `expanded_from_60_minutes`.

De live respons gebruikt `curveType: A03`: een prijspositie blijft bij dit variabele-bloktype geldig tot de volgende gerapporteerde positie.[43] Deze expliciete bronsemantiek wordt gemarkeerd als `expanded_variable_sized_block` en is geen forward-fill van onbekende marktdata. Werkelijk ontbrekende posities in vaste `A01`-curves blijven ontbrekend.

## Geïmplementeerd

`scripts/ingest_entsoe_day_ahead_prices.py`:

- verwerkt ENTSO-E `Publication_MarketDocument` XML;
- ondersteunt native `PT60M` en `PT15M`;
- zet tijdstippen eerst naar UTC om en voegt daarna lokale Belgische tijd toe;
- bewaart document-ID, documenttijd, retrievaltijd en SHA-256 van de respons;
- rapporteert ontbrekende en dubbele kwartieren;
- accepteert negatieve prijzen;
- bewaart `market_issue_time` als `null` zolang geen bronveld met aantoonbaar de oorspronkelijke veilingpublicatietijd beschikbaar is;
- bevat een live fetchpad met token uitsluitend uit `ENTSOE_SECURITY_TOKEN`;
- begrenst genormaliseerde uitvoer expliciet op het aangevraagde halfopen UTC-venster;
- decodeert vaste `A01`-curves en variabele `A03`-prijsblokken afzonderlijk.

Zes regressietests dekken uur-naar-kwartiernormalisatie, native kwartieren, werkelijk ontbrekende posities, variabele prijsblokken, aangevraagde venstergrenzen en scheiding tussen documenttijd en markt-issue-time.

## Live jaarvalidatie

Op 2026-09-30 is het lokale factuurvenster `2025-06-01T00:00:00+02:00` tot
`2026-06-01T00:00:00+02:00` live opgehaald en gevalideerd. Het equivalente
halfopen UTC-venster is `2025-05-31T22:00:00Z` tot
`2026-05-31T22:00:00Z`:

- 35.040 verwachte en beschikbare kwartieren;
- 0 ontbrekende en 0 dubbele kwartieren;
- 11.616 kwartieren uit uurresolutie en 23.424 uit 15-minutenbronresolutie;
- eerste volledig native kwartierlevering: `2025-10-01T00:00:00+02:00`;
- 502 kwartieren uit expliciete `A03`-blokken;
- negatieve prijzen blijven ongewijzigd bewaard;
- ruwe XML en volledige reeks blijven Git-ignored onder `data/raw/`;
- privacy-safe samenvatting staat in `docs/evidence/ENTSOE_DAY_AHEAD_2025-06_TO_2026-05.md`.

De eerste live ingestie gebruikte UTC-middernacht als jaargrens. Hoewel die
reeks intern compleet was, kwam zij niet exact overeen met de lokale
Fluvius-factuurgrenzen. De canonieke reeks is daarom opnieuw opgehaald met het
exacte lokale jaarvenster; dit voorkomt een stille verschuiving van acht
kwartieren in Scenario A.

## Onafhankelijke officiële cross-check

Voor de Belgische leveringsdag 2025-10-06 zijn twintig deterministisch gekozen
kwartieren vergeleken met de officiële EPEX SPOT Day-Ahead-resultatentabel.[44]
De selectie dekt vijf verspreide blokken van telkens vier kwartieren. Alle
twintig EPEX-prijzen komen exact overeen met de genormaliseerde ENTSO-E-reeks;
de maximale absolute afwijking is `0,00 EUR/MWh`.

De reproduceerbare bronselectie staat in
`docs/evidence/epex-be-day-ahead-samples-2025-10-06.json`; het mechanische
vergelijkingsresultaat staat in
`docs/evidence/entsoe-epex-crosscheck-2025-10-06.json`.

## Geaccepteerde metadatabeperking

De oorspronkelijke auction issue time is niet veilig af te leiden uit
`createdDateTime`. Volgens ADR-004 blijft `market_issue_time` daarom expliciet
`null`, terwijl documenttijd en retrievaltijd apart worden bewaard. Dit is
voldoende voor historische shadow billing, maar niet voor as-known-at-time
forecast- of decision-replay.

## Veiligheidsgrens

Deze ingestie leest uitsluitend marktdata en schrijft alleen lokale bestanden. Zij wijzigt geen contract, Home Assistant-configuratie, SMA-instelling, batterijsetpoint of Smappee-laadstatus.

## Sources

[39] https://transparencyplatform.zendesk.com/hc/en-us/articles/15692855254548-Sitemap-for-RESTful-API-integration — ENTSO-E Transparency Platform RESTful API sitemap
[40] https://transparencyplatform.zendesk.com/hc/en-us/articles/12845911031188-Web-API-Documentation — ENTSO-E Web API documentation
[41] https://www.entsoe.eu/news/2025/09/30/entso-e-welcomes-the-go-live-of-the-15-minute-market-time-unit-mtu-in-the-single-day-ahead-coupling-sdac — ENTSO-E welcomes 15-minute MTU in SDAC
[42] https://www.nemo-committee.eu/assets/files/250930-nemo-committee-press-release-15-minute-mtu-sdac-go-live.pdf — NEMO Committee 15-minute MTU SDAC go-live press release
[43] https://transparencyplatform.zendesk.com/hc/en-us/articles/30262342482961-CurveType-A01-vs-CurveType-A03 — ENTSO-E Transparency Platform: CurveType A01 versus A03
[44] https://www.epexspot.com/en/market-results?auction=MRC&data_mode=table&delivery_date=2025-10-06&market_area=BE&modality=Auction&product=15&sub_modality=DayAhead — EPEX SPOT Belgian Day-Ahead market results for 2025-10-06
