# ADR-001 - Monitoring en simulatie vóór fysieke sturing

- Status: accepted
- Datum: 2026-09-28
- Tickets: P1-007, P1-011, P1-014, P2-002

## Context

De installatie bevat meerdere lokale controllers en nog niet volledig geïdentificeerde interfaces. De financiële geschiktheid van een dynamisch tarief is onbewezen. Fysieke sturing vóór betrouwbare metingen en shadow billing kan comfort, veiligheid, facturatie en hardwarelevensduur negatief beïnvloeden.

## Besluit

Het systeem start in `MONITOR` en daarna `SIMULATION`. Geen productie-automation of actuatorcontrol wordt gebouwd of geactiveerd voordat:

1. meetdata en energiebalans zijn gevalideerd;
2. huidig contract en dynamische formule reproduceerbaar zijn;
3. scenario's A-D voldoende representatieve data gebruiken;
4. officiële controlinterfaces en limieten zijn bevestigd;
5. failure modes en fallback zijn getest;
6. de eigenaar expliciet een volgende fase goedkeurt.

## Gevolgen

- Fase 1 blijft read-only.
- Dashboardcontrols blijven conceptueel.
- Vroege waarde komt uit inzicht, datakwaliteit en financiële simulatie.
- Een langere observatieperiode is geaccepteerd als prijs voor betrouwbaarheid.
