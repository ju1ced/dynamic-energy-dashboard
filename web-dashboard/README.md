# Read-only web dashboard

Dit dashboard visualiseert de gevalideerde Fluvius-, ENTSO-E-, Home Assistant-
en shadow-billingresultaten. Het bevat geen muterende API-routes of
apparaatcontrols.

## Data bouwen

```bash
python3 scripts/build_dashboard_data.py
```

De gegenereerde `web-dashboard/data/dashboard-data.json` bevat alleen
privacy-safe samenvattingen en geaggregeerde reeksen. Het bestand blijft lokaal
en wordt niet in Git opgenomen.

De pagina `Sturing` gebruikt de privacy-safe P2-008-samenvatting. Zij vergelijkt
de geplande en historische backtestwaarde voor piekneutraal, `7 kW`, `8 kW` en
`10 kW`. Het gedetailleerde kwartierprofiel blijft Git-ignored in `data/raw/`.
De pagina toont uitsluitend voorgestelde acties en bevat geen uitvoercommando's.

De pagina `Prijzen` gebruikt daarnaast een afzonderlijke actuele feed:

```bash
python3 scripts/build_current_day_ahead_prices.py --fetch
```

Deze feed haalt Belgische ENTSO-E Day-Ahead-prijzen read-only op, past de
geversioneerde Ecopower-formule toe en vergelijkt kwartier-, dag-, week- en
maandgemiddelden met de owner-provided indicatieve referentie van
`€0,2770/kWh`. De kwartiervergelijking bevat geen nettarieven,
capaciteitstarief, heffingen of abonnementsverdeling en is dus geen
factuurprognose.

## Lokaal en via LAN starten

```bash
python3 scripts/serve_dashboard.py --host 0.0.0.0 --port 4173
```

Open daarna `http://<lan-ip>:4173/`. De healthcheck staat op `/healthz`.

## Blijvend draaien

De geïnstalleerde user-service heet `dynamic-energy-dashboard.service`. Omdat
user lingering actief is, start hij automatisch bij het opstarten van de host
en blijft hij draaien zonder actieve Hermes- of shellsessie.

```bash
systemctl --user status dynamic-energy-dashboard.service
systemctl --user restart dynamic-energy-dashboard.service
journalctl --user -u dynamic-energy-dashboard.service
```

Het reproduceerbare servicebestand staat in
`deploy/systemd/dynamic-energy-dashboard.service`.

De actuele prijsfeed wordt door
`dynamic-energy-day-ahead-refresh.timer` vernieuwd om `00:10`, `13:35`, `14:50`
en `16:05` Europe/Brussels. De twee namiddagfallbacks voorkomen dat een nog niet
gepubliceerde volgende dag tot de capture van `23:45` ontbreekt. De
reproduceerbare unitbestanden staan onder `deploy/systemd/`.
Voor herstartbestendige refresh moet `ENTSOE_SECURITY_TOKEN` lokaal in het
Git-ignored `.env`-bestand staan; de token mag nooit in documentatie, Git of
dashboarddata worden opgenomen.

De prospectieve shadow-validatie gebruikt daarnaast twee read-only timers:

- `dynamic-energy-shadow-capture.timer` om `23:45 Europe/Brussels`; deze
  ververst eerst de Day-Ahead-prijzen en bevriest daarna SOC, Solcast,
  loadforecast, maandpiek en prijzen vóór de doeldag;
- `dynamic-energy-shadow-settlement.timer` om `00:45 Europe/Brussels`; deze
  rekent de vorige dag af tegen vijfminutenstatistieken en vernieuwt het
  privacyveilige cohortoverzicht.

De Python MCP-client voor deze lokale timers staat geïsoleerd in `.venv` en is
vastgelegd in `requirements-shadow-capture.txt`. De gedetailleerde kwartierdata
blijven onder het Git-ignored `data/raw/`. Ontbrekende, stale of onvolledige
inputs leveren `NO_ACTION`; de timers voeren geen actuatorwrites uit. Live
entity-ID's staan in de eveneens Git-ignored private mapping
`config/private/prospective-shadow-capture-entities.json`; de tracked example-
mapping bevat uitsluitend placeholders. PV- en prijsinputs mogen maximaal
`18 uur` oud zijn. De monotone maandpiekobservatie moet uit de huidige lokale
kalendermaand komen en mag maximaal `744 uur` oud zijn. Alleen de informatieve
prijsflag `collapsed_identical_duplicate` is toegestaan; onbekende, correctie-
en malformed flags worden geweigerd.

## Cloudflare

Wanneer `cloudflared` op dezelfde host draait, kan de lokale origin naar
`http://127.0.0.1:4173` wijzen. Wanneer de tunnel, zoals in deze installatie,
op een andere LXC draait, moet de origin naar `http://<dashboard-lan-ip>:4173`
wijzen en moet het netwerkverkeer van die LXC naar TCP 4173 toegestaan zijn.
Dit project maakt of activeert geen tunnel, hostname of toegangsbeleid.
Configureer vóór externe ontsluiting minimaal Cloudflare Access en beperk
toegang tot de bedoelde gebruikers.

## Leesbaarheid

Onderaan de navigatie staan drie knoppen voor 100%, 112% en 125% UI-schaal.
De gekozen schaal wordt lokaal in de browser bewaard en wijzigt geen
projectdata of energiesystemen.

## Veiligheidsgrenzen

- read-only statische frontend;
- geen Home Assistant-, SMA- of Smappee-writes;
- geen batterij- of EV-control;
- geen credentials of installatie-identifiers in de dashboarddataset;
- geen publieke exposure zonder afzonderlijke netwerk- en securitybeslissing.
