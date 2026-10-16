# Conclusie dynamische tarieven, native sturing en dashboard

Status: beslisdocument voor review  
Datum: 2026-10-16  
Scope: SMA-batterij, Smappee EV-lader en het actuator-read-only dashboard

## Managementsamenvatting

De installatie kan na een correcte overschakeling naar een dynamisch
energiecontract een groot deel van de optimalisatie automatisch uitvoeren, maar
niet als één gezamenlijk gestuurd systeem:

- **SMA** blijft eigenaar van PV en batterij en kan dynamische afnameprijzen
  gebruiken voor forecast-based battery charging en netladen.
- **Smappee** blijft eigenaar van EV-laden, cloudafhankelijke
  overbelastingsregeling en de gekozen Smart/Solar-laadlogica.
- **Home Assistant en het dashboard** blijven observeren, vergelijken en
  afwijkingen tonen. De configuratiekaart mag na bevestiging uitsluitend eigen,
  hard-geblokkeerde Home Assistant-automatisaties beheren.

De conclusie "alles loopt daarna automatisch optimaal" is te sterk. SMA en
Smappee zijn afzonderlijke controllers. Ze kunnen tegelijk dezelfde goedkope
kwartieren kiezen en wisselen hun volledige planning niet noodzakelijk uit. De
configuratie kan dus veel automatiseren, maar het gezamenlijke financiële en
elektrische resultaat moet eerst worden gemeten en gevalideerd.

Het dashboard is al geschikt om het gedrag zichtbaar te maken. Het kan nog niet
volledig bewijzen waarom een vendorcontroller een actie koos en het kan bewust
geen SMA-, Smappee-, batterij- of laadpaalinstellingen live wijzigen.

## 1. Verwacht gedrag van SMA

Met Sunny Home Manager 2.0 als actieve batterijcontroller zijn de relevante
native bouwstenen:

- het door de actuele SMA-documentatie vereiste optimalisatiedoel;
- dynamisch Day-Ahead-tarief voor regio `BE`;
- zichtbare kwartierprijzen;
- forecast-based battery charging;
- dynamisch netladen met de vereiste batterij-instellingen;
- SMA als enige actieve schrijver voor batterij- en PV-setpoints.

SMA documenteert ondersteuning voor dynamische tarieven, forecast-based battery
charging en netladen van de batterij. Sunny Home Manager 2.0 ondersteunt volgens
de functiematrix echter geen geoptimaliseerde teruglevering van batterij-energie
voor prijsarbitrage. De batterij kan dus dure lokale afname vermijden, maar het
systeem mag niet worden geïnterpreteerd als automatische handel waarbij de
batterij op hoge prijzen aan het net verkoopt.

### Huidige beoordeling

- Het dashboardprofiel registreert het in de Nederlandse interface waargenomen
  label `Economisch`, Day-Ahead, `BE` en EPEX Spot.
- De actuele Engelstalige SMA-instructie noemt voor deze workflow `Efficient`.
  De exacte firmware- en taalafhankelijke equivalentie moet vóór activering in
  de eigen SMA-interface worden bevestigd.
- Forecast-based charging staat in het profiel nog op `OFF`.
- De vaste injectieproxy van `€0,02/kWh` is geen contractnauwkeurige dynamische
  injectieprijs.
- Activering moet daarom als een gecontroleerde pilot gebeuren, niet als een
  onbewezen productieoptimalisatie.

## 2. Verwacht gedrag van Smappee

Smappee kan EV-laden op goedkopere momenten plannen wanneer minstens het
volgende correct is ingesteld:

- dynamische tarieven met de juiste markt en regio;
- relevante prijscomponenten of een bewust gekozen prijsproxy;
- Smart charging;
- een bruikbaar laadvenster, vertrektijd of planning;
- correcte installatie- en stroomlimieten;
- de verplichte `Maximum current`-overbelastingsinstelling;
- de afzonderlijke, optionele `Maximum grid capacity` voor totaal huisverbruik;
- precies één actieve EV-scheduler.

Smart mode alleen bewijst niet dat dynamische tarieven actief zijn. Daarom blijft
`smappee_dynamic_tariff_status` in het dashboard `NOT_VERIFIED` totdat een
betrouwbare uitleesbare status of handmatig vendorbewijs beschikbaar is.

Kia-planning, Kia Smart Charge, Smappee-planning en een toekomstig extern schema
mogen niet gelijktijdig dezelfde laadsessie besturen. Voor de huidige
architectuur is Smappee de aangewezen primaire EV-scheduler.

De overbelastingsregeling van Smappee EV Line is cloudafhankelijk. Ze mag niet
worden beschreven als een volledig autonome lokale beveiligingslaag. Bij verlies
van internet gelden de apart geconfigureerde offline- en maximumstroomregels.

### Aandachtspunt offline laden

Offline laden moet afzonderlijk worden beoordeeld. Tijdens offline werking is de
cloudgebaseerde overbelastingsregeling niet actief. Een vaste fallbackstroom mag
daarom pas als veilig worden beschouwd nadat aansluiting, beveiliging en
werkelijk gedrag zijn gevalideerd.

## 3. Geen gezamenlijke optimalisatiegarantie

De native route bestaat uit twee autonome regelkringen:

| Actuator | Primaire controller | Optimaliseert vooral op |
| --- | --- | --- |
| PV en batterij | SMA Home Manager | PV, verbruik, SOC en prijs |
| EV-lader | Smappee | laadplanning, tariefcontext en gemeten netbelasting |
| Dashboard | geen actuatorcontrol | observatie en waarschuwingen |

Mogelijke conflictsituatie:

1. een goedkoop kwartier begint;
2. SMA start netladen van de batterij;
3. Smappee start tegelijk EV-laden;
4. huisverbruik en warmtepomp blijven actief;
5. de gecombineerde netimport wordt hoger dan afzonderlijk gepland.

Smappee kan via zijn cloudregeling het EV-vermogen begrenzen, maar dit bewijst
niet dat het gehele systeem financieel optimaal plant. Daarom moet werkelijk
gedrag worden vergeleken met prijs, shadow-plan en gedeelde netlimiet.

## 4. Wat het dashboard nu al kan

Release `v0.3.0-alpha.4` kan zonder fysieke actuatorwrites tonen:

- actuele afname- en injectieprijs;
- huidige, volgende goedkoopste en duurste prijsvensters;
- navigeerbare kwartierprijzen en dagelijkse grafieken;
- net-, PV-, batterij-, huis-, warmtepomp- en EV-vermogens;
- batterij-SOC;
- shadow-plan, voorgestelde actie en gepland netvermogen;
- gepland versus werkelijk gedrag;
- ontbrekende, ongeldige en verouderde data;
- `PRICE_READY_PLAN_BLOCKED` wanneer prijsdata bruikbaar is maar het plan niet;
- verschillen tussen de dashboard-netlimiet en de geconfigureerde
  Smappee-capaciteitsdrempel;
- controllerownership en de actieve safety boundary;
- Smappee dynamische tarieven als expliciet `NOT_VERIFIED`.

Daarmee kan visueel worden beoordeeld of:

- de batterij tijdens goedkope kwartieren laadt;
- de batterij tijdens dure lokale afname ontlaadt;
- de EV hoofdzakelijk binnen goedkope laadvensters laadt;
- batterij en EV gelijktijdig een ongewenste piek veroorzaken;
- werkelijk gedrag overeenkomt met het shadow-advies.

## 5. Wat het dashboard nog niet kan

Het dashboard heeft momenteel geen betrouwbare automatische readback voor:

- de werkelijk actieve SMA forecast-chargingstatus;
- de interne reden waarom SMA een batterijactie koos;
- de werkelijk actieve Smappee dynamische-tarievenoptie;
- het leidende Smappee-laadschema of de actuele vertrektijd;
- de oorzaak van een EV-laadactie: prijs, Solar mode, planning of handmatige
  override;
- concurrerende Kia- en Smappee-planningen;
- een gezamenlijke optimaliteitsgarantie voor batterij en EV.

Het dashboard voert bovendien bewust geen live bijsturing uit:

- geen SMA-setpoints;
- geen batterij- of PV-commando's;
- geen Smappee start/stop-, modus- of stroomcommando's;
- geen EV-setpoints;
- geen MQTT- of Modbuswrites;
- geen `LIVE`-modus;
- `execution_allowed` blijft `false`.

De bestaande configuratiekaart kan uitsluitend hard-geblokkeerde Home
Assistant-automatisaties binnen de eigen namespace beheren. Iedere gegenereerde
automatisering stopt vóór een actuatoractie.

## 6. Aanbevolen volgorde van verdere acties

### Stap 1 - Contract en prijsdata verifiëren

- Bevestig het gekozen dynamische afname- en injectiecontract.
- Controleer toeslagen, vaste componenten en btw-behandeling.
- Vergelijk Ecopower-kwartierprijzen met de waarden die SMA en Smappee tonen.
- Gebruik Smappee-prijzen niet als contractnauwkeurige bron zolang toeslagen en
  heffingen niet zijn gereconcilieerd.

### Stap 2 - Protection baseline en ownership verifiëren

Voer vóór activering van een optimizer de elektrische en organisatorische
controles uit:

- leg de huidige SMA- en Smappee-configuratie vast;
- bevestig Smappee-nettopologie en `Maximum current`;
- beoordeel de optionele `Maximum grid capacity` als afzonderlijke huislimiet;
- controleer internetafhankelijkheid, offline laden en fallbackstroom;
- kies één primaire EV-scheduler en schakel concurrerende schema's uit;
- houd externe Home Assistant/Modbus-setpoints en peak shaving uit.

### Stap 3 - SMA als afzonderlijke pilot activeren

- Controleer Day-Ahead, `BE`, EPEX Spot en actuele kwartierprijzen.
- Bevestig in de eigen firmware/interface welk optimalisatiedoel overeenkomt met
  het officieel vereiste `Efficient`; neem `Economisch` niet zonder bewijs als
  synoniem aan.
- Bevestig de vereiste laad-SOC- en batterijconfiguratie.
- Activeer forecast-based battery charging als één afzonderlijke wijziging.
- Houd de EV-planning tijdens de eerste beoordeling stabiel.
- Observeer eerst het SMA-gedrag voordat een tweede optimizer wordt gewijzigd.

### Stap 4 - Smappee als afzonderlijke pilot configureren

- Bevestig de dynamische-tarievenoptie en getoonde prijsbron in de Smappee-app.
- Controleer Smart mode, laadvenster, vertrektijd en gevraagde energie.
- Wijzig één tarief- of planningsinstelling per keer.
- Controleer daarna EV-vermogen, totale netimport en cloudconnectiviteit.

### Stap 5 - Observeren zonder externe sturing

Gebruik minimaal twee tot vier weken als tijdsminimum, maar sluit de pilot pas af
nadat voldoende geldige scenario's zijn verzameld:

- werkdagen en weekenddagen;
- zonnige en donkere dagen;
- lage, normale en hoge prijzen;
- negatieve prijzen wanneer die werkelijk voorkomen;
- dagen met en zonder EV;
- verschillende batterij-SOC's;
- periodes met warmtepomp- en ander hoog huisverbruik;
- gelijktijdige en niet-gelijktijdige batterij- en EV-vraag;
- volledige, verse prijs- en vermogensdata zonder relevante meetgaten.

### Stap 6 - Dashboard uitbreiden met automatische validatie

Voeg per kwartier een auditbare vergelijking toe van:

- prijs;
- shadow-advies;
- batterijvermogen en SOC;
- EV-vermogen;
- netimport en -export;
- PV- en huisvermogen;
- verwachte versus werkelijke actie.

Voeg waarschuwingen toe voor:

- batterij laden tijdens een duur kwartier;
- gemiste goedkope laadvensters;
- EV-laden buiten het verwachte venster;
- gelijktijdig batterij- en EV-laden boven de gedeelde grens;
- stale vendor- of prijsdata;
- langdurige afwijking van het shadow-plan.

Voeg een dagelijkse evaluatie toe met:

- geladen batterij-kWh per prijszone;
- EV-kWh per prijszone;
- gemiddelde aankoopprijs per asset;
- vermeden dure afname;
- extra kwartierpiek;
- werkelijke kosten versus shadow-kosten;
- gemiste of onverwachte acties.

### Stap 7 - Beslissen over eventuele live bijsturing

Live bijsturing is een afzonderlijke fase en vereist vooraf:

1. één expliciete controller per actuator;
2. officiële en firmwarepassende controlinterfaces;
3. teruglezing van ieder commando en werkelijk vermogen;
4. stale-data- en communicatiefallbacks;
5. handmatige override en een duidelijke uitweg naar lokale regeling;
6. rate limits en gedeelde vermogenslimieten;
7. gecontroleerde failure-mode-tests;
8. nieuwe, expliciete eigenaarstoestemming.

Zonder deze gates blijft de native route leidend. Home Assistant blijft zonder
fysieke actuatorwrites; alleen de bestaande, bevestigde configuratiehandelingen
voor eigen hard-geblokkeerde automatisaties blijven beschikbaar.

## 7. Beslispunten voor de eigenaar

Voor de volgende fase zijn deze keuzes nodig:

- Welk dynamisch contract en welke startdatum worden overwogen?
- Mag SMA forecast-based battery charging als beperkte pilot worden geactiveerd?
- Welke EV-scheduler blijft actief: Kia of Smappee?
- Welke standaard EV-doel-SOC en vertrektijden gelden?
- Moet Smappee offline laden uitgeschakeld blijven?
- Hoe lang moet de observatieperiode duren voordat de resultaten worden
  geëvalueerd?
- Is de volgende ontwikkelprioriteit automatische gedragsvalidatie of eerst
  aanvullende vendor-readback?

## 8. Go/no-go-conclusie

### Go voor

- dynamisch contractonderzoek en tariefvergelijking;
- gecontroleerde native SMA-configuratie;
- gecontroleerde native Smappee-configuratie;
- monitoring zonder fysieke actuatorwrites;
- automatische gedrags- en kostenvalidatie;
- alerts en rapportering zonder actuatorwrites.

### Nog geen go voor

- gelijktijdige Home Assistant- en vendorsturing;
- directe SMA-, batterij- of Smappee-setpoints;
- automatische live correcties vanuit het dashboard;
- prijsarbitrage via batterij-export;
- de claim dat de huidige installatie al bewezen optimaal werkt.

## Bronnen

1. [SMA Sunny Home Manager 2.0](https://www.sma.de/en/products/energy-management/sunny-home-manager)
2. [SMA forecast-based battery charging](https://manuals.sma.de/HM-20-ennexOS/en-US/12563269899.html)
3. [SMA electricity tariff configuration](https://manuals.sma.de/HM-20-ennexOS/en-US/16129800843.html)
4. [SMA functiematrix](https://manuals.sma.de/SMA-Premium/nl-NL/16915921419.html)
5. [Smappee charging modes and schedules](https://support.smappee.com/hc/en-gb/articles/4900468508692)
6. [Smappee Smart Charging](https://support.smappee.com/hc/en-gb/articles/4406735969940)
7. [Smappee EV Wall Home](https://support.smappee.com/hc/en-gb/articles/4402413229844-EV-Wall-Home)
8. [Smappee offline charging behavior](https://support.smappee.com/hc/en-gb/articles/54047739821460-Does-my-charger-keep-charging-when-it-is-offline)
