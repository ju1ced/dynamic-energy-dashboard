import test from "node:test";
import assert from "node:assert/strict";

import {
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
      const { id: ignored, ...body } = configs.find((config) => config.id === id);
      return body;
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
      const { id: ignored, ...body } = configs.find((config) => config.id === id);
      return body;
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
      const { id: ignored, ...body } = configs.find((config) => config.id === id);
      return body;
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
  assert.doesNotMatch(html, /Safety lock actief/);
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
