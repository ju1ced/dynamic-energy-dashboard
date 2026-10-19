import test from "node:test";
import assert from "node:assert/strict";

import {
  ACTIVATION_CAPABILITY,
  createAutomationDraft,
  requestOperatingMode,
  serializeAutomationBundle,
  validateAutomationDraft,
} from "../../web-dashboard/control-config.js";

test("active mode remains locked without an explicit live capability", () => {
  const result = requestOperatingMode("simulation", "active", ACTIVATION_CAPABILITY);

  assert.equal(result.mode, "simulation");
  assert.equal(result.accepted, false);
  assert.equal(result.reason, "LIVE_ACTIVATION_LOCKED");
});

test("monitor and simulation are selectable without enabling writes", () => {
  const result = requestOperatingMode("monitor", "simulation", ACTIVATION_CAPABILITY);

  assert.deepEqual(result, {
    mode: "simulation",
    accepted: true,
    reason: "DRY_RUN_MODE_SELECTED",
  });
});

test("automation drafts normalize battery and EV constraints", () => {
  const draft = createAutomationDraft({
    name: "Goedkope nachtvensters",
    target: "joint",
    priority: 20,
    max_grid_import_kw: 7,
    price_ceiling_eur_per_kwh: 0.18,
    battery_min_soc_percent: 15,
    battery_max_soc_percent: 90,
    ev_target_soc_percent: 80,
    ev_departure_time: "07:30",
    days: [1, 2, 3, 4, 5],
  });

  assert.equal(validateAutomationDraft(draft).valid, true);
  assert.equal(draft.execution_allowed, false);
  assert.equal(draft.home_assistant_writes, false);
  assert.equal(draft.sma_writes, false);
  assert.equal(draft.smappee_writes, false);
});

test("invalid automation limits fail closed", () => {
  const draft = createAutomationDraft({
    battery_min_soc_percent: 95,
    battery_max_soc_percent: 20,
    ev_departure_time: "25:00",
    max_grid_import_kw: 0,
  });
  const result = validateAutomationDraft(draft);

  assert.equal(result.valid, false);
  assert.ok(result.errors.includes("BATTERY_SOC_RANGE_INVALID"));
  assert.ok(result.errors.includes("EV_DEPARTURE_TIME_INVALID"));
  assert.ok(result.errors.includes("GRID_IMPORT_LIMIT_INVALID"));
});

test("serialized configuration is explicitly non-executable", () => {
  const bundle = serializeAutomationBundle([
    createAutomationDraft({ name: "Werkdagen", target: "joint" }),
  ]);

  assert.equal(bundle.mode, "DRY_RUN_CONFIGURATION");
  assert.equal(bundle.execution_allowed, false);
  assert.equal(bundle.physical_writes, false);
  assert.equal(bundle.home_assistant_writes, false);
  assert.equal(bundle.sma_writes, false);
  assert.equal(bundle.smappee_writes, false);
  assert.equal(bundle.automations.length, 1);
  assert.equal("endpoint" in bundle, false);
  assert.equal("service" in bundle, false);
});
