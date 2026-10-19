import test from "node:test";
import assert from "node:assert/strict";

import { currentDayAheadView } from "../../web-dashboard/day-ahead-view.js";

function feed(overrides = {}) {
  return {
    source: { retrieved_at: "2026-10-06T08:00:00Z" },
    quality: { stale: false, status: "COMPLETE" },
    coverage: { upcoming_interval_count: 3 },
    upcoming_intervals: [
      { start_utc: "2026-10-06T08:00:00Z" },
      { start_utc: "2026-10-06T08:15:00Z" },
      { start_utc: "2026-10-06T08:30:00Z" },
    ],
    ...overrides,
  };
}

test("elapsed quarters are removed from every current view count", () => {
  const view = currentDayAheadView(feed(), Date.parse("2026-10-06T08:16:00Z"));

  assert.deepEqual(view.upcoming_intervals.map(row => row.start_utc), [
    "2026-10-06T08:30:00Z",
  ]);
  assert.equal(view.coverage.upcoming_interval_count, 1);
});

test("quarter-boundary snapshots change atomically around the boundary", () => {
  const before = currentDayAheadView(feed(), Date.parse("2026-10-06T08:14:59.999Z"));
  const after = currentDayAheadView(feed(), Date.parse("2026-10-06T08:15:00.001Z"));

  assert.equal(before.coverage.upcoming_interval_count, 2);
  assert.equal(after.coverage.upcoming_interval_count, 1);
});

test("a feed older than 36 hours is stale and suppresses current metrics", () => {
  const view = currentDayAheadView(feed(), Date.parse("2026-10-07T20:00:01Z"));

  assert.equal(view.quality.status, "STALE");
  assert.equal(view.quality.stale, true);
  assert.deepEqual(view.upcoming_intervals, []);
  assert.equal(view.coverage.upcoming_interval_count, 0);
});

test("invalid retrieval timestamps fail closed as stale", () => {
  const view = currentDayAheadView(
    feed({ source: { retrieved_at: "not-a-timestamp" } }),
    Date.parse("2026-10-06T08:16:00Z"),
  );

  assert.equal(view.quality.status, "STALE");
  assert.deepEqual(view.upcoming_intervals, []);
});
