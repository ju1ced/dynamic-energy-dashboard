import assert from "node:assert/strict";
import test from "node:test";
import { buildDayCourseQuery, chargingBlocks, dayCourseChart, renderDayCourse, DEFAULT_EV_ASSUMPTIONS } from "../../web-dashboard/day-course-view.js";

const automation = {
  name: "Nacht", enabled: true, target: "joint", max_grid_import_kw: 7,
  price_ceiling_eur_per_kwh: 0.2, ev_target_soc_percent: 80, ev_departure_time: "07:30", days: [1, 2, 3],
};

function interval(index, evKw, overrides = {}) {
  const start = Date.UTC(2026, 9, 19, 22, 0) + index * 900000;
  const local = new Date(start + 2 * 3600000).toISOString().slice(0, 19) + "+02:00";
  return {
    start_utc: new Date(start).toISOString(), start_local: local, duration_hours: 0.25,
    import_rate_eur_per_kwh: 0.3, export_rate_eur_per_kwh: 0.05, house_net_kw: 0.5, battery_kw: 0,
    battery_action: "HOLD", battery_reason: "test <b>", ev_kw: evKw, ev_reason: "Goedkoopste", grid_net_kw: 0.5 + evKw,
    over_limit: false, ...overrides,
  };
}

function course(intervals) {
  return {
    parameters: { ...automation, ev_departure_time: "07:30", ev_enabled: true },
    plan: { target_date: "2026-10-20", generated_at: "2026-10-19T21:00:00+00:00", interval_count: intervals.length },
    assumptions: ["a"], warnings: ["PRICE_CEILING_BLOCKS_TARGET"],
    summary: {
      ev_needed_kwh: 36, ev_planned_kwh: 6, ev_unmet_kwh: 30, ev_target_reached: false, ev_end_soc_percent: 30,
      ev_blocked_intervals: { CEILING: 3, LIMIT: 0 }, required_price_ceiling_eur_per_kwh: 0.3,
      cost_no_control_eur: 5, cost_battery_only_eur: 4, cost_with_ev_eur: 6, ev_cost_eur: 2,
      ev_cost_unmanaged_eur: 3, ev_saving_vs_unmanaged_eur: 1, peak_grid_import_kw: 6, peak_grid_import_unmanaged_kw: 8,
      over_limit_intervals: 0, over_limit_intervals_unmanaged: 4,
    },
    intervals,
  };
}

test("query builder maps the automation and EV assumptions", () => {
  const params = new URLSearchParams(buildDayCourseQuery(automation, DEFAULT_EV_ASSUMPTIONS));
  assert.equal(params.get("max_grid_import_kw"), "7");
  assert.equal(params.get("ev_enabled"), "true");
  assert.equal(params.get("active_days"), "1,2,3");
  assert.equal(params.get("ev_capacity_kwh"), "60");
  assert.equal(new URLSearchParams(buildDayCourseQuery({ ...automation, target: "battery" })).get("ev_enabled"), "false");
});

test("consecutive charging quarters merge into one block", () => {
  const rows = [interval(0, 0), interval(1, 5), interval(2, 5), interval(3, 0), interval(4, 3)];
  const blocks = chargingBlocks(rows);
  assert.equal(blocks.length, 2);
  assert.ok(Math.abs(blocks[0].kwh - 2.5) < 1e-9);
});

test("chart escapes tooltip text and renders one hover target per quarter", () => {
  const rows = Array.from({ length: 96 }, (_, i) => interval(i, i === 5 ? 4 : 0));
  const html = dayCourseChart(course(rows));
  assert.equal((html.match(/class="dc-hover"/g) || []).length, 96);
  assert.ok(!html.includes("<b>"));
  assert.ok(html.includes("&lt;b&gt;"));
});

test("view shows warnings, and an error state without a course", () => {
  const rows = Array.from({ length: 96 }, (_, i) => interval(i, 0));
  const ready = renderDayCourse({ status: "ready", course: course(rows), automation, assumptions: DEFAULT_EV_ASSUMPTIONS });
  assert.ok(ready.includes("prijsplafond is te laag"));
  const failed = renderDayCourse({ status: "error", error: { status: "PLAN_UNAVAILABLE", errors: ["PLAN_UNAVAILABLE"] }, automation, assumptions: DEFAULT_EV_ASSUMPTIONS });
  assert.ok(failed.includes("geen leesbaar shadow-plan"));
});
