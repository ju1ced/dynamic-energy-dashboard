# Backlog en ticketregister

## Epics

| Epic | Naam | Resultaat |
|---|---|---|
| E01 | Discovery & Evidence | Gevalideerde inventaris van hardware, software, configuratie en bronnen |
| E02 | Dynamic Readiness | Componentgewijze readinessmatrix, gaps, risico's en investeringsopties |
| E03 | Energy Data Foundation | Betrouwbare meet-, statistiek-, prijs- en forecastlaag |
| E04 | Shadow Billing | Vergelijking huidig contract en dynamische scenario's op werkelijke data |
| E05 | Dashboard Experience | Wireframes en dashboards voor flows, prijzen, financiën, batterij, EV en beslissingen |
| E06 | Optimization & Control | Veilige, verklaarbare en omkeerbare optimalisatie na validatie |
| E07 | Safety & Operations | Guardrails, fallback, observability, tests en operationele documentatie |

## Uitvoeringsvolgorde

- A: projectfundament en beschikbare informatie
- B: parallel hardware-, platform- en tariefonderzoek
- C: synthese van readiness, gaps, architectuur en simulatie
- D: validatie door eigenaar en formele fase-2-go/no-go
- E: vervolgwerk; geblokkeerd totdat fase 1 is goedgekeurd

## P1-001 - Projectfundament en traceerbaarheid

- Epic: E01
- Fase/volgorde: A
- Prioriteit: P0
- Status: Done
- Doel: Repositorystructuur, documentenset, epics, ticketregister, Kanban en decision-logconventie opzetten.
- Afhankelijkheden: geen
- Acceptance criteria:
  - De elf gevraagde deliverables en een Kanban-board hebben een vast pad.
  - Elk actief board-item verwijst naar exact één ticketheading.
  - Elk ticket bevat doel, afhankelijkheden en testbare acceptance criteria.
  - Productie- en live-systeemwijzigingen zijn expliciet uitgesloten.

## P1-002 - Beschikbare eigenaarinformatie en bewijsmateriaal inventariseren

- Epic: E01
- Fase/volgorde: A
- Prioriteit: P0
- Status: Done
- Doel: Bekende gegevens uit de opdracht vastleggen en ontbrekende hardware-, configuratie- en contractgegevens exact benoemen.
- Afhankelijkheden: P1-001
- Acceptance criteria:
  - Bekende feiten en te verifiëren claims zijn gescheiden.
  - `INFORMATION_REQUIRED_FROM_OWNER` noemt per component de exacte gevraagde gegevens en een veilige verzamelmethode.
  - Geen onbekend merk, model, firmware of protocol wordt ingevuld op basis van aannames.

## P1-003 - PV-installatie onderzoeken

- Epic: E01
- Fase/volgorde: B
- Prioriteit: P0
- Status: Done
- Doel: Exacte PV-topologie, omvormers, lokale interfaces, meetpunten, curtailment en SMA-compatibiliteit bepalen.
- Afhankelijkheden: P1-002; exacte modellen vereist voor definitieve conclusies
- Acceptance criteria:
  - Bekend vermogen en historische jaarproductie zijn vastgelegd als eigenaarinformatie.
  - Per bevestigd omvormermodel zijn API, Modbus, uitleesbare parameters en regelmogelijkheden met officiële bron gedocumenteerd.
  - Zero-export en curtailment worden alleen als beschikbaar gemarkeerd na model- en firmwarevalidatie.

## P1-004 - SMA-batterijsysteem en arbitragemogelijkheden onderzoeken

- Epic: E01
- Fase/volgorde: B
- Prioriteit: P0
- Status: Done
- Doel: Hardware, batterijcapaciteit, vermogenslimieten, SOC-beleid, interfaces en officiële externe sturing onderzoeken.
- Afhankelijkheden: P1-002; exact SBS-type, firmware en batterijtype
- Acceptance criteria:
  - Technisch mogelijk, officieel ondersteund en niet-officieel mogelijk zijn afzonderlijk beoordeeld.
  - Netladen, externe setpoints, reserve-SOC, efficiëntie en garantie-/levensduurrisico's zijn behandeld.
  - Er is nog geen control geactiveerd of getest op productiehardware.

## P1-005 - SMA Home Manager 2.0 rol en controllergrenzen onderzoeken

- Epic: E01
- Fase/volgorde: B
- Prioriteit: P0
- Status: Done
- Doel: Actuele meet-, optimalisatie- en communicatierol bepalen en een conflictvrije grens met Home Assistant formuleren.
- Afhankelijkheden: P1-002, P1-003, P1-004
- Acceptance criteria:
  - Verbonden apparaten en actieve functies zijn als eigenaarbewijs gevraagd.
  - Ondersteuning voor dynamische prijzen en externe EMS-koppeling is met officiële bronnen beoordeeld.
  - Een voorlopig controller-ownershipmodel voorkomt dubbele setpoints.

## P1-006 - EV en laadpaal onderzoeken

- Epic: E01
- Fase/volgorde: B
- Prioriteit: P0
- Status: Done
- Doel: Voertuig- en laadpaalmogelijkheden voor monitoring, start/stop en dynamisch laadvermogen bepalen.
- Afhankelijkheden: P1-002; laadpaalmerk/model, aansluiting en configuratie
- Acceptance criteria:
  - Voertuigfeiten en laadpaalfeiten zijn gescheiden.
  - OCPP, Modbus, lokale API, Home Assistant- en SMA-integratie zijn per bevestigd model onderzocht.
  - Minimumstroom, fasen, limieten en veilige fallback zijn vastgelegd vóór controltickets worden vrijgegeven.

## P1-007 - Home Assistant entity- en datakwaliteitsinventaris

- Epic: E03
- Fase/volgorde: B
- Prioriteit: P0
- Status: Done
- Doel: Relevante entities groeperen en geschiktheid voor statistiek, Energy Dashboard en simulatie beoordelen.
- Afhankelijkheden: P1-002; export van entities, statistieken en relevante configuratie
- Acceptance criteria:
  - Grid, PV, Battery, EV, Charger, House, Tariffs, Forecast, Costs en SMA zijn gedekt.
  - Entity ID, bron, unit, device class, state class, updatefrequentie, beschikbaarheid en long-term-statisticsstatus zijn opgenomen.
  - Bestaande templates worden alleen gelezen en gedocumenteerd.

## P1-008 - Ecopower huidig en dynamisch tarief onderzoeken

- Epic: E02
- Fase/volgorde: B
- Prioriteit: P0
- Status: Done
- Doel: Actuele officiële productvoorwaarden en kostcomponenten documenteren zonder voordeel te veronderstellen.
- Afhankelijkheden: actuele tariefkaarten; huidig contractdocument van eigenaar voor exacte vergelijking
- Acceptance criteria:
  - Energiecomponent, vaste kosten, toeslagen, nettarieven, belastingen en injectie zijn gescheiden.
  - Index, tijdsresolutie, negatieve prijzen, metervereisten en databronnen zijn gedocumenteerd.
  - Iedere actuele claim heeft bron en raadpleegdatum.

## P1-009 - Dynamic Tariff Readiness Matrix en gaps opstellen

- Epic: E02
- Fase/volgorde: C
- Prioriteit: P0
- Status: Done
- Doel: Monitoring, control, automation, readiness en gaps per component beoordelen.
- Afhankelijkheden: P1-003 tot en met P1-008
- Acceptance criteria:
  - Elke cel bevat onderbouwing of expliciet `onbekend`.
  - Verplicht, optioneel en investeringsafhankelijk werk is gescheiden.
  - Iedere actionable gap verwijst naar een ticket.

## P1-010 - Voorlopige architectuur en control ownership

- Epic: E06
- Fase/volgorde: C
- Prioriteit: P1
- Status: Done
- Doel: Verantwoordelijkheden over hardware, SMA, Home Assistant, data, forecasting, optimalisatie en dashboards verdelen.
- Afhankelijkheden: P1-003 tot en met P1-009
- Acceptance criteria:
  - Monitoring-, simulatie- en controlpaden zijn gescheiden.
  - Fail-safe en fallback naar lokale werking zijn beschreven.
  - Toolkeuze blijft voorlopig totdat eisen en interfaces bevestigd zijn.

## P1-011 - Shadow-billing- en scenarioplan

- Epic: E04
- Fase/volgorde: C
- Prioriteit: P0
- Status: Done
- Doel: Meetresolutie, formules, databeheer, validatie en scenario's A-D specificeren.
- Afhankelijkheden: P1-007, P1-008, P1-009
- Acceptance criteria:
  - Werkelijk huidig contract en dynamische simulatie zijn reproduceerbaar gescheiden.
  - Import, export, PV, batterij, huis en EV worden op consistente intervallen verwerkt.
  - Tarief-, optimalisatie- en forecasteffecten kunnen afzonderlijk worden toegeschreven.

## P1-012 - Dashboardvereisten en wireframeplan

- Epic: E05
- Fase/volgorde: C
- Prioriteit: P1
- Status: Done
- Doel: Functionele eisen voor overview, prijstijdlijn, financiën, batterij, EV en Energy Decision Log vastleggen.
- Afhankelijkheden: P1-007, P1-009, P1-011
- Acceptance criteria:
  - Werkelijke waarden en simulaties zijn visueel onderscheiden.
  - Controls zijn conceptueel gemarkeerd en nog niet geïmplementeerd.
  - Wireframes zijn een expliciete gate vóór dashboardimplementatie.

## P1-013 - Fase-1 documentatie valideren

- Epic: E07
- Fase/volgorde: D
- Prioriteit: P0
- Status: Done
- Doel: Interne consistentie, brontraceerbaarheid, ticketkoppelingen en scopebeperkingen controleren.
- Afhankelijkheden: P1-001 tot en met P1-012
- Acceptance criteria:
  - Board-ID's, ticketheadings, links en aantallen zijn programmatisch gevalideerd.
  - Markdowncontroles en `git diff --check` slagen.
  - Onzekerheden en eigenaarvragen zijn niet als bevestigde conclusies geformuleerd.

## P1-014 - Eigenaarvalidatie en fase-2-go/no-go

- Epic: E07
- Fase/volgorde: D
- Prioriteit: P0
- Status: Done
- Doel: Fase-1-bevindingen, informatievragen, risico's en voorgestelde vervolgvolgorde laten bevestigen.
- Afhankelijkheden: P1-013; expliciete eigenaarfeedback
- Acceptance criteria:
  - Eigenaar bevestigt of corrigeert de inventaris.
  - Open P0-informatievragen krijgen een antwoord of geaccepteerde beperking.
  - Fase 2 start alleen na expliciete goedkeuring.

## P2-001 - Veilige Home Assistant data-export verzamelen

- Epic: E03
- Fase/volgorde: E
- Prioriteit: P0
- Status: Done
- Doel: Reproduceerbare vijf-/vijftienminutenreeksen voor Grid, PV, batterij en EV privacy-safe exporteren en met Fluvius reconciliëren.
- Afhankelijkheden: P1-014; goedgekeurde toegangsmethode
- Acceptance criteria:
  - Geen secrets of gevoelige waarden worden gecommit.
  - Export is reproduceerbaar en read-only.
  - UTC, Europe/Brussels, resets, rollovers, ontbrekende intervallen en completeness zijn expliciet verwerkt.
  - Grid-overlap wordt tegen de Fluvius-kwartierexport gevalideerd.
  - Productieconfiguratie blijft ongewijzigd.
- Resultaat 2026-09-30:
  - Read-only vijfminutenexport en kwartieraggregatie geïmplementeerd.
  - Smoke-export van 48 uur leverde 192 kwartieren per stroom zonder ontbrekende buckets, duplicaten of counterdalingen.
  - Eén foutieve HA-`change` voor PV werd zichtbaar gemarkeerd en via cumulative state-delta gecorrigeerd.
  - Volledige vijfminutenexport bevestigt een recente retentiegrens: 662 bruikbare kwartieren per stroom vanaf 2026-09-23T02:30:00Z; oudere buckets blijven expliciet ontbrekend.
  - Hourly long-term statistics leveren 6.020 bruikbare Grid-uren binnen het gevraagde venster.
  - Alle 3.118 uren in de gezamenlijke Fluvius-overlap zijn vergelijkbaar; import wijkt `-0,004 kWh` af en export `0,000 kWh` op de volledige overlap.
  - Twee overlapuren bevatten geschatte Fluvius-kwartieren en zijn ook apart gerapporteerd.

## P2-002 - Shadow-billing minimum viable monitor bouwen

- Epic: E04
- Fase/volgorde: E
- Prioriteit: P0
- Status: Done
- Doel: Huidig contract en dynamische simulatie parallel berekenen zonder fysieke sturing.
- Afhankelijkheden: P1-014, P2-001, P2-004, gevalideerde tariefformules
- Acceptance criteria:
  - Dag-, maand-, kWh-, injectie- en cumulatieve verschillen zijn reproduceerbaar.
  - Ontbrekende prijsdata veroorzaakt een zichtbare foutstatus, geen stille schatting.
  - Resultaten zijn tegen factuur- of portaaldata te valideren.
- Scope 2026-09-30:
  - Scenario A gebruikt ongewijzigde Fluvius-kwartierstromen en de exact
    uitgelijnde ENTSO-E-prijsreeks.
  - De dynamische leverancierscomponenten worden berekend met tariefversie
    `ECOPOWER_DBS_2026-08-01` als expliciete retrospectieve backtest.
  - Netkosten, capaciteitstarief, accijnzen en andere identieke componenten
    worden niet opnieuw uitgevonden; de vergelijking vervangt alleen de
    contractafhankelijke leverancierscomponenten in de gevalideerde factuur.
  - De 99 geschatte Fluvius-kwartieren blijven apart zichtbaar.
- Resultaat 2026-09-30:
  - Alle 35.040 energie-intervallen zijn zonder stille fill aan 35.040
    prijsintervallen gekoppeld.
  - De retrospectieve leverancierscomponent bedraagt `€1.074,57` exclusief
    btw tegenover `€1.305,56` historisch.
  - De volledige tegenberekening bedraagt `€2.607,12` inclusief btw tegenover
    `€2.853,21`, een verschil van `€-246,09`.
  - Dag-, maand- en cumulatieve verschillen, negatieve prijzen en de 99
    geschatte kwartieren zijn reproduceerbaar gerapporteerd.

## P2-003 - Dashboardwireframes ontwerpen

- Epic: E05
- Fase/volgorde: E
- Prioriteit: P1
- Status: Done
- Doel: Een werkend read-only webdashboard bouwen in de door de eigenaar
  gekozen AIHub-geïnspireerde monitorstijl.
- Afhankelijkheden: P1-014, P1-012, P2-001, P2-002, P2-004
- Acceptance criteria:
  - Desktop en mobiel zijn gedekt.
  - Overzicht, prijs, financiën, energie, datakwaliteit en beslissingen zijn
    opgenomen met uitsluitend gevalideerde of expliciet gelabelde data.
  - Het dashboard is via een lokale netwerkbind bereikbaar en kan achter een
    afzonderlijk beheerde Cloudflare Tunnel worden geplaatst.
  - De frontend bevat geen controls die Home Assistant, SMA, Smappee, batterij
    of laadpaal kunnen wijzigen.
  - Desktop- en mobiele browservalidatie zijn reproduceerbaar vastgelegd.
- Owner decision 2026-09-30:
  - apart webdashboard;
  - stijl gebaseerd op de aangeleverde AIHub-screenshot;
  - desktop en mobiel;
  - lokaal IP-adres als eerste exposurelaag;
  - volledig read-only; Cloudflare-activatie blijft een afzonderlijke stap.
- Resultaat 2026-09-30:
  - Werkende statische MVP met zes views, privacy-safe datagenerator en lokale
    read-only server op poort 4173.
  - Desktop en mobiel gevalideerd zonder horizontale overflow of browserfouten.
  - Leesbaarheidscontrols voor 100%, 112% en 125% toegevoegd met lokale
    browserpersistentie.
  - Volledige suite: 31/31 tests geslaagd.
  - Cloudflare-compatibel als lokale origin; geen tunnel of publieke exposure
    geactiveerd.

## P2-004 - Contractpassende EPEX Day-Ahead-kwartierfeed

- Epic: E03
- Fase/volgorde: E
- Prioriteit: P0
- Status: Done
- Doel: Historische en actuele Belgische Day-Ahead-prijzen reproduceerbaar verzamelen met tijd-, bron- en kwaliteitsmetadata.
- Afhankelijkheden: P1-014; goedgekeurde read-only Phase 2-scope
- Acceptance criteria:
  - Marktgebied, bron, ruwe EUR/MWh-prijs, interval, UTC/local time, issue time en bronversie zijn opgeslagen.
  - Minimaal `2025-06-01` tot `2026-05-31` is beschikbaar voor Scenario A.
  - DST, dubbele, ontbrekende, stale en gecorrigeerde waarden worden zichtbaar gerapporteerd.
  - De ingestielaag bewaart ruwe prijzen en past nog geen Ecopower-formule toe.
  - Geen ontbrekende prijs wordt stilzwijgend geforward-filld.
- Voortgang 2026-09-30:
  - ENTSO-E A44/A01 XML-ingestie en PT60M/PT15M-normalisatie geïmplementeerd.
  - Ontbrekende en dubbele kwartieren, bronresolutie en documentmetadata worden bewaard.
  - Live jaarophaal voor het lokale venster `2025-06-01T00:00:00+02:00` tot
    `2026-06-01T00:00:00+02:00` leverde 35.040 complete kwartieren zonder
    ontbrekende of dubbele intervallen.
  - `A03`-variabele prijsblokken en API-respons buiten het aangevraagde venster worden expliciet en getest verwerkt.
  - Twintig verspreide kwartieren van 2025-10-06 zijn exact tegen de officiële EPEX SPOT-tabel gematcht; nul mismatches.
  - ADR-004 bewaart de onbewezen auction issue time expliciet als `null`; documenttijd en retrievaltijd blijven apart.

## P2-005 - Forecastkwaliteit en issue-time-opslag

- Epic: E03
- Fase/volgorde: E
- Prioriteit: P1
- Status: Done
- Doel: Solcast- en latere load-/EV-forecasts geversioneerd opslaan en tegen realisaties beoordelen.
- Afhankelijkheden: P1-014, P2-001; stabiel intervalschema
- Acceptance criteria:
  - Forecast issue time, horizon, target interval, bron en versie blijven bewaard.
  - Forecast versus actual wordt per horizon en dag gerapporteerd.
  - Ontbrekende of achteraf overschreven forecasts worden zichtbaar gemarkeerd.
  - Load- en EV-behoefteforecast zijn aparte uitbreidingen en geen stille afleidingen uit PV.
- Resultaat 2026-10-01:
  - `75` Solcast-versies voor zeven voltooide doeldagen zijn met issue time,
    target interval en revisiehistorie bewaard.
  - Zes Day-Ahead-dagen zijn geëvalueerd; één ontbrekende vorige-dagforecast
    blijft zichtbaar en is niet ingevuld.
  - Day-Ahead MAE is `6,936 kWh` en MAPE `28,69%`; de korte reeks heeft een
    positieve bias van `6,936 kWh`.
  - Ochtendupdates verbeterden de fout in dit korte venster niet.
  - Werkelijke PV-dagenergie is uit opeenvolgende cumulative states afgeleid;
    geresette provider-`change`-waarden zijn niet gebruikt.
  - Load- en EV-forecast blijven expliciet aparte, niet geïmplementeerde stromen.
  - Resultaten staan read-only in de dashboardpagina `Datakwaliteit`.
  - Evidence: `docs/evidence/PV_FORECAST_QUALITY_2026-09-24_TO_2026-09-30.md`.

## P2-006 - Energy Decision Log-datamodel

- Epic: E05
- Fase/volgorde: E
- Prioriteit: P1
- Status: Done
- Doel: Beslissingen in simulatie verklaarbaar registreren zonder productiecontrols te activeren.
- Afhankelijkheden: P1-014, P2-002; stabiele scenario- en resultaatschema's
- Acceptance criteria:
  - Iedere entry bevat tijd, scenario, inputs, constraints, reden, voorgestelde actie, confidence en resultaat.
  - Werkelijke metingen en simulatiebeslissingen zijn expliciet onderscheiden.
  - Het schema ondersteunt audit, herberekening en dashboardweergave.
  - Er worden geen commando's of setpoints naar productieapparaten gestuurd.
- Resultaat 2026-10-01:
  - JSON Schema v1 en een deterministische generator zijn toegevoegd.
  - Zeven privacy-safe entries onderscheiden `MEASUREMENT_CONCLUSION` van
    `SIMULATION_DECISION`.
  - Iedere entry bevat evidence-referenties, read-only constraints, confidence,
    outcome en reproduceerbare scriptargumenten.
  - Productiecommando en setpoint zijn structureel `null`; fysieke writes,
    contractwijziging en productieautomatisatie zijn verboden.
  - De dashboardpagina `Beslissingen` leest rechtstreeks het formele log.
  - Evidence: `docs/evidence/ENERGY_DECISION_LOG_2026-10-01.md`.

## P2-007 - Meerjarige financiële en batterijgevoeligheidsanalyse

- Epic: E04
- Fase/volgorde: E
- Prioriteit: P0 voor contractadvies
- Status: Done for owner-approved indicative decision support
- Doel: De dynamische contractbacktest en offline batterijarbitrage over drie
  volledige Fluvius-jaren vergelijken.
- Afhankelijkheden: P2-002, P2-004; uitgebreide Fluvius-export en exact
  uitgelijnde Belgische Day-Ahead-prijzen zijn beschikbaar; de aangeleverde
  DSMR-schermexport bevat de historische contractprijzen en vaste dagkosten;
  alle negen historische Home Assistant-maandwaarden van 2026 stemmen daarmee
  overeen; batterijparameters en een empirische efficiëntieschatting zijn beschikbaar
- Acceptance criteria:
  - De drie lokale jaarvensters worden afzonderlijk en gecombineerd berekend.
  - De zes onbeschikbare historische kwartieren blijven zichtbaar en worden
    niet als nul of met forward-fill verwerkt.
  - Contracteffect, theoretische batterijbovengrens en realistische
    Day-Ahead-strategie worden afzonderlijk gerapporteerd.
  - Efficiëntieverlies, SOC-limieten, vermogenslimieten en degradatiekost zijn
    expliciete sensitiviteitsparameters.
  - Resultaten worden in het read-only dashboard opgenomen.
  - Er worden geen contract-, Home Assistant-, SMA- of batterijwrites uitgevoerd.
- Batterijresultaat 2026-10-01:
  - 5.814 van 6.024 Home Assistant-uren zijn zonder stille fill gebruikt.
  - Bij `€0,06/kWh` degradatie geeft perfect foresight `+€88,96` met export en
    `+€68,46` met uitsluitend zelfverbruik ten opzichte van werkelijk gedrag.
  - De geteste realistische Day-Ahead-heuristiek geeft `-€107,73`, inclusief
    `+€63,57` benaderd capaciteitspiekeffect.
  - Geen van de extra-capaciteitsvarianten van `5`, `10` of `14,24 kWh`
    ondersteunt een positieve realistische investeringscase.
  - Resultaten en beperkingen zijn privacy-safe in evidence en dashboard opgenomen.
  - De meerjarige vergelijking dekt `105.216` Fluvius-kwartieren en evenveel
    gekoppelde Belgische Day-Ahead-prijzen; `6` kwartieren blijven expliciet
    onbeschikbaar en `304` kwartieren blijven als geschat gemarkeerd.
  - Netafname stijgt van `7.820,473 kWh` in 2023-2024 naar `9.510,180 kWh` in
    2025-2026 (`+21,61%`), terwijl injectie daalt van `1.471,811 kWh` naar
    `989,269 kWh` (`-32,79%`).
  - Sunny Portal en Home Assistant tonen per lokaal jaar een verhouding
    ontladen/laden tussen `84,59%` en `85,07%`.
  - Voor `14,24 kWh` extra virtuele opslag is de perfecte gemiddelde
    jaarbovengrens `€84,21`; prijsbewuste netlading voegt daarin gemiddeld
    slechts `€5,99/jaar` toe boven de PV-only-bovengrens.
  - Een afzonderlijke piekneutrale simulatie voor softwarematig slimmer gebruik
    van `14,24 kWh` opslag geeft gemiddeld `€36,86/jaar` extra door netladen,
    waarvan `€19,69/jaar` in oktober-maart.
  - Absolute gezamenlijke kwartiergrenzen van `7`, `8` en `10 kW` zijn over de
    drie jaren technisch doorgerekend. De beste perfecte modelwaarden zijn
    respectievelijk `€98,12`, `€89,95` en `€74,95` per jaar; die waarde komt
    hoofdzakelijk uit peak shaving en PV-opslag, niet uit extra netladen.
  - EV-, warmtepomp- en gezamenlijke EMS-optimalisatie blijven `DATA_GATED`
    totdat beschikbaarheids-, comfort- en gedesaggregeerde intervaldata
    beschikbaar zijn.
  - Een afzonderlijke read-only dashboardpagina `Scenario's` toont welke opties
    kansrijk zijn, welke eerst getest moeten worden en welke nog data missen.
  - Een maandledger met `36` perioden is opnieuw opgebouwd uit de aangeleverde
    DSMR-schermexport. Afname, injectie en vaste dagkosten zijn volledig gedekt;
    de negen historische HA-maandprijzen van 2026 stemmen exact overeen.
  - De weergegeven DSMR-energiekosten zijn per relevant contractblok binnen
    `€0,10` tegen de geëxporteerde tarieven gereconcilieerd.
  - Voor het gevalideerde factuurjaar ligt het DSMR-totaal `€24,37` lager dan de
    factuur, maar de variabele kost is `€102,56` lager en de vaste kost `€78,19`
    hoger. De bijna gelijke totalen zijn dus het gevolg van compenserende
    componentafwijkingen, niet van component-complete validatie.
  - De sensitivity houdt de DSMR-vaste dagkosten in beide scenario's gelijk en
    voegt het dynamische abonnement van `€5,30/maand` inclusief geconfigureerde
    btw apart toe. Het driejaarsverschil is daardoor `€-806,00`, gemiddeld
    `€-268,67/jaar`.
  - De eigenaar heeft op 2026-10-06 besloten dat exacte historische
    prijsreconstructie niet langer beslissend is voor de huidige shadow-
    vergelijking. Voor indicatieve vergelijking wordt voortaan
    `€0,2770/kWh` inclusief btw als owner-provided gemiddelde referentie gebruikt.
  - Daarmee is P2-007 afgerond voor indicatieve beslissteun. De onvolledige
    componentreconstructie blijft gearchiveerd als
    `MODELLED_WITH_UNVERIFIED_COMPONENTS` en mag niet als factuurvalidatie of
    contractadvies worden gebruikt.
  - De owner-confirmed aprilpiek is verwerkt als `5,031 kW`, maar blijft
    `OWNER_CONFIRMED` zolang direct gearchiveerd Fluvius-bewijs ontbreekt.
  - Onafhankelijke review corrigeerde het Fluvius West-capaciteitstarief voor
    oktober-december 2023 van `€43,5071` naar `€41,0823/kW/jaar` inclusief btw.
    De modelreconstructie bedraagt daardoor `€331,33` voor 2023-2024, tegenover
    `€372,59` DSMR-configuratiekost; het onopgeloste modelresidu is `€41,26`.
  - Voor 2024-2025 blijft de modelreconstructie `€306,57` tegenover `€395,82`,
    met een onopgelost modelresidu van `€89,25`.
  - De reconstructie is gedegradeerd van `VERIFIED` naar
    `MODELLED_WITH_UNVERIFIED_COMPONENTS`: toepasbaarheid van de eMobility-
    leverancierskost, officiële maandpieken, domiciliebewijs voor het
    Energiefonds en factuurtotalen ontbreken nog.
  - Evidence voor de nieuwe referentie en actuele prijsvergelijking:
    `docs/evidence/CURRENT_DAY_AHEAD_PRICE_DASHBOARD_2026-10-06.md`.

## P2-008 - Read-only shadow-controller voor dynamische sturing

- Epic: E06
- Fase/volgorde: E
- Prioriteit: P0
- Status: In Progress
- Doel: Een reproduceerbare shadow-controller ontwerpen die iedere dag een
  prijs-, forecast- en piekbewust plan maakt voor de bestaande batterij, zonder
  commando's naar SMA, Smappee of Home Assistant te sturen.
- Afhankelijkheden: P2-005, P2-007; gevalideerde Day-Ahead-prijzen, actuele
  metingen en expliciete controllergrenzen
- Scope en volgorde:
  1. Maak een kwartierplan voor de volgende dag met batterij-SOC, PV-forecast,
     verwacht huisverbruik en een gezamenlijke netpiekgrens.
  2. Vergelijk minimaal `piekneutraal`, `7 kW`, `8 kW` en `10 kW`.
  3. Houd SMA exclusief eigenaar van PV en batterij en Smappee exclusief eigenaar
     van EV-laden; de shadow-controller publiceert alleen een voorgesteld plan.
  4. Meet plan versus werkelijkheid, forecastfout, gemiste waarde, verliezen,
     degradatie en piekeffect.
  5. Ontwerp pas daarna een gecontroleerd activatie- en rollbackplan voor een
     afzonderlijke eigenaarbeslissing.
- Acceptance criteria:
  - Iedere beslissing is herleidbaar tot prijs, forecast, SOC, load-headroom en
    harde batterijconstraints.
  - Ontbrekende of stale data veroorzaakt `NO_ACTION`, nooit een gegist plan.
  - De gezamenlijke kwartierpiek telt huis, warmtepomp, EV en batterijladen mee.
  - EV en warmtepomp blijven observatie-input totdat hun individuele constraints
    voldoende zijn gevalideerd.
  - Het dashboard toont gepland versus werkelijk gedrag en de reden voor iedere
    voorgestelde actie.
  - Er zijn geen Home Assistant-servicecalls, SMA-/Smappee-writes,
    contractwijzigingen of productieautomatisaties.
- Owner decision 2026-10-01:
  - De meerjarige analyse is voldoende positief om dynamisch als interessante
    richting te behandelen en de sturingsfase verder uit te werken.
  - Deze beslissing autoriseert ontwerp, shadow planning en offline validatie,
    maar nog geen contractwissel of fysieke sturing.
- Implementatiestatus 2026-10-02:
  - De read-only optimizer, veiligheidsinvarianten, `NO_ACTION`-fallback en
    privacyveilige evidence-export zijn geïmplementeerd.
  - Een eerste historische dagrun over `96/96` kwartieren vergelijkt
    piekneutraal, `7 kW`, `8 kW` en `10 kW`; alle vier bleven op deze dag onder
    de bestaande maandpiek en leverden dezelfde planning.
  - De geselecteerde planning gaf `€0,0432` forecastwaarde en `€0,0406`
    backtestwaarde na degradatie, met `1,8927 kWh` netlading en `1,6158 kWh`
    ontlading.
  - Het dashboard toont de resultaten in een afzonderlijke read-only
    `Sturing`-weergave.
  - Het ticket blijft `In Progress` totdat meerdere representatieve dagen met
    gemeten start-SOC en apart gevalideerde forecastinputs zijn beoordeeld.
  - Op 2026-10-05 zijn prospectieve capture- en settlementtooling toegevoegd.
    De dagelijkse capture om `23:45 Europe/Brussels` bevriest measured SOC,
    afzonderlijke load-/PV-forecasts en Day-Ahead-prijzen; de afrekening gebruikt
    uitsluitend later gemeten read-only vijfminutenstatistieken.
  - De acceptatiegrens blijft minimaal `12` geaccepteerde en afgerekende
    prospectieve dagen, twee per vastgelegde primaire stratum. De eerste capture
    voor `2026-10-06` telt niet mee: de inputs waren vóór de doeldag bevroren,
    maar de planner eindigde `1 minuut 42,849512 seconden` na de doeldagstart.
    Planning, settlement en cohortrapport weigeren dit nu expliciet met
    `PLAN_GENERATED_AFTER_TARGET_START`; de teller blijft `0/12`.
  - De machineleesbare cohortaggregatie telt dagen per stratum en aggregeert
    forecastfouten en forecast-/uitvoeringskosten per policy zonder
    kwartierprofielen te publiceren.
  - Op 2026-10-06 is de tijdelijke handmatige capture vervangen door een
    reproduceerbare lokale pipeline. `dynamic-energy-shadow-capture.timer`
    draait om `23:45 Europe/Brussels`, vernieuwt eerst de ENTSO-E-feed en
    bevriest daarna actuele SOC, Solcast-detailforecast, versiegebonden
    loadforecast, maandpiek en prijzen. De bron gebruikt `last_reported` voor
    SOC-freshness en faalt bij ontbrekende of onvolledige doeldagdata naar
    `NO_ACTION`. Live entity-ID's staan uitsluitend in een Git-ignored private
    mapping; de tracked configuratie bevat alleen kwaliteitsdrempels. PV- en
    prijsfeeds ouder dan `18 uur` of met ontbrekende/malformed qualitymetadata
    worden geweigerd. De maandpiek moet uit de huidige lokale kalendermaand komen
    en mag maximaal `744 uur` oud zijn, omdat deze monotone state legitiem alleen
    bij een nieuwe piek wijzigt. Alleen de expliciet informatieve prijsflag
    `collapsed_identical_duplicate` is
    toegestaan; malformed, onbekende en correctieflags falen gesloten.
  - `dynamic-energy-shadow-settlement.timer` draait om `00:45`, exporteert de
    voorbije dag read-only op vijfminutenresolutie, behoudt ontbrekende buckets
    als afwijzende quality flags, rekent alle vier policies af en vernieuwt het
    privacyveilige cohortoverzicht. Primaire strata worden deterministisch
    toegekend met voorrang voor negatieve prijzen, weekend en hoge EV-load.
    Ontbrekende plannen, MCP-fouten of malformed configuratie schrijven een
    expliciete read-only `REJECTED` settlement en `IN_PROGRESS` cohortstatus;
    de service probeert maximaal viermaal opnieuw met `15 minuten` tussenruimte.
    Cohorttoewijzingen worden pas als laatste atomair opgeslagen nadat settlement,
    summary en cohortoutput succesvol zijn geschreven; een outputfout herschrijft
    best-effort expliciete fail-closed artifacts zonder runtime-toewijzing.
  - Beide timers zijn `enabled` en `active`; systemd-unitvalidatie is geslaagd.
    De geplande capture voor doeldag `2026-10-07` faalde gesloten omdat de
    monotone maandpiekstate ouder was dan de toenmalige grens van `6 uur`. De
    validatie vereist nu dezelfde lokale kalendermaand met een maximale leeftijd
    van `744 uur`; de eerstvolgende geplande capture is doeldag `2026-10-08`.
    Het cohort blijft terecht `0/12`.
  - Status op 2026-10-12: doeldagen `2026-10-08` en `2026-10-11` zijn
    geaccepteerd en afgerekend, respectievelijk als `high_load_ev_day` en
    `weekend`; het cohort staat op `2/12`. De capture leest nu optioneel de
    bestaande EPEX Spot Data- en Ecopower Dynamic Prices-entities wanneer geen
    lokaal ENTSO-E-token beschikbaar is. Identieke dubbele integratierijen worden
    met provenanceflag samengevoegd; conflicterende duplicaten falen gesloten.
  - Evidence:
    `docs/evidence/SHADOW_CONTROLLER_VALIDATION_2026-10-02.md` en
    `docs/evidence/PROSPECTIVE_SHADOW_VALIDATION_PIPELINE_2026-10-05.md` en
    `docs/evidence/prospective-shadow-validation-cohort.json`.

## P2-009 - HACS-installable live Lovelace shadow dashboard

- Epic: E05
- Fase/volgorde: E
- Prioriteit: P0
- Status: In Progress
- Doel: De read-only shadow-planning als live Home Assistant Lovelace-kaart
  aanbieden, installeerbaar als HACS-dashboardplugin en configureerbaar via de
  grafische kaarteditor.
- Afhankelijkheden: P2-008; gepubliceerde GitHub-revisie of release voor echte
  HACS-installatie; eigenaarselectie van live Home Assistant-entiteiten
- Scope:
  - Lees live Home Assistant-states uitsluitend via het frontend-`hass`-object.
  - Configureer entiteiten, piekgrens, stale-drempel en planattribuut via GUI.
  - Toon actuele flow, gezamenlijke netruimte, datakwaliteit, geplande actie en
    afwijking tussen plan en werkelijkheid.
  - Accepteer optioneel een read-only planentity met de kwartierplanning in een
    attribuut; de Python-optimizer blijft de planningsbron.
  - Lever een HACS `dashboard`-artifact zonder runtime-afhankelijkheden.
- Acceptance criteria:
  - `hacs.json` verwijst naar één installeerbaar JavaScript-artifact.
  - De kaart registreert zich in de Lovelace-kaartkiezer en biedt een visueel
    configuratieformulier zonder YAML-verplichting.
  - Ontbrekende of stale entities worden zichtbaar, niet als nul behandeld.
  - De kaart roept geen Home Assistant-services aan en toont geen controls.
  - Desktop, mobiel, lege configuratie, stale data en een actief plan zijn in
    een echte browser gevalideerd.
  - Documentatie maakt onderscheid tussen lokaal gebouwd, via GitHub
    publiceerbaar en werkelijk via HACS geïnstalleerd.
- Owner decision 2026-10-02:
  - De eigenaar autoriseert deze read-only Lovelace-/HACS-implementatie en
    GUI-configuratie.
  - SMA en Smappee behouden exclusieve actuatorownership; publicatie,
    installatie en fysieke sturing blijven afzonderlijke gates.
- Implementatiestatus 2026-10-02:
  - Het HACS `dashboard`-artifact, de kaartregistratie en een visuele editor met
    `19` configuratievelden zijn lokaal gebouwd.
  - De kaart leest live Home Assistant-states, normaliseert vermogen en prijs,
    toont stale/missing data en vergelijkt een optionele actuele planregel met
    werkelijk netvermogen.
  - Desktop-, mobiele, stale- en setup-required browserstates zijn zonder
    horizontale overflow gevalideerd.
  - De privacyveilige kaart is gepubliceerd op GitHub; commit `375f583` staat op
    `origin/main` en de officiële HACS-validator is geslaagd.
  - De eigenaar bevestigde op 2026-10-05 dat de kaart via HACS in de echte Home
    Assistant-frontend is geïnstalleerd en gedeeltelijk is geconfigureerd.
  - Read-only live-inspectie valideerde de vereiste grid-, PV-, batterij- en
    SOC-bronnen. De geselecteerde batterijsensor is ontlaadpositief; de kaart
    moet daarom `battery_charge_positive: false` gebruiken.
  - De expliciet gekozen huissensor omvat batterijontlading niet consistent en
    moet leeg blijven zodat de kaart huisvermogen afleidt. De gekozen importprijs
    is een jaargemiddelde en geen actuele Day-Ahead-prijs.
  - Een privacygeminimaliseerde, fail-closed planfeed en een niet-toegepast
    REST-sensorvoorbeeld zijn gebouwd. De endpoint herleest en valideert de bron
    bij elke request, weigert ongeldige structuren, statussen en timestamps en
    toont momenteel terecht `NO_ACTION`/`PLAN_EXPIRED`, omdat nog geen actueel
    dagplan bestaat. De voorbeeldintegratie vereist authenticated HTTPS of een
    expliciet geïsoleerd vertrouwd netwerk.
  - Op 2026-10-05 is de owner-approved observerende MQTT-planentity met private
    alias `shadow_plan` aangemaakt. De initiële status is veilig
    `NO_ACTION`; alle fysieke en integratiewrite-flags zijn `false` en er bestaat
    geen actuator- of commandtopic.
  - De live kaartmapping is via de storage-dashboard-API gecorrigeerd: de onjuiste
    expliciete huissensor en niet-actuele prijsentities zijn verwijderd en de
    planentity is aangesloten. De geschreven dashboardconfiguratie is teruggelezen
    en geverifieerd.
  - Het ticket blijft `In Progress` totdat de kaart live visueel is gevalideerd
    met het eerste actuele prospectieve kwartierplan. De dashboard-screenshotfunctie
    is uitgeschakeld en de beschikbare browser heeft geen opgeslagen HA-login.
  - Het afzonderlijke read-only shadow-webdashboard toont sinds 2026-10-06 de
    komende Belgische Day-Ahead-kwartierprijzen met de Ecopower-formule,
    vergelijking tegen `€0,2770/kWh` en aggregaties per dag, week en maand.
    Een user-systemd-timer vernieuwt de prijsfeed om `00:10`, `13:35`, `14:50`
    en `16:05` Europe/Brussels. De namiddagfallbacks zijn toegevoegd nadat de
    run van `13:35` op 2026-10-06 nog geen volgende dag bevatte maar de read-only
    run van `14:44` wel `96` kwartieren ophaalde. Deze uitbreiding bevat geen
    Home Assistant- of apparaatwrites.
  - De Lovelace-kaart en observerfeed zijn op 2026-10-07 lokaal uitgebreid met
    toekomstige ENTSO-E-kwartierprijzen, Ecopower-afnameprijzen, de indicatieve
    referentie en uitlijning met geplande acties. Prijzen blijven beschikbaar
    wanneer het batterijplan `NO_ACTION` is. De ingebouwde Home Assistant REST-
    integratie kan deze gecombineerde feed read-only ophalen; een afzonderlijke
    Nord Pool-integratie is niet vereist. Live installatie en visuele validatie
    van deze nieuwe kaartversie blijven open.
  - HACS-release `v0.2.1` is op 2026-10-12 gepubliceerd. Zij verwerkt de in de
    live EPEX/Ecopower-entities aangetroffen `192` rijen als `96` identieke
    kwartierparen en behoudt fail-closed afwijzing bij conflicten. Mergecommit
    `1de22ff`, de officiële HACS-validatie, `37/37` JavaScript-tests en de
    onafhankelijke review zijn geslaagd. Installatie van `v0.2.1` en visuele
    validatie in de echte Home Assistant-frontend blijven open.
  - Evidence:
    `docs/evidence/HACS_LOVELACE_SHADOW_DASHBOARD_2026-10-02.md` en
    `docs/evidence/LIVE_HA_SHADOW_CARD_MAPPING_2026-10-05.md` en
    `docs/evidence/CURRENT_DAY_AHEAD_PRICE_DASHBOARD_2026-10-06.md`.

## P3-001 - EV-laadoptimalisatie in simulatie

- Epic: E06
- Fase/volgorde: E
- Prioriteit: P1
- Status: In Progress
- Doel: Goedkoopste laadvensters simuleren met target-SOC, vertrektijd, minimum-SOC en overrides.
- Afhankelijkheden: P2-002; read-only EV- en chargerdata; owner-go voor dry-run
  ontwikkeling op 2026-10-12
- Acceptance criteria:
  - Planning respecteert aansluitings-, laadpaal- en voertuiglimieten.
  - Boost en fallback zijn opgenomen.
  - Geen productiecommando's zonder aparte goedkeuring.
  - De planner deelt één netimportlimiet met huislast en batterijplanning.
  - Ontbrekende vertrektijd, energiebehoefte of chargerbeschikbaarheid geeft
    `NO_ACTION` voor EV-sturing, geen aangenomen laadopdracht.

## P3-002 - Batterijarbitrage in simulatie

- Epic: E06
- Fase/volgorde: E
- Prioriteit: P1
- Status: In Progress
- Doel: Batterijscenario's simuleren met efficiëntie, SOC-limieten, PV-forecast en degradatiekosten.
- Afhankelijkheden: P2-002; P2-008; owner-go voor dry-run ontwikkeling op
  2026-10-12. Een officiële actuatorinterface blijft vereist vóór een live test,
  maar blokkeert actuator-neutrale simulatie niet.
- Acceptance criteria:
  - Resultaten tonen bruto prijsverschil, omzettingsverlies en aangenomen degradatiekost afzonderlijk.
  - Reserve-SOC en lokale fallback zijn harde constraints.
  - Fysieke sturing blijft buiten scope.
  - De batterijplanning deelt één netimportlimiet met huislast en EV-laden.
  - SMA blijft de enige actieve PV- en batterijcontroller.

## P3-003 - Control authority en failure modes valideren

- Epic: E07
- Fase/volgorde: E
- Prioriteit: P0 voor activatie
- Status: Blocked
- Doel: PV-, batterij- en laadpaalgedrag gecontroleerd valideren voordat enige productiecontrol wordt overwogen.
- Afhankelijkheden: P2-002; afzonderlijke expliciete goedkeuring voor fysieke tests; installatiespecifiek testplan
- Acceptance criteria:
  - Per actuator is exact één actieve controller en één gedocumenteerde fallback aanwezig.
  - Curtailment, grid charging, PCC-begrenzing, laadpaal-load-balancing en offline fallback zijn afzonderlijk getest.
  - Setpointlimieten, timeouts, rate limits, handmatige override en herstel zijn vastgelegd.
  - Bruikbare batterijcapaciteit en relevante SOC-/capacity-semantiek zijn gemeten of officieel bevestigd.
  - Geen test start zonder vooraf goedgekeurde stappen, stopcriteria en herstelprocedure.

## P3-004 - Gezamenlijke batterij- en EV-sturingslogica in dry-run

- Epic: E06 / E07
- Fase/volgorde: E
- Prioriteit: P0
- Status: In Progress
- Doel: Eén verklaarbaar kwartierplan omzetten naar afzonderlijke batterij- en
  EV-intents, ze fail-closed laten beoordelen en als niet-uitvoerbare dry-run
  commandovoorstellen vastleggen.
- Afhankelijkheden: P2-008, P3-001, P3-002; owner-go van 2026-10-12 voor logica,
  safety supervisor en dry-run adapters zonder live writes
- Acceptance criteria:
  - Ieder intent bevat targetinterval, bronplan, geldigheidsvenster, limieten,
    reden, ownership en expliciete `execution_allowed: false`.
  - De supervisor weigert stale, incomplete, toekomstige of conflicterende
    input, verlopen plannen, dubbele controllerownership en overschrijding van
    SOC-, laad-, vermogens- of gedeelde netlimieten.
  - SMA- en Smappee-adapters bevatten geen netwerkclient, Home Assistant-call,
    MQTT-publicatie, servicecall of apparaatcommando.
  - Handmatige override, timeout en lokale fallback worden als geobserveerde
    safety state gemodelleerd; de dry-run kan ze nooit wijzigen.
  - Replay- en fault-injectiontests dekken normale prijssturing, ontbrekende EV,
    stale data, DST, negatieve prijzen, charger unavailable en controllerconflict.
  - Geen fysieke actuatorproef zonder afzonderlijk goedgekeurd P3-003-testplan.
- Implementatiestatus 2026-10-13:
  - Intentcontract, safety supervisor en technisch niet-uitvoerbare adapters zijn
    geïmplementeerd en onafhankelijk zonder high/medium findings beoordeeld.
  - De prospectieve capture schrijft joint intents, review, proposals, een
    privacyveilige summary en als laatste een lokaal HMAC-geauthenticeerd manifest;
    ontbrekende private snapshots of integriteitssleutel falen gesloten.
  - De settlement scoort alleen volledige read-only proposals tegen gemeten
    batterij-/EV-energie over exact 92, 96 of 100 kwartieren en publiceert
    uitsluitend geaggregeerde joint-evidence.
  - De afsluitreview na adversarial probes gaf `PASS`: proposalmanipulatie,
    gemengde artifactgeneraties, ontbrekende/ongeldige sleutel, afgeknotte of
    ongeordende doeldagen en verkorte planvaliditeit worden fail-closed geweigerd.
  - Volledige regressie: `220/220` Python-tests en `58/58` JavaScript-tests
    geslaagd; compile-, syntax-, systemd-, Markdown- en diffchecks zijn groen.
  - Een read-only snapshotrefresher verwijdert vóór iedere capture oude joint
    snapshots en schrijft pas een nieuw paar wanneer alle afzonderlijke Home
    Assistant-observaties vers, beschikbaar en niet future-dated zijn. De
    geïnstalleerde user-service voert deze refresher nu fail-closed uit.
  - De lokale artifact-HMAC-sleutel is met modus `0600` aangemaakt en wordt door
    Git genegeerd; een handmatige rejected capture produceerde een manifest met
    vier artifactdigests en een aanwezige HMAC zonder fysieke writes.
  - Live joint acceptance blijft data-gated: doel-SOC, vertrektijd en expliciete
    read-only safety-signalen voor override, fallback en acknowledgement timeout
    zijn nog niet als complete private bronmapping beschikbaar. Er worden geen
    veilige `false`-waarden aangenomen.
  - De eerste onafhankelijke refresherreview vond vier medium issues. Die zijn
    hersteld met geobserveerde device-availability, generatiebinding van het
    snapshotpaar, verwijdering van beide outputs bij een gedeeltelijke write,
    begrensde soft-fail-afhandeling en correcte MCP `structured_content`-parsing.
  - Een volgende adversarial review vond nog rollback-cleanup, cross-field-
    validatie, dubbele bronmapping en een voorspelbaar tijdelijk pad. Rollback-
    cleanup is nu altijd hard-fail, tijdelijke bestanden worden veilig uniek
    aangemaakt en dubbele entitymapping, omgekeerde SOC-grenzen, verstreken
    vertrektijden en EV-doel-SOC onder actuele SOC worden geweigerd.
  - De gemelde root-servicebevinding was niet van toepassing op de geïnstalleerde
    user-service: de actieve user-manager draait onder de projectgebruiker, niet
    als root. De tijdelijke-bestandsroute is desondanks gehard tegen symlinks.
  - Volledige regressie na deze fixes: `237/237` Python-tests en `58/58`
    JavaScript-tests geslaagd; compile-, syntax-, systemd-, Markdown- en
    diffchecks zijn groen.
  - De finale smalle herbeoordeling gaf `PASS` zonder resterende high/medium
    findings. De gecombineerde replace-, rollback-unlink- en temp-unlinkprobe
    bleef ook met `--soft-fail` hard op exitcode `2`; een gewone transportfout
    vóór persistence blijft bewust een privacyveilige soft-fail met exitcode `0`.
  - Ticket blijft `In Progress` totdat verse prospectieve control- en
    safetysnapshots een representatieve joint dry-runreeks hebben opgeleverd.
