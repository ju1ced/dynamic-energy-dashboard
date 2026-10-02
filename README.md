# Dynamic Energy Shadow Dashboard

Read-only Lovelace monitor for live Home Assistant energy values and a proposed
Day-Ahead battery shadow plan. The card never calls Home Assistant actions,
changes helper state or writes to SMA, Smappee, a battery or an EV charger.

![Dynamic Energy Shadow Dashboard preview](images/dynamic-energy-shadow-card.png)

## Features

- live grid, PV, battery and SOC values;
- optional house, EV, heat-pump and price entities;
- configurable shared grid-import limit and remaining headroom;
- current shadow-plan action, reason and planned-versus-actual deviation;
- visible missing, unavailable and stale-data states;
- visual editor for entity mapping and thresholds;
- responsive light/dark Home Assistant styling;
- no runtime dependencies.

The Python optimizer remains the authoritative planning engine. This card is the
live observation and explanation layer.

## Install with HACS

A committed GitHub revision or release is required before HACS can install the
artifact. No publication is performed automatically by this repository.

1. Open HACS in Home Assistant.
2. Open the three-dot menu and choose `Custom repositories`.
3. Select `Add custom repository`.
4. Enter the GitHub repository URL.
5. Select repository type `Dashboard`.
6. Install `Dynamic Energy Shadow Dashboard`.
7. Refresh the browser when HACS requests it.

## Configure through the GUI

1. Open or create a Lovelace dashboard.
2. Choose `Edit dashboard` and then `Add card`.
3. Select `Dynamic Energy Shadow Dashboard` from the card picker.
4. Use the visual editor to select the live entities and thresholds.

Recommended live mappings:

- grid power: signed grid power sensor;
- PV power: current PV generation;
- battery power: signed charge/discharge power;
- battery SOC: current percentage;
- optional house, EV and heat-pump power;
- optional current import and export price;
- optional plan entity containing the generated shadow schedule.

The GUI supports sign conventions because integrations differ: grid import can
be positive or negative, and battery charging can be positive or negative.

## Plan entity contract

The optional plan entity should expose an attribute named `schedule` by default.
The attribute is a list of quarter-hour objects:

```yaml
schedule:
  - start_utc: "2026-10-02T10:15:00+00:00"
    duration_hours: 0.25
    action: CHARGE_FROM_GRID
    reason: LOW_PRICE; shared-grid headroom remains
    planned_grid_import_kw: 3.5
    planned_grid_export_kw: 0
    charge_kwh: 0.25
    discharge_kwh: 0
```

The attribute name can be changed in the visual editor. Missing or stale plan
data remains visible and does not trigger a guessed action.

## Manual YAML fallback

The visual editor is the default. YAML remains available for troubleshooting:

```yaml
type: custom:dynamic-energy-shadow-card
title: Shadow-sturing
grid_power_entity: sensor.grid_power
pv_power_entity: sensor.pv_power
battery_power_entity: sensor.battery_power
battery_soc_entity: sensor.battery_soc
plan_entity: sensor.dynamic_energy_shadow_plan
plan_attribute: schedule
peak_limit_kw: 7
stale_after_minutes: 10
grid_import_positive: true
battery_charge_positive: true
```

## Development validation

```bash
python3 -m unittest tests.test_hacs_lovelace_package -v
npm run test:hacs
npm run check:hacs
```

The HACS artifact is `dist/dynamic-energy-dashboard.js`.
