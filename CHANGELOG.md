# Changelog

## 0.3.0-alpha.6 — 2026-10-16

- Ignore Home Assistant updates that do not affect any entity configured on the
  shadow card, avoiding unnecessary full card rebuilds and lost interaction.
- Preserve quarter-price navigation position and focused navigation control when
  a relevant state update does require a render.
- Add the live-dashboard rollout contract for a separate third `Validatie` view
  using the actuator-read-only validation card.
- Preserve `OFF`/`ARMED_BLOCKED`, `execution_allowed: false` and the absence of
  physical SMA, Smappee, battery, EV, MQTT or Modbus writes.

## 0.3.0-alpha.5 — 2026-10-16

- Add a separate actuator-read-only validation card for current-quarter
  expected-versus-observed battery behavior.
- Show measured EV, PV and heat-pump context plus clearly labelled measured or
  derived house power without inferring a vendor-internal reason.
- Detect simultaneous battery/EV charging and effective shared-limit
  exceedances using the stricter dashboard or Smappee capacity threshold.
- Add current price-zone context while preserving current-quarter source
  precedence over longer future-only feeds.
- Support a bounded and internally cross-validated optional daily evidence
  summary without inventing zero values for missing or invalid history.
- Keep pilot status fail-closed, `execution_allowed: false` and the validation
  card free of Home Assistant, SMA, Smappee, battery and EV write actions.

## 0.3.0-alpha.4 — 2026-10-15

- Let the control panel read fresh EPEX/Ecopower price entities independently
  from the shadow-plan freshness window.
- Keep current, cheapest and highest quarter prices visible when an old or
  missing shadow plan blocks planned actions.
- Add a distinct `PRICE_READY_PLAN_BLOCKED` readiness state so usable price
  context is not presented as executable planning readiness.
- Expose the price-entity mappings, price freshness threshold and explicit
  Smappee dynamic-tariff verification status in the visual editor.
- Keep Smappee dynamic tariffs informational only; Ecopower remains the
  read-only observation source unless a separately verified mapping is chosen.
- Preserve `OFF`/`ARMED_BLOCKED`, `execution_allowed: false` and the absence of
  physical SMA, Smappee, battery, EV, MQTT or Modbus writes.

## 0.3.0-alpha.3 — 2026-10-14

- Keep the horizontal quarter-price position stable when Home Assistant refreshes
  the card.
- Add explicit previous/next controls with keyboard-accessible 44 px targets for
  quarter-price navigation.
- Add a responsive, non-scrolling daily graph that retains elapsed quarters,
  groups prices by the Europe/Brussels calendar day and handles 92/100-quarter
  daylight-saving days.
- Parse each price source once, reuse timezone formatters and cache unchanged
  graph markup to keep frequent Home Assistant refreshes responsive.
- Bound unusually long feeds to the three latest local price days.
- Preserve the read-only boundary and all `OFF`/`ARMED_BLOCKED` safety limits.

## 0.3.0-alpha.2 — 2026-10-14

- Expand the alpha card into a dynamic-price control panel with current,
  cheapest and highest upcoming prices, live battery/grid/EV context and the
  current shadow action.
- Add an explicit readiness state and warnings for stale plan data, pending SMA
  forecast charging, Smappee offline fallback and differing capacity limits.
- Add separate SMA battery and Smappee EV configuration guides while preserving
  one active controller per actuator.
- Keep all physical and provider writes absent; the only existing writes remain
  the confirmed, namespaced and hard-blocked Home Assistant automations.
- Add optional visual-editor mappings for control-panel entities and documented
  vendor-profile values.

## 0.3.0-alpha.1 — 2026-10-14

- Add a separate `dynamic-energy-control-config-card` for creating and managing
  only the card's namespaced Home Assistant automations.
- Restrict the control card to `OFF` and `ARMED_BLOCKED`; live execution is not
  available and every generated automation stops before any actuator action.
- Require explicit confirmation and verified ownership for every write; creation
  and updates additionally use Home Assistant configuration validation.
- Seal each generated automation with its deterministic canonical configuration
  snapshot and reject ambiguous, foreign or modified automations instead of
  overwriting or enabling them.
- Keep the existing `dynamic-energy-shadow-card` observation-only and separate
  from all configuration actions.
- Verify real Home Assistant automation responses that retain their matching ID,
  and fail closed when a retired managed configuration has no unique state entity.
- Require Home Assistant 2024.10.0 or newer for the generated automation syntax.

## 0.2.1 — 2026-10-12

- Collapse identical duplicate intervals emitted by current EPEX Spot Data and
  Ecopower Dynamic Prices entities.
- Continue to reject duplicate starts when their end time or price conflicts.

## 0.2.0 — 2026-10-07

- Show upcoming quarter-hour ENTSO-E and Ecopower prices in the Lovelace card.
- Compare future prices with the configurable indicative reference price.
- Align planned battery actions with their price intervals.
- Show compact day, ISO-week and month price comparisons.
- Read future `data` attributes directly from EPEX Spot Data and Ecopower
  Dynamic Prices entities when the shadow feed has no price timeline.
- Validate external schedule, price, export and aggregate rows before use.
- Select one fresh price source by upcoming coverage and keep its timeline,
  current values and metadata coherent.
- Treat the GUI comparison reference as authoritative and recompute aggregate
  differences from it.
- Preserve the strictly read-only boundary: no Home Assistant actions, command
  topics, inverter writes or charger controls.

## 0.1.0 — 2026-10-02

- Initial HACS-ready read-only energy shadow dashboard.
