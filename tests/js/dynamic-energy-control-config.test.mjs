import test from "node:test";
import assert from "node:assert/strict";

import {
  buildControlPanelSnapshot,
  buildBlockedAutomationConfigs,
  DynamicEnergyControlConfigCard,
  getBlockedAutomationState,
  loadBlockedAutomationState,
  performBlockedControlAction,
  renderBlockedControlConfig,
  saveBlockedAutomations,
  setBlockedAutomationsArmed,
} from "../../dist/dynamic-energy-dashboard.js";

const SPEC = Object.freeze({
  name_prefix: "Dynamic Energy",
  plan_entity: "sensor.dynamic_energy_shadow_plan",
  interval_minutes: 15,
  peak_limit_kw: 7,
  battery_enabled: true,
  battery_reserve_soc_percent: 10,
  ev_enabled: true,
  ev_target_soc_percent: 80,
  ev_departure_time: "07:00:00",
});

const CONTROL_NOW = new Date("2026-10-14T10:05:00+02:00");

function controlPanelHass(updated = "2026-10-14T08:04:00Z") {
  return {
    states: {
      "sensor.dynamic_energy_shadow_plan": {
        state: "planned",
        last_updated: updated,
        last_changed: updated,
        attributes: {
          mode: "READ_ONLY_SHADOW",
          price_source: "Validated Day-Ahead feed",
          price_tariff_version: "TEST_TARIFF_2026",
          prices: [
            { start_utc: "2026-10-14T08:00:00Z", duration_hours: 0.25, import_eur_per_kwh: 0.12 },
            { start_utc: "2026-10-14T08:15:00Z", duration_hours: 0.25, import_eur_per_kwh: 0.08 },
            { start_utc: "2026-10-14T08:30:00Z", duration_hours: 0.25, import_eur_per_kwh: 0.31 },
          ],
          schedule: [{
            start_utc: "2026-10-14T08:00:00Z",
            duration_hours: 0.25,
            action: "CHARGE_FROM_GRID",
            reason: "LOW_PRICE",
            planned_grid_import_kw: 3.5,
          }],
        },
      },
      "sensor.battery_soc": {
        state: "58",
        last_updated: updated,
        last_changed: updated,
        attributes: { unit_of_measurement: "%" },
      },
      "sensor.grid_power": {
        state: "4200",
        last_updated: updated,
        last_changed: updated,
        attributes: { unit_of_measurement: "W" },
      },
      "sensor.ev_power": {
        state: "2200",
        last_updated: updated,
        last_changed: updated,
        attributes: { unit_of_measurement: "W" },
      },
    },
  };
}

const PANEL_SPEC = Object.freeze({
  ...SPEC,
  battery_soc_entity: "sensor.battery_soc",
  grid_power_entity: "sensor.grid_power",
  grid_import_positive: true,
  ev_power_entity: "sensor.ev_power",
  data_stale_after_minutes: 10,
  plan_stale_after_hours: 30,
  sma_controller: "Sunny Home Manager 2.0",
  sma_optimization_goal: "Economisch",
  sma_tariff_type: "Dynamisch · Day-Ahead · BE · EPEX Spot",
  sma_forecast_charging: "OFF",
  sma_grid_charge_soc_percent: 0,
  sma_feed_in_eur_per_kwh: 0.02,
  smappee_mode: "smart",
  smappee_grid_connection: "Driefasig – Delta · 2 × 40 A",
  smappee_capacity_threshold_kw: 5.5,
  smappee_max_current_ampere: 32,
  smappee_offline_fallback_ampere: 8,
});

test("joint control builder creates namespaced battery and EV automations that stop before any actuator action", () => {
  const automations = buildBlockedAutomationConfigs(SPEC);

  assert.deepEqual(
    automations.map((automation) => automation.id),
    ["dynamic_energy_battery_v1", "dynamic_energy_ev_v1"],
  );
  for (const automation of automations) {
    assert.match(automation.alias, /^Dynamic Energy · /);
    assert.match(automation.description, /managed_by=dynamic-energy-control-config-card/);
    assert.equal(automation.mode, "single");
    assert.deepEqual(automation.triggers, [{ trigger: "time_pattern", minutes: "/15" }]);
    assert.deepEqual(automation.actions, [{
      stop: "Dynamic Energy safety lock: live actuator execution is not authorized",
      error: false,
    }]);
    assert.equal(automation.variables.execution_allowed, false);
    assert.equal(automation.variables.control_mode, "ARMED_BLOCKED");
    assert.equal(automation.variables.peak_limit_kw, 7);
    assert.equal(JSON.stringify(automation).includes("callService"), false);
    assert.equal(JSON.stringify(automation).includes("device_id"), false);
  }
  assert.equal(automations[0].variables.battery_reserve_soc_percent, 10);
  assert.equal(automations[1].variables.ev_target_soc_percent, 80);
  assert.equal(automations[1].variables.ev_departure_time, "07:00:00");
});

test("automation creation validates every blocked config before saving it through the Home Assistant automation API", async () => {
  const calls = [];
  const hass = {
    async callWS(message) {
      calls.push(["ws", message]);
      return {
        trigger: { valid: true, error: null },
        condition: { valid: true, error: null },
        action: { valid: true, error: null },
      };
    },
    async callApi(method, path, body) {
      calls.push(["api", method, path, body]);
      if (method === "GET") {
        const error = new Error("not found");
        error.status = 404;
        throw error;
      }
      return { result: "ok" };
    },
  };

  const result = await saveBlockedAutomations(hass, SPEC);

  assert.deepEqual(result.map((entry) => entry.id), [
    "dynamic_energy_battery_v1",
    "dynamic_energy_ev_v1",
  ]);
  assert.equal(calls.filter(([kind]) => kind === "ws").length, 2);
  assert.deepEqual(
    calls.filter(([kind, method]) => kind === "api" && method === "POST")
      .map(([, method, path]) => [method, path]),
    [
      ["POST", "config/automation/config/dynamic_energy_battery_v1"],
      ["POST", "config/automation/config/dynamic_energy_ev_v1"],
    ],
  );
  for (const [, message] of calls.filter(([kind]) => kind === "ws")) {
    assert.equal(message.type, "validate_config");
    assert.deepEqual(message.action, [{
      stop: "Dynamic Energy safety lock: live actuator execution is not authorized",
      error: false,
    }]);
  }
  const firstWrite = calls.findIndex(([kind, method]) => kind === "api" && method === "POST");
  const lastValidation = calls.map(([kind]) => kind).lastIndexOf("ws");
  assert.ok(lastValidation < firstWrite);
});

test("automation creation stops before the first write when the second Home Assistant validation fails", async () => {
  let writes = 0;
  let validations = 0;
  const hass = {
    async callWS() {
      validations += 1;
      return validations === 1
        ? {
            trigger: { valid: true, error: null },
            condition: { valid: true, error: null },
            action: { valid: true, error: null },
          }
        : {
            trigger: { valid: true, error: null },
            condition: { valid: true, error: null },
            action: { valid: false, error: "invalid stop action" },
          };
    },
    async callApi(method) {
      if (method === "GET") {
        const error = new Error("not found");
        error.status = 404;
        throw error;
      }
      writes += 1;
    },
  };

  await assert.rejects(
    saveBlockedAutomations(hass, SPEC),
    /Home Assistant rejected dynamic_energy_ev_v1/,
  );
  assert.equal(writes, 0);
});

test("automation creation refuses to overwrite an existing automation without ownership", async () => {
  let writes = 0;
  const hass = {
    async callWS() {
      return {
        trigger: { valid: true, error: null },
        condition: { valid: true, error: null },
        action: { valid: true, error: null },
      };
    },
    async callApi(method) {
      if (method === "GET") return { alias: "Unrelated user automation", actions: [] };
      writes += 1;
    },
  };

  await assert.rejects(saveBlockedAutomations(hass, SPEC), /existing automation is not managed/);
  assert.equal(writes, 0);
});

test("automation update accepts realistic Home Assistant responses that retain the matching id", async () => {
  const configs = buildBlockedAutomationConfigs(SPEC);
  let writes = 0;
  const hass = {
    async callWS() {
      return {
        trigger: { valid: true, error: null },
        condition: { valid: true, error: null },
        action: { valid: true, error: null },
      };
    },
    async callApi(method, path) {
      const id = path.split("/").at(-1);
      if (method === "GET") return configs.find((config) => config.id === id);
      writes += 1;
      return {};
    },
  };

  await saveBlockedAutomations(hass, SPEC);
  assert.equal(writes, 2);
});

test("active mode only enables verified managed automations that remain hard-blocked", async () => {
  const configs = buildBlockedAutomationConfigs(SPEC);
  const calls = [];
  const hass = {
    states: {
      "automation.dynamic_energy_battery": { state: "off", attributes: { id: configs[0].id } },
      "automation.dynamic_energy_ev": { state: "off", attributes: { id: configs[1].id } },
    },
    async callApi(method, path) {
      calls.push(["api", method, path]);
      const id = path.split("/").at(-1);
      return configs.find((config) => config.id === id);
    },
    async callService(domain, service, data, target) {
      calls.push(["service", domain, service, data, target]);
    },
  };

  const result = await setBlockedAutomationsArmed(
    hass,
    configs.map((config) => config.id),
    true,
  );

  assert.equal(result.mode, "ARMED_BLOCKED");
  assert.deepEqual(result.entity_ids, [
    "automation.dynamic_energy_battery",
    "automation.dynamic_energy_ev",
  ]);
  assert.deepEqual(calls.at(-1), [
    "service",
    "automation",
    "turn_on",
    {},
    { entity_id: result.entity_ids },
  ]);
});

test("active mode refuses an automation if its stop action was replaced by a service call", async () => {
  const [config] = buildBlockedAutomationConfigs({ ...SPEC, ev_enabled: false });
  let serviceCalls = 0;
  const hass = {
    states: {
      "automation.dynamic_energy_battery": { state: "off", attributes: { id: config.id } },
    },
    async callApi() {
      const { id: ignored, ...body } = config;
      return { ...body, actions: [{ action: "switch.turn_on", target: { entity_id: "switch.battery" } }] };
    },
    async callService() {
      serviceCalls += 1;
    },
  };

  await assert.rejects(
    setBlockedAutomationsArmed(hass, [config.id], true),
    /is not a verified blocked automation/,
  );
  assert.equal(serviceCalls, 0);
});

test("active mode refuses any managed automation changed after creation", async () => {
  const [config] = buildBlockedAutomationConfigs({ ...SPEC, ev_enabled: false });
  const mutations = [
    (body) => ({ ...body, alias: "Modified alias" }),
    (body) => ({ ...body, mode: "restart" }),
    (body) => ({ ...body, triggers: [{ trigger: "time", at: "12:00:00" }] }),
    (body) => ({ ...body, conditions: [{ condition: "template", value_template: "{{ true }}" }] }),
    (body) => ({ ...body, variables: { ...body.variables, peak_limit_kw: 12 } }),
    (body) => ({
      ...body,
      alias: "Trigger changed gtLc0I",
      triggers: [{ trigger: "time_pattern", minutes: "/5" }],
    }),
    (body) => ({ ...body, description: `${body.description}; externally modified` }),
    (body) => ({ ...body, id: "dynamic_energy_ev_v1" }),
  ];

  for (const mutate of mutations) {
    let serviceCalls = 0;
    const hass = {
      states: {
        "automation.dynamic_energy_battery": { state: "off", attributes: { id: config.id } },
      },
      async callApi() {
        return mutate(config);
      },
      async callService() {
        serviceCalls += 1;
      },
    };

    await assert.rejects(
      setBlockedAutomationsArmed(hass, [config.id], true),
      /is not a verified blocked automation/,
    );
    assert.equal(serviceCalls, 0);
  }
});

test("control status distinguishes setup, off, armed-blocked and conflicting automation states", () => {
  assert.equal(getBlockedAutomationState({ states: {} }, SPEC).mode, "SETUP_REQUIRED");

  const off = {
    states: {
      "automation.battery": { state: "off", attributes: { id: "dynamic_energy_battery_v1" } },
      "automation.ev": { state: "off", attributes: { id: "dynamic_energy_ev_v1" } },
    },
  };
  assert.equal(getBlockedAutomationState(off, SPEC).mode, "CONFLICT");
  assert.equal(
    getBlockedAutomationState(off, SPEC, new Set(["dynamic_energy_battery_v1", "dynamic_energy_ev_v1"])).mode,
    "OFF",
  );

  const armed = {
    states: {
      "automation.battery": { state: "on", attributes: { id: "dynamic_energy_battery_v1" } },
      "automation.ev": { state: "on", attributes: { id: "dynamic_energy_ev_v1" } },
    },
  };
  assert.equal(getBlockedAutomationState(armed, SPEC).mode, "CONFLICT");
  assert.equal(
    getBlockedAutomationState(armed, SPEC, new Set(["dynamic_energy_battery_v1", "dynamic_energy_ev_v1"])).mode,
    "ARMED_BLOCKED",
  );

  const conflict = {
    states: {
      "automation.battery": { state: "on", attributes: { id: "dynamic_energy_battery_v1" } },
      "automation.ev": { state: "off", attributes: { id: "dynamic_energy_ev_v1" } },
    },
  };
  assert.equal(getBlockedAutomationState(conflict, SPEC).mode, "CONFLICT");
});

test("verified status loads and checks the stored blocked configurations", async () => {
  const configs = buildBlockedAutomationConfigs(SPEC);
  const hass = {
    states: {
      "automation.battery": { state: "on", attributes: { id: configs[0].id } },
      "automation.ev": { state: "on", attributes: { id: configs[1].id } },
    },
    async callApi(method, path) {
      assert.equal(method, "GET");
      const id = path.split("/").at(-1);
      return configs.find((config) => config.id === id);
    },
  };

  assert.equal((await loadBlockedAutomationState(hass, SPEC)).mode, "ARMED_BLOCKED");
  hass.callApi = async () => ({ alias: "tampered", actions: [{ service: "switch.turn_on" }] });
  assert.equal((await loadBlockedAutomationState(hass, SPEC)).mode, "CONFLICT");
});

test("off disables every existing managed automation including a retired option", async () => {
  const configs = buildBlockedAutomationConfigs(SPEC);
  const serviceCalls = [];
  const hass = {
    states: {
      "automation.battery": { state: "on", attributes: { id: configs[0].id } },
      "automation.ev": { state: "on", attributes: { id: configs[1].id } },
    },
    async callApi(method, path) {
      const id = path.split("/").at(-1);
      return configs.find((config) => config.id === id);
    },
    async callService(...args) {
      serviceCalls.push(args);
    },
  };

  await performBlockedControlAction(
    hass,
    { ...SPEC, ev_enabled: false },
    "off",
    () => true,
  );

  assert.deepEqual(serviceCalls[0][3].entity_id, [
    "automation.battery",
    "automation.ev",
  ]);
});

test("duplicate retired automation entities force conflict and make off fail closed", async () => {
  const [battery] = buildBlockedAutomationConfigs({ ...SPEC, ev_enabled: false });
  const [, ev] = buildBlockedAutomationConfigs(SPEC);
  const hass = {
    states: {
      "automation.battery": { state: "on", attributes: { id: battery.id } },
      "automation.ev_one": { state: "on", attributes: { id: "dynamic_energy_ev_v1" } },
      "automation.ev_two": { state: "on", attributes: { id: "dynamic_energy_ev_v1" } },
    },
    async callApi(method, path) {
      const id = path.split("/").at(-1);
      const config = id === battery.id ? battery : ev;
      const { id: ignored, ...body } = config;
      return body;
    },
    async callService() {
      assert.fail("off must not report success for ambiguous managed entities");
    },
  };

  assert.equal((await loadBlockedAutomationState(hass, { ...SPEC, ev_enabled: false })).mode, "CONFLICT");
  await assert.rejects(
    performBlockedControlAction(hass, { ...SPEC, ev_enabled: false }, "off", () => true),
    /multiple Home Assistant entities/,
  );
});

test("create refuses a foreign retired automation before writing a desired automation", async () => {
  let writes = 0;
  const hass = {
    states: {
      "automation.ev": { state: "on", attributes: { id: "dynamic_energy_ev_v1" } },
    },
    async callWS() {
      return {
        trigger: { valid: true, error: null },
        condition: { valid: true, error: null },
        action: { valid: true, error: null },
      };
    },
    async callApi(method, path) {
      if (method === "POST") {
        writes += 1;
        return {};
      }
      if (path.endsWith("dynamic_energy_ev_v1")) {
        return { alias: "Unrelated user automation", actions: [] };
      }
      const error = new Error("not found");
      error.status = 404;
      throw error;
    },
    async callService() {},
  };

  await assert.rejects(
    performBlockedControlAction(hass, { ...SPEC, ev_enabled: false }, "create", () => true),
    /dynamic_energy_ev_v1 is not a verified blocked automation/,
  );
  assert.equal(writes, 0);
});

test("arm refuses foreign retired automation ownership whether it is off or on", async () => {
  const [battery] = buildBlockedAutomationConfigs({ ...SPEC, ev_enabled: false });
  for (const retiredState of ["off", "on"]) {
    let serviceCalls = 0;
    const hass = {
      states: {
        "automation.battery": { state: "off", attributes: { id: battery.id } },
        "automation.foreign_ev": { state: retiredState, attributes: { id: "dynamic_energy_ev_v1" } },
      },
      async callApi(method, path) {
        const id = path.split("/").at(-1);
        if (id === battery.id) {
          const { id: ignored, ...body } = battery;
          return body;
        }
        return { alias: "Foreign retired automation", actions: [] };
      },
      async callService() {
        serviceCalls += 1;
      },
    };

    assert.equal(
      (await loadBlockedAutomationState(hass, { ...SPEC, ev_enabled: false })).mode,
      "CONFLICT",
    );
    await assert.rejects(
      performBlockedControlAction(hass, { ...SPEC, ev_enabled: false }, "arm", () => true),
      /dynamic_energy_ev_v1 is not a verified blocked automation/,
    );
    assert.equal(serviceCalls, 0);
  }
});

test("hidden retired automation configuration forces conflict and blocks every action", async () => {
  const [battery] = buildBlockedAutomationConfigs({ ...SPEC, ev_enabled: false });
  let serviceCalls = 0;
  const hass = {
    states: {
      "automation.battery": { state: "off", attributes: { id: battery.id } },
    },
    async callApi(method, path) {
      assert.equal(method, "GET");
      const id = path.split("/").at(-1);
      if (id === battery.id) return battery;
      if (id === "dynamic_energy_ev_v1") {
        return { id, alias: "Foreign hidden retired automation", actions: [] };
      }
      const error = new Error("not found");
      error.status = 404;
      throw error;
    },
    async callService() {
      serviceCalls += 1;
    },
  };

  assert.equal(
    (await loadBlockedAutomationState(hass, { ...SPEC, ev_enabled: false })).mode,
    "CONFLICT",
  );
  for (const action of ["create", "arm", "off"]) {
    await assert.rejects(
      performBlockedControlAction(hass, { ...SPEC, ev_enabled: false }, action, () => true),
      /dynamic_energy_ev_v1 is not a verified blocked automation/,
    );
  }
  assert.equal(serviceCalls, 0);
});

test("control panel snapshot explains live prices, plan, assets and stricter device constraints", () => {
  const snapshot = buildControlPanelSnapshot(controlPanelHass(), PANEL_SPEC, CONTROL_NOW);

  assert.equal(snapshot.price.quality, "GOOD");
  assert.equal(snapshot.price.currentEurPerKwh, 0.12);
  assert.equal(snapshot.price.cheapestEurPerKwh, 0.08);
  assert.equal(snapshot.price.highestEurPerKwh, 0.31);
  assert.equal(snapshot.plan.action, "CHARGE_FROM_GRID");
  assert.equal(snapshot.plan.plannedGridImportKw, 3.5);
  assert.equal(snapshot.live.batterySocPercent, 58);
  assert.equal(snapshot.live.gridKw, 4.2);
  assert.equal(snapshot.live.evKw, 2.2);
  assert.equal(snapshot.readiness.mode, "SHADOW_READY");
  assert.match(snapshot.readiness.warnings.join(" "), /5\.5 kW/);
  assert.match(snapshot.readiness.warnings.join(" "), /7 kW/);
});

test("control panel marks stale plan data unavailable instead of showing old prices", () => {
  const snapshot = buildControlPanelSnapshot(
    controlPanelHass("2026-10-12T23:00:00Z"),
    PANEL_SPEC,
    CONTROL_NOW,
  );

  assert.equal(snapshot.price.quality, "STALE");
  assert.equal(snapshot.price.currentEurPerKwh, null);
  assert.equal(snapshot.plan.action, "NO_ACTION");
  assert.equal(snapshot.readiness.mode, "DATA_BLOCKED");
});

test("control panel keeps a valid Day-Ahead plan visible when it is older than live telemetry", () => {
  const snapshot = buildControlPanelSnapshot(
    controlPanelHass("2026-10-14T06:00:00Z"),
    PANEL_SPEC,
    CONTROL_NOW,
  );

  assert.equal(snapshot.price.quality, "GOOD");
  assert.equal(snapshot.price.currentEurPerKwh, 0.12);
  assert.equal(snapshot.live.gridQuality, "STALE");
  assert.equal(snapshot.readiness.mode, "SHADOW_READY_LIVE_DEGRADED");
  assert.match(snapshot.readiness.warnings.join(" "), /live netvermogen is verouderd/i);

  const html = renderBlockedControlConfig(
    PANEL_SPEC,
    { mode: "ARMED_BLOCKED", automations: [] },
    "",
    snapshot,
  );
  assert.match(html, /Prijsdata gereed · live data beperkt/);
  assert.match(html, /Netimport[\s\S]*4,2 kW[\s\S]*verouderd/);
});

test("control panel rejects future-dated plan and live observations", () => {
  const snapshot = buildControlPanelSnapshot(
    controlPanelHass("2026-10-15T08:04:00Z"),
    PANEL_SPEC,
    CONTROL_NOW,
  );

  assert.equal(snapshot.price.quality, "INVALID");
  assert.equal(snapshot.price.currentEurPerKwh, null);
  assert.equal(snapshot.live.gridQuality, "INVALID");
  assert.equal(snapshot.readiness.mode, "DATA_BLOCKED");
});

test("control panel rejects out-of-range SOC and unsupported power units", () => {
  const hass = controlPanelHass();
  hass.states["sensor.battery_soc"].state = "999";
  hass.states["sensor.grid_power"].state = "16";
  hass.states["sensor.grid_power"].attributes.unit_of_measurement = "A";

  const snapshot = buildControlPanelSnapshot(hass, PANEL_SPEC, CONTROL_NOW);

  assert.equal(snapshot.live.batterySocPercent, null);
  assert.equal(snapshot.live.batterySocQuality, "INVALID");
  assert.equal(snapshot.live.gridKw, null);
  assert.equal(snapshot.live.gridQuality, "INVALID");
  assert.equal(snapshot.readiness.mode, "SHADOW_READY_LIVE_DEGRADED");
  assert.match(snapshot.readiness.warnings.join(" "), /batterij-SOC is ongeldig/i);
  assert.match(snapshot.readiness.warnings.join(" "), /netvermogen is ongeldig/i);
});

test("control panel supports an explicit negative-import grid sign convention", () => {
  const hass = controlPanelHass();
  hass.states["sensor.grid_power"].state = "-4200";

  const snapshot = buildControlPanelSnapshot(
    hass,
    { ...PANEL_SPEC, grid_import_positive: false },
    CONTROL_NOW,
  );

  assert.equal(snapshot.live.gridKw, 4.2);
});

test("control panel rejects YAML freshness limits outside the visual editor bounds", () => {
  for (const override of [
    { data_stale_after_minutes: 0 },
    { data_stale_after_minutes: 181 },
    { plan_stale_after_hours: 0 },
    { plan_stale_after_hours: 73 },
    { plan_stale_after_hours: 999999 },
  ]) {
    assert.throws(
      () => buildControlPanelSnapshot(controlPanelHass(), { ...PANEL_SPEC, ...override }, CONTROL_NOW),
      /must be between/,
    );
  }
});

test("next cheapest excludes the already-started current interval", () => {
  const hass = controlPanelHass();
  hass.states["sensor.dynamic_energy_shadow_plan"].attributes.prices = [
    { start_utc: "2026-10-14T08:00:00Z", duration_hours: 0.25, import_eur_per_kwh: 0.01 },
    { start_utc: "2026-10-14T08:15:00Z", duration_hours: 0.25, import_eur_per_kwh: 0.09 },
    { start_utc: "2026-10-14T08:30:00Z", duration_hours: 0.25, import_eur_per_kwh: 0.11 },
  ];

  const snapshot = buildControlPanelSnapshot(hass, PANEL_SPEC, CONTROL_NOW);

  assert.equal(snapshot.price.currentEurPerKwh, 0.01);
  assert.equal(snapshot.price.cheapestEurPerKwh, 0.09);
  assert.equal(snapshot.price.cheapestStartUtc, "2026-10-14T08:15:00.000Z");
});

test("the richer control card renders prices, readiness and separate SMA and Smappee setup guidance", () => {
  const snapshot = buildControlPanelSnapshot(controlPanelHass(), PANEL_SPEC, CONTROL_NOW);
  const html = renderBlockedControlConfig(
    PANEL_SPEC,
    { mode: "ARMED_BLOCKED", automations: [] },
    "",
    snapshot,
  );

  assert.match(html, /Prijsstrategie/);
  assert.match(html, /€0,120\/kWh/);
  assert.match(html, /Volgende goedkoopste/);
  assert.match(html, /SMA batterij · aanbevolen configuratie/);
  assert.match(html, /Sunny Home Manager 2\.0/);
  assert.match(html, /Economisch/);
  assert.match(html, /Forecast-based charging pas activeren na gecontroleerde pilot/);
  assert.match(html, /Smappee EV · aanbevolen configuratie/);
  assert.match(html, /Smart/);
  assert.match(html, /5,5 kW/);
  assert.match(html, /één actieve controller per actuator/);
  assert.match(html, /Geen instelling wordt vanuit deze kaart naar SMA of Smappee geschreven/);
  assert.match(html, /Offline laden[\s\S]*UIT aanbevolen[\s\S]*Huidige sitefallback 8 A/);
  assert.doesNotMatch(html, /data-action="sma|data-action="smappee/);
});

test("the separate HACS control card exposes a bounded visual configuration schema", () => {
  const form = DynamicEnergyControlConfigCard.getConfigForm();
  const names = form.schema.map((field) => field.name);

  assert.deepEqual(names, [
    "title",
    "name_prefix",
    "plan_entity",
    "interval_minutes",
    "peak_limit_kw",
    "battery_enabled",
    "battery_reserve_soc_percent",
    "ev_enabled",
    "ev_target_soc_percent",
    "ev_departure_time",
    "battery_soc_entity",
    "grid_power_entity",
    "grid_import_positive",
    "ev_power_entity",
    "data_stale_after_minutes",
    "plan_stale_after_hours",
    "sma_controller",
    "sma_optimization_goal",
    "sma_tariff_type",
    "sma_forecast_charging",
    "sma_grid_charge_soc_percent",
    "sma_feed_in_eur_per_kwh",
    "smappee_mode",
    "smappee_grid_connection",
    "smappee_capacity_threshold_kw",
    "smappee_max_current_ampere",
    "smappee_offline_fallback_ampere",
  ]);
  assert.equal(DynamicEnergyControlConfigCard.getStubConfig().control_mode, "ARMED_BLOCKED");
  assert.equal(DynamicEnergyControlConfigCard.getStubConfig().execution_allowed, false);
});

test("the control card renders an operate surface with create, arm-blocked and off actions but no live mode", () => {
  const html = renderBlockedControlConfig(SPEC, {
    mode: "ARMED_BLOCKED",
    automations: [
      { id: "dynamic_energy_battery_v1", entity_id: "automation.battery", state: "on" },
      { id: "dynamic_energy_ev_v1", entity_id: "automation.ev", state: "on" },
    ],
  });

  assert.match(html, /Gewapend · fysiek geblokkeerd/);
  assert.match(html, /data-action="create"/);
  assert.match(html, /data-action="arm"/);
  assert.match(html, /data-action="off"/);
  assert.match(html, /execution_allowed = false/);
  assert.doesNotMatch(html, /LIVE/);
  assert.doesNotMatch(html, /SMA.*turn_on|Smappee.*turn_on/);
});

test("the configuration card does not claim a verified safety lock during a conflict", () => {
  const html = renderBlockedControlConfig(SPEC, { mode: "CONFLICT", automations: [] });

  assert.match(html, /Safety status niet geverifieerd/);
  assert.match(html, /safety-lock conflict/);
  assert.doesNotMatch(html, /Safety lock actief/);
});

test("setup-required safety state is visibly unverified rather than successful", () => {
  const html = renderBlockedControlConfig(SPEC, { mode: "SETUP_REQUIRED", automations: [] });

  assert.match(html, /safety-lock unverified/);
  assert.match(html, /Safety status niet geverifieerd/);
  assert.doesNotMatch(html, /safety-lock verified/);
});

test("the card requires explicit confirmation before creating Home Assistant automations", async () => {
  let writes = 0;
  const hass = {
    async callWS() {
      return {
        trigger: { valid: true, error: null },
        condition: { valid: true, error: null },
        action: { valid: true, error: null },
      };
    },
    async callApi() {
      writes += 1;
    },
  };

  const result = await performBlockedControlAction(hass, SPEC, "create", () => false);

  assert.equal(result.status, "CANCELLED");
  assert.equal(writes, 0);
});
