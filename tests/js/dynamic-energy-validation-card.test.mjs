import test from "node:test";
import assert from "node:assert/strict";

import {
  buildValidationSnapshot,
  DynamicEnergyValidationCard,
  fetchValidationTelemetry,
  hassWithValidationTelemetry,
  renderValidationCard,
} from "../../dist/dynamic-energy-dashboard.js";

const NOW = new Date("2026-10-16T10:05:00+02:00");

function state(value, unit = null, attributes = {}) {
  return {
    state: String(value),
    last_updated: "2026-10-16T08:04:00Z",
    last_changed: "2026-10-16T08:04:00Z",
    attributes: {
      ...(unit ? { unit_of_measurement: unit } : {}),
      ...attributes,
    },
  };
}

function validationHass() {
  return {
    states: {
      "sensor.shadow_plan": state("planned", null, {
        schedule: [{
          start_utc: "2026-10-16T08:00:00Z",
          duration_hours: 0.25,
          action: "CHARGE_FROM_GRID",
          reason: "LOW_PRICE",
          planned_grid_import_kw: 4.5,
        }],
        prices: [
          { start_utc: "2026-10-16T08:00:00Z", duration_hours: 0.25, import_eur_per_kwh: 0.08 },
          { start_utc: "2026-10-16T08:15:00Z", duration_hours: 0.25, import_eur_per_kwh: 0.12 },
          { start_utc: "2026-10-16T08:30:00Z", duration_hours: 0.25, import_eur_per_kwh: 0.22 },
          { start_utc: "2026-10-16T08:45:00Z", duration_hours: 0.25, import_eur_per_kwh: 0.31 },
        ],
      }),
      "sensor.grid_power": state(6200, "W"),
      "sensor.battery_power": state(2700, "W"),
      "sensor.ev_power": state(3100, "W"),
      "sensor.house_power": state(6600, "W"),
      "sensor.pv_power": state(400, "W"),
      "sensor.heat_pump_power": state(800, "W"),
    },
  };
}

const CONFIG = Object.freeze({
  plan_entity: "sensor.shadow_plan",
  grid_power_entity: "sensor.grid_power",
  grid_import_positive: true,
  battery_power_entity: "sensor.battery_power",
  battery_charge_positive: true,
  ev_power_entity: "sensor.ev_power",
  house_power_entity: "sensor.house_power",
  pv_power_entity: "sensor.pv_power",
  heat_pump_power_entity: "sensor.heat_pump_power",
  peak_limit_kw: 7,
  smappee_capacity_threshold_kw: 5.5,
  activity_threshold_kw: 0.2,
  import_price_entity: "",
  export_price_entity: "",
  integration_price_attribute: "data",
  price_stale_after_minutes: 20,
  data_stale_after_minutes: 10,
  plan_stale_after_hours: 30,
  pilot_status: "COMBINED_OBSERVATION",
});

test("validation snapshot compares expected and observed battery behavior and flags a shared peak", () => {
  const snapshot = buildValidationSnapshot(validationHass(), CONFIG, NOW);

  assert.equal(snapshot.interval.expectedBatteryAction, "CHARGING");
  assert.equal(snapshot.interval.observedBatteryAction, "CHARGING");
  assert.equal(snapshot.interval.batteryOutcome, "MATCH");
  assert.equal(snapshot.interval.evAction, "CHARGING");
  assert.equal(snapshot.grid.effectiveLimitKw, 5.5);
  assert.equal(snapshot.grid.headroomKw, -0.7);
  assert.equal(snapshot.grid.collision, true);
  assert.equal(snapshot.status, "SHARED_PEAK_WARNING");
  assert.equal(snapshot.price.currentEurPerKwh, 0.08);
  assert.equal(snapshot.price.zone, "CHEAP");
  assert.equal(snapshot.live.houseKw, 6.6);
  assert.equal(snapshot.live.houseSource, "MEASURED");
  assert.equal(snapshot.live.pvKw, 0.4);
  assert.equal(snapshot.live.heatPumpKw, 0.8);
  assert.equal(snapshot.pilotStatus, "COMBINED_OBSERVATION");
  assert.equal(snapshot.executionAllowed, false);
});

test("validation snapshot derives house load when no measured house entity is configured", () => {
  const hass = validationHass();
  delete hass.states["sensor.house_power"];

  const snapshot = buildValidationSnapshot(hass, {
    ...CONFIG,
    house_power_entity: "",
  }, NOW);

  assert.equal(snapshot.live.houseKw, 3.9);
  assert.equal(snapshot.live.houseQuality, "GOOD");
  assert.equal(snapshot.live.houseSource, "DERIVED");

  const html = renderValidationCard(CONFIG, snapshot);
  assert.match(html, /Huisvermogen[\s\S]*3,9 kW[\s\S]*afgeleid uit net, PV en batterij/);
});

test("validation telemetry refresh uses read-only entity GETs for unchanged measurements", async () => {
  const calls = [];
  const refreshed = await fetchValidationTelemetry({
    callApi: async (method, path) => {
      calls.push([method, path]);
      const entityId = decodeURIComponent(path.replace("states/", ""));
      return {
        ...state(0, "W"),
        entity_id: entityId,
        last_reported: "2026-10-16T08:04:50Z",
      };
    },
  }, {
    grid_power_entity: "sensor.grid",
    battery_power_entity: "sensor.battery",
    battery_freshness_entity: "sensor.battery_status",
    ev_power_entity: "sensor.ev",
  });

  assert.deepEqual(calls, [
    ["GET", "states/sensor.grid"],
    ["GET", "states/sensor.battery"],
    ["GET", "states/sensor.battery_status"],
    ["GET", "states/sensor.ev"],
  ]);
  assert.equal(refreshed["sensor.battery"].last_reported, "2026-10-16T08:04:50Z");
});

test("validation card caches refreshed telemetry returned by Home Assistant", async () => {
  const card = new DynamicEnergyValidationCard();
  card._config = {
    ...CONFIG,
    grid_power_entity: "sensor.grid",
    battery_power_entity: "",
    ev_power_entity: "",
    house_power_entity: "",
    pv_power_entity: "",
    heat_pump_power_entity: "",
  };
  card._hass = {
    callApi: async () => ({
      ...state(0, "W"),
      entity_id: "sensor.grid",
      last_reported: "2026-10-16T08:04:55Z",
    }),
  };

  await card._refreshTelemetry(true);

  assert.equal(card._telemetryStates["sensor.grid"].last_reported, "2026-10-16T08:04:55Z");
});

test("a fresh configured battery heartbeat validates an unchanged numeric battery state", () => {
  const hass = validationHass();
  hass.states["sensor.battery_power"].last_updated = "2026-10-15T08:00:00Z";
  hass.states["sensor.battery_power"].last_changed = "2026-10-15T08:00:00Z";
  hass.states["sensor.battery_status"] = state("Ok");

  const snapshot = buildValidationSnapshot(hass, {
    ...CONFIG,
    battery_freshness_entity: "sensor.battery_status",
  }, NOW);
  const html = renderValidationCard(CONFIG, snapshot);

  assert.equal(snapshot.live.batteryQuality, "GOOD");
  assert.equal(snapshot.live.batteryFreshnessSource, "HEARTBEAT");
  assert.notEqual(snapshot.status, "INSUFFICIENT_DATA");
  assert.match(html, /actueel via heartbeat/);
});

test("a stale battery heartbeat cannot revive stale battery telemetry", () => {
  const hass = validationHass();
  hass.states["sensor.battery_power"].last_updated = "2026-10-15T08:00:00Z";
  hass.states["sensor.battery_power"].last_changed = "2026-10-15T08:00:00Z";
  hass.states["sensor.battery_status"] = {
    ...state("Ok"),
    last_updated: "2026-10-15T08:00:00Z",
    last_changed: "2026-10-15T08:00:00Z",
  };

  const snapshot = buildValidationSnapshot(hass, {
    ...CONFIG,
    battery_freshness_entity: "sensor.battery_status",
  }, NOW);

  assert.equal(snapshot.live.batteryQuality, "STALE");
  assert.equal(snapshot.live.batteryFreshnessSource, null);
  assert.equal(snapshot.status, "INSUFFICIENT_DATA");
});

function staleBatteryHass(extra = {}) {
  const hass = validationHass();
  hass.states["sensor.battery_power"].last_updated = "2026-10-15T08:00:00Z";
  hass.states["sensor.battery_power"].last_changed = "2026-10-15T08:00:00Z";
  Object.assign(hass.states, extra);
  return hass;
}

const HEARTBEAT_CONFIG = Object.freeze({ ...CONFIG, battery_freshness_entity: "sensor.battery_status" });

test("the heartbeat keeps the measured battery value and the real measurement age", () => {
  const snapshot = buildValidationSnapshot(
    staleBatteryHass({ "sensor.battery_status": state("Ok") }), HEARTBEAT_CONFIG, NOW,
  );

  assert.equal(snapshot.live.batteryKw, 2.7);
  assert.ok(snapshot.live.batteryMeasurementAgeMinutes > 60);
});

test("an unavailable, unknown or missing heartbeat cannot revive stale battery telemetry", () => {
  for (const extra of [
    { "sensor.battery_status": state("unavailable") },
    { "sensor.battery_status": state("unknown") },
    {},
  ]) {
    const snapshot = buildValidationSnapshot(staleBatteryHass(extra), HEARTBEAT_CONFIG, NOW);
    assert.equal(snapshot.live.batteryQuality, "STALE");
    assert.equal(snapshot.live.batteryFreshnessSource, null);
  }
});

test("a heartbeat pointing at the stale battery entity cannot revive itself", () => {
  const snapshot = buildValidationSnapshot(
    staleBatteryHass(), { ...CONFIG, battery_freshness_entity: "sensor.battery_power" }, NOW,
  );

  assert.equal(snapshot.live.batteryQuality, "STALE");
});

test("a fresh heartbeat does not revive an unavailable or wrong-unit battery value", () => {
  const unavailable = staleBatteryHass({
    "sensor.battery_power": state("unavailable"),
    "sensor.battery_status": state("Ok"),
  });
  const wrongUnit = staleBatteryHass({ "sensor.battery_status": state("Ok") });
  wrongUnit.states["sensor.battery_power"] = {
    ...state(2700, "V"),
    last_updated: "2026-10-15T08:00:00Z",
    last_changed: "2026-10-15T08:00:00Z",
  };

  const first = buildValidationSnapshot(unavailable, HEARTBEAT_CONFIG, NOW);
  const second = buildValidationSnapshot(wrongUnit, HEARTBEAT_CONFIG, NOW);

  assert.notEqual(first.live.batteryQuality, "GOOD");
  assert.equal(first.live.batteryKw, null);
  assert.equal(second.live.batteryQuality, "INVALID");
  assert.equal(second.live.batteryKw, null);
});

test("future-dated cached telemetry cannot replace newer live telemetry", () => {
  const nowMs = Date.now();
  const live = {
    ...state(5000, "W"),
    last_updated: new Date(nowMs - 5_000).toISOString(),
    last_changed: new Date(nowMs - 5_000).toISOString(),
  };
  const cached = {
    ...state(0, "W"),
    last_reported: new Date(nowMs + 3_600_000).toISOString(),
    last_updated: new Date(nowMs - 3_600_000).toISOString(),
    last_changed: new Date(nowMs - 3_600_000).toISOString(),
  };

  const merged = hassWithValidationTelemetry(
    { states: { "sensor.grid": live } },
    { "sensor.grid": cached },
  );

  assert.equal(merged.states["sensor.grid"].state, "5000");
});

test("validation snapshot reads a bounded daily scorecard without turning missing history into a zero", () => {
  const hass = validationHass();
  hass.states["sensor.validation_summary"] = state("2026-10-16", null, {
    local_date: "2026-10-16",
    coverage_percent: 97.5,
    battery_charge_cheap_kwh: 4.2,
    battery_discharge_expensive_kwh: 2.1,
    ev_charge_cheap_kwh: 7.4,
    ev_cheap_share_percent: 82,
    max_grid_import_kw: 6.2,
    collision_intervals: 1,
    matched_intervals: 67,
    deviation_intervals: 4,
    actual_cost_eur: 5.84,
    shadow_cost_eur: 5.31,
  });

  const snapshot = buildValidationSnapshot(hass, {
    ...CONFIG,
    validation_summary_entity: "sensor.validation_summary",
  }, NOW);

  assert.deepEqual(snapshot.summary, {
    quality: "GOOD",
    localDate: "2026-10-16",
    coveragePercent: 97.5,
    batteryChargeCheapKwh: 4.2,
    batteryDischargeExpensiveKwh: 2.1,
    evChargeCheapKwh: 7.4,
    evCheapSharePercent: 82,
    maxGridImportKw: 6.2,
    collisionIntervals: 1,
    matchedIntervals: 67,
    deviationIntervals: 4,
    actualCostEur: 5.84,
    shadowCostEur: 5.31,
    costDeltaEur: 0.53,
  });

  const missing = buildValidationSnapshot(validationHass(), CONFIG, NOW);
  assert.equal(missing.summary.quality, "NOT_CONFIGURED");
  assert.equal(missing.summary.coveragePercent, null);
  assert.equal(missing.summary.actualCostEur, null);
});

test("daily scorecard rejects impossible dates and fractional interval counts", () => {
  const hass = validationHass();
  hass.states["sensor.validation_summary"] = state("invalid", null, {
    local_date: "2026-02-31",
    coverage_percent: 97.5,
    battery_charge_cheap_kwh: 4.2,
    battery_discharge_expensive_kwh: 2.1,
    ev_charge_cheap_kwh: 7.4,
    ev_cheap_share_percent: 82,
    max_grid_import_kw: 6.2,
    collision_intervals: 1.5,
    matched_intervals: 67,
    deviation_intervals: 4,
    actual_cost_eur: 5.84,
    shadow_cost_eur: 5.31,
  });

  const snapshot = buildValidationSnapshot(hass, {
    ...CONFIG,
    validation_summary_entity: "sensor.validation_summary",
  }, NOW);

  assert.equal(snapshot.summary.quality, "INVALID");
  assert.equal(snapshot.summary.localDate, null);
  assert.equal(snapshot.summary.collisionIntervals, null);
});

test("daily scorecard rejects unbounded or internally inconsistent evidence", () => {
  const baseAttributes = {
    local_date: "2026-10-16",
    coverage_percent: 50,
    battery_charge_cheap_kwh: 4.2,
    battery_discharge_expensive_kwh: 2.1,
    ev_charge_cheap_kwh: 7.4,
    ev_cheap_share_percent: 82,
    max_grid_import_kw: 6.2,
    collision_intervals: 5,
    matched_intervals: 35,
    deviation_intervals: 10,
    actual_cost_eur: 5.84,
    shadow_cost_eur: 5.31,
  };
  for (const attributes of [
    { ...baseAttributes, battery_charge_cheap_kwh: "   " },
    { ...baseAttributes, battery_charge_cheap_kwh: 999999 },
    { ...baseAttributes, max_grid_import_kw: 999999 },
    { ...baseAttributes, actual_cost_eur: 999999 },
    { ...baseAttributes, coverage_percent: 40 },
    { ...baseAttributes, coverage_percent: 100, collision_intervals: 46 },
  ]) {
    const hass = validationHass();
    hass.states["sensor.validation_summary"] = state("invalid", null, attributes);
    const snapshot = buildValidationSnapshot(hass, {
      ...CONFIG,
      validation_summary_entity: "sensor.validation_summary",
    }, NOW);

    assert.equal(snapshot.summary.quality, "INVALID");
  }
});

test("validation card renders expected-versus-actual, shared headroom and the daily evidence scorecard", () => {
  const hass = validationHass();
  hass.states["sensor.validation_summary"] = state("2026-10-16", null, {
    local_date: "2026-10-16",
    coverage_percent: 97.5,
    battery_charge_cheap_kwh: 4.2,
    battery_discharge_expensive_kwh: 2.1,
    ev_charge_cheap_kwh: 7.4,
    ev_cheap_share_percent: 82,
    max_grid_import_kw: 6.2,
    collision_intervals: 1,
    matched_intervals: 67,
    deviation_intervals: 4,
    actual_cost_eur: 5.84,
    shadow_cost_eur: 5.31,
  });
  const config = {
    ...CONFIG,
    title: "Gedragsvalidatie",
    validation_summary_entity: "sensor.validation_summary",
  };
  const html = renderValidationCard(config, buildValidationSnapshot(hass, config, NOW));

  assert.match(html, /Gedragsvalidatie/);
  assert.match(html, /Gecombineerde observatie/);
  assert.doesNotMatch(html, />COMBINED_OBSERVATION</);
  assert.match(html, /validation-status shared_peak_warning/);
  assert.match(html, /Alleen observeren · er worden geen acties uitgevoerd/);
  assert.match(html, /Verwacht batterijgedrag[\s\S]*Laden/);
  assert.match(html, /Werkelijk batterijgedrag[\s\S]*Laden/);
  assert.match(html, /Gedeelde headroom[\s\S]*-0,7 kW/);
  assert.match(html, /Prijszone[\s\S]*Goedkoop/);
  assert.match(html, /Actuele afnameprijs[\s\S]*€0,080/);
  assert.match(html, /Huisvermogen[\s\S]*6,6 kW/);
  assert.match(html, /PV-vermogen[\s\S]*0,4 kW/);
  assert.match(html, /Warmtepomp[\s\S]*0,8 kW/);
  assert.match(html, /batterij en EV gelijktijdig laden/i);
  assert.match(html, /Dagscore · 2026-10-16/);
  assert.match(html, /Datadekking[\s\S]*97,5%/);
  assert.match(html, /EV goedkoop aandeel[\s\S]*82%/);
  assert.match(html, /Kostenverschil[\s\S]*€\s*0,53/);
  assert.match(html, /execution_allowed = false/);
  assert.match(html, /Doelarchitectuur[\s\S]*niet automatisch geverifieerd/);
  assert.doesNotMatch(html, /SMA bestuurt batterij\/PV · Smappee bestuurt EV/);
  assert.doesNotMatch(html, /<button|data-action=|callService|LIVE/);
});

test("a matching validation status uses explicit positive semantics", () => {
  const hass = validationHass();
  hass.states["sensor.grid_power"].state = "4200";
  hass.states["sensor.ev_power"].state = "0";
  const snapshot = buildValidationSnapshot(hass, CONFIG, NOW);
  const html = renderValidationCard(CONFIG, snapshot);

  assert.equal(snapshot.status, "MATCH");
  assert.match(html, /validation-status match/);
  assert.match(html, /Gedrag komt overeen/);
});

test("validation card exposes a bounded read-only visual editor schema", () => {
  const names = DynamicEnergyValidationCard.getConfigForm().schema.map((field) => field.name);

  assert.deepEqual(names, [
    "title",
    "plan_entity",
    "grid_power_entity",
    "grid_import_positive",
    "battery_power_entity",
    "battery_charge_positive",
    "battery_freshness_entity",
    "ev_power_entity",
    "house_power_entity",
    "pv_power_entity",
    "heat_pump_power_entity",
    "validation_summary_entity",
    "import_price_entity",
    "export_price_entity",
    "integration_price_attribute",
    "price_stale_after_minutes",
    "peak_limit_kw",
    "smappee_capacity_threshold_kw",
    "activity_threshold_kw",
    "data_stale_after_minutes",
    "plan_stale_after_hours",
    "summary_stale_after_hours",
    "pilot_status",
  ]);
  assert.equal(DynamicEnergyValidationCard.getStubConfig().execution_allowed, false);
});

test("validation snapshot fails closed on an unknown pilot status", () => {
  const snapshot = buildValidationSnapshot(validationHass(), {
    ...CONFIG,
    pilot_status: "LIVE",
  }, NOW);

  assert.equal(snapshot.pilotStatus, "BLOCKED");
  assert.equal(snapshot.status, "BLOCKED");
  assert.equal(snapshot.executionAllowed, false);
  assert.match(snapshot.warnings.join(" "), /onbekende pilotstatus/i);
});

test("an explicitly blocked pilot cannot render a positive validation status", () => {
  const hass = validationHass();
  hass.states["sensor.grid_power"].state = "4200";
  hass.states["sensor.ev_power"].state = "0";

  const snapshot = buildValidationSnapshot(hass, {
    ...CONFIG,
    pilot_status: "BLOCKED",
  }, NOW);

  assert.equal(snapshot.interval.batteryOutcome, "MATCH");
  assert.equal(snapshot.pilotStatus, "BLOCKED");
  assert.equal(snapshot.status, "BLOCKED");
});

test("simultaneous battery and EV charging is visible even below the shared limit", () => {
  const hass = validationHass();
  hass.states["sensor.grid_power"].state = "4200";
  hass.states["sensor.battery_power"].state = "1000";
  hass.states["sensor.ev_power"].state = "1000";

  const snapshot = buildValidationSnapshot(hass, CONFIG, NOW);

  assert.equal(snapshot.grid.collision, true);
  assert.equal(snapshot.grid.headroomKw, 1.3);
  assert.equal(snapshot.status, "SHARED_PEAK_WARNING");
  assert.match(snapshot.warnings.join(" "), /gelijktijdig/i);
});

test("missing current price context cannot report an overall validation match", () => {
  const hass = validationHass();
  hass.states["sensor.shadow_plan"].attributes.prices = [];
  hass.states["sensor.grid_power"].state = "4200";
  hass.states["sensor.ev_power"].state = "0";

  const snapshot = buildValidationSnapshot(hass, CONFIG, NOW);

  assert.equal(snapshot.interval.batteryOutcome, "MATCH");
  assert.equal(snapshot.price.quality, "UNAVAILABLE");
  assert.equal(snapshot.status, "INSUFFICIENT_DATA");
});

test("a single price interval is not enough to assign a relative price zone", () => {
  const hass = validationHass();
  hass.states["sensor.shadow_plan"].attributes.prices = [
    { start_utc: "2026-10-16T08:00:00Z", duration_hours: 0.25, import_eur_per_kwh: 0.08 },
  ];
  hass.states["sensor.grid_power"].state = "4200";
  hass.states["sensor.ev_power"].state = "0";

  const snapshot = buildValidationSnapshot(hass, CONFIG, NOW);

  assert.equal(snapshot.price.currentEurPerKwh, 0.08);
  assert.equal(snapshot.price.zone, "INSUFFICIENT_DATA");
  assert.equal(snapshot.status, "INSUFFICIENT_DATA");
});

test("a flat price feed is neutral instead of falsely cheap", () => {
  const hass = validationHass();
  hass.states["sensor.shadow_plan"].attributes.prices = [0, 1, 2, 3].map((index) => ({
    start_utc: new Date(Date.parse("2026-10-16T08:00:00Z") + index * 900000).toISOString(),
    duration_hours: 0.25,
    import_eur_per_kwh: 0.2,
  }));
  hass.states["sensor.grid_power"].state = "4200";
  hass.states["sensor.ev_power"].state = "0";

  const snapshot = buildValidationSnapshot(hass, CONFIG, NOW);

  assert.equal(snapshot.price.currentEurPerKwh, 0.2);
  assert.equal(snapshot.price.zone, "NORMAL");
  assert.equal(snapshot.status, "MATCH");
});

test("validation snapshot warns when the effective shared limit is exceeded without a charging collision", () => {
  const hass = validationHass();
  hass.states["sensor.battery_power"].state = "0";
  hass.states["sensor.ev_power"].state = "0";

  const snapshot = buildValidationSnapshot(hass, CONFIG, NOW);

  assert.equal(snapshot.grid.collision, false);
  assert.equal(snapshot.grid.headroomKw, -0.7);
  assert.equal(snapshot.status, "SHARED_PEAK_WARNING");

  const html = renderValidationCard(CONFIG, snapshot);
  assert.match(html, /Piek- en collisionbewaking[\s\S]*EXCEEDED/);
  assert.match(html, /effectieve gedeelde netgrens is overschreden/i);
  assert.doesNotMatch(html, /Piek- en collisionbewaking[\s\S]*CLEAR/);
});

test("shared-net rendering remains unknown when required telemetry is unavailable", () => {
  const hass = validationHass();
  hass.states["sensor.grid_power"].state = "unavailable";
  const snapshot = buildValidationSnapshot(hass, CONFIG, NOW);
  const html = renderValidationCard(CONFIG, snapshot);

  assert.equal(snapshot.status, "INSUFFICIENT_DATA");
  assert.match(html, /Piek- en collisionbewaking[\s\S]*UNKNOWN/);
  assert.match(html, /Onvoldoende actuele meetdata/);
  assert.doesNotMatch(html, /Geen gelijktijdige laadactie of gedeelde grensoverschrijding/);
});

test("validation price selection prefers the longer feed only when it also covers the current quarter", () => {
  const hass = validationHass();
  hass.states["sensor.import_price"] = state(0.25, "EUR/kWh", {
    data: [
      { start_time: "2026-10-16T08:00:00Z", end_time: "2026-10-16T08:15:00Z", price_per_kwh: 0.25 },
      { start_time: "2026-10-16T08:15:00Z", end_time: "2026-10-16T08:30:00Z", price_per_kwh: 0.07 },
      { start_time: "2026-10-16T08:30:00Z", end_time: "2026-10-16T08:45:00Z", price_per_kwh: 0.31 },
      { start_time: "2026-10-16T08:45:00Z", end_time: "2026-10-16T09:00:00Z", price_per_kwh: 0.18 },
      { start_time: "2026-10-16T09:00:00Z", end_time: "2026-10-16T09:15:00Z", price_per_kwh: 0.16 },
    ],
  });

  const currentIntegration = buildValidationSnapshot(hass, {
    ...CONFIG,
    import_price_entity: "sensor.import_price",
  }, NOW);
  assert.equal(currentIntegration.price.currentEurPerKwh, 0.25);
  assert.equal(currentIntegration.price.source, "Home Assistant price entities");

  hass.states["sensor.import_price"].attributes.data[0] = {
    start_time: "2026-10-16T08:15:00Z",
    end_time: "2026-10-16T08:30:00Z",
    price_per_kwh: 0.07,
  };
  const futureOnlyIntegration = buildValidationSnapshot(hass, {
    ...CONFIG,
    import_price_entity: "sensor.import_price",
  }, NOW);
  assert.equal(futureOnlyIntegration.price.currentEurPerKwh, 0.08);
  assert.equal(futureOnlyIntegration.price.source, "Shadow plan");
});
