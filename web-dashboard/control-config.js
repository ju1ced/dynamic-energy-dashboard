"use strict";

export const ACTIVATION_CAPABILITY = Object.freeze({
  live_activation_allowed: false,
  explicit_owner_go: false,
  backend_control_adapter_available: false,
  safety_preflight_available: false,
  reason: "LIVE_ACTIVATION_REQUIRES_SEPARATE_OWNER_GO",
});

const TARGETS = new Set(["battery", "ev", "joint"]);
const MODES = new Set(["monitor", "simulation", "active"]);
const TIME_PATTERN = /^(?:[01]\d|2[0-3]):[0-5]\d$/;

function finiteNumber(value, fallback) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function boundedInteger(value, fallback, minimum, maximum) {
  const number = Math.round(finiteNumber(value, fallback));
  return Math.min(maximum, Math.max(minimum, number));
}

function automationId() {
  return `automation-${Date.now()}-${Math.random().toString(16).slice(2, 10)}`;
}

export function createAutomationDraft(input = {}) {
  const days = Array.isArray(input.days)
    ? [...new Set(input.days.map(Number).filter(day => Number.isInteger(day) && day >= 0 && day <= 6))].sort()
    : [0, 1, 2, 3, 4, 5, 6];
  return {
    id: typeof input.id === "string" && input.id.trim() ? input.id.trim() : automationId(),
    schema_version: 1,
    name: typeof input.name === "string" && input.name.trim() ? input.name.trim() : "Nieuwe automatisatie",
    target: TARGETS.has(input.target) ? input.target : "joint",
    enabled: input.enabled !== false,
    priority: boundedInteger(input.priority, 50, 0, 100),
    days,
    max_grid_import_kw: finiteNumber(input.max_grid_import_kw, 7),
    price_ceiling_eur_per_kwh: finiteNumber(input.price_ceiling_eur_per_kwh, 0.2),
    battery_min_soc_percent: finiteNumber(input.battery_min_soc_percent, 15),
    battery_max_soc_percent: finiteNumber(input.battery_max_soc_percent, 90),
    ev_target_soc_percent: finiteNumber(input.ev_target_soc_percent, 80),
    ev_departure_time: typeof input.ev_departure_time === "string" ? input.ev_departure_time : "07:30",
    strategy: typeof input.strategy === "string" ? input.strategy : "CHEAPEST_VALIDATED_INTERVALS",
    mode: "DRY_RUN_ONLY",
    execution_allowed: false,
    physical_writes: false,
    home_assistant_writes: false,
    sma_writes: false,
    smappee_writes: false,
  };
}

export function validateAutomationDraft(draft) {
  const errors = [];
  if (!draft || typeof draft !== "object" || Array.isArray(draft)) {
    return { valid: false, errors: ["AUTOMATION_DRAFT_INVALID"] };
  }
  if (typeof draft.name !== "string" || !draft.name.trim()) errors.push("NAME_REQUIRED");
  if (!TARGETS.has(draft.target)) errors.push("TARGET_INVALID");
  if (!Number.isFinite(draft.max_grid_import_kw) || draft.max_grid_import_kw <= 0) {
    errors.push("GRID_IMPORT_LIMIT_INVALID");
  }
  if (
    !Number.isFinite(draft.battery_min_soc_percent)
    || !Number.isFinite(draft.battery_max_soc_percent)
    || draft.battery_min_soc_percent < 0
    || draft.battery_max_soc_percent > 100
    || draft.battery_min_soc_percent >= draft.battery_max_soc_percent
  ) {
    errors.push("BATTERY_SOC_RANGE_INVALID");
  }
  if (
    !Number.isFinite(draft.ev_target_soc_percent)
    || draft.ev_target_soc_percent < 0
    || draft.ev_target_soc_percent > 100
  ) {
    errors.push("EV_TARGET_SOC_INVALID");
  }
  if (!TIME_PATTERN.test(String(draft.ev_departure_time || ""))) {
    errors.push("EV_DEPARTURE_TIME_INVALID");
  }
  if (!Array.isArray(draft.days) || draft.days.length === 0) errors.push("ACTIVE_DAYS_REQUIRED");
  if (
    draft.execution_allowed !== false
    || draft.physical_writes !== false
    || draft.home_assistant_writes !== false
    || draft.sma_writes !== false
    || draft.smappee_writes !== false
  ) {
    errors.push("WRITE_BOUNDARY_INVALID");
  }
  return { valid: errors.length === 0, errors };
}

export function requestOperatingMode(currentMode, requestedMode, capability = ACTIVATION_CAPABILITY) {
  const current = MODES.has(currentMode) ? currentMode : "monitor";
  if (!MODES.has(requestedMode)) {
    return { mode: current, accepted: false, reason: "MODE_INVALID" };
  }
  if (requestedMode === "active") {
    const accepted = capability?.live_activation_allowed === true
      && capability?.explicit_owner_go === true
      && capability?.backend_control_adapter_available === true
      && capability?.safety_preflight_available === true;
    return accepted
      ? { mode: "active", accepted: true, reason: "LIVE_ACTIVATION_ACCEPTED" }
      : { mode: current, accepted: false, reason: "LIVE_ACTIVATION_LOCKED" };
  }
  return {
    mode: requestedMode,
    accepted: true,
    reason: requestedMode === "simulation" ? "DRY_RUN_MODE_SELECTED" : "MONITOR_MODE_SELECTED",
  };
}

export function serializeAutomationBundle(drafts) {
  const automations = (Array.isArray(drafts) ? drafts : []).map(createAutomationDraft);
  const invalid = automations.flatMap(draft => {
    const result = validateAutomationDraft(draft);
    return result.errors.map(error => `${draft.id}:${error}`);
  });
  return {
    schema_version: 1,
    mode: "DRY_RUN_CONFIGURATION",
    classification: "CONFIGURATION_DRAFT_NO_CONTROL",
    execution_allowed: false,
    physical_writes: false,
    home_assistant_writes: false,
    sma_writes: false,
    smappee_writes: false,
    valid: invalid.length === 0,
    validation_errors: invalid,
    automations,
  };
}
