# Changelog

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
