# ADR-006 - HACS-installable read-only Lovelace shadow dashboard

Status: Accepted  
Date: 2026-10-02  
Decision owner: installation owner  
Related tickets: P2-008 and P2-009

## Context

The standalone web dashboard proves the historical and financial presentation,
but it does not receive Home Assistant state updates. The owner wants the
operational shadow view inside Home Assistant so live SOC, grid, PV, battery,
price, EV and heat-pump values can be compared with the proposed Day-Ahead
plan.

A Lovelace dashboard is a presentation layer, not the correct location for the
Python optimization engine. The optimizer must remain independently testable
and reproducible. The Home Assistant surface may observe live entities and
calculate presentation-only deviations, but it must not become an actuator.

## Decision

Build a HACS-compatible Lovelace custom card with a visual configuration form.

The card will:

- read selected Home Assistant entities directly from the browser's `hass`
  object;
- allow entity mapping and display settings through the Lovelace GUI editor;
- show live grid, PV, battery, SOC, optional house, EV and heat-pump values;
- show shared-grid headroom against a configurable peak limit;
- optionally consume a read-only plan entity whose attributes contain the
  shadow schedule;
- compare the current planned interval with live grid and battery values;
- make unavailable and stale inputs visible;
- render no buttons, service calls, setpoints or actuator payloads.

The Python planner remains the authoritative planning engine. The Lovelace card
is the live observation and explanation surface.

## Authorization boundary

The owner's instruction on 2026-10-02 authorizes implementation of the
read-only HACS/Lovelace package and the configuration UI required to select
entities. This narrowly supersedes ADR-003's prohibition on Home Assistant
configuration work for this dashboard package.

It does not authorize:

- Home Assistant service calls that change device or helper state;
- writes to SMA, Smappee, inverter, battery, EV or charger;
- production automation or physical control;
- automatic installation into the owner's live Home Assistant instance;
- a Git commit, push, GitHub release or HACS publication.

## Packaging decision

The repository will contain a HACS `dashboard` plugin artifact named
`dynamic-energy-dashboard.js`, a root `hacs.json`, documentation and automated
contract tests. Actual HACS installation requires the artifact to be available
from a committed GitHub revision or release; publication remains a separate
approval gate.

## Consequences

P2-009 starts. P2-008 remains the planning and validation ticket. The existing
standalone dashboard remains the historical audit surface. The HACS card becomes
the proposed live read-only operational surface after separate publication and
installation.
