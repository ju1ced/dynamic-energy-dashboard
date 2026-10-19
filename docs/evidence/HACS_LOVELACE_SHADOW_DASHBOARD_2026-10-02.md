# HACS Lovelace Shadow Dashboard Validation — 2026-10-02

## Classification

`VERIFIED_LOCAL_HACS_READY_READ_ONLY_CARD`

Related ticket: P2-009  
Related decision: ADR-006

## Delivered artifact

- HACS dashboard manifest: `hacs.json`
- Installable frontend artifact: `dist/dynamic-energy-dashboard.js`
- Card type: `custom:dynamic-energy-shadow-card`
- Visual editor: `18` GUI-configurable fields
- HACS validation workflow: `.github/workflows/hacs-validate.yml`
- User and developer documentation: `README.md`

The card has no runtime dependencies. It registers itself in the Lovelace card
picker and uses Home Assistant's built-in form schema for visual configuration.
YAML remains an optional troubleshooting fallback.

## Live data contract

Required live entity mappings:

- signed grid power;
- PV power;
- signed battery power;
- battery SOC.

Optional mappings:

- measured house power;
- EV charging power;
- heat-pump power;
- current import and export price;
- a plan entity containing the proposed quarter-hour schedule.

Power values in `W`, `kW` and `MW` are normalized to kW. Price values in
`EUR/kWh`, `ct/kWh` and `EUR/MWh` are normalized to EUR/kWh. Grid and battery
sign conventions are configurable through the GUI.

When no explicit house-power entity is configured, the card derives the current
house load from signed grid, PV and battery power. Missing, unavailable and
stale states remain visible and are not coerced to zero.

## Plan comparison

The optional plan entity exposes a configurable schedule attribute. The card
selects the current interval by absolute timestamp and shows:

- proposed action and reason;
- planned grid import;
- actual grid import;
- planned-versus-actual deviation;
- shared peak-limit utilization and remaining headroom.

The Python P2-008 optimizer remains the authoritative planning engine. The card
does not reproduce or replace the optimizer in the browser.

## Safety verification

- No Home Assistant action calls are present.
- No WebSocket command calls are present.
- No device controls, tap actions or hold actions are rendered.
- No SMA, Smappee, battery, EV or charger payload is generated.
- The footer states `READ_ONLY_SHADOW` and the no-write boundary.
- The card remains useful without a plan entity and reports `Plan ontbreekt`.
- Missing required mappings report `Configuratie nodig`.
- Stale live values report `Data verouderd`.

## Browser validation

A real browser fixture loaded the exact HACS artifact as an ES module.

Desktop at `1280 px`:

- custom element registered;
- visual-editor schema exposed `18` fields;
- active plan rendered as `Laden vanaf net`;
- planned-versus-actual deviation rendered;
- four live metrics and the no-write footer were present;
- body-level horizontal overflow: `0 px`.

Mobile at `390 px` and narrow mobile at `320 px`:

- responsive two-column metrics and flow grids rendered;
- active, stale and setup-required states rendered correctly;
- body-level horizontal overflow: `0 px`.

Visual inspection found no overlap or internal clipping. Small secondary labels
remain intentionally subordinate but readable in both desktop and mobile
captures.

## Automated validation

- Python repository suite: `95/95` tests passed.
- JavaScript card suite: `7/7` tests passed.
- JavaScript syntax check: passed.
- Python compile check: passed.
- JSON validation: `30/30` files passed.
- Workflow YAML lint: passed.
- Markdownlint: `50/50` files passed with zero errors.
- Git whitespace check: passed.
- Privacy scan found no installation EAN or LAN address in the HACS artifact,
  browser fixture or HACS evidence.
- Existing standalone dashboard service remained active and returned
  `READ_ONLY` from its loopback health endpoint.

## HACS publication status

The privacy-safe HACS package was published to the public repository
`ju1ced/dynamic-energy-dashboard` on branch `main`.

- Initial HACS commit: `10724b8`.
- Validation remediation commit: `375f583`.
- GitHub default branch: `main`.
- Official HACS validation workflow: passed for commit `375f583`.
- Repository metadata, topics, MIT license and preview image: validated.

The repository can now be added to HACS as a custom `Dashboard` repository.
Installation and entity selection in the owner's live Home Assistant instance
remain separate runtime-validation steps.

## HACS release 0.2.1 — 2026-10-12

De live EPEX Spot Data- en Ecopower Dynamic Prices-entities bleken ieder `192`
rijen voor `96` unieke kwartieren te publiceren. Release `v0.2.1` reduceert
identieke dubbele rijen veilig tot één interval. Conflicterende duplicaten blijven
de volledige bron fail-closed afwijzen.

- Mergecommit: `1de22ff`.
- GitHub-release en tag: `v0.2.1`.
- Officiële HACS-validatie op `main`: geslaagd.
- JavaScript-tests: `37/37` geslaagd.
- Onafhankelijke review: geslaagd zonder bevindingen.
- De release-ZIP bevat het bijgewerkte `dist/dynamic-energy-dashboard.js` en
  packageversie `0.2.1`.

Werkelijke installatie van `v0.2.1` in Home Assistant en visuele readback van de
live kaart blijven de laatste P2-009-validatiegate.

## Remaining integration gate

The live card can already consume Home Assistant entity state. Showing a real
future Day-Ahead schedule additionally requires a read-only Home Assistant plan
entity, or another approved bridge that exposes the P2-008 schedule as entity
attributes. That bridge must preserve the same no-control boundary and is not
silently created by the frontend card.

## Prospectieve prijsuitbreiding 2026-10-07

De kaart en privacyveilige observerfeed zijn uitgebreid met:

- toekomstige ENTSO-E-marktprijzen per kwartier;
- Ecopower-afname- en injectieprijzen volgens `ECOPOWER_DBS_2026-08-01`;
- vergelijking met de indicatieve referentie van `€0,277/kWh`;
- koppeling van ieder kwartier aan de voorgestelde shadow-planactie;
- compacte vergelijkingen voor dag, ISO-week en maand, met zichtbare partiële
  periodes;
- behoud van negatieve markt- en injectieprijzen.

De prijsreeks blijft beschikbaar wanneer het batterijplan fail-closed
`NO_ACTION` is of nog geen planbestand bestaat. De feed bevat uitsluitend
publieke markt-/tariefwaarden en geminimaliseerde planvelden, geen huishoudelijk
kwartierprofiel of installatie-ID's. De actuele gecombineerde payload bevatte
`62` toekomstige kwartieren en was `13.480` bytes groot.

Een echte browser valideerde `32` kwartieren, dag/week/maand-samenvattingen en
een geplande actie op desktop en `390 px` mobiel, beide zonder body-overflow. De
visuele editor bevat nu `19` velden. De volledige validatie slaagde met `165`
Python-tests en `15` JavaScript-tests, plus syntax-, compile-, systemd-,
Markdown- en whitespacecontroles. Een scan van `167` publieke kandidaatbestanden
vond geen waarden uit de private mappings.

De actieve read-only dashboardservice levert de gecombineerde endpoint met
`physical_writes=false` en `home_assistant_writes=false`. Home Assistant kan die
feed via de ingebouwde REST-integratie lezen; een Nord Pool-integratie is niet
nodig. Publicatie van de nieuwe HACS-versie en toepassing van de REST-sensor in
de live Home Assistant-installatie blijven afzonderlijke gates.
