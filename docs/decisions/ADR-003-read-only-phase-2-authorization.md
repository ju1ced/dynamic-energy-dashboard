# ADR-003 - Read-only Phase 2 Authorization

Status: Accepted  
Date: 2026-09-29  
Decision owner: installation owner  
Related tickets: P1-014, P2-001, P2-004 and P2-002

## Context

Phase 1 established the hardware inventory, controller boundaries, Home Assistant source hierarchy, Ecopower contract baseline, one-year Fluvius quarter-hour dataset and the requirements for shadow billing.

The owner explicitly approved Phase 2 after reviewing `PHASE_1_GO_NO_GO.md`.

## Decision

Start a strictly read-only Phase 2.

Authorized first workstreams:

1. P2-004: contract-compatible Belgian Day-Ahead price ingestion.
2. P2-001: reproducible Home Assistant interval export and Fluvius reconciliation.
3. P2-002 may start only after P2-001 and P2-004 provide validated inputs.

Authorized operations:

- read-only retrieval from Home Assistant and public/approved market-data sources;
- local scripts, tests, schemas and derived privacy-safe evidence;
- offline calculations, simulations and wireframes;
- documentation and dashboard design without deployment.

## Explicitly not authorized

- changing the Ecopower contract;
- Home Assistant configuration writes;
- Home Assistant service calls that change device or helper state;
- SMA, battery, inverter or Home Manager setpoints/configuration;
- Smappee mode, current, charging-status or load-balancing changes;
- enabling Modbus TCP or OCPP;
- production automations or deployment;
- physical failure-mode or fallback tests;
- Phase 3 EV or battery optimization.

## Controller ownership

- SMA remains the sole active controller for PV and battery.
- Smappee remains the sole active controller for EV charging.
- Home Assistant remains read-only for monitoring, export, calculation and simulation.

## Consequences

P1-014 is complete. P2-001 and P2-004 move to `In Progress`. P2-002 remains blocked on their validated outputs. All control-related work remains blocked behind P3-003 and a separate explicit approval.
