export function currentDayAheadView(feed, nowMs = Date.now()) {
  const retrievedAtMs = Date.parse(feed?.source?.retrieved_at);
  const stale = feed?.quality?.stale === true
    || !Number.isFinite(retrievedAtMs)
    || nowMs - retrievedAtMs > 36 * 60 * 60 * 1000;
  const upcoming = stale
    ? []
    : (feed?.upcoming_intervals || []).filter(row => Date.parse(row.start_utc) >= nowMs);
  return {
    ...feed,
    upcoming_intervals: upcoming,
    coverage: { ...feed.coverage, upcoming_interval_count: upcoming.length },
    quality: { ...feed.quality, stale, status: stale ? "STALE" : feed.quality.status },
  };
}
