# ADR-005 - Read-only dynamic steering investigation

Status: Accepted  
Date: 2026-10-01  
Decision owner: installation owner  
Related tickets: P2-005, P2-007 and P2-008

## Context

The validated invoice-year backtest, three-year tariff sensitivity and battery
scenarios consistently show that a dynamic contract is worth further
investigation. Winter grid charging is technically relevant, while uncontrolled
charging can increase the capacity peak and destroy part of the value.

The installed SMA Home Manager can perform native forecast-based battery
charging, but it is currently disabled. Smappee already owns EV charging and
load balancing. Direct Home Assistant control would create conflicting actuator
ownership and is therefore not the first implementation route.

## Decision

Proceed with a read-only shadow-controller phase.

The shadow controller will calculate proposed quarter-hour schedules using:

- Belgian Day-Ahead prices and the versioned Ecopower formula;
- measured battery SOC and power constraints;
- PV and base-load forecasts with explicit uncertainty;
- a shared grid-import ceiling for house, heat pump, EV and battery charging;
- conversion losses, degradation and capacity-peak effects.

It will compare at least peak-neutral, `7 kW`, `8 kW` and `10 kW` policies and
record why each action was proposed. It will not send commands or setpoints.

## Controller ownership

- SMA remains the sole active controller for PV and battery.
- Smappee remains the sole active controller for EV charging and overload
  protection.
- Home Assistant and the external data layer remain read-only observers.
- The optimizer produces plans and evidence only.

## Explicitly not authorized

- changing the electricity contract;
- enabling SMA forecast charging, time-window charging or peak shaving;
- changing SMA, Smappee or Home Assistant configuration;
- issuing battery, inverter, charger or EV commands;
- enabling Modbus TCP or OCPP;
- production automation or physical failure-mode testing.

## Exit criteria

A later controlled test may be proposed only after the shadow phase demonstrates:

1. reliable next-day inputs and visible stale-data handling;
2. repeatable savings after losses, degradation and peak costs;
3. acceptable forecast and schedule error across representative seasons;
4. one conflict-free, officially supported actuator interface;
5. documented timeout, acknowledgement, rollback and local fallback behavior;
6. a new explicit owner approval for the exact physical test.

## Consequences

P2-008 starts in read-only mode. P3-001, P3-002 and P3-003 remain blocked for
physical control. A positive shadow result may support a later activation
proposal, but does not itself authorize a contract or configuration change.

## Implementation evidence — 2026-10-02

The first offline implementation now produces a deterministic 96-quarter plan,
compares peak-neutral, `7 kW`, `8 kW` and `10 kW`, and publishes only a
privacy-safe aggregate to the dashboard. The detailed household-profile plan
remains in a Git-ignored raw-data path.

The first historical run retained a small positive value after applying the
plan to measured residual grid flow, but one day is not sufficient evidence for
activation. P2-008 therefore remains in progress for representative multi-day
shadow validation, measured start-SOC and separately versioned PV, house, EV
and heat-pump forecast inputs.
