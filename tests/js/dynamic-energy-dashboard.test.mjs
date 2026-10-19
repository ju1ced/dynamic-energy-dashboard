import test from "node:test";
import assert from "node:assert/strict";

import {
  buildSnapshot,
  DynamicEnergyShadowCard,
  getCurrentPlanInterval,
  getEntityPriceIntervals,
  getUpcomingPriceIntervals,
  readEntity,
  renderDailyPriceGraph,
  renderPriceAggregates,
  renderPriceTimeline,
  toKilowatts,
} from "../../dist/dynamic-energy-dashboard.js";

function state(value, unit, updated = "2026-10-02T10:00:00Z", attributes = {}) {
  return {
    state: String(value),
    last_updated: updated,
    attributes: { unit_of_measurement: unit, ...attributes },
  };
}

function hostilePrimitive() {
  return {
    [Symbol.toPrimitive]() { throw new Error("hostile primitive"); },
    toString() { throw new Error("hostile string"); },
  };
}

test("telemetry freshness prefers Home Assistant last_reported for unchanged measurements", () => {
  const reading = readEntity({ states: {
    "sensor.battery": {
      ...state(0, "W", "2026-10-19T00:49:22Z"),
      last_reported: "2026-10-19T08:44:00Z",
    },
  } }, "sensor.battery", new Date("2026-10-19T08:44:15Z"), 10, true);

  assert.equal(reading.quality, "GOOD");
  assert.equal(reading.ageMinutes, 0.25);
});

test("telemetry freshness falls back when last_reported is invalid or future dated", () => {
  for (const lastReported of ["not-a-date", "2026-10-19T09:30:00Z"]) {
    const reading = readEntity({ states: {
      "sensor.battery": {
        ...state(0, "W", "2026-10-19T08:43:00Z"),
        last_reported: lastReported,
      },
    } }, "sensor.battery", new Date("2026-10-19T08:44:15Z"), 10, true);

    assert.equal(reading.quality, "GOOD");
    assert.equal(reading.ageMinutes, 1.25);
  }
});

test("shadow card ignores Home Assistant updates unrelated to its configured entities", () => {
  const card = new DynamicEnergyShadowCard();
  let renderCount = 0;
  card._render = () => { renderCount += 1; };
  card.setConfig({
    grid_power_entity: "sensor.grid",
    pv_power_entity: "sensor.pv",
    battery_power_entity: "sensor.battery",
    battery_soc_entity: "sensor.soc",
    plan_entity: "sensor.plan",
  });
  const relevantStates = {
    "sensor.grid": state(1200, "W"),
    "sensor.pv": state(800, "W"),
    "sensor.battery": state(0, "W"),
    "sensor.soc": state(58, "%"),
    "sensor.plan": state("planned", null),
  };

  card.hass = { states: { ...relevantStates, "sensor.unrelated": state(1, "") } };
  card.hass = { states: { ...relevantStates, "sensor.unrelated": state(2, "") } };

  assert.equal(renderCount, 2);

  card.hass = {
    states: {
      ...relevantStates,
      "sensor.grid": state(1400, "W"),
    },
  };
  assert.equal(renderCount, 3);
});

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

test("future prices remain visible without a valid battery plan", () => {
  const now = new Date("2026-10-02T10:20:00Z");
  const plan = state("NO_ACTION", null, "2026-10-02T10:15:00Z", {
    prices: [
      {
        start_utc: "2026-10-02T10:15:00Z",
        duration_hours: 0.25,
        market_eur_per_mwh: 80,
        import_eur_per_kwh: 0.12,
      },
      {
        start_utc: "2026-10-02T10:30:00Z",
        duration_hours: 0.25,
        market_eur_per_mwh: 50,
        import_eur_per_kwh: 0.08,
      },
    ],
    price_reference_eur_per_kwh: 0.277,
  });

  const prices = getUpcomingPriceIntervals(plan, "prices", now);

  assert.equal(prices.length, 2);
  assert.equal(prices[0].importEurPerKwh, 0.12);
  assert.equal(prices[1].importEurPerKwh, 0.08);
});

test("Ecopower Dynamic data attributes provide future import and injection prices", () => {
  const now = new Date("2026-10-07T10:00:00Z");
  const importState = state(0.12, "EUR/kWh", "2026-10-07T09:59:00Z", {
    data: [
      { start_time: "2026-10-07T10:00:00Z", end_time: "2026-10-07T10:15:00Z", price_per_kwh: 0.12 },
      { start_time: "2026-10-07T10:15:00Z", end_time: "2026-10-07T10:30:00Z", price_per_kwh: 0.08 },
    ],
  });
  const exportState = state(0.04, "EUR/kWh", "2026-10-07T09:59:00Z", {
    data: [
      { start_time: "2026-10-07T10:00:00Z", end_time: "2026-10-07T10:15:00Z", price_per_kwh: 0.04 },
      { start_time: "2026-10-07T10:15:00Z", end_time: "2026-10-07T10:30:00Z", price_per_kwh: 0.02 },
    ],
  });

  const prices = getEntityPriceIntervals(importState, exportState, "data", now);

  assert.equal(prices.length, 2);
  assert.equal(prices[0].importEurPerKwh, 0.12);
  assert.equal(prices[0].exportEurPerKwh, 0.04);
  assert.equal(prices[1].importEurPerKwh, 0.08);
  assert.equal(prices[1].exportEurPerKwh, 0.02);
});

test("daily price data retains elapsed quarters for the full-day graph", () => {
  const now = new Date("2026-10-07T10:20:00Z");
  const importState = state(0.08, "EUR/kWh", "2026-10-07T10:19:00Z", {
    data: [
      { start_time: "2026-10-07T10:00:00Z", end_time: "2026-10-07T10:15:00Z", price_per_kwh: 0.12 },
      { start_time: "2026-10-07T10:15:00Z", end_time: "2026-10-07T10:30:00Z", price_per_kwh: 0.08 },
    ],
  });

  const futureOnly = getEntityPriceIntervals(importState, null, "data", now);
  const completeDay = getEntityPriceIntervals(importState, null, "data", now, true);

  assert.equal(futureOnly.length, 1);
  assert.equal(completeDay.length, 2);
  assert.equal(completeDay[0].importEurPerKwh, 0.12);
});

test("EPEX and Ecopower identical duplicate rows are collapsed", () => {
  const now = new Date("2026-10-12T08:00:00+02:00");
  const importRow = {
    start_time: "2026-10-12T08:00:00+02:00",
    end_time: "2026-10-12T08:15:00+02:00",
    price_per_kwh: 0.23641,
  };
  const exportRow = { ...importRow, price_per_kwh: 0.1167 };
  const importState = state(0.23641, "EUR/kWh", "2026-10-12T07:59:00+02:00", {
    data: [importRow, { ...importRow }],
  });
  const exportState = state(0.1167, "EUR/kWh", "2026-10-12T07:59:00+02:00", {
    data: [exportRow, { ...exportRow }],
  });

  const prices = getEntityPriceIntervals(importState, exportState, "data", now);

  assert.equal(prices.length, 1);
  assert.equal(prices[0].importEurPerKwh, 0.23641);
  assert.equal(prices[0].exportEurPerKwh, 0.1167);
});

test("price entities supply the timeline when the shadow entity has no price attribute", () => {
  const now = new Date("2026-10-07T10:05:00Z");
  const updated = "2026-10-07T10:04:30Z";
  const futureData = [{
    start_time: "2026-10-07T10:00:00Z",
    end_time: "2026-10-07T10:15:00Z",
    price_per_kwh: 0.12,
  }];
  const snapshot = buildSnapshot(
    {
      states: {
        "sensor.grid": state(1200, "W", updated),
        "sensor.pv": state(800, "W", updated),
        "sensor.battery": state(0, "W", updated),
        "sensor.soc": state(58, "%", updated),
        "sensor.plan": state("NO_ACTION", null, updated, { schedule: [] }),
        "sensor.ecopower_import": state(0.12, "EUR/kWh", updated, { data: futureData }),
        "sensor.ecopower_export": state(0.04, "EUR/kWh", updated, {
          data: [{ ...futureData[0], price_per_kwh: 0.04 }],
        }),
      },
    },
    {
      grid_power_entity: "sensor.grid",
      pv_power_entity: "sensor.pv",
      battery_power_entity: "sensor.battery",
      battery_soc_entity: "sensor.soc",
      plan_entity: "sensor.plan",
      import_price_entity: "sensor.ecopower_import",
      export_price_entity: "sensor.ecopower_export",
      integration_price_attribute: "data",
    },
    now,
  );

  assert.equal(snapshot.prices.intervals.length, 1);
  assert.equal(snapshot.prices.intervals[0].importEurPerKwh, 0.12);
  assert.equal(snapshot.prices.intervals[0].exportEurPerKwh, 0.04);
  assert.equal(snapshot.prices.source, "Home Assistant price entities");
});

test("stale price entities do not publish a future timeline", () => {
  const now = new Date("2026-10-07T10:05:00Z");
  const stale = "2026-10-07T08:00:00Z";
  const snapshot = buildSnapshot(
    {
      states: {
        "sensor.grid": state(1200, "W", "2026-10-07T10:04:30Z"),
        "sensor.pv": state(800, "W", "2026-10-07T10:04:30Z"),
        "sensor.battery": state(0, "W", "2026-10-07T10:04:30Z"),
        "sensor.soc": state(58, "%", "2026-10-07T10:04:30Z"),
        "sensor.plan": state("NO_ACTION", null, "2026-10-07T10:04:30Z", { schedule: [] }),
        "sensor.ecopower_import": state(0.12, "EUR/kWh", stale, {
          data: [{ start_time: "2026-10-07T10:00:00Z", end_time: "2026-10-07T10:15:00Z", price_per_kwh: 0.12 }],
        }),
      },
    },
    {
      grid_power_entity: "sensor.grid",
      pv_power_entity: "sensor.pv",
      battery_power_entity: "sensor.battery",
      battery_soc_entity: "sensor.soc",
      plan_entity: "sensor.plan",
      import_price_entity: "sensor.ecopower_import",
      stale_after_minutes: 10,
    },
    now,
  );

  assert.deepEqual(snapshot.prices.intervals, []);
  assert.equal(snapshot.prices.source, null);
});

test("quarter prices remain available between ten and twenty minutes after a price update", () => {
  const now = new Date("2026-10-19T06:44:15Z");
  const liveUpdated = "2026-10-19T06:44:00Z";
  const priceUpdated = "2026-10-19T06:30:00Z";
  const snapshot = buildSnapshot({ states: {
    "sensor.grid": state(4574, "W", liveUpdated),
    "sensor.pv": state(0, "W", liveUpdated),
    "sensor.battery": state(0, "W", liveUpdated),
    "sensor.soc": state(0, "%", liveUpdated),
    "sensor.plan": state("PLANNED", null, liveUpdated, { schedule: [] }),
    "sensor.import": state(0.4316, "EUR/kWh", priceUpdated, {
      data: [{
        start_time: "2026-10-19T08:30:00+02:00",
        end_time: "2026-10-19T08:45:00+02:00",
        price_per_kwh: 0.4316,
      }],
    }),
  } }, {
    grid_power_entity: "sensor.grid",
    pv_power_entity: "sensor.pv",
    battery_power_entity: "sensor.battery",
    battery_soc_entity: "sensor.soc",
    plan_entity: "sensor.plan",
    import_price_entity: "sensor.import",
    stale_after_minutes: 10,
  }, now);

  assert.equal(snapshot.prices.source, "Home Assistant price entities");
  assert.equal(snapshot.prices.intervals.length, 1);
  assert.equal(snapshot.live.importPriceEurPerKwh, 0.4316);
});

test("plan price timeline supplies the current price when no price entity is configured", () => {
  const now = new Date("2026-10-02T10:20:00Z");
  const updated = "2026-10-02T10:19:30Z";
  const snapshot = buildSnapshot(
    {
      states: {
        "sensor.grid": state(1200, "W", updated),
        "sensor.pv": state(800, "W", updated),
        "sensor.battery": state(0, "W", updated),
        "sensor.soc": state(58, "%", updated),
        "sensor.plan": state("NO_ACTION", null, updated, {
          prices: [
            {
              start_utc: "2026-10-02T10:15:00Z",
              duration_hours: 0.25,
              market_eur_per_mwh: 80,
              import_eur_per_kwh: 0.12,
            },
          ],
          price_reference_eur_per_kwh: 0.277,
        }),
      },
    },
    {
      grid_power_entity: "sensor.grid",
      pv_power_entity: "sensor.pv",
      battery_power_entity: "sensor.battery",
      battery_soc_entity: "sensor.soc",
      plan_entity: "sensor.plan",
    },
    now,
  );

  assert.equal(snapshot.live.importPriceEurPerKwh, 0.12);
  assert.equal(snapshot.prices.referenceEurPerKwh, 0.277);
  assert.equal(snapshot.prices.intervals.length, 1);
});

test("price timeline renders quarter prices reference and planned actions", () => {
  const html = renderPriceTimeline(
    [
      {
        startUtc: "2026-10-02T10:15:00.000Z",
        endUtc: "2026-10-02T10:30:00.000Z",
        importEurPerKwh: 0.12,
        marketEurPerMwh: 80,
      },
      {
        startUtc: "2026-10-02T10:30:00.000Z",
        endUtc: "2026-10-02T10:45:00.000Z",
        importEurPerKwh: 0.31,
        marketEurPerMwh: 250,
      },
    ],
    [
      {
        start_utc: "2026-10-02T10:30:00Z",
        action: "CHARGE_FROM_GRID",
      },
    ],
    0.277,
  );

  assert.match(html, /Komende kwartierprijzen/);
  assert.match(html, /€0,120/);
  assert.match(html, /€0,310/);
  assert.match(html, /€0,277/);
  assert.match(html, /Laden vanaf net/);
  assert.match(html, /data-price-scroll-by="-1"/);
  assert.match(html, /data-price-scroll-by="1"/);
  assert.match(html, /aria-label="Eerdere kwartierprijzen"/);
});

test("daily price graph groups quarter prices by local day without horizontal scrolling", () => {
  const intervals = Array.from({ length: 100 }, (_, index) => {
    const start = new Date(Date.parse("2026-10-24T22:00:00Z") + index * 900000);
    return {
      startUtc: start.toISOString(),
      endUtc: new Date(start.getTime() + 900000).toISOString(),
      importEurPerKwh: 0.08 + index * 0.001,
      exportEurPerKwh: 0.03,
      marketEurPerMwh: null,
    };
  });

  const html = renderDailyPriceGraph(intervals, 0.277);

  assert.match(html, /Kwartierprijzen per dag/);
  assert.match(html, /data-quarter-count="100"/);
  assert.match(html, /<svg/);
  assert.match(html, /price-reference-line/);
  assert.match(html, /€0,080–€0,179\/kWh/);
  assert.match(html, /data-axis-hour="6" style="left:28\.00%"/);
  assert.doesNotMatch(html, /price-scroll/);
  assert.equal((html.match(/class="price-bar /g) || []).length, 100);
});

test("daily price graph positions local-time markers correctly on a 92-quarter DST day", () => {
  const intervals = Array.from({ length: 92 }, (_, index) => {
    const start = new Date(Date.parse("2027-03-27T23:00:00Z") + index * 900000);
    return {
      startUtc: start.toISOString(),
      endUtc: new Date(start.getTime() + 900000).toISOString(),
      importEurPerKwh: 0.1,
    };
  });

  const html = renderDailyPriceGraph(intervals, 0.277);

  assert.match(html, /data-quarter-count="92"/);
  assert.match(html, /data-axis-hour="6" style="left:21\.74%"/);
  assert.match(html, /data-axis-hour="12" style="left:47\.83%"/);
  assert.match(html, /data-axis-hour="18" style="left:73\.91%"/);
});

test("daily price graph renders an ordinary 96-quarter day", () => {
  const intervals = Array.from({ length: 96 }, (_, index) => {
    const start = new Date(Date.parse("2026-10-14T22:00:00Z") + index * 900000);
    return {
      startUtc: start.toISOString(),
      endUtc: new Date(start.getTime() + 900000).toISOString(),
      importEurPerKwh: 0.1,
    };
  });

  const html = renderDailyPriceGraph(intervals, 0.277);

  assert.match(html, /data-quarter-count="96"/);
  assert.match(html, /data-axis-hour="6" style="left:25\.00%"/);
  assert.match(html, /data-axis-hour="12" style="left:50\.00%"/);
  assert.match(html, /data-axis-hour="18" style="left:75\.00%"/);
});

test("daily price graph bounds long feeds to the three latest days", () => {
  const intervals = Array.from({ length: 96 * 5 }, (_, index) => {
    const start = new Date(Date.parse("2026-10-10T22:00:00Z") + index * 900000);
    return {
      startUtc: start.toISOString(),
      endUtc: new Date(start.getTime() + 900000).toISOString(),
      importEurPerKwh: 0.1 + index * 0.0001,
    };
  });

  const html = renderDailyPriceGraph(intervals, 0.277);

  assert.equal((html.match(/class="price-day-chart"/g) || []).length, 3);
  assert.doesNotMatch(html, /data-day="2026-10-11"/);
  assert.match(html, /data-day="2026-10-15"/);
});

test("price aggregates render day week and month comparisons", () => {
  const html = renderPriceAggregates({
    daily: [{ period: "2026-10-08", average_eur_per_kwh: 0.18, difference_vs_reference_eur_per_kwh: -0.097, partial_period: false }],
    weekly: [{ period: "2026-W41", average_eur_per_kwh: 0.21, difference_vs_reference_eur_per_kwh: -0.067, partial_period: true }],
    monthly: [{ period: "2026-10", average_eur_per_kwh: 0.24, difference_vs_reference_eur_per_kwh: -0.037, partial_period: true }],
  }, 0.277);

  assert.match(html, /Dag/);
  assert.match(html, /Week/);
  assert.match(html, /Maand/);
  assert.match(html, /€0,180/);
  assert.match(html, /partieel/);
});

test("price timeline renders signed export prices and disambiguates repeated DST hours", () => {
  const html = renderPriceTimeline(
    [
      { startUtc: "2026-10-25T00:00:00.000Z", endUtc: "2026-10-25T00:15:00.000Z", importEurPerKwh: 0.1, exportEurPerKwh: -0.02, marketEurPerMwh: -25 },
      { startUtc: "2026-10-25T01:00:00.000Z", endUtc: "2026-10-25T01:15:00.000Z", importEurPerKwh: 0.11, exportEurPerKwh: 0.01, marketEurPerMwh: 10 },
    ],
    [],
    0.277,
  );

  assert.match(html, /injectie €-0,020/);
  assert.match(html, /GMT\+2/);
  assert.match(html, /GMT\+1/);
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

test("malformed schedule and shadow-price rows fail closed without throwing", () => {
  const hostile = new Proxy({}, { get() { throw new Error("hostile getter"); } });
  const plan = state("planned", null, "2026-10-07T10:04:00Z", {
    schedule: [
      null, 7, "row", [], new Date(), hostile,
      { start_utc: "not-a-date", duration_hours: 0.25, action: "HOLD" },
      { start_utc: "2026-10-07T10:00:00Z", duration_hours: 0, action: "HOLD" },
    ],
    prices: [
      null, false, "row", hostile,
      { start_utc: "not-a-date", duration_hours: 0.25, import_eur_per_kwh: 0.1 },
      { start_utc: "2026-10-07T10:00:00Z", duration_hours: 0, import_eur_per_kwh: 0.1 },
    ],
  });
  const now = new Date("2026-10-07T10:05:00Z");

  assert.doesNotThrow(() => getCurrentPlanInterval(plan, "schedule", now));
  assert.equal(getCurrentPlanInterval(plan, "schedule", now), null);
  assert.doesNotThrow(() => getUpcomingPriceIntervals(plan, "prices", now));
  assert.deepEqual(getUpcomingPriceIntervals(plan, "prices", now), []);
});

test("duplicate schedule and shadow-price starts are rejected", () => {
  const plan = state("planned", null, "2026-10-07T10:04:00Z", {
    schedule: [
      { start_utc: "2026-10-07T10:00:00Z", duration_hours: 0.25, action: "HOLD" },
      { start_utc: "2026-10-07T10:00:00Z", duration_hours: 0.5, action: "CHARGE_FROM_GRID" },
    ],
    prices: [
      { start_utc: "2026-10-07T10:00:00Z", duration_hours: 0.25, import_eur_per_kwh: 0.1 },
      { start_utc: "2026-10-07T10:00:00Z", duration_hours: 0.5, import_eur_per_kwh: 0.2 },
    ],
  });
  const now = new Date("2026-10-07T10:05:00Z");

  assert.equal(getCurrentPlanInterval(plan, "schedule", now), null);
  assert.deepEqual(getUpcomingPriceIntervals(plan, "prices", now), []);
});

test("integration rows require plain objects valid intervals unique starts and price_per_kwh", () => {
  const hostile = new Proxy({}, { get() { throw new Error("hostile integration row"); } });
  const importState = state(0.12, "EUR/kWh", "2026-10-07T10:04:00Z", {
    data: [
      null, 12, hostile,
      { start_time: "bad", end_time: "2026-10-07T10:15:00Z", price_per_kwh: 0.12 },
      { start_time: "2026-10-07T10:00:00Z", end_time: "2026-10-07T10:00:00Z", price_per_kwh: 0.12 },
      { start_time: "2026-10-07T10:15:00Z", duration_hours: 0, price_per_kwh: 0.12 },
      { start_time: "2026-10-07T10:30:00Z", end_time: "2026-10-07T10:45:00Z", price: 0.12 },
      { start_time: "2026-10-07T10:45:00Z", end_time: "2026-10-07T11:00:00Z", value: 0.12 },
      { start_time: "2026-10-07T11:00:00Z", end_time: "2026-10-07T11:15:00Z", price_per_kwh: 0.11 },
      { start_time: "2026-10-07T11:00:00Z", end_time: "2026-10-07T11:30:00Z", price_per_kwh: 0.09 },
    ],
  });
  const exportState = state(0.04, "EUR/kWh", "2026-10-07T10:04:00Z", {
    data: [null, hostile, {
      start_time: "2026-10-07T11:00:00Z",
      end_time: "2026-10-07T11:15:00Z",
      price: 0.04,
    }],
  });
  const now = new Date("2026-10-07T10:05:00Z");

  assert.doesNotThrow(() => getEntityPriceIntervals(importState, exportState, "data", now));
  assert.deepEqual(getEntityPriceIntervals(importState, exportState, "data", now), []);
});

test("a stale shadow plan cannot suppress a fresh integration timeline", () => {
  const now = new Date("2026-10-07T10:05:00Z");
  const fresh = "2026-10-07T10:04:00Z";
  const snapshot = buildSnapshot({ states: {
    "sensor.grid": state(1000, "W", fresh),
    "sensor.pv": state(500, "W", fresh),
    "sensor.battery": state(0, "W", fresh),
    "sensor.soc": state(50, "%", fresh),
    "sensor.plan": state("planned", null, "2026-10-05T10:00:00Z", {
      prices: [{ start_utc: "2026-10-07T10:00:00Z", duration_hours: 1, import_eur_per_kwh: 0.99 }],
      price_source: "stale shadow",
    }),
    "sensor.import": state(0.12, "EUR/kWh", fresh, {
      data: [{ start_time: "2026-10-07T10:00:00Z", end_time: "2026-10-07T10:15:00Z", price_per_kwh: 0.12 }],
    }),
  } }, {
    grid_power_entity: "sensor.grid", pv_power_entity: "sensor.pv",
    battery_power_entity: "sensor.battery", battery_soc_entity: "sensor.soc",
    plan_entity: "sensor.plan", import_price_entity: "sensor.import",
    plan_stale_after_hours: 1,
  }, now);

  assert.equal(snapshot.prices.source, "Home Assistant price entities");
  assert.equal(snapshot.prices.intervals[0].importEurPerKwh, 0.12);
  assert.equal(snapshot.live.importPriceEurPerKwh, 0.12);
});

test("a recently re-reported old plan remains stale and cannot restore an action", () => {
  const now = new Date("2026-10-19T08:45:00Z");
  const plan = state("planned", null, "2026-10-16T08:45:00Z", {
    schedule: [{
      start: "2026-10-19T08:45:00Z",
      end: "2026-10-19T09:00:00Z",
      action: "CHARGE_FROM_GRID",
      reason: "LOW_PRICE",
      battery_power_kw: 3,
    }],
  });
  plan.last_reported = "2026-10-19T08:44:55Z";
  const snapshot = buildSnapshot({ states: {
    "sensor.grid": state(1, "kW", "2026-10-19T08:44:30Z"),
    "sensor.pv": state(0, "kW", "2026-10-19T08:44:30Z"),
    "sensor.battery": state(0, "kW", "2026-10-19T08:44:30Z"),
    "sensor.soc": state(50, "%", "2026-10-19T08:44:30Z"),
    "sensor.plan": plan,
  } }, {
    grid_power_entity: "sensor.grid",
    pv_power_entity: "sensor.pv",
    battery_power_entity: "sensor.battery",
    battery_soc_entity: "sensor.soc",
    plan_entity: "sensor.plan",
    plan_stale_after_hours: 30,
  }, now);

  assert.equal(snapshot.plan.quality, "STALE");
  assert.equal(snapshot.plan.action ?? null, null);
});

test("stale configured current price entities are never displayed", () => {
  const now = new Date("2026-10-07T10:05:00Z");
  const fresh = "2026-10-07T10:04:00Z";
  const snapshot = buildSnapshot({ states: {
    "sensor.grid": state(1000, "W", fresh),
    "sensor.pv": state(500, "W", fresh),
    "sensor.battery": state(0, "W", fresh),
    "sensor.soc": state(50, "%", fresh),
    "sensor.plan": state("planned", null, fresh, {
      prices: [{ start_utc: "2026-10-07T10:00:00Z", duration_hours: 0.25, import_eur_per_kwh: 0.18, export_eur_per_kwh: 0.03 }],
    }),
    "sensor.import": state(9.99, "EUR/kWh", "2026-10-07T08:00:00Z"),
    "sensor.export": state(8.88, "EUR/kWh", "2026-10-07T08:00:00Z"),
  } }, {
    grid_power_entity: "sensor.grid", pv_power_entity: "sensor.pv",
    battery_power_entity: "sensor.battery", battery_soc_entity: "sensor.soc",
    plan_entity: "sensor.plan", import_price_entity: "sensor.import",
    export_price_entity: "sensor.export", stale_after_minutes: 10,
  }, now);

  assert.equal(snapshot.live.importPriceEurPerKwh, 0.18);
  assert.equal(snapshot.live.exportPriceEurPerKwh, 0.03);
});

test("the source with better upcoming coverage wins without mixing metadata", () => {
  const now = new Date("2026-10-07T10:05:00Z");
  const fresh = "2026-10-07T10:04:00Z";
  const snapshot = buildSnapshot({ states: {
    "sensor.grid": state(1000, "W", fresh),
    "sensor.pv": state(500, "W", fresh),
    "sensor.battery": state(0, "W", fresh),
    "sensor.soc": state(50, "%", fresh),
    "sensor.plan": state("planned", null, fresh, {
      prices: [{ start_utc: "2026-10-07T10:00:00Z", duration_hours: 0.25, import_eur_per_kwh: 0.99 }],
      price_source: "shadow feed",
      price_tariff_version: "SHADOW_TARIFF",
      price_aggregates: { daily: [{ period: "shadow", average_eur_per_kwh: 0.99 }] },
    }),
    "sensor.import": state(0.12, "EUR/kWh", fresh, { data: [
      { start_time: "2026-10-07T10:00:00Z", end_time: "2026-10-07T10:15:00Z", price_per_kwh: 0.12 },
      { start_time: "2026-10-07T10:15:00Z", end_time: "2026-10-07T10:30:00Z", price_per_kwh: 0.08 },
    ] }),
  } }, {
    grid_power_entity: "sensor.grid", pv_power_entity: "sensor.pv",
    battery_power_entity: "sensor.battery", battery_soc_entity: "sensor.soc",
    plan_entity: "sensor.plan", import_price_entity: "sensor.import",
    price_reference_eur_per_kwh: 0.3,
  }, now);

  assert.equal(snapshot.prices.source, "Home Assistant price entities");
  assert.equal(snapshot.prices.tariffVersion, null);
  assert.deepEqual(snapshot.prices.aggregates, { daily: [], weekly: [], monthly: [] });
  assert.equal(snapshot.prices.referenceEurPerKwh, 0.3);
  assert.equal(snapshot.prices.intervals.length, 2);
  assert.equal(snapshot.live.importPriceEurPerKwh, 0.12);
});

test("configured reference overrides feed reference and aggregate differences are recomputed", () => {
  const html = renderPriceAggregates({ daily: [{
    period: "2026-10-07",
    average_eur_per_kwh: 0.18,
    difference_vs_reference_eur_per_kwh: -0.097,
    partial_period: false,
  }] }, 0.3);

  assert.match(html, /€-0,120 vs referentie/);
  assert.doesNotMatch(html, /€-0,097/);
});

test("aggregate rows reject null primitive duplicate invalid and hostile entries", () => {
  const hostile = new Proxy({}, { get() { throw new Error("hostile aggregate row"); } });
  const aggregates = {
    daily: [null, 2, hostile, { period: "", average_eur_per_kwh: 0.1 }, { period: "not-a-date", average_eur_per_kwh: 0.1 }, { period: "2026-10-07", average_eur_per_kwh: "bad" }],
    weekly: [{ period: "2026-W41", average_eur_per_kwh: 0.2 }, { period: "2026-W41", average_eur_per_kwh: 0.3 }],
    monthly: [{ period: "2026-10", average_eur_per_kwh: 0.25 }],
  };

  assert.doesNotThrow(() => renderPriceAggregates(aggregates, 0.3));
  const html = renderPriceAggregates(aggregates, 0.3);
  assert.doesNotMatch(html, /not-a-date/);
  assert.doesNotMatch(html, /2026-W41/);
  assert.match(html, /2026-10/);
});

test("malformed export intervals are rejected instead of being attached by start", () => {
  const now = new Date("2026-10-07T10:05:00Z");
  const importState = state(0.12, "EUR/kWh", "2026-10-07T10:04:00Z", {
    data: [{
      start_time: "2026-10-07T10:15:00Z",
      end_time: "2026-10-07T10:30:00Z",
      price_per_kwh: 0.12,
    }],
  });
  const exportState = state(0.04, "EUR/kWh", "2026-10-07T10:04:00Z", {
    data: [{
      start_time: "2026-10-07T10:15:00Z",
      end_time: "2026-10-07T10:15:00Z",
      price_per_kwh: 0.04,
    }],
  });

  const prices = getEntityPriceIntervals(importState, exportState, "data", now);
  assert.equal(prices.length, 1);
  assert.equal(prices[0].exportEurPerKwh, null);
});

test("an unavailable shadow entity cannot suppress a fresh integration source", () => {
  const now = new Date("2026-10-07T10:05:00Z");
  const fresh = "2026-10-07T10:04:00Z";
  const unavailablePlan = state("unavailable", null, fresh, {
    prices: [{ start_utc: "2026-10-07T10:00:00Z", duration_hours: 1, import_eur_per_kwh: 0.99 }],
  });
  const snapshot = buildSnapshot({ states: {
    "sensor.grid": state(1000, "W", fresh),
    "sensor.pv": state(500, "W", fresh),
    "sensor.battery": state(0, "W", fresh),
    "sensor.soc": state(50, "%", fresh),
    "sensor.plan": unavailablePlan,
    "sensor.import": state(0.12, "EUR/kWh", fresh, { data: [{
      start_time: "2026-10-07T10:00:00Z",
      end_time: "2026-10-07T10:15:00Z",
      price_per_kwh: 0.12,
    }] }),
  } }, {
    grid_power_entity: "sensor.grid", pv_power_entity: "sensor.pv",
    battery_power_entity: "sensor.battery", battery_soc_entity: "sensor.soc",
    plan_entity: "sensor.plan", import_price_entity: "sensor.import",
  }, now);

  assert.equal(snapshot.prices.source, "Home Assistant price entities");
  assert.equal(snapshot.live.importPriceEurPerKwh, 0.12);
});

test("a fresh shadow source wins when it has better coverage and keeps its metadata", () => {
  const now = new Date("2026-10-07T10:05:00Z");
  const fresh = "2026-10-07T10:04:00Z";
  const snapshot = buildSnapshot({ states: {
    "sensor.grid": state(1000, "W", fresh),
    "sensor.pv": state(500, "W", fresh),
    "sensor.battery": state(0, "W", fresh),
    "sensor.soc": state(50, "%", fresh),
    "sensor.plan": state("planned", null, fresh, {
      prices: [
        { start_utc: "2026-10-07T10:00:00Z", duration_hours: 0.25, import_eur_per_kwh: 0.18 },
        { start_utc: "2026-10-07T10:15:00Z", duration_hours: 0.25, import_eur_per_kwh: 0.16 },
      ],
      price_source: "validated shadow",
      price_tariff_version: "TARIFF_V2",
      price_reference_eur_per_kwh: 0.277,
      price_aggregates: { daily: [{ period: "2026-10-07", average_eur_per_kwh: 0.17 }] },
    }),
    "sensor.import": state(0.12, "EUR/kWh", fresh, { data: [{
      start_time: "2026-10-07T10:00:00Z",
      end_time: "2026-10-07T10:15:00Z",
      price_per_kwh: 0.12,
    }] }),
  } }, {
    grid_power_entity: "sensor.grid", pv_power_entity: "sensor.pv",
    battery_power_entity: "sensor.battery", battery_soc_entity: "sensor.soc",
    plan_entity: "sensor.plan", import_price_entity: "sensor.import",
    price_reference_eur_per_kwh: 0.3,
  }, now);

  assert.equal(snapshot.prices.source, "validated shadow");
  assert.equal(snapshot.prices.tariffVersion, "TARIFF_V2");
  assert.equal(snapshot.prices.referenceEurPerKwh, 0.3);
  assert.equal(snapshot.prices.aggregates.daily.length, 1);
  assert.equal(snapshot.live.importPriceEurPerKwh, 0.18);
});

test("timeline source metadata is selected and escaped", () => {
  const html = renderPriceTimeline(
    [{
      startUtc: "2026-10-07T10:00:00Z",
      endUtc: "2026-10-07T10:15:00Z",
      importEurPerKwh: 0.12,
      exportEurPerKwh: 0.04,
      marketEurPerMwh: null,
    }],
    [],
    0.3,
    "<img src=x onerror=alert(1)>",
    "TARIFF_V2",
  );

  assert.match(html, /&lt;img src=x onerror=alert\(1\)&gt; · TARIFF_V2/);
  assert.doesNotMatch(html, /<img/);
  assert.doesNotMatch(html, /ENTSO-E · Ecopower/);
});

test("hostile numeric and date property values never escape coercion guards", () => {
  const hostile = hostilePrimitive();
  const now = new Date("2026-10-07T10:05:00Z");
  const numericStates = [
    { state: hostile, attributes: { unit_of_measurement: "W" } },
    { state: 1000, attributes: { unit_of_measurement: hostile } },
  ];
  for (const stateObject of numericStates) {
    assert.doesNotThrow(() => toKilowatts(stateObject));
    assert.equal(toKilowatts(stateObject), null);
  }

  const hostileScheduleRows = [
    { start_utc: hostile, duration_hours: 0.25, action: "HOLD" },
    { start: hostile, duration_hours: 0.25, action: "HOLD" },
    { start_local: hostile, duration_hours: 0.25, action: "HOLD" },
    { start_utc: "2026-10-07T10:00:00Z", end_utc: hostile, action: "HOLD" },
    { start_utc: "2026-10-07T10:00:00Z", end: hostile, action: "HOLD" },
    { start_utc: "2026-10-07T10:00:00Z", duration_hours: hostile, action: "HOLD" },
  ];
  for (const row of hostileScheduleRows) {
    const plan = state("planned", null, "2026-10-07T10:04:00Z", { schedule: [row] });
    assert.doesNotThrow(() => getCurrentPlanInterval(plan, "schedule", now));
    assert.equal(getCurrentPlanInterval(plan, "schedule", now), null);
  }

  const hostilePriceRows = [
    { start_utc: hostile, duration_hours: 0.25, import_eur_per_kwh: 0.12 },
    { start: hostile, duration_hours: 0.25, import_eur_per_kwh: 0.12 },
    { start_utc: "2026-10-07T10:00:00Z", end_utc: hostile, duration_hours: 0.25, import_eur_per_kwh: 0.12 },
    { start_utc: "2026-10-07T10:00:00Z", end: hostile, duration_hours: 0.25, import_eur_per_kwh: 0.12 },
    ...["duration_hours", "import_eur_per_kwh", "market_eur_per_mwh", "export_eur_per_kwh"].map((field) => ({
      start_utc: "2026-10-07T10:00:00Z", duration_hours: 0.25, import_eur_per_kwh: 0.12, [field]: hostile,
    })),
  ];
  for (const row of hostilePriceRows) {
    const plan = state("planned", null, "2026-10-07T10:04:00Z", { prices: [row] });
    assert.doesNotThrow(() => getUpcomingPriceIntervals(plan, "prices", now));
    assert.deepEqual(getUpcomingPriceIntervals(plan, "prices", now), []);
  }

  const hostileIntegrationRows = [
    { start_time: hostile, end_time: "2026-10-07T10:15:00Z", price_per_kwh: 0.12 },
    { start_utc: hostile, end_time: "2026-10-07T10:15:00Z", price_per_kwh: 0.12 },
    { start: hostile, end_time: "2026-10-07T10:15:00Z", price_per_kwh: 0.12 },
    { start_time: "2026-10-07T10:00:00Z", end_time: hostile, price_per_kwh: 0.12 },
    { start_time: "2026-10-07T10:00:00Z", end_utc: hostile, price_per_kwh: 0.12 },
    { start_time: "2026-10-07T10:00:00Z", end: hostile, price_per_kwh: 0.12 },
    { start_time: "2026-10-07T10:00:00Z", duration_hours: hostile, price_per_kwh: 0.12 },
    { start_time: "2026-10-07T10:00:00Z", end_time: "2026-10-07T10:15:00Z", price_per_kwh: hostile },
  ];
  for (const row of hostileIntegrationRows) {
    const importState = state(0.12, "EUR/kWh", "2026-10-07T10:04:00Z", { data: [row] });
    assert.doesNotThrow(() => getEntityPriceIntervals(importState, null, "data", now));
    assert.deepEqual(getEntityPriceIntervals(importState, null, "data", now), []);
  }

  for (const field of ["period", "average_eur_per_kwh"]) {
    const row = { period: "2026-10-07", average_eur_per_kwh: 0.12 };
    row[field] = hostile;
    assert.doesNotThrow(() => renderPriceAggregates({ daily: [row] }, hostile), field);
  }

  assert.doesNotThrow(() => renderPriceTimeline(
    [{ startUtc: hostile, endUtc: hostile, importEurPerKwh: hostile, exportEurPerKwh: hostile, marketEurPerMwh: hostile }],
    [{ start_utc: hostile, action: hostile }],
    hostile,
    hostile,
    hostile,
  ));
});

test("missing or invalid entity timestamps fail closed and cannot supply plan or prices", () => {
  const now = new Date("2026-10-07T10:05:00Z");
  const fresh = "2026-10-07T10:04:00Z";
  for (const timestamp of [undefined, "not-a-date", hostilePrimitive()]) {
    const plan = state("planned", null, timestamp ?? "2026-10-07T10:04:00Z", {
      schedule: [{ start_utc: "2026-10-07T10:00:00Z", duration_hours: 0.25, action: "HOLD" }],
      prices: [{ start_utc: "2026-10-07T10:00:00Z", duration_hours: 0.25, import_eur_per_kwh: 0.99 }],
    });
    const price = state(0.88, "EUR/kWh", timestamp ?? "2026-10-07T10:04:00Z", { data: [{
      start_time: "2026-10-07T10:00:00Z",
      end_time: "2026-10-07T10:15:00Z",
      price_per_kwh: 0.88,
    }] });
    if (timestamp === undefined) {
      delete plan.last_updated;
      delete price.last_updated;
    }
    const hass = { states: {
      "sensor.grid": state(1000, "W", fresh),
      "sensor.pv": state(500, "W", fresh),
      "sensor.battery": state(0, "W", fresh),
      "sensor.soc": state(50, "%", fresh),
      "sensor.plan": plan,
      "sensor.import": price,
    } };
    const snapshot = buildSnapshot(hass, {
      grid_power_entity: "sensor.grid", pv_power_entity: "sensor.pv",
      battery_power_entity: "sensor.battery", battery_soc_entity: "sensor.soc",
      plan_entity: "sensor.plan", import_price_entity: "sensor.import",
    }, now);

    assert.equal(readEntity(hass, "sensor.plan", now, 10).quality, "INVALID");
    assert.equal(snapshot.plan.quality, "INVALID");
    assert.equal(snapshot.plan.interval, null);
    assert.deepEqual(snapshot.plan.schedule, []);
    assert.deepEqual(snapshot.prices.intervals, []);
    assert.equal(snapshot.prices.source, null);
    assert.equal(snapshot.live.importPriceEurPerKwh, null);
  }
});

test("unique-start overlapping intervals invalidate each price source", () => {
  const now = new Date("2026-10-07T10:05:00Z");
  const plan = state("planned", null, "2026-10-07T10:04:00Z", { prices: [
    { start_utc: "2026-10-07T10:00:00Z", duration_hours: 0.5, import_eur_per_kwh: 0.12 },
    { start_utc: "2026-10-07T10:15:00Z", duration_hours: 0.25, import_eur_per_kwh: 0.08 },
  ] });
  const importState = state(0.12, "EUR/kWh", "2026-10-07T10:04:00Z", { data: [
    { start_time: "2026-10-07T10:00:00Z", end_time: "2026-10-07T10:30:00Z", price_per_kwh: 0.12 },
    { start_time: "2026-10-07T10:15:00Z", end_time: "2026-10-07T10:30:00Z", price_per_kwh: 0.08 },
  ] });

  assert.deepEqual(getUpcomingPriceIntervals(plan, "prices", now), []);
  assert.deepEqual(getEntityPriceIntervals(importState, null, "data", now), []);
});

test("export prices only join imports with the same validated start and end", () => {
  const now = new Date("2026-10-07T10:05:00Z");
  const importState = state(0.12, "EUR/kWh", "2026-10-07T10:04:00Z", { data: [{
    start_time: "2026-10-07T10:15:00Z",
    end_time: "2026-10-07T10:30:00Z",
    price_per_kwh: 0.12,
  }] });
  const exportState = state(0.04, "EUR/kWh", "2026-10-07T10:04:00Z", { data: [{
    start_time: "2026-10-07T10:15:00Z",
    end_time: "2026-10-07T10:45:00Z",
    price_per_kwh: 0.04,
  }] });

  const prices = getEntityPriceIntervals(importState, exportState, "data", now);
  assert.equal(prices.length, 1);
  assert.equal(prices[0].exportEurPerKwh, null);
});

test("reverse aggregate input still renders the latest validated periods", () => {
  const html = renderPriceAggregates({
    daily: [
      { period: "2026-10-08", average_eur_per_kwh: 0.18 },
      { period: "2026-10-07", average_eur_per_kwh: 0.99 },
    ],
    weekly: [
      { period: "2026-W41", average_eur_per_kwh: 0.21 },
      { period: "2026-W40", average_eur_per_kwh: 0.98 },
    ],
    monthly: [
      { period: "2026-10", average_eur_per_kwh: 0.24 },
      { period: "2026-09", average_eur_per_kwh: 0.97 },
    ],
  }, 0.3);

  assert.match(html, /2026-10-08/);
  assert.match(html, /2026-W41/);
  assert.match(html, /2026-10/);
  assert.doesNotMatch(html, /€0,990|€0,980|€0,970/);
});

test("BE electricity prices today/tomorrow attributes provide import and injection prices", () => {
  const now = new Date("2026-10-19T00:20:00+02:00");
  const importState = state(0.3385, "EUR/kWh", "2026-10-19T00:19:00+02:00", {
    today: [
      { start: "2026-10-19T23:30:00+02:00", all_in: 0.358203 },
      { start: "2026-10-19T23:45:00+02:00", all_in: 0.339088 },
      { start: "2026-10-19T00:00:00+02:00", all_in: 0.340039 },
      { start: "2026-10-19T00:15:00+02:00", all_in: 0.338504 },
    ],
    tomorrow: [
      { start: "2026-10-20T00:00:00+02:00", all_in: 0.33 },
      { start: "2026-10-20T00:15:00+02:00", all_in: 0.32 },
    ],
  });
  const exportState = state(0.17, "EUR/kWh", "2026-10-19T00:19:00+02:00", {
    today: [
      { start: "2026-10-19T00:00:00+02:00", injection: 0.170122 },
      { start: "2026-10-19T00:15:00+02:00", injection: 0.16 },
    ],
    tomorrow: [],
  });

  const prices = getEntityPriceIntervals(importState, exportState, "today,tomorrow", now, true);

  assert.equal(prices.length, 6);
  assert.equal(prices[0].startUtc, "2026-10-18T22:00:00.000Z");
  assert.equal(prices[0].durationHours, 0.25);
  assert.equal(prices[0].importEurPerKwh, 0.340039);
  assert.equal(prices[0].exportEurPerKwh, 0.170122);
  assert.equal(prices[1].exportEurPerKwh, 0.16);
  assert.equal(prices[2].exportEurPerKwh, null);
  // The last row repeats the previous slot length; the day boundary is contiguous.
  assert.equal(prices[5].durationHours, 0.25);
  assert.equal(prices[5].endUtc, "2026-10-19T22:30:00.000Z");
});

test("hourly rows without an end are inferred as one hour", () => {
  const importState = state(0.31, "EUR/kWh", "2026-10-19T10:00:00+02:00", {
    today: [
      { start: "2026-10-19T10:00:00+02:00", all_in: 0.31 },
      { start: "2026-10-19T11:00:00+02:00", all_in: 0.31 },
    ],
  });

  const prices = getEntityPriceIntervals(
    importState, null, "today,tomorrow", new Date("2026-10-19T10:05:00+02:00"),
  );

  assert.deepEqual(prices.map((row) => row.durationHours), [1, 1]);
});

test("rows without an end are rejected when no slot length can be inferred", () => {
  const importState = state(0.31, "EUR/kWh", "2026-10-19T10:00:00+02:00", {
    today: [{ start: "2026-10-19T10:00:00+02:00", all_in: 0.31 }],
  });

  assert.deepEqual(
    getEntityPriceIntervals(importState, null, "today", new Date("2026-10-19T10:05:00+02:00")),
    [],
  );
});

test("a malformed or conflicting price row discards the whole attribute", () => {
  const now = new Date("2026-10-19T10:05:00+02:00");
  const malformed = state(0.31, "EUR/kWh", "2026-10-19T10:00:00+02:00", {
    today: [
      { start: "2026-10-19T10:00:00+02:00", all_in: 0.31 },
      { start: "2026-10-19T10:15:00+02:00", all_in: "n/a" },
    ],
  });
  const conflicting = state(0.31, "EUR/kWh", "2026-10-19T10:00:00+02:00", {
    today: [
      { start: "2026-10-19T10:00:00+02:00", all_in: 0.31 },
      { start: "2026-10-19T10:00:00+02:00", all_in: 0.32 },
    ],
  });

  assert.deepEqual(getEntityPriceIntervals(malformed, null, "today", now), []);
  assert.deepEqual(getEntityPriceIntervals(conflicting, null, "today", now), []);
});

test("a missing attribute keeps returning no intervals", () => {
  const importState = state(0.31, "EUR/kWh", "2026-10-19T10:00:00+02:00", {});
  assert.deepEqual(
    getEntityPriceIntervals(importState, null, "today,tomorrow", new Date("2026-10-19T10:05:00+02:00")),
    [],
  );
});
