# ADR-002 - Eén actieve controller per actuator

- Status: proposed
- Datum: 2026-09-28
- Tickets: P1-005, P1-006, P1-010

## Context

SMA Home Manager, Sunny Boy Storage, een laadpaalcloud, voertuigschema's, Kia Smart Charge en Home Assistant kunnen elk planning of setpoints beïnvloeden. Ongecoördineerde co-control kan tegengestelde commando's, oscillatie, stale setpoints en onverklaarbaar gedrag veroorzaken.

## Voorgesteld besluit

Per actuator is op ieder moment exact één controller eigenaar van schrijfsetpoints:

- batterij/PV: standaard SMA totdat een alternatief expliciet is gevalideerd;
- EV-laadpaal: lokale laadpaalveiligheid blijft leidend; één planner kiest laadvensters;
- Home Assistant: read-only in fase 1 en alleen toekomstige control via een expliciete adapter met timeout, acknowledgement en rollback.

Concurrerende schema's worden vóór een controltest geïnventariseerd en bewust uitgeschakeld of als harde constraint behandeld.

## Gevolgen

- Geen gelijktijdige batterijschrijfacties door SHM en Home Assistant zonder expliciete officiële prioriteitssemantiek.
- Geen gelijktijdige EV-planning door Kia, laadpaalcloud en Home Assistant.
- Iedere toekomstige controlmodus heeft ownership, lease/timeout, readback en fallback nodig.

## Open validatie

Dit voorstel wordt pas `accepted` na bevestiging van concrete SMA- en laadpaalinterfaces en eigenaarreview.
