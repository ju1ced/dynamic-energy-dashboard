# ADR-004: Preserve unavailable auction issue time as null

Status: Accepted  
Date: 2026-09-30  
Tickets: P2-004, P2-005

## Context

The ENTSO-E Day-Ahead response contains document creation metadata but does not
provide a field that has been proven to be the original auction publication
instant. Renaming `createdDateTime` to auction issue time would create false
precision.

Historical shadow billing needs delivery intervals, market area, prices,
resolution and source-version metadata. It does not need to reconstruct what a
controller knew at a particular historical decision instant. Forecast-quality
and decision-replay work does require true issue-time semantics.

## Decision

- Store `market_issue_time` explicitly as `null` when the source does not prove
  the original auction publication instant.
- Keep `document_created_at` and `retrieved_at` as separate metadata.
- Report `market_issue_time_available: false` in quality evidence.
- Permit the validated historical price dataset to feed offline shadow billing.
- Keep as-known-at-time forecast evaluation and decision replay under P2-005
  until a source with reliable issue-time metadata is implemented.

## Consequences

P2-004 can close after independent official price validation because the
missing issue time is represented honestly rather than inferred. The dataset
must not be presented as suitable for historical forecast-replay or causal
controller evaluation.
