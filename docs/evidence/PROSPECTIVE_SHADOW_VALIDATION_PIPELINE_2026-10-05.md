# Prospectieve shadow-controller-validatie — pipeline 2026-10-05

## Status

Status: `IN_PROGRESS_AWAITING_PROSPECTIVE_DAYS`

Geaccepteerde en afgerekende prospectieve dagen: `2/12` op 2026-10-12.

De eerste capture voor `2026-10-06` bevatte volledige en tijdig bevroren inputs,
maar de optimalisatie eindigde om `2026-10-05T22:01:42.849512+00:00`, na de
doeldagstart om `2026-10-05T22:00:00+00:00`. Deze dag is daarom fail-closed
afgewezen met `PLAN_GENERATED_AFTER_TARGET_START` en telt niet mee in het cohort.

De implementatie is gereed voor tijdgebonden verzameling, maar dit document sluit
P2-008 niet. Twaalf opeenvolgende dagen bewijzen bovendien niet automatisch de
vereiste seizoens- en scenariodiversiteit; die wordt na de verzameling apart
beoordeeld.

De pipeline bevat sinds 2026-10-12 ook de gezamenlijke batterij-/EV-dry-runlaag.
Deze uitbreiding verandert de cohortstand niet: er is nog geen prospectieve dag
met een verse volledige private control- en safetysnapshot vastgelegd.

Op 2026-10-13 is de capture-service uitgebreid met een read-only
snapshotrefresher. Die verwijdert bestaande control- en safetysnapshots vóór
iedere poging, leest uitsluitend expliciet gemapte Home Assistant-states en
schrijft alleen een nieuw paar wanneer iedere bronobservatie vers, beschikbaar
en niet future-dated is. Ontbrekende override-, fallback- of
acknowledgement-signalen worden niet als `false` geïnterpreteerd.

Na onafhankelijke adversarial review is de refresher verder aangescherpt:
device availability komt nu uit afzonderlijke read-only states; control en
safety delen één generatie-ID; een gedeeltelijke pair-write verwijdert beide
outputs; transportfouten produceren een begrensde privacyveilige `REJECTED`;
en SDK-responses worden via `structured_content` verwerkt. Een cleanupfout die
stale input niet veilig kan verwijderen blijft expres een harde servicefout,
zodat de capture niet met mogelijk oude snapshots start.

Een vervolgreview vond nog vier fail-closed-gaten. De refresher weigert nu
dubbele entitymapping, omgekeerde batterij-SOC-grenzen, een EV-doel-SOC onder de
actuele SOC en een vertrektijd die al verstreken is. Tijdelijke bestanden worden
veilig uniek aangemaakt in plaats van via een voorspelbare PID-naam. Als een
gedeeltelijke pair-write niet volledig kan worden teruggedraaid, blijft de
exitcode ook met `--soft-fail` hard `2`. De reviewmelding dat de service root zou
zijn bleek niet van toepassing op de geïnstalleerde user-unit: de actieve
systemd-user-manager draait onder de projectgebruiker. Na de fixes slaagden
`237/237` Python-tests en `58/58` JavaScript-tests.

De finale gerichte herbeoordeling gaf `PASS` zonder resterende high/medium
findings. Een gecombineerde fout tijdens de tweede replace, rollback-unlink en
temp-unlink blijft ook onder `--soft-fail` een harde exitcode `2`. Een gewone
Home Assistant-transportfout vóór persistence blijft daarentegen bewust een
privacyveilige `REJECTED` met exitcode `0`, nadat oude snapshots zijn verwijderd.

De lokale Git-ignored artifact-HMAC-sleutel is met restrictieve rechten
aangemaakt. Een handmatige fail-closed capture voor `2026-10-14` eindigde door
onvolledige vroege prijsdekking in `REJECTED`, maar schreef wel het verwachte
geauthenticeerde manifest over intents, review, proposals en summary. Alle
write-capabilityvelden bleven `false`.

De geaccepteerde doeldagen zijn `2026-10-08` (`high_load_ev_day`) en
`2026-10-11` (`weekend`). Doeldag `2026-10-12` wacht nog op settlement.

## Prospectieve capture

De capture draait dagelijks om `23:45 Europe/Brussels` en bevriest uitsluitend
informatie die vóór de doeldag beschikbaar is:

- gemeten start-SOC met freshnesscontrole;
- versie- en issue-timegebonden PV-forecast;
- aparte kwartierforecast voor de totale exogene huislast;
- volledige Belgische Day-Ahead-prijsreeks;
- maandpiek tot dan toe;
- batterij- en piekconstraints.

De planner vergelijkt `piekneutraal`, `7 kW`, `8 kW` en `10 kW`. Ontbrekende,
stale, verschoven, dubbele of niet-finite inputs produceren `NO_ACTION` met een
lege planning. EV en warmtepomp blijven uitsluitend onderdeel van de gemeten
totale load en behouden status `DATA_GATED` voor afzonderlijke optimalisatie.

Gedetailleerde kwartierbundels en plannen blijven onder
`data/raw/shadow-validation-captures/` en zijn Git-ignored.

Voor dezelfde doeldag worden actuator-neutrale batterij- en EV-intents, een
fail-closed safety review en niet-dispatchbare SMA-/Smappee-voorstellen gebouwd.
Ontbrekende private controlsnapshots leveren daar `NO_ACTION`/`REJECTED`, zonder
de bestaande batterij-shadowplanning als fysieke actie te behandelen. De
privacyveilige joint-summary bevat alleen statussen, tellingen en reason counts.

## Afrekening tegen werkelijkheid

De afrekening draait na afloop van de doeldag en verzamelt uitsluitend read-only
vijfminutenstatistieken. Drie exacte vijfminutenbuckets worden zonder forward-fill
naar één kwartier geaggregeerd. De bestaande batterijwerking wordt eerst uit het
gemeten netprofiel verwijderd:

`base_net = grid_import - grid_export - battery_charge + battery_discharge`

Een plan telt alleen als prospectief wanneer ook de volledige optimalisatie vóór
de doeldagstart gereed is. Daarna wordt iedere geplande policy tegen de werkelijke basislast afgespeeld. De
uitvoering wordt begrensd door werkelijk meterheadroom, batterijvermogen,
beschikbare SOC, zelfverbruik, efficiëntie en degradatie. De samenvatting bevat
alleen forecastfouten en geaggregeerde kosten/energie; kwartierprofielen blijven
privé.

De joint-settlement vergelijkt daarnaast ieder volledig en read-only gevalideerd
voorstel met de gemeten batterij- of EV-energie. Zij rapporteert energie-MAE en
action-matchratio per target, maar schrijft geen causaliteit toe: SMA en Smappee
blijven de werkelijke controllers. Onvolledige target/intervalcoverage, quality
flags of enige dispatch-/write-capability wijzen de volledige joint-score af.
De scorer controleert ook de targetdatum, bronplan-ID, capturegeldigheid,
summary-aantallen, intent-ID en exacte gemeten kwartierduur. De prospectieve
adapter vereist een volledige UTC-kwartierreeks en accepteert daardoor correct
92, 96 of 100 kwartieren op Belgische DST-doeldagen, maar geen afgeknotte dag.
Capture schrijft als laatste een lokaal HMAC-SHA-256-geauthenticeerd manifest met
digests van intents, review, proposals en summary. Settlement weigert ontbrekende,
gemengde of gewijzigde artifact-sets vóór scoring. De gedeelde sleutel blijft
uitsluitend onder `config/private/`; zonder geldige sleutel blijft joint-evidence
fail-closed `REJECTED`.

## Live observatielaag

De privacygeminimaliseerde planning wordt gepubliceerd naar de uitsluitend
observerende entity met private alias `shadow_plan`. Alle write-flags zijn
expliciet `false`; de entity heeft geen command topic of actuatorpad. De
Lovelace-kaart gebruikt de entity alleen om gepland versus werkelijk gedrag te
tonen.

De live status valt terug naar `NO_ACTION` wanneer de planner niet vóór de
doeldagstart gereed is. Na de afgewezen eerste run is de capture vervroegd naar
`23:45 Europe/Brussels`. De geplande doeldag `2026-10-07` werd eveneens veilig
afgewezen door een te strikte maandpiek-freshnessgrens; de eerstvolgende run is
voor doeldag `2026-10-08` met de gecorrigeerde kalendermaandvalidatie.

## Tests

- Prospectieve capture/planner: `21/21` tests geslaagd.
- Prospectieve afrekening: `12/12` tests geslaagd.
- Cohortaggregatie: `4/4` tests geslaagd.
- DST-doeldagen met `92`, `96` en `100` kwartieren zijn gedekt.
- Stale SOC en forecasts met future leakage falen gesloten.
- Een afgewezen capture blijft omzetbaar naar een veilige `NO_ACTION`-planentity.
- Een pas na de doeldagstart voltooid plan wordt geweigerd bij planning,
  afrekening en cohortaggregatie.
- Privacy-safe samenvattingen bevatten geen kwartierprofielen of schedules.
- Gezamenlijke intents, safety review, proposals en scoring blijven expliciet
  niet-uitvoerbaar en falen gesloten bij ontbrekende snapshots, onvolledige
  targetcoverage of gemanipuleerde writegrenzen.
- Volledige regressie op 2026-10-13: `220/220` Python-tests en `58/58`
  JavaScript-tests geslaagd; HACS-, compile-, syntax-, systemd-, Markdown- en
  diffchecks zijn groen.
- Onafhankelijke afsluitreview: `PASS`, zonder resterende high- of
  medium-severity findings. Adversarial probes bevestigden afwijzing van
  gemanipuleerde of gemengde artifact-sets, een ontbrekende/ongeldige lokale
  integriteitssleutel, afgeknotte of ongeordende 23/24/25-uursdoeldagen en een
  plan dat zijn gedeclareerde geldigheidsvenster niet volledig afdekt.

De machineleesbare cohortstatus staat in
`docs/evidence/prospective-shadow-validation-cohort.json`. Deze telt uitsluitend
afgerekende dagen met één toegewezen primaire stratum en aggregeert forecast- en
uitvoeringsresultaten per policy zonder kwartierprofielen te publiceren.

## Geautomatiseerde lokale uitvoering vanaf 2026-10-06

De handmatige eerste capture is vervangen door twee reproduceerbare
user-systemd-timers:

- `dynamic-energy-shadow-capture.timer`: dagelijks `23:45 Europe/Brussels`;
- `dynamic-energy-shadow-settlement.timer`: dagelijks `00:45 Europe/Brussels`.

De capture ververst eerst de Belgische Day-Ahead-feed, leest vervolgens de
actuele SOC, maandpiek en Solcast-detailforecast, en bouwt de loadforecast uit
read-only vijfminutenstatistieken. De planner schrijft uitsluitend lokale raw-
en privacyveilige evidencebestanden. Een onvolledige prijsdag, verschoven
PV-forecast, onvoldoende loadhistoriek of stale bron produceert een expliciete
`NO_ACTION`-planning. De maximale ouderdom voor PV- en prijsinputs is `18 uur`;
de prijsfeed moet bovendien expliciet `stale: false` en
`sequence_complete: true` rapporteren. Installatiespecifieke entity-ID's staan
alleen in `config/private/` en worden door Git genegeerd.
De maandpiekobservatie gebruikt `last_reported` met `last_updated` als fallback
en moet uit de huidige lokale kalendermaand komen. De maximale leeftijd is
`744 uur`, omdat deze monotone state legitiem alleen rapporteert wanneer een
nieuwe maandpiek ontstaat. Alleen de expliciet informatieve bronflag
`collapsed_identical_duplicate` is toegestaan en wordt als provenance bewaard;
malformed, onbekende en correctieflags worden geweigerd.

De settlement exporteert Grid import/export, PV, batterijlading/-ontlading en
EV-lading read-only. Ontbrekende energie of bron-quality flags worden niet als
geldige nul behandeld: ze blijven als afwijzende flags aanwezig. De primaire
cohortklasse wordt na afrekening deterministisch toegewezen; negatieve prijzen,
weekend en hoge EV-load krijgen voorrang op de seizoensklassen.
De cohortaggregatie valideert zowel plan- als settlementflags en weigert ieder
resultaat waarin een write-capability niet expliciet `false` is. Ontbrekende
plannen, MCP-fouten en malformed configuratie schrijven een expliciete
`REJECTED` settlement plus een niet-stale `IN_PROGRESS` cohortstatus. De
settlementservice probeert een mislukte run maximaal viermaal opnieuw met
`15 minuten` tussenruimte.
Cohorttoewijzingen worden in-memory gestaged en pas na succesvolle cohortbouw als
laatste bestand geschreven. Wanneer een outputwrite faalt, probeert de pipeline
ieder onafhankelijk normaal outputpad te vervangen door een expliciet fail-closed
artifact en schrijft zij geen runtime cohorttoewijzing. Ook wanneer één
fallbackpad persistent faalt, worden de overige fallbackartifacts nog geprobeerd;
de service eindigt daarna niet-succesvol zodat de systemd-retry policy herneemt.

Beide timers zijn op 2026-10-06 geïnstalleerd, `enabled` en `active` bevonden.
Hun unitbestanden slagen voor `systemd-analyze --user verify`. De geplande
capture om 2026-10-06 23:45 voor doeldag `2026-10-07` produceerde fail-closed
`NO_ACTION`, omdat de monotone maandpiekstate ouder was dan de toenmalige grens
van `6 uur`. Dat is als ongeschikte freshnesssemantiek gecorrigeerd: de state
moet nu uit dezelfde lokale kalendermaand komen en mag maximaal `744 uur` oud
zijn. De eerstvolgende geplande capture is doeldag `2026-10-08`; de cohortteller
blijft terecht `0/12`.

Een read-only scratch-smokerun voor doeldag `2026-10-07` slaagde op 2026-10-06
om `14:47 Europe/Brussels` met status `PLANNED`, capturekwaliteit
`ACCEPTED_PROSPECTIVE_DAY` en lege qualityflags. Deze scratch-run telt niet mee
voor het cohort; de geplande capture om `23:45` blijft de prospectieve evidence.

Op 2026-10-07 om `08:20 Europe/Brussels` waren de capture- en
settlementtimers actief, met volgende runs om respectievelijk `23:45` en `00:45`.
De bijbehorende oneshot-services waren na hun vorige succesvolle uitvoering
terecht `inactive (dead)` met `Result=success` en `ExecMainStatus=0`.

## Onafhankelijke review

De finale onafhankelijke herbeoordeling op 2026-10-07 is geslaagd zonder
securitybevindingen, logische fouten of open suggesties. Zij bevestigde de
gecorrigeerde status van doeldagen `2026-10-07` en `2026-10-08`, de strikte
read-only Home Assistant-grens en de expliciete regressiedekking voor huidige-
maandpieken, toekomstige observaties en alle fail-closed fallbackpaden. Deze
implementatiereview sluit P2-008 niet: het prospectieve cohort blijft `0/12`.
Dit was de cohortstand tijdens die review; de actuele stand staat bovenaan en is
inmiddels `2/12`.

## Read-only Home Assistant-prijsfallback 2026-10-12

De capture van doeldag `2026-10-12` kon de lokale ENTSO-E-feed niet vernieuwen,
omdat `ENTSOE_SECURITY_TOKEN` niet in het door systemd geladen lokale `.env`-
bestand stond. De geplande capture faalde daardoor vóór de eigen fail-closed
capturecode kon starten.

De pipeline leest nu optioneel drie reeds aanwezige Home Assistant-entities:

- EPEX Spot Data marktprijs;
- Ecopower Dynamic afnameprijs;
- Ecopower Dynamic injectieprijs.

Deze entities worden uitsluitend met `ha_get_state` gelezen. De huidige
integraties leveren per kalenderdag `192` rijen met `96` unieke kwartierstarts:
iedere rij komt tweemaal identiek voor. De normalisatie reduceert die vorm naar
`96` kwartieren en bewaart `collapsed_identical_duplicate` als informatieve
provenanceflag. Een afwijkende prijs of eindtijd voor dezelfde starttijd wordt
fail-closed geweigerd. De drie afzonderlijke observation timestamps worden
bewaard en ieder afzonderlijk tegen de capturetijd gecontroleerd, zodat één
future-dated entity niet achter een oudere minimumtimestamp verborgen kan blijven.
De gesynthetiseerde feed bevat daarnaast dezelfde schema-verplichte indicatieve
referentie (`€0,2770/kWh`) en een expliciete HA/Ecopower-tariefversie als de
downstream Lovelace-payload verwacht; de referentie blijft nadrukkelijk geen
factuurreconstructie of all-in prognose.

De capture-unit voert de rechtstreekse ENTSO-E-refresh alleen uit wanneer het
token aanwezig is. Zonder token gebruikt de planner de complete read-only
EPEX/Ecopower-reeks uit Home Assistant; de bestaande lokale feed blijft fallback.
De geïnstalleerde unit is opnieuw geladen en gevalideerd. De timer blijft actief
voor `2026-10-12 23:45 Europe/Brussels`.

## Veiligheidsgrens

Deze pipeline verricht geen Home Assistant-, SMA-, Smappee-, batterij-,
laadpaal- of andere fysieke writes. Home Assistant mag de geminimaliseerde
shadow-planfeed uitsluitend via de observerende read-only integratie lezen; de
capture- en settlementpipeline publiceert geen Home Assistant-state en roept
geen Home Assistant-write-service aan. Een positieve shadow-uitkomst autoriseert
geen contractwijziging, productieautomatisatie of fysieke test.
