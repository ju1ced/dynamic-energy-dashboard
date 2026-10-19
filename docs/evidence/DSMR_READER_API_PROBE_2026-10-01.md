# DSMR Reader API Probe — 2026-10-01

## Classification

`VERIFIED_READ_ONLY_API_PROBE`

## Result

The configured DSMR Reader v2 electricity endpoint accepted an authenticated
read-only GET request. The probe did not print or store the API key or any
measurement values.

Observed API metadata:

- `144.254` electricity records;
- default page size: `25` records;
- pagination link available;
- oldest observed timestamp: `2020-12-19T12:33:00+01:00`;
- newest observed timestamp: `2026-10-01T06:46:00+02:00`;
- cumulative delivered and returned registers are available;
- current delivered and returned power are available;
- per-phase delivered power, returned power, current and voltage are available.

The oldest two ordered records were not adjacent. The start timestamp proves
that records exist from 2020, but it does not prove continuous coverage from
that date. Completeness must be measured mechanically during export.

## Engineering consequences

- Fetch every API page; a successful first page is not a complete export.
- Derive interval energy primarily from adjacent cumulative delivered/returned
  registers.
- Canonicalize timestamps in UTC before aggregation and retain local Belgian
  timestamps for display.
- Preserve source gaps rather than filling them.
- Store full household profiles only below Git-ignored `data/raw/`.
- Reconcile a DSMR export against the existing Fluvius and Home Assistant grid
  datasets before using it in battery scenarios.

## Security

The private endpoint and API key remain in the Git-ignored `.env`. The committed
probe evidence contains no credential, private network address or meter value.
