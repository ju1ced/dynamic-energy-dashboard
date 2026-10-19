# Live Home Assistant shadow-card mapping validation — 2026-10-05

## Scope and authorization boundary

The initial validation used read-only Home Assistant dashboard, registry, state
and history inspection. After separate owner approval, one observation-only
MQTT plan entity and the storage-dashboard mapping were changed. No SMA device,
Smappee device, battery, charger, contract or physical actuator was changed.

The owner confirmed that the HACS card is installed and partially configured in
the live Home Assistant frontend.

## Live card discovery

The installed `custom:dynamic-energy-shadow-card` was found in a storage-mode
test dashboard on its Energy view. Exact entity IDs and device identifiers are
kept only in the Git-ignored private mapping file
`config/private/lovelace-shadow-card-live.json`.

## Mapping conclusions

| Alias | Conclusion | Status |
|---|---|---|
| Grid power | W measurement; positive import and negative export | VERIFIED |
| PV power | W measurement with current production | VERIFIED |
| Battery power | Combined value is positive while the SMA discharge component is positive | VERIFIED |
| Battery SOC | Percentage measurement | VERIFIED |
| House power | Smappee value does not consistently include installed-battery discharge | REQUIRES CORRECTION |
| EV power | W measurement; usable as an optional observation input | VERIFIED |
| Heat-pump power | W measurement; usable as an optional observation input | VERIFIED |
| Import price | Configured value is an annual average, not the current Day-Ahead interval price | REQUIRES CORRECTION |
| Export price | Configured value is a fixed input, not a current interval price | REQUIRES CORRECTION |
| Shadow plan | Dedicated observation-only entity exists and currently reports `NO_ACTION` | VERIFIED |

Recommended card settings:

- keep grid import positive;
- set battery charging positive to `false`, because the selected combined
  battery sensor is discharge-positive;
- leave house power empty so the card derives it from grid, PV and normalized
  battery power;
- leave import and export price empty until current interval-price entities
  exist;
- use the private `shadow_plan` alias with attribute `schedule`.

The live storage-dashboard configuration was updated and read back. The explicit
house-power mapping and non-current import/export price mappings were removed;
the dedicated plan entity was added. Home Assistant confirmed the dashboard
write and the subsequent read returned the intended mapping.

The plan entity was created through MQTT discovery with a retained state topic,
but no command topic. A narrowly scoped Home Assistant script publishes only to
that fixed observation topic. Its first run completed successfully and readback
showed `NO_ACTION`, an empty schedule and all write-capability flags set to
`false`. The temporary installation script was deleted after verification.

## Read-only plan feed

A privacy-minimized feed generator was added in
`scripts/build_shadow_plan_feed.py`. It exposes only the fields consumed by the
card and rejects any plan that does not explicitly disable all write
capabilities. It validates timezone-aware bounds, finite non-negative values,
supported plan states and actions, JSON object/list structure and a contiguous
schedule covering the declared plan window. Invalid or overflow-sized durations
are rejected before they can reach the endpoint.

The local read-only dashboard serves `/data/shadow-plan.json` dynamically. It
reloads the latest detailed plan and re-evaluates expiry on every request, so a
previously active static payload cannot remain `PLANNED` beyond its target end.
Malformed, unsupported or unavailable plans fail closed as `NO_ACTION` with
`PLAN_UNAVAILABLE`; parser details are not returned. Because the only
available detailed plan targets 2026-09-30, the current feed correctly reports
`NO_ACTION` and `PLAN_EXPIRED`. It does not expose household forecasts, prices,
entity IDs or device IDs.

A non-applied Home Assistant REST sensor example remains available at
`deploy/home-assistant/shadow-plan-rest-sensor.yaml.example`. It requires an
authenticated HTTPS endpoint; direct cleartext HTTP is acceptable only on an
explicitly isolated trusted network. Applying the example is a separate Home
Assistant configuration change and was not used; the approved live bridge
uses the observation-only MQTT entity instead.

## Validation

- Fifteen focused feed and live-endpoint tests pass, including malformed JSON
  shapes, unsupported states, naïve timestamps, numeric overflow and expiry.
- The complete Python suite passes: `111/111` tests.
- The HACS card suite passes: `7/7` JavaScript tests.
- Python compilation, `55` JSON files, `51` Markdown files and
  `git diff --check` pass.
- The feed is reachable from the active read-only dashboard service on loopback
  and the explicitly approved trusted-LAN endpoint; both return `Cache-Control:
  no-store` and the expired source returns an empty `NO_ACTION` schedule.
- The private live mapping is Git-ignored.
- Live browser rendering with an active plan remains pending. The configured
  dashboard-screenshot feature is disabled, and the available browser session
  has no saved Home Assistant login. Entity state, script trace and written
  dashboard configuration were nevertheless read back through Home Assistant.
- Prospectieve capture is scheduled from 2026-10-05 at 23:55
  `Europe/Brussels`; the first active target day is 2026-10-06.
