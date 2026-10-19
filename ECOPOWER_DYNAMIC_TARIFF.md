# Ecopower Dynamic Tariff

Status: actuele contractanalyse; meetregimes owner-confirmed  
Gerelateerd ticket: P1-008  
Laatst bijgewerkt: 2026-09-30

## Samenvatting

Ecopower biedt voor Vlaamse huishoudelijke klanten een standaardproduct, Groene Burgerstroom, en Dynamische Burgerstroom. Groene Burgerstroom combineert een vaste en maandelijks variabele energiecomponent; Dynamische Burgerstroom rekent werkelijke afname en injectie af per kwartier.[1][2]

Ecopower waarschuwt dat dynamisch vooral interessant kan zijn wanneer grote verbruikers automatisch verschoven kunnen worden. Alleen handmatig sturen leverde in het beschreven proefproject geen duidelijk voordeel op, en zonnepanelen kunnen de businesscase verminderen.[1]

Conclusie voor dit project: geen contractwissel vóór shadow billing op werkelijke data.

## Groene Burgerstroom - huidige baseline

De eigenaar bevestigt Groene Burgerstroom als huidig product. De officiële tariefkaart van augustus 2026 is lokaal aangeleverd en publiek geverifieerd.[38]

### Afname-energiecomponent augustus 2026

De maandformule is:

`0,5 × €0,17/kWh + 0,5 × BELPEX_RLP`

Voor augustus vermeldt de kaart `BELPEX_RLP = €0,13511/kWh`, zodat de afname-energiecomponent uitkomt op `€0,1526/kWh` exclusief btw.[38]

Daarboven staan als afzonderlijke leverancierscomponenten:

- GSC: `€0,011/kWh` exclusief btw;
- WKK: `€0,00392/kWh` exclusief btw.

`BELPEX_RLP` is een maandelijks, met het theoretische Belgische afnameprofiel gewogen gemiddelde van de Belgische day-ahead-prijzen. Dit is dus een maandprijs: het werkelijke kwartier waarin een kWh werd afgenomen bepaalt binnen Groene Burgerstroom niet rechtstreeks de energieprijs.[1][38]

### Injectie augustus 2026

Sinds 1 juli 2026 publiceert Ecopower voor Groene Burgerstroom:

`0,5 × €0,02/kWh + 0,5 × (0,9 × BELPEX_SPP - €0,01/kWh)`

Voor augustus vermeldt de kaart `BELPEX_SPP = €0,07910839/kWh`. De variabele helft gebruikt daardoor `€0,06119755/kWh` en de totale terugleververgoeding komt uit op `€0,0406/kWh` exclusief btw. Voor particuliere klanten is deze vergoeding vrijgesteld van btw.[38]

De uitkomst heeft een bodem op nul en kan voor dit standaardproduct dus niet negatief worden.[1]

De in Sunny Portal ingevoerde `€0,02/kWh` is daarmee niet de volledige augustusvergoeding. Het getal is gelijk aan de vaste component binnen de Groene Burgerstroom-formule en kan tegelijk als conservatieve SMA-proxy worden gebruikt; contractnauwkeurige shadow billing moet de volledige maandformule toepassen.

## Historische factuurbaseline 2025-06 tot 2026-05

Een owner-provided Fluvius-kwartierexport en bijbehorende Ecopower-afrekeningsfactuur zijn privacy-safe gereconcilieerd. De factuur bevestigt Groene Burgerstroom met jaarlijkse meterlezing over `2025-06-01` tot en met `2026-05-31`.

VERIFIED:

- 35.040 volledige kwartierintervallen met afname en injectie;
- 99 geschatte intervallen (`0,282534%`), expliciet gemarkeerd;
- afname: CSV `9.161,589 kWh`, factuur `9.161,59 kWh`;
- injectie: CSV `1.160,728 kWh`, factuur `1.160,74 kWh`;
- factuurtotaal: `€2.690,39` exclusief btw en `€2.853,21` inclusief btw;
- historische injectievergoeding: `€0,0200/kWh`;
- facturatiepiek: `5,26 kW`, detailwaarde `5,264 kW`.

De historische `€0,0200/kWh` is niet in tegenspraak met de augustus-2026-vergoeding van `€0,0406/kWh`: het zijn verschillende tariefperioden. Tariefwaarden worden daarom altijd met hun geldigheidsperiode opgeslagen.

De factuur gebruikt twaalf maandelijkse Groene Burgerstroom-volumes en -prijzen; de historische kwartierpositie bepaalt de standaardproductprijs niet rechtstreeks. De kwartierdata is wel geschikt om hetzelfde gedrag onder Dynamische Burgerstroom te simuleren.

De factuur vermeldt `Meterlezing: Jaarlijks`. Ecopower heeft volgens de eigenaar op 2026-09-30 rechtstreeks bevestigd dat het huidige meetregime `SMR1` is en bij een eventuele overschakeling naar Dynamische Burgerstroom `SMR3` wordt. Deze regimecodes zijn daarom `OWNER CONFIRMED`; de factuur zelf blijft direct bewijs voor de historische jaarlijkse meterlezing.

Volledige privacy-safe analyse: `docs/evidence/ECOPOWER_RECONCILIATION_2025-06_TO_2026-05.md`.

## Gevalideerde tariefkaart vanaf 1 augustus 2026

De door de eigenaar aangeleverde officiële tariefkaart `20260801_dbs_tariefkaart.pdf` bevestigt voor Dynamische Burgerstroom:[28]

- doelgroep: digitale laagspanningsmeters in meetregime 3;
- afname per kwartier: `0,00102 × EPEX_DA_EUR_per_MWh + €0,004/kWh`;
- injectie per kwartier: `0,00098 × EPEX_DA_EUR_per_MWh - €0,015/kWh`;
- abonnement: `€5,00/maand` exclusief btw;
- kost GSC: `€0,011/kWh` exclusief btw;
- kost WKK: `€0,00392/kWh` exclusief btw;
- particuliere afnamecomponenten: 6% btw;
- particuliere terugleververgoeding: vrijgesteld van btw;
- nettarieven, capaciteitstarief, afnametarief en heffingen worden afzonderlijk doorgerekend;
- injectienettarief geldt volgens de kaart alleen bij omvormervermogen boven 10 kVA.

De twee PV-omvormers hebben samen 8 kW nominaal AC. Het niet-toepasselijk zijn van het injectienettarief is daarom `INFERRED` maar moet tegen de officiële Fluvius-classificatie worden bevestigd.

Deze tariefkaart wordt de contractversie `ECOPOWER_DBS_2026-08-01` voor shadow billing. De Sunny Portal-terugleververgoeding van vast `€0,02/kWh` is noch de volledige Groene Burgerstroom-vergoeding van augustus (`€0,0406/kWh`) noch de Dynamische Burgerstroom-formule; zij wordt uitsluitend als aparte SMA-optimalisatieproxy behandeld.

## Dynamische Burgerstroom

### Afname

Voor een gewone digitale laagspanningsmeter in meetregime 3 publiceert Ecopower vanaf 1 augustus 2026:

`1,02 × EPEX DA + €4/MWh`

Equivalent bij opslag in euro per kWh:

`0,00102 × EPEX_DA_EUR_per_MWh + €0,004/kWh`

De formule wordt toegepast op de werkelijke afname van ieder kwartier.[2][3]

### Injectie

De gepubliceerde injectieformule is:

`0,98 × EPEX DA - €15/MWh`

Equivalent:

`0,00098 × EPEX_DA_EUR_per_MWh - €0,015/kWh`

Deze vergoeding kan negatief zijn. Bij een voldoende lage positieve of negatieve beursprijs betaalt de klant voor injectie in dat kwartier.[2]

### Vaste en andere leverancierscomponenten

Ecopower vermeldt voor Dynamische Burgerstroom onder meer:

- €5 per maand abonnement, exclusief btw en pro rata;
- groenestroomcertificaten;
- warmtekrachtcertificaten;
- een aanvullende bijdrage bij energiedelen waar van toepassing.[2]

De exacte waarden en geldigheidsperiode moeten uit de tariefkaart worden geversioneerd in de simulatie.

## Nettarieven, heffingen en belastingen

Deze staan los van de EPEX-kwartierprijs en moeten afzonderlijk worden gemodelleerd. Minimaal zijn nodig:

- Fluvius-netgebied;
- afnametarief per kWh;
- capaciteitstarief en maandpiek;
- databeheerkost;
- accijnzen en Energiefonds;
- btw-regime;
- eventueel injectietarief voor de toepasselijke installatiecategorie.

Een generiek Vlaams all-in bedrag is onvoldoende voor factuurreconciliatie.

## Meter- en contractvereisten

Dynamische Burgerstroom vereist:

- digitale elektriciteitsmeter;
- geactiveerde kwartierwaarden;
- meetregime 3;
- toestemming voor doorgifte van kwartierdata aan Ecopower;
- maandelijkse digitale afrekening.[3]

Fluvius maakt onderscheid tussen informatieve kwartierwaarden en gevalideerde facturatiedata. Ontbrekende waarden kunnen worden geschat en later gecorrigeerd.[4]

## Data-ingestie

Ecopower biedt volgens de geraadpleegde productinformatie geen eigen publieke day-ahead-API. Voor automatische analyse is daarom een contractueel passende marktbron nodig, terwijl gevalideerde meterdata via Fluvius/leverancier nodig blijft voor factuurcontrole.

De Home Assistant-prijslaag moet per interval minstens bevatten:

- start en einde;
- EPEX DA in EUR/MWh;
- afname-energiecomponent in EUR/kWh;
- injectie-energiecomponent in EUR/kWh;
- formuleversie;
- bron en ophaaltijd;
- stale/complete-status;
- nettarieven en belastingen als aparte componenten.

## Smappee-tarieven zijn geen factuurbron

De Smappee-app toont ondersteuning voor dynamische tarieven, maar de aangeleverde screenshot bewijst niet dat deze functie actief of met Ecopower-waarden geconfigureerd is. De app vermeldt bovendien expliciet dat heffingen en andere kosten niet worden meegerekend.

Gevolg: Smappee-kostwaarden mogen als indicatieve visualisatie dienen, maar niet als bron voor contractreconciliatie of Ecopower-shadow billing. De reproduceerbare simulatie blijft de volledige contractformule, nettarieven, capaciteitstarief, heffingen en btw afzonderlijk modelleren.

## Shadow-billingvergelijking

### Baseline

Groene Burgerstroom wordt per maand berekend met de gerealiseerde `BELPEX_RLP`/`BELPEX_SPP` en de contractuele vaste helft.

### Dynamisch zonder optimalisatie

Dezelfde werkelijke kwartierimport en -export wordt afgerekend met de dynamische formules. Dit is Scenario A en isoleert het contracteffect.

### Optimalisatiescenario's

Scenario's B-D verschuiven alleen technisch flexibele energie. Resultaten tonen afzonderlijk:

- verschil door contract;
- verschil door EV-verschuiving;
- verschil door batterij;
- verschil door forecastgestuurde combinatie;
- extra vaste kosten;
- impact van negatieve injectieprijzen;
- capaciteitstariefeffect;
- conversieverliezen en batterijthroughput.

## Open eigenaarinformatie

1. Formele bevestiging van SMR1 versus SMR3 en of Fluvius-kwartierwaarden aan Ecopower worden doorgegeven.
2. Bevestiging dat geen individuele afwijkende voorwaarden of energiedelen van toepassing zijn.
3. Bevestiging door Fluvius of het injectienettarief niet van toepassing is bij de 8 kW AC-omvormerconfiguratie.

## Voorlopig oordeel

Ecopower Dynamische Burgerstroom is technisch simuleerbaar zodra kwartierdata en de toepasselijke contractcomponenten beschikbaar zijn. Financiële geschiktheid is nog onbewezen. De combinatie van circa 8,5 kWp PV, thuisbatterij en EV biedt flexibiliteit, maar kan ook extra risico creëren door injectie op lage prijzen, conversieverliezen, capaciteitspieken en onvoldoende bruikbare controlinterfaces.

## Sources

[1] https://ecopower.be/groene-stroom/prijs-nieuw
[2] https://ecopower.be/groene-stroom/dynamische-burgerstroom
[3] https://ecopower.be/groene-stroom/bijzondere-voorwaarden-dynamische-burgerstroom
[4] https://www.fluvius.be/nl/factuur-en-tarieven/kwartierwaarden
[28] https://cdn.nimbu.io/s/4tn7vz5/channelentries/ma28q8f/files/1790570062186/20260801_dbs_tariefkaart.pdf?7l4n7vq=
[38] https://cdn.nimbu.io/s/4tn7vz5/channelentries/spiilz4/files/1788271546519/202608_gbs_tariefkaart.pdf?w01uqtn=&dl=1 — Ecopower Groene Burgerstroom - tariefkaart augustus 2026
