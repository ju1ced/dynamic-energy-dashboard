# Changelog

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
