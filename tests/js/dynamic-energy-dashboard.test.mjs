import test from "node:test";
import assert from "node:assert/strict";

import {
  buildSnapshot,
  getCurrentPlanInterval,
  readEntity,
  toKilowatts,
} from "../../dist/dynamic-energy-dashboard.js";

function state(value, unit, updated = "2026-10-02T10:00:00Z", attributes = {}) {
  return {
    state: String(value),
    last_updated: updated,
    attributes: { unit_of_measurement: unit, ...attributes },
  };
}

test("power values are normalized to kW", () => {
  assert.equal(toKilowatts(state(2500, "W")), 2.5);
  assert.equal(toKilowatts(state(2.5, "kW")), 2.5);
  assert.equal(toKilowatts(state("unavailable", "W")), null);
});

test("missing and stale entities remain visible quality states", () => {
  const now = new Date("2026-10-02T10:30:00Z");
  const hass = {
    states: {
      "sensor.grid": state(1200, "W", "2026-10-02T10:00:00Z"),
    },
  };

  assert.equal(readEntity(hass, "sensor.missing", now, 10).quality, "MISSING");
  assert.equal(readEntity(hass, "sensor.grid", now, 10).quality, "STALE");
});

test("invalid required numeric states cannot report healthy tracking", () => {
  const updated = "2026-10-02T10:19:30Z";
  const snapshot = buildSnapshot(
    {
      states: {
        "sensor.grid": state("not-a-number", "W", updated),
        "sensor.pv": state(800, "W", updated),
        "sensor.battery": state(0, "W", updated),
        "sensor.soc": state(58, "%", updated),
      },
    },
    {
      grid_power_entity: "sensor.grid",
      pv_power_entity: "sensor.pv",
      battery_power_entity: "sensor.battery",
      battery_soc_entity: "sensor.soc",
    },
    new Date("2026-10-02T10:20:00Z"),
  );

  assert.equal(snapshot.status, "UNAVAILABLE_DATA");
  assert.equal(snapshot.live.gridKw, null);
  assert.deepEqual(snapshot.quality.live, [
    { key: "grid", entityId: "sensor.grid", quality: "INVALID" },
  ]);
});

test("invalid numeric states take precedence over stale timestamps", () => {
  const updated = "2026-10-02T09:00:00Z";
  const snapshot = buildSnapshot(
    {
      states: {
        "sensor.grid": state("not-a-number", "W", updated),
        "sensor.pv": state(800, "W", updated),
        "sensor.battery": state(0, "W", updated),
        "sensor.soc": state(58, "%", updated),
      },
    },
    {
      grid_power_entity: "sensor.grid",
      pv_power_entity: "sensor.pv",
      battery_power_entity: "sensor.battery",
      battery_soc_entity: "sensor.soc",
      stale_after_minutes: 10,
    },
    new Date("2026-10-02T10:20:00Z"),
  );

  assert.equal(snapshot.status, "UNAVAILABLE_DATA");
  assert.deepEqual(snapshot.quality.live[0], {
    key: "grid",
    entityId: "sensor.grid",
    quality: "INVALID",
  });
});

test("the current quarter plan is selected by absolute timestamps", () => {
  const plan = state("planned", null, "2026-10-02T10:00:00Z", {
    schedule: [
      {
        start_utc: "2026-10-02T10:00:00Z",
        duration_hours: 0.25,
        action: "CHARGE_FROM_GRID",
      },
      {
        start_utc: "2026-10-02T10:15:00Z",
        duration_hours: 0.25,
        action: "HOLD",
      },
    ],
  });

  const selected = getCurrentPlanInterval(
    plan,
    "schedule",
    new Date("2026-10-02T10:20:00Z"),
  );
  assert.equal(selected.action, "HOLD");
});

test("snapshot combines live flow, peak headroom and plan deviation", () => {
  const now = new Date("2026-10-02T10:20:00Z");
  const hass = {
    states: {
      "sensor.grid": state(4200, "W", "2026-10-02T10:19:30Z"),
      "sensor.pv": state(1800, "W", "2026-10-02T10:19:30Z"),
      "sensor.battery": state(500, "W", "2026-10-02T10:19:30Z"),
      "sensor.soc": state(58, "%", "2026-10-02T10:19:30Z"),
      "sensor.plan": state("planned", null, "2026-10-02T10:15:00Z", {
        mode: "READ_ONLY_SHADOW",
        schedule: [
          {
            start_utc: "2026-10-02T10:15:00Z",
            duration_hours: 0.25,
            action: "CHARGE_FROM_GRID",
            reason: "LOW_PRICE; headroom remains",
            planned_grid_import_kw: 3.5,
            charge_kwh: 0.25,
          },
        ],
      }),
    },
  };

  const snapshot = buildSnapshot(
    hass,
    {
      grid_power_entity: "sensor.grid",
      pv_power_entity: "sensor.pv",
      battery_power_entity: "sensor.battery",
      battery_soc_entity: "sensor.soc",
      plan_entity: "sensor.plan",
      plan_attribute: "schedule",
      peak_limit_kw: 7,
      stale_after_minutes: 10,
      grid_import_positive: true,
      battery_charge_positive: true,
    },
    now,
  );

  assert.equal(snapshot.live.gridKw, 4.2);
  assert.equal(snapshot.live.houseKw, 5.5);
  assert.equal(snapshot.peak.headroomKw, 2.8);
  assert.equal(snapshot.plan.interval.action, "CHARGE_FROM_GRID");
  assert.ok(Math.abs(snapshot.plan.gridDeviationKw - 0.7) < 1e-9);
  assert.equal(snapshot.status, "DEVIATION");
  assert.equal(snapshot.readOnly, true);
});

test("snapshot stays useful when no plan entity is configured", () => {
  const states = {
    "sensor.grid": state(1200, "W", "2026-10-02T10:19:30Z"),
    "sensor.pv": state(800, "W", "2026-10-02T10:19:30Z"),
    "sensor.battery": state(0, "W", "2026-10-02T10:19:30Z"),
    "sensor.soc": state(58, "%", "2026-10-02T10:19:30Z"),
  };
  const snapshot = buildSnapshot(
    { states },
    {
      grid_power_entity: "sensor.grid",
      pv_power_entity: "sensor.pv",
      battery_power_entity: "sensor.battery",
      battery_soc_entity: "sensor.soc",
      peak_limit_kw: 7,
      stale_after_minutes: 10,
    },
    new Date("2026-10-02T10:20:00Z"),
  );

  assert.equal(snapshot.status, "DATA_GATED");
  assert.equal(snapshot.plan.interval, null);
  assert.equal(snapshot.readOnly, true);
});
