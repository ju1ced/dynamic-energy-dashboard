# Web Dashboard MVP Validation — 2026-09-30

## Classification

`VERIFIED_LOCAL_READ_ONLY_MVP`

Related ticket: P2-003

## Implemented surface

- Separate static web dashboard; no Home Assistant dashboard changes.
- AIHub-inspired monitor layout with compact navigation, muted green header,
  flat work panes and monospaced data detail.
- Responsive desktop and mobile states.
- Views: Overview, Financial, Prices, Energy, Data Quality and Decisions.
- Privacy-safe generated JSON derived from validated project evidence.
- Local HTTP origin with explicit `0.0.0.0` bind and `/healthz` endpoint.
- No mutating routes or device controls.

## Validation

- Dashboard data build: 12 monthly and 365 daily aggregate rows.
- Full Python test suite: 31/31 passed.
- Python compile check: passed.
- JavaScript syntax check: passed.
- Git whitespace check: passed.
- Browser routes rendered: 6/6.
- Browser runtime errors: 0 on desktop and mobile.
- Desktop horizontal overflow: 0 px at 1440 px viewport.
- Mobile horizontal overflow: 0 px at 390 px viewport.
- Mobile navigation drawer and Financial route: passed.
- Readability controls: 100%, 112% and 125% scales passed on desktop and
  mobile; the selected value persists through browser reloads.
- Mobile shell width at 125%: 390 px in a 390 px viewport; horizontal scroll
  remained unavailable.
- Localhost healthcheck: `READ_ONLY`.
- LAN healthcheck: `READ_ONLY`.
- Listener: all local interfaces on TCP port 4173.
- Runtime: enabled systemd user-service with restart-on-failure and user
  lingering; no active Hermes session is required.

Browser screenshots were written below `browser-evidence/`, which is Git-ignored.

## Security and exposure

The dashboard is reachable on the trusted LAN through the host's local address.
Because `cloudflared` runs on a different LXC, that tunnel must use the
dashboard host's LAN origin on TCP 4173 rather than loopback. No Cloudflare
Tunnel, public hostname or Cloudflare Access policy was created by this
project. External exposure remains blocked pending an explicit hostname,
tunnel and access-control decision.

## Design self-audit

Surface archetype: Monitor.

AI-design-slop score after visual review: 0/10. The interface uses the supplied
reference's compact monitoring composition instead of a marketing hero,
generic feature tiles, decorative gradients or glass effects.

## Limitations

- The dashboard is based on validated exports and backtest evidence, not live
  Home Assistant polling.
- Scenario A is retrospective and is not contract advice.
- The Energy Decision Log view is an initial read-only presentation; P2-006
  remains required for the formal decision schema.
