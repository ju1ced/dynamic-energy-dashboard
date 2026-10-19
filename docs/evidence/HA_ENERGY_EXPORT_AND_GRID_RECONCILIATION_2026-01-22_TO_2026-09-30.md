# Home Assistant historical export and Fluvius reconciliation

Status: `VERIFIED`

## Scope

P2-001 exported cumulative Home Assistant energy statistics read-only for the
requested UTC period from `2026-01-22T00:00:00Z` through
`2026-09-30T00:00:00Z`. The full raw responses and interval series remain in
Git-ignored storage. This document contains no entity IDs or installation
identifiers.

## Resolution and retention finding

The five-minute export requested `72,288` source buckets per stream. Home
Assistant returned `1,989` recent buckets per stream. This produced `662`
usable quarter-hours from `2026-09-23T02:30:00Z` through
`2026-09-29T23:45:00Z`; earlier five-minute buckets remain explicitly missing
and were not zero-filled or forward-filled.

Home Assistant did retain hourly long-term statistics. The separate hourly
export requested `6,023` hours. Grid import and export each provided `6,020`
usable hours, with three missing hours. Historical quarter-hour shadow billing
therefore cannot use Home Assistant before the recent retention boundary; the
hourly series is suitable for hourly external reconciliation only.

## Counter-quality handling

The exporter derives energy from timestamp-adjacent cumulative states rather
than trusting the reported `change` field. Identical chunk-seam rows are
collapsed. Gaps, counter decreases and unusable deltas remain null.

PV contained four transient counter drops followed by four recoveries to the
prior cumulative range. Both sides of those events are excluded rather than
counted as energy. The PV series also contained `101` reported-change
mismatches; cumulative-state deltas remain authoritative and each mismatch is
flagged.

## Fluvius grid reconciliation

The common hourly overlap is `2026-01-22T00:00:00Z` through
`2026-05-31T22:00:00Z`:

- expected and comparable hours: `3,118`;
- Home Assistant unusable hours in the overlap: `0`;
- incomplete Fluvius hours: `0`;
- hours containing at least one estimated Fluvius quarter: `2`;
- hours containing only read Fluvius quarters: `3,116`.

Across all comparable hours, Home Assistant grid import is `3,091.552 kWh`
versus `3,091.556 kWh` in Fluvius, a difference of `-0.004 kWh`
(`-0.000129%`). Grid export is `503.942 kWh` in both datasets at the reported
precision.

After excluding the two hours that contain estimated Fluvius quarters, import
is `3,091.508 kWh` in Home Assistant versus `3,091.511 kWh` in Fluvius, a
`-0.003 kWh` difference (`-0.000097%`). Export is `503.931 kWh` in both
datasets at the reported precision.

## Conclusion

The hourly Home Assistant grid counters reconcile with the independent
Fluvius export within rounding precision for the full common overlap. The
historical grid series is accepted for read-only hourly reconciliation. It does
not recreate missing historical quarter-hours and does not replace Fluvius as
the quarter-hour billing source.
