# Read-only Shadow Controller Validation — 2026-10-02

## Classification

`VERIFIED_OFFLINE_READ_ONLY_SHADOW_PROTOTYPE`

Related ticket: P2-008  
Related decision: ADR-005

## Implemented contract

- `scripts/build_shadow_controller_plan.py` builds a Day-Ahead quarter-hour plan.
- Output is explicitly `READ_ONLY_SHADOW` and
  `PROPOSED_PLAN_NO_CONTROL`.
- Home Assistant, SMA, Smappee and physical writes are all `false`.
- Missing, stale, invalid or incomplete inputs return `NO_ACTION`.
- The optimizer enforces usable SOC, charge/discharge power, conversion losses,
  degradation cost, no simultaneous charge/discharge and no battery export.
- The grid-import ceiling is shared by forecast residual household load and
  battery charging.
- Policies compared: peak-neutral, `7 kW`, `8 kW` and `10 kW`.
- A privacy-safe evidence summary excludes the quarter-hour household profile.
  The detailed schedule remains below the Git-ignored `data/raw/` boundary.

## Historical shadow run

Target local day: `2026-09-30`  
Intervals: `96/96`  
Assumed initial SOC: `50%`  
Usable battery capacity: `14.24 kWh`  
Maximum charge/discharge power: `5 kW`  
Round-trip efficiency: `85.3727%`  
Degradation cost: `€0.06` per discharged kWh

The load input is a trailing same-quarter median forecast over the residual
Fluvius grid profile. It is not a separately reconstructed house-load forecast.
The historical target day is then used only for the after-the-fact execution
comparison.

## Result

All four peak policies produced the same schedule because the optimized import
remained below the already observed month-to-date peak of `5.42 kW`.

| Policy | Shared limit | Forecast saving | Backtest saving | Grid charge | Discharge |
|---|---:|---:|---:|---:|---:|
| Peak-neutral | 5.42 kW | €0.0432 | €0.0406 | 1.8927 kWh | 1.6158 kWh |
| 7 kW | 7.00 kW | €0.0432 | €0.0406 | 1.8927 kWh | 1.6158 kWh |
| 8 kW | 8.00 kW | €0.0432 | €0.0406 | 1.8927 kWh | 1.6158 kWh |
| 10 kW | 10.00 kW | €0.0432 | €0.0406 | 1.8927 kWh | 1.6158 kWh |

The selected peak-neutral plan proposed two grid-charge quarters, seven
discharge quarters and 87 hold quarters. The after-the-fact execution model
retained a positive but small `€0.0406` day saving after degradation.

## Interpretation

- `VERIFIED`: the planner produces a complete, deterministic, read-only plan
  and a separate planned-versus-actual aggregate comparison.
- `VERIFIED`: all output safety flags remain non-mutating and no write payload
  is emitted.
- `INFERRED`: the shared peak was non-binding on this one test day; therefore
  this run cannot distinguish the economic effect of the `7/8/10 kW` policies.
- `REQUIRES TESTING`: repeat over representative winter, summer, weekend,
  negative-price and high-load days before assessing repeatable value.
- `REQUIRES TESTING`: replace assumed initial SOC with the target-time measured
  SOC and replace the residual profile forecast with separately versioned PV,
  house, EV and heat-pump inputs.
- `DATA_GATED`: EV availability, departure SOC and heat-pump comfort/thermal
  constraints are not yet available.

## Dashboard

The read-only dashboard now contains a separate `Sturing` view with:

- selected shared-peak policy;
- forecast value versus historical backtest value;
- side-by-side policy results;
- proposed action counts;
- explicit no-write status for Home Assistant, SMA and Smappee;
- limitations and the remaining shadow-validation gate.

## Evidence

- Privacy-safe summary:
  `docs/evidence/shadow-controller-plan-2026-09-30.json`
- Detailed Git-ignored plan:
  `data/raw/shadow-controller-plan-2026-09-30.json`
- Planner tests:
  `tests/test_build_shadow_controller_plan.py`
- Dashboard contract test:
  `tests/test_build_dashboard_data.py`

## Validation performed

- Full Python suite: `90/90` tests passed.
- Python compile check: passed.
- JavaScript syntax check: passed.
- JSON validation: `28/28` files passed.
- Markdownlint: `47/47` files passed with zero errors.
- Git whitespace check: passed.
- Detailed plan confirmed Git-ignored under `data/raw/`.
- Dashboard user-service: enabled and active.
- Loopback and LAN healthchecks: `READ_ONLY`.
- Desktop browser: `Sturing` route active, expected policy/action text present,
  zero body-level horizontal overflow.
- Mobile browser at `390 × 844`: expected route and status present, zero
  body-level horizontal overflow.

## Authorization boundary

This validation does not authorize a contract change, production automation,
Home Assistant service call, SMA/Smappee configuration change or physical
actuator test. SMA remains the active PV/battery controller and Smappee remains
the active EV controller.
