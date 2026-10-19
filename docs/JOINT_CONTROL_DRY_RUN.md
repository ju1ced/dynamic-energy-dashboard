# Gezamenlijke batterij- en EV-control in dry-run

## Status en grens

`scripts/joint_control_dry_run.py` vertaalt een gezamenlijk kwartierplan naar
actuator-neutrale batterij- en EV-intents, beoordeelt die fail-closed en maakt
niet-dispatchbare SMA- en Smappee-commandovoorstellen.

Deze laag kan niets fysiek uitvoeren:

- `execution_allowed`, `physical_writes`, `home_assistant_writes`, `sma_writes`
  en `smappee_writes` blijven `false`;
- de adapters bevatten geen netwerkclient, endpoint, servicecall, MQTT-topic,
  apparaat-ID of authenticatieveld;
- ieder adapterresultaat heeft `transport: "NONE"`,
  `dispatch_supported: false` en `execution_action: "NO_ACTION"`;
- `LIVE` bestaat niet in dit contract.

Een geaccepteerd intent betekent alleen dat het voorstel geschikt is voor
analyse in dry-run. Het autoriseert geen Home Assistant-, SMA-, Smappee-,
batterij- of laadpaalactie.

## Inputcontract

De plannerinput bevat minimaal:

- `plan_id`, `generated_at`, `valid_from_utc` en `valid_until_utc`;
- `selected_policy_id`;
- één `shared_grid_import_limit_kw` voor batterij en EV samen;
- aaneengesloten, unieke intervallen met absolute UTC-timestamps;
- per interval `forecast_base_load_kw`, `battery_power_kw`, `ev_power_kw` en
  een verklaarbare `reason`.

Voor `battery_power_kw` geldt:

- positief: laden;
- negatief: ontladen;
- nul: vasthouden.

`ev_power_kw` kan alleen nul of positief zijn. Ontbreekt de volledige EV-input,
dan produceert ieder interval expliciet een EV-intent met `NO_ACTION` en
`MISSING_EV_REQUIREMENT`; de planner neemt geen laadbehoefte aan.

De geobserveerde controlinput bevat:

- een timestamp voor het volledige snapshot en per apparaat;
- batterij-SOC, bruikbare capaciteit, SOC-grenzen, laad-/ontlaadvermogen en
  controllerownership;
- indien beschikbaar: EV-SOC, doel-SOC, vertrektijd, maximaal laadvermogen,
  bruikbare capaciteit, connectiestatus en controllerownership.

De verwachte enige controllers zijn `SMA` voor de batterij en `SMAPPEE` voor
de EV-lader.

## Intentcontract

Elk intent bevat:

- een deterministische `intent_id`;
- `target` (`BATTERY` of `EV_CHARGER`);
- één targetinterval met `start_utc` en `end_utc`;
- bronplan-ID en generatietijd;
- geldigheidsvenster;
- voorgestelde actie en vermogen;
- effect op de gedeelde netimport;
- reden;
- verwacht en geobserveerd controllerownership;
- apparaatlimieten en gedeelde netimportlimiet;
- inputtimestamp;
- expliciete niet-uitvoerbare veiligheidsvelden.

De volledige intentbundle bevat een canonieke HMAC-SHA-256-integriteitswaarde
met een proceslokale, niet-geëxporteerde sleutel. De bundle bevat daarnaast het
volledige verwachte intervalmanifest. Iedere wijziging na het bouwen — ook een
consistent gewijzigde actie, apparaatlimiet, verwijderd targetintent of volledig
verwijderd interval — maakt de bundle ongeldig voor de safety supervisor.

Deze HMAC bewaakt uitsluitend de in-process dry-run-overdracht. Een bundle of
review uit een eerder proces wordt bewust niet opnieuw vertrouwd. Voor de vier
persistente prospectieve capture-artefacten bestaat daarnaast een afzonderlijk
duurzaam manifest met SHA-256-digests en een HMAC-SHA-256 op basis van een lokale,
Git-ignored gedeelde sleutel. Dit authenticeert de overdracht tussen capture en
settlement op dezelfde host; het is geen externe bronauthenticatie.

Ongeldige, overlappende of niet-aaneengesloten plannerintervallen, of een reeks
die het gedeclareerde geldigheidsvenster niet exact afdekt, leveren een lege
`NO_ACTION`-bundle op.

## Safety supervisor

`supervise_intents(...)` beoordeelt ieder intent afzonderlijk. De supervisor
weigert onder andere:

- stale, ontbrekende, ongeldige of toekomstgedateerde observaties;
- een verlopen of te oud bronplan;
- conflicterende bronplan-ID's of intentgeldigheid;
- onbekende acties of inconsistente combinaties van actie, vermogen en
  neteffect;
- dubbele target/interval-combinaties;
- ontbrekende batterij- of EV-intents per gepland interval;
- een gewijzigde bundle-HMAC;
- gewijzigd write- of executionbeleid;
- controllerownership dat afwijkt van SMA of Smappee;
- unavailable apparaten, handmatige override, lokale fallback en
  acknowledgement-timeout;
- laad-/ontlaadvermogen buiten apparaatlimieten;
- batterij-SOC die vóór of door het volledige kwartier buiten de toegestane
  actieruimte komt;
- EV-laden wanneer de lader niet verbonden is, vóór het interval vertrekt of
  het doel-SOC vóór of door het volledige kwartier bereikt;
- gezamenlijke voorspelde netimport boven de gedeelde limiet.

Een geweigerd intent wordt `NO_ACTION`. Een geaccepteerd intent behoudt alleen
zijn `dry_run_action`; `execution_action` blijft ook dan `NO_ACTION`.

Ook het safety-reviewartefact krijgt een proceslokale HMAC. De dry-run-adapters
accepteren alleen een intacte, volledig geaccepteerde review uit hetzelfde
proces en valideren actie, vermogen en reasonstructuur opnieuw. Een vervalste,
gedeeltelijk geweigerde, opnieuw gehashte of malformed review levert uitsluitend
`NO_ACTION` op.

## Commandoregel

```text
python3 scripts/joint_control_dry_run.py \
  --plan PLAN.json \
  --inputs INPUTS.json \
  --safety-state SAFETY.json \
  --now 2026-10-12T20:00:00+00:00 \
  --intent-output INTENTS.json \
  --review-output REVIEW.json \
  --proposals-output PROPOSALS.json
```

De drie outputs zijn lokale analyseartefacten. Ze mogen niet naar een
actuatortransport worden doorgestuurd.

Bij ontbrekende, onleesbare of malformed JSON-inputbestanden schrijft de CLI
deterministische `NO_ACTION`-, `REJECTED`- en lege proposal-artefacten en eindigt
met exitcode `2`; een traceback vervangt de fail-closed outputs niet.

## Prospectieve capture en scoring

De bestaande prospectieve capture maakt nu voor iedere doeldag vijf aanvullende
artefacten onder de Git-ignored raw-directory:

- `joint-intents-YYYY-MM-DD.json`;
- `joint-review-YYYY-MM-DD.json`;
- `joint-proposals-YYYY-MM-DD.json`;
- `joint-summary-YYYY-MM-DD.json`;
- `joint-manifest-YYYY-MM-DD.json`.

De geselecteerde batterijpolicy wordt naar het gezamenlijke plannercontract
vertaald. De huidige prospectieve batterijplanner levert nog geen afzonderlijk
EV-laadprofiel; `ev_power_kw` blijft daarom nul totdat een expliciete EV-behoefte
door de gezamenlijke optimizer wordt geleverd. Een ontbrekende of ongeldige
private controlsnapshot levert uitsluitend een `NO_ACTION`-/`REJECTED`-artefact.
Hij maakt de bestaande batterij-shadowcapture niet uitvoerbaar en wist die ook
niet.

De dynamische snapshots worden alleen uit Git-ignored bestanden gelezen:

- `config/private/prospective-joint-control-inputs.json`;
- `config/private/prospective-joint-safety-state.json`.

Direct vóór iedere geplande capture voert de user-service
`scripts/refresh_prospective_joint_snapshots.py --soft-fail` uit. De refresher
leest uitsluitend actuele Home Assistant-states, valideert iedere afzonderlijke
`last_reported`/`last_updated`-timestamp en schrijft de twee snapshots pas nadat
alle bronwaarden geldig en vers zijn. Oude snapshots worden vóór de poging
verwijderd. Een ontbrekende mapping, `unknown`/`unavailable`-state, future-dated
waarde of één stale safetywaarde laat beide snapshots ontbreken, waarna de
capture fail-closed `REJECTED` publiceert.

Ieder snapshotpaar krijgt één willekeurige `snapshot_generation_id`. De capture
accepteert control- en safetystate alleen wanneer beide IDs exact gelijk zijn.
Als één van de twee finale bestandsvervangingen faalt, verwijdert de refresher
beide outputs; een gemengde generatie kan daardoor niet als geldige input worden
gebruikt. Overlappende refreshes blijven eveneens fail-closed door deze
generatiecontrole.

De private bronmapping staat in
`config/private/prospective-joint-snapshot-source.json`; het publieke contract
staat in
`config/validation/prospective-joint-snapshot-source.schema.json`. Naast SOC,
connectiviteit, doel-SOC en vertrektijd vereist dit contract expliciete
read-only states voor device availability, manual override, local fallback en
acknowledgement timeout voor beide apparaten. Deze signalen worden niet als
`true` of `false` aangenomen.

De duurzame artifact-set gebruikt eveneens een Git-ignored sleutel:

- `config/private/joint-artifact-hmac.key`.

De sleutel moet op de capture- en settlementhost eenmalig met restrictieve
rechten worden aangemaakt, bijvoorbeeld:

```sh
umask 077
openssl rand -hex 32 > config/private/joint-artifact-hmac.key
```

De sleutelwaarde mag niet in Git, logs, evidence of chat terechtkomen. Als de
sleutel ontbreekt of ongeldig is, wordt geen authenticeerbaar joint-manifest
gepubliceerd en kan de settlement de joint-score uitsluitend afwijzen.

De publieke contracten staan in
`config/validation/prospective-joint-control-inputs.schema.json` en
`config/validation/prospective-joint-safety-state.schema.json`. Snapshotwaarden
moeten vóór iedere capture read-only uit de bron worden vernieuwd; statische of
stale waarden worden door de supervisor geweigerd.

Na de doeldag vergelijkt de settlement de niet-dispatchbare voorstellen met de
gemeten batterij- en EV-energie. Deze vergelijking heet nadrukkelijk geen
uitvoering: de echte SMA- en Smappee-regelaars kunnen onafhankelijk hetzelfde,
ander of geen gedrag hebben gekozen. Het resultaat krijgt classificatie
`AFTER_THE_FACT_JOINT_DRY_RUN_SCORE_NO_CONTROL` en rapporteert per target:

- energie-MAE;
- voorgestelde en gemeten energie;
- action-matchaantal en -ratio.

De scorer vereist exact 92, 96 of 100 gemeten kwartieren voor de volledige
Belgische doeldag en volledige `BATTERY`- en `EV_CHARGER`-coverage voor ieder
kwartier. Iedere transport-, dispatch- of write-capability wordt geweigerd.
Gedetailleerde intervalscores blijven raw; de privacyveilige summary bevat
alleen aggregaten. De settlement verifieert eerst het duurzaam ondertekende
manifest over intents, review, proposals en summary en valideert daarna het
volledige read-only proposalcontract opnieuw. Targetdatum, bronplan-ID,
geldigheidsvenster, aantallen, proposal-setdigest, intent-ID, kwartierduur en
volledige targetcoverage moeten onderling en met de gemeten kwartieren
overeenstemmen. Een afwijking wijst de volledige joint-score af.

## Validatie

`tests/test_joint_control_dry_run.py` dekt:

- normale gezamenlijke planning;
- ontbrekende EV-input;
- stale, toekomstige en verlopen data;
- gemanipuleerde writegrenzen en bronplanconflicten;
- controllerconflict, handmatige override, fallback en timeout;
- SOC-, laad-, vermogens- en gedeelde netlimieten;
- geprojecteerde SOC-grenzen over het volledige interval;
- onbekende of intern inconsistente acties;
- ontbrekende safetyvelden, malformed supervisorinput en vervalste reviews;
- charger unavailable en bereikt EV-doel-SOC;
- dubbele intents;
- ontbrekende targets en consistente manipulatie van acties en limieten;
- intacte en vervalste bundle- en reviewintegriteit;
- malformed CLI-input en malformed reviewredenen;
- negatieve-prijsreden en een geaccepteerde replay over de DST-offsetwissel;
- volledige prospectieve doeldagen met 92, 96 en 100 kwartieren;
- settlementafwijzing bij gewijzigde intervalduur, intentidentiteit of aantallen;
- settlementafwijzing bij een gemanipuleerde of gemengde duurzame artifact-set;
- afwijzing van een onvolledige 23-, 24- of 25-uurs doeldag;
- deterministische replay;
- technisch niet-dispatchbare SMA- en Smappee-output.
