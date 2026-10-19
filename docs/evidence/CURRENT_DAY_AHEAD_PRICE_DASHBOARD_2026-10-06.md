# Actuele Day-Ahead-prijzen op het shadow dashboard

Datum: 2026-10-06  
Classificatie: `READ_ONLY` / `INDICATIVE_PRICE_SIGNAL_NOT_INVOICE`

## Ownerbeslissing

De exacte historische elektriciteitsprijzen zijn niet langer beslissend voor de
huidige indicatieve vergelijking. Het dashboard gebruikt daarom
`€0,2770/kWh` inclusief btw als owner-provided gemiddelde referentie voor het
verbruik. Dit is geen factuurreconstructie of contractadvies.

## Ecopower-berekening

Voor Dynamische Burgerstroom gebruikt het dashboard de geversioneerde formule
`ECOPOWER_DBS_2026-08-01`:

- afname-energie: `0,00102 × EPEX_DA_EUR_per_MWh + €0,004/kWh`;
- groenestroomcertificaten: `€0,011/kWh` exclusief btw;
- warmtekrachtcertificaten: `€0,00392/kWh` exclusief btw;
- particuliere afname: `6%` btw;
- abonnement: `€5/maand` exclusief btw, niet verdeeld over de kwartierlijn.

De officiële Ecopower-productpagina vermeldt dat afname en injectie per kwartier
tegen de dynamische formule worden afgerekend. De tariefkaart vanaf 1 augustus
2026 bevestigt de formule en de afzonderlijke GSC-, WKK-, abonnements- en
btw-componenten.[1][2]

## Eerste actuele generatie

ENTSO-E-ophaaltijd: `2026-10-06T08:05:07Z`

- dekking: `2026-09-01 00:00` tot `2026-10-06 23:45` Europe/Brussels;
- `3.456` kwartieren;
- `0` ontbrekende kwartieren;
- `0` dubbele kwartieren;
- komende/gepubliceerde kwartieren: `96` voor 2026-10-06;
- gemiddelde Ecopower-afnameprijs: `€0,241391/kWh`;
- minimum: `€0,161909/kWh`;
- maximum: `€0,459022/kWh`;
- `72/96` kwartieren liggen onder de indicatieve referentie van `€0,2770/kWh`.

Op het moment van ophalen, vóór de publicatie van de volgende dag, waren nog geen
prijzen voor 2026-10-07 beschikbaar. Ook de geplande run van `13:35
Europe/Brussels` bleef terecht `PARTIAL`. Een read-only herhaling om `14:44`
haalde vervolgens alle `96` kwartieren voor 2026-10-07 op en classificeerde de
feed als `COMPLETE`.

Een herhaalde validatierun om `2026-10-06T08:18:06Z` classificeerde het gevraagde
venster daarom terecht als `PARTIAL`: 2026-10-07 ontbrak nog volledig. De feed
publiceerde op dat moment alleen de `54` nog niet verstreken kwartieren vanaf
`10:30 Europe/Brussels`; verstreken kwartieren van dezelfde dag worden niet meer
als “komend” gepresenteerd.

## Dashboardweergave

De pagina `Prijzen` toont nu:

- de Ecopower-afnameprijs per kwartier tegenover `€0,2770/kWh`;
- minimum, maximum, daggemiddelde en aantal kwartieren onder de referentie;
- aggregaties per dag, ISO-week en maand;
- expliciete labels voor gedeeltelijke weken en maanden;
- formuleversie, ophaaltijd, kwaliteitsstatus en ontbrekende kwartieren;
- de bestaande historische marktcontext als secundaire grafiek.

De builder controleert daarnaast dat UTC- en lokale timestamps hetzelfde moment
voorstellen en vergelijkt de werkelijk ontvangen kwartieren met het volledige
aangevraagde halfopen ENTSO-E-venster. De browser herberekent bij iedere weergave
welke kwartieren nog toekomstig zijn. Wanneer de bron ouder is dan 36 uur, wordt
de status client-side `STALE` en worden actuele kwartiermetrics onderdrukt.

De vergelijking is bewust niet als all-in factuurprognose gelabeld. Nettarieven,
capaciteitstarief, accijnzen, Energiefonds en de verdeling van het maandabonnement
zijn niet opgenomen in de kwartierlijn.

## Automatische vernieuwing

De user-systemd-timer `dynamic-energy-day-ahead-refresh.timer` is ingeschakeld en
actief met geplande runs om `00:10`, `13:35`, `14:50` en `16:05
Europe/Brussels`. De extra namiddagmomenten zijn fail-safe publicatiefallbacks
vóór de prospectieve capture van `23:45`. De refresh is read-only en schrijft
uitsluitend de lokale dashboardprijsfeed en een Git-ignored ruwe ENTSO-E-export.

De ENTSO-E-token is momenteel in de actieve user-systemd-manager geïmporteerd.
Voor herstartbestendige automatische refresh moet dezelfde token lokaal in het
Git-ignored projectbestand `.env` beschikbaar zijn; de waarde is niet gelezen,
geprint of gecommit.

## Validatie

- `6/6` prijsfeedtests geslaagd;
- `12/12` bestaande dashboarddatatests geslaagd;
- gecombineerde gerichte suite: `18/18` geslaagd;
- volledige Python-suite: `131/131` geslaagd;
- JavaScript-suite: `11/11` geslaagd, inclusief uitvoerbare regressietests voor
  verstreken kwartieren, kwartiergrenzen, stale feeds en fail-closed ongeldige
  ophaaltijden;
- JavaScript-syntaxcontrole geslaagd;
- Python-compilecontrole geslaagd;
- onafhankelijke reviewbevindingen rond verstreken kwartieren, stale feeds,
  ontbrekende volledige dagen en inconsistente timestamps zijn opgelost;
- desktopbrowser: actuele prijskaart, grafiek en drie aggregatietabellen zichtbaar
  met kwaliteitsstatus `PARTIAL` zolang 2026-10-07 nog niet gepubliceerd was;
- desktopbrowser: hoofdweergave en contextpaneel tonen beide dezelfde actuele
  telling van `54` komende kwartieren;
- hoofdweergave en contextpaneel delen per render exact dezelfde tijdsnapshot,
  zodat een render rond een kwartiergrens geen verschillende tellingen kan tonen;
- mobiel `390 × 844`: geen horizontale body- of contentoverflow;
- mobiel menudoel: `44 × 44` CSS-pixels;
- geen Home Assistant-, SMA-, Smappee-, batterij- of laadpaalwrites.

## Sources

[1] https://ecopower.be/groene-stroom/dynamische-burgerstroom  
[2] https://cdn.nimbu.io/s/4tn7vz5/channelentries/ma28q8f/files/1790570062186/20260801_dbs_tariefkaart.pdf
