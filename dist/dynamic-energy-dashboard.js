const CARD_TAG = "dynamic-energy-shadow-card";
const DEFAULT_CONFIG = Object.freeze({
  title: "Shadow-sturing",
  plan_attribute: "schedule",
  price_attribute: "prices",
  integration_price_attribute: "data",
  price_reference_eur_per_kwh: 0.277,
  peak_limit_kw: 7,
  stale_after_minutes: 10,
  price_stale_after_minutes: 20,
  plan_stale_after_hours: 30,
  deviation_warning_kw: 0.5,
  grid_import_positive: true,
  battery_charge_positive: true,
});

const ACTION_LABELS = Object.freeze({
  CHARGE_FROM_GRID: "Laden vanaf net",
  STORE_PV_SURPLUS: "PV-overschot opslaan",
  DISCHARGE_TO_LOAD: "Ontladen naar woning",
  HOLD: "Geen batterijactie",
  NO_ACTION: "Geen actie",
});

const STATUS_LABELS = Object.freeze({
  TRACKING: "Plan gevolgd",
  DEVIATION: "Afwijking",
  PEAK_RISK: "Piekgrens bereikt",
  STALE_DATA: "Data verouderd",
  UNAVAILABLE_DATA: "Data onbeschikbaar",
  DATA_GATED: "Plan ontbreekt",
  NO_ACTION: "Geen geldig interval",
  SETUP_REQUIRED: "Configuratie nodig",
});

const REQUIRED_ENTITY_FIELDS = Object.freeze([
  "grid_power_entity",
  "pv_power_entity",
  "battery_power_entity",
  "battery_soc_entity",
]);
const SHADOW_RENDER_ENTITY_FIELDS = Object.freeze([
  ...REQUIRED_ENTITY_FIELDS,
  "house_power_entity",
  "ev_power_entity",
  "heat_pump_power_entity",
  "import_price_entity",
  "export_price_entity",
  "plan_entity",
]);
const VALIDATION_TELEMETRY_ENTITY_FIELDS = Object.freeze([
  "grid_power_entity",
  "battery_power_entity",
  "battery_freshness_entity",
  "ev_power_entity",
  "house_power_entity",
  "pv_power_entity",
  "heat_pump_power_entity",
]);
const VALIDATION_TELEMETRY_REFRESH_MS = 60_000;

const CONTROL_CARD_TAG = "dynamic-energy-control-config-card";
const VALIDATION_CARD_TAG = "dynamic-energy-validation-card";
const CONTROL_MARKER = "managed_by=dynamic-energy-control-config-card";
const CONTROL_SNAPSHOT_PREFIX = `${CONTROL_MARKER}; execution_allowed=false; controller_state=ARMED_BLOCKED; config_snapshot=`;
const BLOCKED_STOP = "Dynamic Energy safety lock: live actuator execution is not authorized";
const ALL_MANAGED_AUTOMATION_IDS = Object.freeze([
  "dynamic_energy_battery_v1",
  "dynamic_energy_ev_v1",
]);
const DEFAULT_CONTROL_CONFIG = Object.freeze({
  title: "Dynamic Energy configuratie",
  name_prefix: "Dynamic Energy",
  plan_entity: "sensor.dynamic_energy_shadow_plan",
  interval_minutes: 15,
  peak_limit_kw: 7,
  battery_enabled: true,
  battery_reserve_soc_percent: 10,
  ev_enabled: true,
  ev_target_soc_percent: 80,
  ev_departure_time: "07:00:00",
  battery_soc_entity: "",
  grid_power_entity: "",
  grid_import_positive: true,
  ev_power_entity: "",
  import_price_entity: "",
  export_price_entity: "",
  integration_price_attribute: "data",
  price_stale_after_minutes: 20,
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
  smappee_dynamic_tariff_status: "NOT_VERIFIED",
  control_mode: "ARMED_BLOCKED",
  execution_allowed: false,
});

const DEFAULT_VALIDATION_CONFIG = Object.freeze({
  title: "Dynamic Energy validatie",
  plan_entity: "sensor.dynamic_energy_shadow_plan",
  grid_power_entity: "",
  grid_import_positive: true,
  battery_power_entity: "",
  battery_charge_positive: true,
  battery_freshness_entity: "",
  ev_power_entity: "",
  house_power_entity: "",
  pv_power_entity: "",
  heat_pump_power_entity: "",
  validation_summary_entity: "",
  import_price_entity: "",
  export_price_entity: "",
  integration_price_attribute: "data",
  price_stale_after_minutes: 20,
  peak_limit_kw: 7,
  smappee_capacity_threshold_kw: 5.5,
  activity_threshold_kw: 0.2,
  data_stale_after_minutes: 10,
  plan_stale_after_hours: 30,
  summary_stale_after_hours: 36,
  pilot_status: "NOT_STARTED",
  execution_allowed: false,
});
const VALIDATION_PILOT_STATUSES = Object.freeze([
  "NOT_STARTED",
  "PROTECTION_BASELINE_PENDING",
  "SMA_ONLY_PILOT",
  "SMAPPEE_ONLY_PILOT",
  "COMBINED_OBSERVATION",
  "EVIDENCE_INSUFFICIENT",
  "READY_FOR_REVIEW",
  "BLOCKED",
]);

function requiredFinite(value, field, minimum, maximum) {
  const parsed = finiteNumber(value);
  if (parsed === null || parsed < minimum || parsed > maximum) {
    throw new Error(`${field} must be between ${minimum} and ${maximum}`);
  }
  return parsed;
}

function requiredText(value, field) {
  if (typeof value !== "string" || value.trim() === "") {
    throw new Error(`${field} is required`);
  }
  return value.trim();
}

function canonicalJson(value) {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (isPlainObject(value)) {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

function blockedAutomationSnapshot(config) {
  const unsigned = Object.fromEntries(
    Object.entries(config).filter(([key]) => !["description", "id"].includes(key)),
  );
  return encodeURIComponent(canonicalJson(unsigned));
}

function sealBlockedAutomation(config) {
  return {
    ...config,
    description: `${CONTROL_SNAPSHOT_PREFIX}${blockedAutomationSnapshot(config)}`,
  };
}

export function buildBlockedAutomationConfigs(spec) {
  if (!isPlainObject(spec)) throw new Error("control specification must be an object");
  const prefix = requiredText(spec.name_prefix, "name_prefix");
  const planEntity = requiredText(spec.plan_entity, "plan_entity");
  const intervalMinutes = requiredFinite(spec.interval_minutes, "interval_minutes", 5, 60);
  if (![5, 10, 15, 30, 60].includes(intervalMinutes)) {
    throw new Error("interval_minutes is not supported");
  }
  const peakLimitKw = requiredFinite(spec.peak_limit_kw, "peak_limit_kw", 0.1, 30);
  const common = {
    mode: "single",
    max_exceeded: "silent",
    triggers: [{ trigger: "time_pattern", minutes: `/${intervalMinutes}` }],
    conditions: [],
    actions: [{ stop: BLOCKED_STOP, error: false }],
  };
  const automations = [];
  if (spec.battery_enabled === true) {
    automations.push(sealBlockedAutomation({
      id: "dynamic_energy_battery_v1",
      alias: `${prefix} · Batterij dry-run`,
      ...common,
      variables: {
        execution_allowed: false,
        control_mode: "ARMED_BLOCKED",
        actuator_owner: "SMA",
        plan_entity: planEntity,
        peak_limit_kw: peakLimitKw,
        battery_reserve_soc_percent: requiredFinite(
          spec.battery_reserve_soc_percent,
          "battery_reserve_soc_percent",
          0,
          100,
        ),
      },
    }));
  }
  if (spec.ev_enabled === true) {
    automations.push(sealBlockedAutomation({
      id: "dynamic_energy_ev_v1",
      alias: `${prefix} · EV dry-run`,
      ...common,
      variables: {
        execution_allowed: false,
        control_mode: "ARMED_BLOCKED",
        actuator_owner: "SMAPPEE",
        plan_entity: planEntity,
        peak_limit_kw: peakLimitKw,
        ev_target_soc_percent: requiredFinite(
          spec.ev_target_soc_percent,
          "ev_target_soc_percent",
          0,
          100,
        ),
        ev_departure_time: requiredText(spec.ev_departure_time, "ev_departure_time"),
      },
    }));
  }
  if (!automations.length) throw new Error("at least one dry-run automation must be enabled");
  return automations;
}

function validationErrors(result) {
  if (!isPlainObject(result)) return ["invalid validation response"];
  const errors = [];
  for (const key of ["trigger", "condition", "action"]) {
    const section = result[key];
    if (Array.isArray(section)) {
      errors.push(...section.filter((value) => value !== undefined && value !== null && value !== ""));
      continue;
    }
    if (!isPlainObject(section)) {
      errors.push(`${key}: invalid validation response`);
      continue;
    }
    if (section.valid === true && (section.error === null || section.error === undefined || section.error === "")) {
      continue;
    }
    errors.push(section.error || `${key}: invalid configuration`);
  }
  return errors;
}

function isNotFoundError(error) {
  return error?.status === 404
    || error?.status_code === 404
    || error?.code === 404
    || error?.body?.status === 404;
}

async function loadExistingAutomationConfig(hass, automationId) {
  try {
    return await hass.callApi(
      "GET",
      `config/automation/config/${encodeURIComponent(automationId)}`,
    );
  } catch (error) {
    if (isNotFoundError(error)) return null;
    throw error;
  }
}

export async function saveBlockedAutomations(hass, spec) {
  if (!hass || typeof hass.callWS !== "function" || typeof hass.callApi !== "function") {
    throw new Error("Home Assistant automation API is unavailable");
  }
  const automations = buildBlockedAutomationConfigs(spec);
  for (const automation of automations) {
    const existing = await loadExistingAutomationConfig(hass, automation.id);
    if (existing !== null && !isVerifiedBlockedAutomation(existing, automation.id)) {
      throw new Error(`${automation.id} existing automation is not managed by this card`);
    }
  }
  const validations = [];
  for (const automation of automations) {
    validations.push({
      automation,
      result: await hass.callWS({
        type: "validate_config",
        trigger: automation.triggers,
        condition: automation.conditions,
        action: automation.actions,
      }),
    });
  }
  for (const { automation, result } of validations) {
    const errors = validationErrors(result);
    if (errors.length) {
      throw new Error(`Home Assistant rejected ${automation.id}: ${JSON.stringify(errors)}`);
    }
  }
  const saved = [];
  for (const automation of automations) {
    const { id, ...body } = automation;
    await hass.callApi("POST", `config/automation/config/${encodeURIComponent(id)}`, body);
    saved.push({ id, alias: automation.alias });
  }
  return saved;
}

function isVerifiedBlockedAutomation(config, expectedId = null) {
  try {
    return isPlainObject(config)
      && (!Object.hasOwn(config, "id") || config.id === expectedId)
      && config.description === `${CONTROL_SNAPSHOT_PREFIX}${blockedAutomationSnapshot(config)}`
      && isPlainObject(config.variables)
      && config.variables.execution_allowed === false
      && config.variables.control_mode === "ARMED_BLOCKED"
      && Array.isArray(config.actions)
      && config.actions.length === 1
      && isPlainObject(config.actions[0])
      && config.actions[0].stop === BLOCKED_STOP
      && config.actions[0].error === false
      && !Object.hasOwn(config.actions[0], "action")
      && !Object.hasOwn(config.actions[0], "service")
      && !Object.hasOwn(config.actions[0], "target")
      && !Object.hasOwn(config.actions[0], "device_id");
  } catch {
    return false;
  }
}

function managedEntityIds(hass, automationId) {
  return Object.entries(safeValue(hass, "states") || {})
    .filter(([entityId, stateObject]) => entityId.startsWith("automation.")
      && safeValue(safeAttributes(stateObject), "id") === automationId)
    .map(([entityId]) => entityId);
}

function managedEntityId(hass, automationId) {
  const matches = managedEntityIds(hass, automationId);
  return matches.length === 1 ? matches[0] : null;
}

export function getBlockedAutomationState(
  hass,
  spec,
  verifiedIds = new Set(),
  existingIds = new Set(),
) {
  const ids = buildBlockedAutomationConfigs(spec).map((automation) => automation.id);
  if (ALL_MANAGED_AUTOMATION_IDS.some((id) => managedEntityIds(hass, id).length > 1)) {
    return { mode: "CONFLICT", automations: [] };
  }
  const rows = ids.map((id) => {
    const entityId = managedEntityId(hass, id);
    const stateObject = entityId ? safeValue(safeValue(hass, "states") || {}, entityId) : null;
    return {
      id,
      entity_id: entityId,
      state: safeValue(stateObject, "state") || null,
      verified: verifiedIds.has(id),
    };
  });
  const retiredIds = ALL_MANAGED_AUTOMATION_IDS.filter(
    (id) => !ids.includes(id) && (existingIds.has(id) || managedEntityId(hass, id)),
  );
  const retiredConflict = retiredIds.some((id) => {
    const entityId = managedEntityId(hass, id);
    const state = entityId
      ? safeValue(safeValue(safeValue(hass, "states") || {}, entityId), "state")
      : null;
    return !verifiedIds.has(id) || state !== "off";
  });
  if (retiredConflict) return { mode: "CONFLICT", automations: rows };
  if (rows.every((row) => row.entity_id === null)) {
    const desiredConfigurationExists = ids.some((id) => existingIds.has(id));
    return {
      mode: desiredConfigurationExists ? "CONFLICT" : "SETUP_REQUIRED",
      automations: rows,
    };
  }
  if (rows.some((row) => row.entity_id === null)) return { mode: "CONFLICT", automations: rows };
  if (rows.some((row) => row.verified !== true)) return { mode: "CONFLICT", automations: rows };
  if (rows.every((row) => row.state === "off")) return { mode: "OFF", automations: rows };
  if (rows.every((row) => row.state === "on")) return { mode: "ARMED_BLOCKED", automations: rows };
  return { mode: "CONFLICT", automations: rows };
}

export async function loadBlockedAutomationState(hass, spec) {
  if (!hass || typeof hass.callApi !== "function") {
    return { mode: "CONFLICT", automations: [] };
  }
  const verifiedIds = new Set();
  const existingIds = new Set();
  for (const id of ALL_MANAGED_AUTOMATION_IDS) {
    const config = await loadExistingAutomationConfig(hass, id);
    if (config === null) continue;
    existingIds.add(id);
    if (isVerifiedBlockedAutomation(config, id)) verifiedIds.add(id);
  }
  return getBlockedAutomationState(hass, spec, verifiedIds, existingIds);
}

export async function setBlockedAutomationsArmed(hass, automationIds, armed) {
  if (!hass || typeof hass.callApi !== "function" || typeof hass.callService !== "function") {
    throw new Error("Home Assistant control API is unavailable");
  }
  if (!Array.isArray(automationIds) || automationIds.length === 0) {
    throw new Error("managed automation ids are required");
  }
  const uniqueIds = [...new Set(automationIds)];
  const entityIds = [];
  for (const automationId of uniqueIds) {
    if (!/^dynamic_energy_(battery|ev)_v1$/.test(automationId)) {
      throw new Error(`${automationId} is outside the managed namespace`);
    }
    const matches = managedEntityIds(hass, automationId);
    if (matches.length > 1) {
      throw new Error(`${automationId} has multiple Home Assistant entities`);
    }
    const [entityId] = matches;
    if (!entityId) throw new Error(`${automationId} has no unique Home Assistant entity`);
    const config = await hass.callApi(
      "GET",
      `config/automation/config/${encodeURIComponent(automationId)}`,
    );
    if (!isVerifiedBlockedAutomation(config, automationId)) {
      throw new Error(`${automationId} is not a verified blocked automation`);
    }
    entityIds.push(entityId);
  }
  await hass.callService(
    "automation",
    armed ? "turn_on" : "turn_off",
    {},
    { entity_id: entityIds },
  );
  return {
    mode: armed ? "ARMED_BLOCKED" : "OFF",
    entity_ids: entityIds,
  };
}

export async function performBlockedControlAction(hass, config, action, confirmAction) {
  if (!["create", "arm", "off"].includes(action)) throw new Error("unsupported control action");
  if (typeof confirmAction !== "function") throw new Error("explicit confirmation callback is required");
  const prompts = {
    create: "Home Assistant-automatisaties aanmaken of bijwerken? Ze blijven hard geblokkeerd voor actuatorwrites.",
    arm: "De beheerde automatisaties inschakelen in ARMED_BLOCKED-modus? Fysieke uitvoering blijft geblokkeerd.",
    off: "De beheerde Dynamic Energy-automatisaties uitschakelen?",
  };
  const confirmed = await Promise.resolve(confirmAction(prompts[action]));
  if (confirmed !== true) return { status: "CANCELLED" };
  const desiredIds = buildBlockedAutomationConfigs(config).map((automation) => automation.id);
  for (const id of ALL_MANAGED_AUTOMATION_IDS) {
    if (managedEntityIds(hass, id).length > 1) {
      throw new Error(`${id} has multiple Home Assistant entities`);
    }
  }
  const existingConfigs = new Map();
  for (const id of ALL_MANAGED_AUTOMATION_IDS) {
    const existing = await loadExistingAutomationConfig(hass, id);
    if (existing !== null) existingConfigs.set(id, existing);
  }
  const retiredIds = ALL_MANAGED_AUTOMATION_IDS
    .filter((id) => !desiredIds.includes(id)
      && (existingConfigs.has(id) || managedEntityId(hass, id)));
  if (["create", "arm"].includes(action)) {
    for (const id of retiredIds) {
      const existing = existingConfigs.get(id) || null;
      if (existing === null || !isVerifiedBlockedAutomation(existing, id)) {
        throw new Error(`${id} is not a verified blocked automation`);
      }
      const entityId = managedEntityId(hass, id);
      if (!entityId) throw new Error(`${id} has no unique Home Assistant entity`);
      const state = safeValue(safeValue(safeValue(hass, "states") || {}, entityId), "state");
      if (action === "arm" && state !== "off") {
        throw new Error(`${id} retired automation must be off before arming`);
      }
    }
  }
  if (action === "off") {
    for (const [id, existing] of existingConfigs) {
      if (!isVerifiedBlockedAutomation(existing, id)) {
        throw new Error(`${id} is not a verified blocked automation`);
      }
      if (!managedEntityId(hass, id)) {
        throw new Error(`${id} has no unique Home Assistant entity`);
      }
    }
  }
  if (action === "create") {
    const saved = await saveBlockedAutomations(hass, config);
    if (retiredIds.length) await setBlockedAutomationsArmed(hass, retiredIds, false);
    return { status: "SAVED", automations: saved, retired_ids_disabled: retiredIds };
  }
  const ids = action === "arm"
    ? desiredIds
    : ALL_MANAGED_AUTOMATION_IDS.filter(
        (id) => existingConfigs.has(id) || managedEntityId(hass, id),
      );
  const state = await setBlockedAutomationsArmed(hass, ids, action === "arm");
  return { status: "UPDATED", ...state };
}

const HTMLElementBase = globalThis.HTMLElement || class {};

export function finiteNumber(value) {
  if (value === null || value === undefined || value === "") return null;
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  if (typeof value !== "string") return null;
  if (value.trim() === "") return null;
  const parsed = Number(value.replace(",", "."));
  return Number.isFinite(parsed) ? parsed : null;
}

function externalDateMs(value) {
  if (typeof value !== "string" || value.trim() === "") return NaN;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : NaN;
}

function isPlainObject(value) {
  if (value === null || typeof value !== "object" || Array.isArray(value)) return false;
  try {
    const prototype = Object.getPrototypeOf(value);
    return prototype === Object.prototype || prototype === null;
  } catch {
    return false;
  }
}

function safeValue(object, key) {
  try {
    return object[key];
  } catch {
    return undefined;
  }
}

function safeAttributes(stateObject) {
  const attributes = safeValue(stateObject, "attributes");
  return attributes !== null && typeof attributes === "object" ? attributes : {};
}

function firstExternalValue(object, keys) {
  for (const key of keys) {
    const value = safeValue(object, key);
    if (value !== undefined && value !== null && value !== "") return value;
  }
  return undefined;
}

function nonOverlappingRows(rows) {
  const sorted = [...rows].sort((left, right) => left.startMs - right.startMs);
  for (let index = 1; index < sorted.length; index += 1) {
    if (sorted[index].startMs < sorted[index - 1].endMs) return [];
  }
  return sorted;
}

function uniqueRowsByStart(rows) {
  const counts = new Map();
  rows.forEach((row) => counts.set(row.startMs, (counts.get(row.startMs) || 0) + 1));
  return rows.filter((row) => counts.get(row.startMs) === 1);
}

function normaliseScheduleRows(planState, attributeName) {
  const schedule = safeValue(safeAttributes(planState), attributeName);
  if (!Array.isArray(schedule)) return [];
  const rows = [];
  for (const row of schedule) {
    if (!isPlainObject(row)) return [];
    const startMs = externalDateMs(firstExternalValue(row, ["start_utc", "start", "start_local"]));
    const explicitEnd = firstExternalValue(row, ["end_utc", "end"]);
    const explicitEndMs = externalDateMs(explicitEnd);
    const rawDuration = safeValue(row, "duration_hours");
    const durationHours = finiteNumber(rawDuration);
    if (
      !Number.isFinite(startMs)
      || (explicitEnd !== undefined && !Number.isFinite(explicitEndMs))
      || (rawDuration !== undefined && (durationHours === null || durationHours <= 0))
    ) return [];
    const endMs = Number.isFinite(explicitEndMs)
      ? explicitEndMs
      : durationHours === null ? NaN : startMs + durationHours * 3600000;
    if (!Number.isFinite(endMs) || endMs <= startMs) return [];
    rows.push({
      startMs,
      endMs,
      start_utc: new Date(startMs).toISOString(),
      end_utc: new Date(endMs).toISOString(),
      duration_hours: (endMs - startMs) / 3600000,
      action: safeValue(row, "action"),
      reason: safeValue(row, "reason"),
      planned_grid_import_kw: safeValue(row, "planned_grid_import_kw"),
      planned_grid_export_kw: safeValue(row, "planned_grid_export_kw"),
      charge_kwh: safeValue(row, "charge_kwh"),
      discharge_kwh: safeValue(row, "discharge_kwh"),
    });
  }
  return nonOverlappingRows(rows);
}

export function toKilowatts(stateObject) {
  if (!stateObject) return null;
  const value = finiteNumber(safeValue(stateObject, "state"));
  if (value === null) return null;
  const rawUnit = safeValue(safeAttributes(stateObject), "unit_of_measurement");
  if (rawUnit !== undefined && rawUnit !== null && typeof rawUnit !== "string") return null;
  const unit = (rawUnit || "").trim();
  if (["W", "watt", "watts"].includes(unit)) return value / 1000;
  if (["MW", "megawatt", "megawatts"].includes(unit)) return value * 1000;
  return value;
}

export function toEuroPerKwh(stateObject) {
  if (!stateObject) return null;
  const value = finiteNumber(safeValue(stateObject, "state"));
  if (value === null) return null;
  const rawUnit = safeValue(safeAttributes(stateObject), "unit_of_measurement");
  if (rawUnit !== undefined && rawUnit !== null && typeof rawUnit !== "string") return null;
  const unit = (rawUnit || "")
    .trim()
    .toLowerCase();
  if (["ct/kwh", "c/kwh", "cent/kwh"].includes(unit)) return value / 100;
  if (["eur/mwh", "€/mwh"].includes(unit)) return value / 1000;
  return value;
}

export function readEntity(
  hass,
  entityId,
  now = new Date(),
  staleMinutes = 10,
  preferLastReported = false,
) {
  if (!entityId) {
    return { entityId: null, stateObject: null, value: null, quality: "NOT_CONFIGURED" };
  }
  const stateObject = safeValue(safeValue(hass, "states") || {}, entityId);
  if (!stateObject) {
    return { entityId, stateObject: null, value: null, quality: "MISSING" };
  }
  if (typeof stateObject !== "object") {
    return { entityId, stateObject: null, value: null, quality: "INVALID" };
  }
  const rawStateValue = safeValue(stateObject, "state");
  if (typeof rawStateValue !== "string" && typeof rawStateValue !== "number") {
    return { entityId, stateObject, value: null, quality: "INVALID" };
  }
  const rawState = String(rawStateValue).toLowerCase();
  if (["unknown", "unavailable", "none", "null", ""].includes(rawState)) {
    return { entityId, stateObject, value: null, quality: "UNAVAILABLE" };
  }
  const nowMs = now instanceof Date ? now.getTime() : NaN;
  const timestampFields = preferLastReported
    ? ["last_reported", "last_updated", "last_changed"]
    : ["last_updated", "last_changed"];
  let ageMinutes = null;
  for (const field of timestampFields) {
    const updatedMs = externalDateMs(safeValue(stateObject, field));
    const candidateAge = (nowMs - updatedMs) / 60000;
    if (Number.isFinite(updatedMs) && Number.isFinite(candidateAge) && candidateAge >= -1) {
      ageMinutes = Math.max(0, candidateAge);
      break;
    }
  }
  const quality = ageMinutes === null
    ? "INVALID"
    : ageMinutes > staleMinutes ? "STALE" : "GOOD";
  const friendlyName = safeValue(safeAttributes(stateObject), "friendly_name");
  return {
    entityId,
    stateObject,
    value: finiteNumber(rawStateValue),
    quality,
    ageMinutes,
    name: typeof friendlyName === "string" ? friendlyName : entityId,
  };
}

function hasSupportedPowerUnit(stateObject) {
  const rawUnit = safeValue(safeAttributes(stateObject), "unit_of_measurement");
  if (typeof rawUnit !== "string") return false;
  return [
    "W", "watt", "watts",
    "kW", "kilowatt", "kilowatts",
    "MW", "megawatt", "megawatts",
  ].includes(rawUnit.trim());
}

function readPower(
  hass,
  entityId,
  now,
  staleMinutes,
  positive = true,
  strictUnits = false,
  freshnessEntityId = "",
) {
  const originalReading = readEntity(hass, entityId, now, staleMinutes, true);
  const heartbeat = originalReading.quality === "STALE" && freshnessEntityId
    ? readEntity(hass, freshnessEntityId, now, staleMinutes, true)
    : null;
  const reading = heartbeat?.quality === "GOOD"
    ? {
      ...originalReading,
      quality: "GOOD",
      ageMinutes: heartbeat.ageMinutes,
      freshnessSource: "HEARTBEAT",
    }
    : { ...originalReading, freshnessSource: null };
  if (strictUnits && reading.stateObject && !hasSupportedPowerUnit(reading.stateObject)) {
    return { ...reading, quality: "INVALID", value: null };
  }
  const normalised = toKilowatts(reading.stateObject);
  const quality = normalised === null && ["GOOD", "STALE"].includes(reading.quality)
    ? "INVALID"
    : reading.quality;
  return { ...reading, quality, value: normalised === null ? null : normalised * (positive ? 1 : -1) };
}

function readPercentage(hass, entityId, now, staleMinutes) {
  const reading = readEntity(hass, entityId, now, staleMinutes, true);
  const outOfRange = reading.value !== null && (reading.value < 0 || reading.value > 100);
  const quality = (reading.value === null || outOfRange) && ["GOOD", "STALE"].includes(reading.quality)
    ? "INVALID"
    : reading.quality;
  return { ...reading, quality, value: reading.value === null || outOfRange ? null : reading.value };
}

function readPrice(hass, entityId, now, staleMinutes) {
  const reading = readEntity(hass, entityId, now, staleMinutes);
  const value = toEuroPerKwh(reading.stateObject);
  const quality = value === null && ["GOOD", "STALE"].includes(reading.quality)
    ? "INVALID"
    : reading.quality;
  return { ...reading, quality, value };
}

export function getCurrentPlanInterval(planState, attributeName = "schedule", now = new Date()) {
  if (!planState) return null;
  const nowMs = now.getTime();
  const selected = normaliseScheduleRows(planState, attributeName)
    .find((row) => row.startMs <= nowMs && nowMs < row.endMs);
  if (!selected) return null;
  const { startMs, endMs, ...interval } = selected;
  return interval;
}

export function getUpcomingPriceIntervals(
  planState,
  attributeName = "prices",
  now = new Date(),
  includeElapsed = false,
) {
  if (!planState) return [];
  const rows = safeValue(safeAttributes(planState), attributeName);
  if (!Array.isArray(rows)) return [];
  const nowMs = now.getTime();
  const parsedRows = [];
  for (const row of rows) {
    if (!isPlainObject(row)) return [];
    const startMs = externalDateMs(firstExternalValue(row, ["start_utc", "start"]));
    const explicitEnd = firstExternalValue(row, ["end_utc", "end"]);
    const explicitEndMs = externalDateMs(explicitEnd);
    const rawDuration = safeValue(row, "duration_hours");
    const durationHours = finiteNumber(rawDuration);
    const rawImport = safeValue(row, "import_eur_per_kwh");
    const importEurPerKwh = finiteNumber(rawImport);
    const rawMarket = safeValue(row, "market_eur_per_mwh");
    const marketEurPerMwh = finiteNumber(rawMarket);
    const rawExport = safeValue(row, "export_eur_per_kwh");
    const exportEurPerKwh = finiteNumber(rawExport);
    if (
      !Number.isFinite(startMs)
      || (explicitEnd !== undefined && !Number.isFinite(explicitEndMs))
      || durationHours === null
      || durationHours <= 0
      || importEurPerKwh === null
      || (rawMarket !== undefined && rawMarket !== null && rawMarket !== "" && marketEurPerMwh === null)
      || (rawExport !== undefined && rawExport !== null && rawExport !== "" && exportEurPerKwh === null)
    ) return [];
    const endMs = Number.isFinite(explicitEndMs)
      ? explicitEndMs
      : startMs + durationHours * 3600000;
    if (!Number.isFinite(endMs) || endMs <= startMs) return [];
    parsedRows.push({
      startMs,
      endMs,
      startUtc: new Date(startMs).toISOString(),
      endUtc: new Date(endMs).toISOString(),
      durationHours: (endMs - startMs) / 3600000,
      marketEurPerMwh,
      importEurPerKwh,
      exportEurPerKwh,
    });
  }
  return nonOverlappingRows(parsedRows)
    .filter((row) => includeElapsed || row.endMs > nowMs)
    .map(({ startMs, endMs, ...row }) => row);
}

export function getEntityPriceIntervals(
  importState,
  exportState = null,
  attributeName = "data",
  now = new Date(),
  includeElapsed = false,
) {
  const importRows = safeValue(safeAttributes(importState), attributeName);
  if (!Array.isArray(importRows)) return [];
  const candidateExportRows = safeValue(safeAttributes(exportState), attributeName);
  const exportRows = Array.isArray(candidateExportRows) ? candidateExportRows : [];

  const parseIntegrationRows = (rows) => {
    const parsed = [];
    const byStart = new Map();
    for (const row of rows) {
      if (!isPlainObject(row)) return [];
      const startMs = externalDateMs(firstExternalValue(row, ["start_time", "start_utc", "start"]));
      const explicitEndValue = firstExternalValue(row, ["end_time", "end_utc", "end"]);
      const explicitEndMs = externalDateMs(explicitEndValue);
      const rawDuration = safeValue(row, "duration_hours");
      const durationHours = finiteNumber(rawDuration);
      if (
        (explicitEndValue !== undefined && !Number.isFinite(explicitEndMs))
        || (rawDuration !== undefined && (durationHours === null || durationHours <= 0))
      ) return [];
      const endMs = Number.isFinite(explicitEndMs)
        ? explicitEndMs
        : durationHours === null ? NaN : startMs + durationHours * 3600000;
      const price = finiteNumber(safeValue(row, "price_per_kwh"));
      if (!Number.isFinite(startMs) || !Number.isFinite(endMs) || endMs <= startMs || price === null) return [];
      const existing = byStart.get(startMs);
      if (existing) {
        if (existing.endMs !== endMs || existing.price !== price) return [];
        continue;
      }
      const parsedRow = { startMs, endMs, price };
      byStart.set(startMs, parsedRow);
      parsed.push(parsedRow);
    }
    return nonOverlappingRows(parsed);
  };

  const parsedExportRows = parseIntegrationRows(exportRows);
  const exportByInterval = new Map(
    parsedExportRows.map((row) => [`${row.startMs}:${row.endMs}`, row.price]),
  );
  const nowMs = now.getTime();
  const parsedImportRows = parseIntegrationRows(importRows);
  return parsedImportRows
    .filter((row) => includeElapsed || row.endMs > nowMs)
    .map((row) => ({
      startUtc: new Date(row.startMs).toISOString(),
      endUtc: new Date(row.endMs).toISOString(),
      durationHours: (row.endMs - row.startMs) / 3600000,
      marketEurPerMwh: null,
      importEurPerKwh: row.price,
      exportEurPerKwh: exportByInterval.get(`${row.startMs}:${row.endMs}`) ?? null,
    }));
}

function qualityRank(quality) {
  return { INVALID: 5, UNAVAILABLE: 4, MISSING: 3, STALE: 2, NOT_CONFIGURED: 1, GOOD: 0 }[quality] ?? 0;
}

function collectQuality(readings) {
  return Object.entries(readings)
    .filter(([, reading]) => reading && reading.quality !== "GOOD")
    .sort((left, right) => qualityRank(right[1].quality) - qualityRank(left[1].quality))
    .map(([key, reading]) => ({ key, entityId: reading.entityId, quality: reading.quality }));
}

function intervalCoverageMs(intervals, nowMs) {
  return intervals.reduce((total, row) => {
    const startMs = Date.parse(row.startUtc);
    const endMs = Date.parse(row.endUtc);
    return total + Math.max(0, endMs - Math.max(nowMs, startMs));
  }, 0);
}

function emptyAggregates() {
  return { daily: [], weekly: [], monthly: [] };
}

function validAggregatePeriod(kind, period) {
  if (kind === "daily") {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(period)) return false;
    const parsed = new Date(`${period}T00:00:00Z`);
    return Number.isFinite(parsed.getTime()) && parsed.toISOString().slice(0, 10) === period;
  }
  if (kind === "weekly") return /^\d{4}-W(?:0[1-9]|[1-4]\d|5[0-3])$/.test(period);
  if (kind === "monthly") return /^\d{4}-(?:0[1-9]|1[0-2])$/.test(period);
  return false;
}

function normaliseAggregateRows(rows, kind) {
  if (!Array.isArray(rows)) return [];
  const parsed = rows.flatMap((row) => {
    if (!isPlainObject(row)) return [];
    const periodValue = safeValue(row, "period");
    const period = typeof periodValue === "string" ? periodValue.trim() : "";
    const average = finiteNumber(safeValue(row, "average_eur_per_kwh"));
    if (!validAggregatePeriod(kind, period) || average === null) return [];
    return [{
      period,
      average_eur_per_kwh: average,
      partial_period: safeValue(row, "partial_period") === true,
    }];
  });
  const counts = new Map();
  parsed.forEach((row) => counts.set(row.period, (counts.get(row.period) || 0) + 1));
  return parsed
    .filter((row) => counts.get(row.period) === 1)
    .sort((left, right) => left.period.localeCompare(right.period));
}

function normaliseAggregates(aggregates) {
  if (!isPlainObject(aggregates)) return emptyAggregates();
  return {
    daily: normaliseAggregateRows(safeValue(aggregates, "daily"), "daily"),
    weekly: normaliseAggregateRows(safeValue(aggregates, "weekly"), "weekly"),
    monthly: normaliseAggregateRows(safeValue(aggregates, "monthly"), "monthly"),
  };
}

export function buildSnapshot(hass, suppliedConfig = {}, now = new Date()) {
  const config = { ...DEFAULT_CONFIG, ...suppliedConfig };
  const staleMinutes = finiteNumber(config.stale_after_minutes) ?? DEFAULT_CONFIG.stale_after_minutes;
  const priceStaleMinutes = finiteNumber(config.price_stale_after_minutes)
    ?? DEFAULT_CONFIG.price_stale_after_minutes;
  const grid = readPower(
    hass,
    config.grid_power_entity,
    now,
    staleMinutes,
    config.grid_import_positive !== false,
  );
  const pv = readPower(hass, config.pv_power_entity, now, staleMinutes, true);
  const battery = readPower(
    hass,
    config.battery_power_entity,
    now,
    staleMinutes,
    config.battery_charge_positive !== false,
  );
  const soc = readPercentage(hass, config.battery_soc_entity, now, staleMinutes);
  const configuredHouse = readPower(hass, config.house_power_entity, now, staleMinutes, true);
  const ev = readPower(hass, config.ev_power_entity, now, staleMinutes, true);
  const heatPump = readPower(hass, config.heat_pump_power_entity, now, staleMinutes, true);
  const importPrice = readPrice(hass, config.import_price_entity, now, priceStaleMinutes);
  const exportPrice = readPrice(hass, config.export_price_entity, now, priceStaleMinutes);

  const gridKw = grid.value;
  const pvKw = pv.value === null ? null : Math.max(0, pv.value);
  const batteryKw = battery.value;
  const derivedHouseKw = [gridKw, pvKw, batteryKw].every((value) => value !== null)
    ? Math.max(0, gridKw + pvKw - batteryKw)
    : null;
  const houseKw = configuredHouse.value ?? derivedHouseKw;
  const peakLimitKw = finiteNumber(config.peak_limit_kw) ?? DEFAULT_CONFIG.peak_limit_kw;
  const gridImportKw = gridKw === null ? null : Math.max(0, gridKw);
  const headroomKw = gridImportKw === null ? null : peakLimitKw - gridImportKw;

  const planHours = finiteNumber(config.plan_stale_after_hours) ?? DEFAULT_CONFIG.plan_stale_after_hours;
  const planReading = readEntity(hass, config.plan_entity, now, planHours * 60);
  const planIsFresh = planReading.quality === "GOOD";
  const planAttribute = config.plan_attribute || DEFAULT_CONFIG.plan_attribute;
  const planInterval = planIsFresh
    ? getCurrentPlanInterval(planReading.stateObject, planAttribute, now)
    : null;
  const planSchedule = planIsFresh
    ? normaliseScheduleRows(planReading.stateObject, planAttribute).map(({ startMs, endMs, ...row }) => row)
    : [];
  const nowMs = now.getTime();
  const planDailyPriceIntervals = planIsFresh
    ? getUpcomingPriceIntervals(
      planReading.stateObject,
      config.price_attribute || "prices",
      now,
      true,
    )
    : [];
  const planPriceIntervals = planDailyPriceIntervals.filter(
    (row) => Date.parse(row.endUtc) > nowMs,
  );
  const entityDailyPriceIntervals = importPrice.quality === "GOOD"
    ? getEntityPriceIntervals(
      importPrice.stateObject,
      exportPrice.quality === "GOOD" ? exportPrice.stateObject : null,
      config.integration_price_attribute || DEFAULT_CONFIG.integration_price_attribute,
      now,
      true,
    )
    : [];
  const entityPriceIntervals = entityDailyPriceIntervals.filter(
    (row) => Date.parse(row.endUtc) > nowMs,
  );
  const shadowCoverage = intervalCoverageMs(planPriceIntervals, nowMs);
  const integrationCoverage = intervalCoverageMs(entityPriceIntervals, nowMs);
  const hasIntegrationSource = importPrice.quality === "GOOD"
    && (entityPriceIntervals.length > 0 || importPrice.value !== null);
  const selectedPriceSource = hasIntegrationSource && integrationCoverage > shadowCoverage
    ? "integration"
    : planPriceIntervals.length > 0 ? "shadow" : hasIntegrationSource ? "integration" : null;
  const priceIntervals = selectedPriceSource === "shadow" ? planPriceIntervals
    : selectedPriceSource === "integration" ? entityPriceIntervals : [];
  const dailyPriceIntervals = selectedPriceSource === "shadow" ? planDailyPriceIntervals
    : selectedPriceSource === "integration" ? entityDailyPriceIntervals : [];
  const currentTimelinePrice = priceIntervals.find(
    (row) => Date.parse(row.startUtc) <= nowMs && nowMs < Date.parse(row.endUtc),
  );
  const effectiveImportPrice = currentTimelinePrice?.importEurPerKwh
    ?? (selectedPriceSource === "integration" && importPrice.quality === "GOOD" ? importPrice.value : null);
  const effectiveExportPrice = currentTimelinePrice?.exportEurPerKwh
    ?? (selectedPriceSource === "integration" && exportPrice.quality === "GOOD" ? exportPrice.value : null);
  const shadowAttributes = planReading.stateObject?.attributes;
  const selectedAggregates = selectedPriceSource === "shadow"
    ? normaliseAggregates(safeValue(shadowAttributes || {}, "price_aggregates"))
    : emptyAggregates();
  const selectedSourceLabel = selectedPriceSource === "shadow"
    ? (safeValue(shadowAttributes || {}, "price_source") || "Shadow plan entity")
    : selectedPriceSource === "integration" ? "Home Assistant price entities" : null;
  const selectedTariffVersion = selectedPriceSource === "shadow"
    ? (safeValue(shadowAttributes || {}, "price_tariff_version") || null)
    : null;
  const priceReference = finiteNumber(config.price_reference_eur_per_kwh)
    ?? DEFAULT_CONFIG.price_reference_eur_per_kwh;
  const plannedGridImportKw = finiteNumber(planInterval?.planned_grid_import_kw);
  const gridDeviationKw = gridImportKw !== null && plannedGridImportKw !== null
    ? gridImportKw - plannedGridImportKw
    : null;

  const liveReadings = { grid, pv, battery, soc };
  const optionalReadings = {
    house: configuredHouse,
    ev,
    heatPump,
    importPrice,
    exportPrice,
  };
  const requiredMissing = REQUIRED_ENTITY_FIELDS.filter((field) => !config[field]);
  const liveQuality = collectQuality(liveReadings);
  const optionalQuality = collectQuality(optionalReadings).filter((row) => row.quality !== "NOT_CONFIGURED");

  let status = "TRACKING";
  if (requiredMissing.length) {
    status = "SETUP_REQUIRED";
  } else if (liveQuality.some((row) => ["INVALID", "MISSING", "UNAVAILABLE"].includes(row.quality))) {
    status = "UNAVAILABLE_DATA";
  } else if (liveQuality.some((row) => row.quality === "STALE")) {
    status = "STALE_DATA";
  } else if (!config.plan_entity) {
    status = "DATA_GATED";
  } else if (["INVALID", "MISSING", "UNAVAILABLE", "STALE"].includes(planReading.quality)) {
    status = planReading.quality === "STALE" ? "STALE_DATA" : "UNAVAILABLE_DATA";
  } else if (!planInterval) {
    status = "NO_ACTION";
  } else if (headroomKw !== null && headroomKw < 0) {
    status = "PEAK_RISK";
  } else if (
    gridDeviationKw !== null
    && Math.abs(gridDeviationKw) >= (finiteNumber(config.deviation_warning_kw) ?? DEFAULT_CONFIG.deviation_warning_kw)
  ) {
    status = "DEVIATION";
  }

  return {
    generatedAt: now.toISOString(),
    status,
    statusLabel: STATUS_LABELS[status] || status,
    readOnly: true,
    config,
    live: {
      gridKw,
      gridImportKw,
      gridExportKw: gridKw === null ? null : Math.max(0, -gridKw),
      pvKw,
      batteryKw,
      batteryChargeKw: batteryKw === null ? null : Math.max(0, batteryKw),
      batteryDischargeKw: batteryKw === null ? null : Math.max(0, -batteryKw),
      socPercent: soc.value,
      houseKw,
      houseSource: configuredHouse.value === null ? "DERIVED" : "MEASURED",
      evKw: ev.value,
      heatPumpKw: heatPump.value,
      importPriceEurPerKwh: effectiveImportPrice,
      exportPriceEurPerKwh: effectiveExportPrice,
    },
    peak: {
      limitKw: peakLimitKw,
      headroomKw,
      utilizationPercent: gridImportKw === null || peakLimitKw <= 0
        ? null
        : (gridImportKw / peakLimitKw) * 100,
    },
    plan: {
      mode: planReading.stateObject?.attributes?.mode || planReading.stateObject?.state || null,
      quality: planReading.quality,
      interval: planInterval,
      schedule: planSchedule,
      plannedGridImportKw,
      gridDeviationKw,
    },
    prices: {
      intervals: priceIntervals,
      dailyIntervals: dailyPriceIntervals,
      referenceEurPerKwh: priceReference,
      source: selectedSourceLabel,
      tariffVersion: selectedTariffVersion,
      aggregates: selectedAggregates,
    },
    quality: {
      requiredMissing,
      live: liveQuality,
      optional: optionalQuality,
    },
  };
}

export function buildControlPanelSnapshot(hass, suppliedConfig = {}, now = new Date()) {
  const config = { ...DEFAULT_CONTROL_CONFIG, ...suppliedConfig };
  const staleMinutes = requiredFinite(
    config.data_stale_after_minutes,
    "data_stale_after_minutes",
    1,
    180,
  );
  const planStaleHours = requiredFinite(
    config.plan_stale_after_hours,
    "plan_stale_after_hours",
    1,
    72,
  );
  const priceStaleMinutes = requiredFinite(
    config.price_stale_after_minutes,
    "price_stale_after_minutes",
    1,
    180,
  );
  const planReading = readEntity(hass, config.plan_entity, now, planStaleHours * 60);
  const planIsFresh = planReading.quality === "GOOD";
  const planPrices = planIsFresh
    ? getUpcomingPriceIntervals(planReading.stateObject, "prices", now)
    : [];
  const nowMs = now.getTime();
  const importPrice = readPrice(hass, config.import_price_entity, now, priceStaleMinutes);
  const exportPrice = readPrice(hass, config.export_price_entity, now, priceStaleMinutes);
  const integrationPrices = importPrice.quality === "GOOD"
    ? getEntityPriceIntervals(
      importPrice.stateObject,
      exportPrice.quality === "GOOD" ? exportPrice.stateObject : null,
      config.integration_price_attribute || DEFAULT_CONTROL_CONFIG.integration_price_attribute,
      now,
    )
    : [];
  const planCoverage = intervalCoverageMs(planPrices, nowMs);
  const integrationCoverage = intervalCoverageMs(integrationPrices, nowMs);
  const coversNow = (rows) => rows.some(
    (row) => Date.parse(row.startUtc) <= nowMs && nowMs < Date.parse(row.endUtc),
  );
  const planCoversNow = coversNow(planPrices);
  const integrationCoversNow = coversNow(integrationPrices);
  const hasIntegrationSource = importPrice.quality === "GOOD"
    && (integrationPrices.length > 0 || importPrice.value !== null);
  const selectedPriceSource = planCoversNow !== integrationCoversNow
    ? planCoversNow ? "shadow" : "integration"
    : hasIntegrationSource && integrationCoverage > planCoverage
      ? "integration"
      : planPrices.length > 0 ? "shadow" : hasIntegrationSource ? "integration" : null;
  const prices = selectedPriceSource === "integration" ? integrationPrices
    : selectedPriceSource === "shadow" ? planPrices : [];
  const current = prices.find(
    (row) => Date.parse(row.startUtc) <= nowMs && nowMs < Date.parse(row.endUtc),
  ) || null;
  const pricedRows = prices.filter((row) => finiteNumber(row.importEurPerKwh) !== null);
  const futurePricedRows = pricedRows.filter((row) => Date.parse(row.startUtc) > nowMs);
  const cheapest = futurePricedRows.reduce(
    (best, row) => best === null || row.importEurPerKwh < best.importEurPerKwh ? row : best,
    null,
  );
  const highest = futurePricedRows.reduce(
    (best, row) => best === null || row.importEurPerKwh > best.importEurPerKwh ? row : best,
    null,
  );
  const planInterval = planIsFresh
    ? getCurrentPlanInterval(planReading.stateObject, "schedule", now)
    : null;
  const batterySoc = readPercentage(hass, config.battery_soc_entity, now, staleMinutes);
  const grid = readPower(
    hass,
    config.grid_power_entity,
    now,
    staleMinutes,
    config.grid_import_positive !== false,
    true,
  );
  const ev = readPower(hass, config.ev_power_entity, now, staleMinutes, true, true);
  const peakLimitKw = finiteNumber(config.peak_limit_kw);
  const smappeeLimitKw = finiteNumber(config.smappee_capacity_threshold_kw);
  const warnings = [];
  if (planReading.quality !== "GOOD") {
    warnings.push(
      `Shadow-plan is ${qualityLabel(planReading.quality)}; eventuele verse prijsdata blijft alleen observatiecontext.`,
    );
  }
  if (
    peakLimitKw !== null
    && smappeeLimitKw !== null
    && Math.abs(peakLimitKw - smappeeLimitKw) >= 0.01
  ) {
    warnings.push(
      `Smappee begrenst EV-laden op ${smappeeLimitKw} kW; de gedeelde dashboardgrens is ${peakLimitKw} kW. De strengste limiet blijft leidend.`,
    );
  }
  if (String(config.sma_forecast_charging).toUpperCase() !== "ACTIVE") {
    warnings.push("SMA forecast-based charging staat nog niet als actief gevalideerd.");
  }
  const offlineAmpere = finiteNumber(config.smappee_offline_fallback_ampere);
  if (offlineAmpere !== null && offlineAmpere > 0) {
    warnings.push(
      `Smappee offline laden gebruikt ${offlineAmpere} A zonder gegarandeerde automatische overbelastingsregeling.`,
    );
  }
  const smappeeDynamicTariffStatus = String(
    config.smappee_dynamic_tariff_status || "NOT_VERIFIED",
  ).toUpperCase();
  if (smappeeDynamicTariffStatus === "NOT_VERIFIED") {
    warnings.push(
      "Smappee-dynamische tarieven zijn niet geverifieerd; Ecopower-prijsentities blijven de observatiebron.",
    );
  }
  const liveReadings = [
    ["batterij-SOC", batterySoc],
    ["netvermogen", grid],
    ["EV-laadvermogen", ev],
  ];
  const degradedLiveReadings = liveReadings.filter(
    ([, reading]) => !["GOOD", "NOT_CONFIGURED"].includes(reading.quality),
  );
  for (const [label, reading] of degradedLiveReadings) {
    warnings.push(`Live ${label} is ${qualityLabel(reading.quality)}.`);
  }
  const configuredPriceQualities = [
    planReading.quality,
    config.import_price_entity ? importPrice.quality : "NOT_CONFIGURED",
  ].filter((quality) => quality !== "NOT_CONFIGURED");
  const unavailablePriceQuality = configuredPriceQualities.includes("INVALID")
    ? "INVALID"
    : configuredPriceQualities.includes("STALE")
      ? "STALE"
      : configuredPriceQualities.includes("MISSING")
        ? "MISSING"
        : "UNAVAILABLE";
  const priceQuality = current && prices.length ? "GOOD" : unavailablePriceQuality;
  const readinessMode = priceQuality !== "GOOD"
    ? "DATA_BLOCKED"
    : planReading.quality !== "GOOD"
      ? "PRICE_READY_PLAN_BLOCKED"
      : degradedLiveReadings.length ? "SHADOW_READY_LIVE_DEGRADED" : "SHADOW_READY";
  const attrs = safeAttributes(planReading.stateObject);
  return {
    generatedAt: now.toISOString(),
    live: {
      batterySocPercent: batterySoc.value,
      batterySocQuality: batterySoc.quality,
      gridKw: grid.value,
      gridQuality: grid.quality,
      evKw: ev.value,
      evQuality: ev.quality,
    },
    price: {
      quality: priceQuality,
      currentEurPerKwh: priceQuality === "GOOD" ? current.importEurPerKwh : null,
      cheapestEurPerKwh: priceQuality === "GOOD" ? cheapest?.importEurPerKwh ?? null : null,
      cheapestStartUtc: priceQuality === "GOOD" ? cheapest?.startUtc ?? null : null,
      highestEurPerKwh: priceQuality === "GOOD" ? highest?.importEurPerKwh ?? null : null,
      highestStartUtc: priceQuality === "GOOD" ? highest?.startUtc ?? null : null,
      intervalCount: priceQuality === "GOOD" ? prices.length : 0,
      source: selectedPriceSource === "integration"
        ? "Home Assistant price entities"
        : typeof attrs.price_source === "string" ? attrs.price_source : null,
      tariffVersion: selectedPriceSource === "integration"
        ? null
        : typeof attrs.price_tariff_version === "string" ? attrs.price_tariff_version : null,
    },
    plan: {
      quality: planReading.quality,
      mode: planIsFresh ? attrs.mode || planReading.stateObject?.state || null : null,
      action: planInterval?.action || "NO_ACTION",
      reason: planInterval?.reason || null,
      plannedGridImportKw: finiteNumber(planInterval?.planned_grid_import_kw),
    },
    readiness: {
      mode: readinessMode,
      executionAllowed: false,
      controllerOwners: { battery: "SMA", ev: "SMAPPEE" },
      warnings,
    },
  };
}

function validationActionFromPlan(action) {
  if (["CHARGE_FROM_GRID", "STORE_PV_SURPLUS"].includes(action)) return "CHARGING";
  if (action === "DISCHARGE_TO_LOAD") return "DISCHARGING";
  if (["HOLD", "NO_ACTION"].includes(action)) return "IDLE";
  return "INSUFFICIENT_DATA";
}

function observedBatteryAction(reading, thresholdKw) {
  if (reading.quality !== "GOOD" || reading.value === null) return "INSUFFICIENT_DATA";
  if (reading.value > thresholdKw) return "CHARGING";
  if (reading.value < -thresholdKw) return "DISCHARGING";
  return "IDLE";
}

function observedLoadAction(reading, thresholdKw) {
  if (reading.quality !== "GOOD" || reading.value === null) return "INSUFFICIENT_DATA";
  return reading.value > thresholdKw ? "CHARGING" : "IDLE";
}

function validationSummary(reading) {
  const empty = {
    quality: reading.quality,
    localDate: null,
    coveragePercent: null,
    batteryChargeCheapKwh: null,
    batteryDischargeExpensiveKwh: null,
    evChargeCheapKwh: null,
    evCheapSharePercent: null,
    maxGridImportKw: null,
    collisionIntervals: null,
    matchedIntervals: null,
    deviationIntervals: null,
    actualCostEur: null,
    shadowCostEur: null,
    costDeltaEur: null,
  };
  if (reading.quality !== "GOOD") return empty;
  const attrs = safeAttributes(reading.stateObject);
  const number = (name, minimum = Number.NEGATIVE_INFINITY, maximum = Number.POSITIVE_INFINITY) => {
    const value = finiteNumber(attrs[name]);
    return value !== null && value >= minimum && value <= maximum ? value : null;
  };
  const coveragePercent = number("coverage_percent", 0, 100);
  const evCheapSharePercent = number("ev_cheap_share_percent", 0, 100);
  const batteryChargeCheapKwh = number("battery_charge_cheap_kwh", 0, 500);
  const batteryDischargeExpensiveKwh = number("battery_discharge_expensive_kwh", 0, 500);
  const evChargeCheapKwh = number("ev_charge_cheap_kwh", 0, 500);
  const maxGridImportKw = number("max_grid_import_kw", 0, 100);
  const collisionIntervals = number("collision_intervals", 0, 100);
  const matchedIntervals = number("matched_intervals", 0, 100);
  const deviationIntervals = number("deviation_intervals", 0, 100);
  const actualCostEur = number("actual_cost_eur", -1000, 1000);
  const shadowCostEur = number("shadow_cost_eur", -1000, 1000);
  const requiredValues = [
    coveragePercent,
    batteryChargeCheapKwh,
    batteryDischargeExpensiveKwh,
    evChargeCheapKwh,
    evCheapSharePercent,
    maxGridImportKw,
    collisionIntervals,
    matchedIntervals,
    deviationIntervals,
    actualCostEur,
    shadowCostEur,
  ];
  const localDate = typeof attrs.local_date === "string"
    && validAggregatePeriod("daily", attrs.local_date)
    ? attrs.local_date
    : null;
  const intervalCounts = [collisionIntervals, matchedIntervals, deviationIntervals];
  const evaluatedIntervals = matchedIntervals === null || deviationIntervals === null
    ? null
    : matchedIntervals + deviationIntervals;
  if (
    !localDate
    || requiredValues.some((value) => value === null)
    || intervalCounts.some((value) => !Number.isInteger(value))
    || evaluatedIntervals > 100
    || evaluatedIntervals > Math.ceil(coveragePercent)
    || collisionIntervals > evaluatedIntervals
  ) {
    return { ...empty, quality: "INVALID" };
  }
  return {
    quality: "GOOD",
    localDate,
    coveragePercent,
    batteryChargeCheapKwh,
    batteryDischargeExpensiveKwh,
    evChargeCheapKwh,
    evCheapSharePercent,
    maxGridImportKw,
    collisionIntervals,
    matchedIntervals,
    deviationIntervals,
    actualCostEur,
    shadowCostEur,
    costDeltaEur: Math.round((actualCostEur - shadowCostEur) * 100) / 100,
  };
}

export async function fetchValidationTelemetry(hass, suppliedConfig = {}) {
  if (!hass || typeof hass.callApi !== "function") return {};
  const config = { ...DEFAULT_VALIDATION_CONFIG, ...suppliedConfig };
  const entityIds = [...new Set(VALIDATION_TELEMETRY_ENTITY_FIELDS
    .map((field) => safeValue(config, field))
    .filter((entityId) => typeof entityId === "string" && entityId.trim() !== ""))];
  const results = await Promise.allSettled(entityIds.map(async (entityId) => {
    const stateObject = await hass.callApi("GET", `states/${encodeURIComponent(entityId)}`);
    return { entityId, stateObject };
  }));
  const states = {};
  for (const result of results) {
    if (result.status !== "fulfilled") continue;
    const { entityId, stateObject } = result.value;
    if (!isPlainObject(stateObject) || safeValue(stateObject, "entity_id") !== entityId) continue;
    states[entityId] = stateObject;
  }
  return states;
}

function latestStateTimestamp(stateObject, nowMs = Date.now()) {
  if (!isPlainObject(stateObject)) return -Infinity;
  const timestamps = [
    externalDateMs(safeValue(stateObject, "last_reported")),
    externalDateMs(safeValue(stateObject, "last_updated")),
    externalDateMs(safeValue(stateObject, "last_changed")),
  ].filter((timestamp) => Number.isFinite(timestamp) && timestamp <= nowMs + 60_000);
  return timestamps.length > 0 ? Math.max(...timestamps) : -Infinity;
}

export function hassWithValidationTelemetry(hass, telemetryStates, nowMs = Date.now()) {
  if (!hass || !isPlainObject(telemetryStates) || Object.keys(telemetryStates).length === 0) {
    return hass;
  }
  const states = { ...(safeValue(hass, "states") || {}) };
  for (const [entityId, stateObject] of Object.entries(telemetryStates)) {
    if (latestStateTimestamp(stateObject, nowMs) >= latestStateTimestamp(states[entityId], nowMs)) {
      states[entityId] = stateObject;
    }
  }
  return { ...hass, states };
}

export function buildValidationSnapshot(hass, suppliedConfig = {}, now = new Date()) {
  const config = { ...DEFAULT_VALIDATION_CONFIG, ...suppliedConfig };
  const staleMinutes = requiredFinite(
    config.data_stale_after_minutes,
    "data_stale_after_minutes",
    1,
    180,
  );
  const planStaleHours = requiredFinite(
    config.plan_stale_after_hours,
    "plan_stale_after_hours",
    1,
    72,
  );
  const summaryStaleHours = requiredFinite(
    config.summary_stale_after_hours,
    "summary_stale_after_hours",
    1,
    168,
  );
  const priceStaleMinutes = requiredFinite(
    config.price_stale_after_minutes,
    "price_stale_after_minutes",
    1,
    180,
  );
  const thresholdKw = requiredFinite(
    config.activity_threshold_kw,
    "activity_threshold_kw",
    0.01,
    5,
  );
  const peakLimitKw = requiredFinite(config.peak_limit_kw, "peak_limit_kw", 0.1, 30);
  const smappeeLimitKw = requiredFinite(
    config.smappee_capacity_threshold_kw,
    "smappee_capacity_threshold_kw",
    0.1,
    30,
  );
  const plan = readEntity(hass, config.plan_entity, now, planStaleHours * 60);
  const planInterval = plan.quality === "GOOD"
    ? getCurrentPlanInterval(plan.stateObject, "schedule", now)
    : null;
  const planPrices = plan.quality === "GOOD"
    ? getUpcomingPriceIntervals(plan.stateObject, "prices", now)
    : [];
  const importPrice = readPrice(hass, config.import_price_entity, now, priceStaleMinutes);
  const exportPrice = readPrice(hass, config.export_price_entity, now, priceStaleMinutes);
  const integrationPrices = importPrice.quality === "GOOD"
    ? getEntityPriceIntervals(
      importPrice.stateObject,
      exportPrice.quality === "GOOD" ? exportPrice.stateObject : null,
      config.integration_price_attribute || "data",
      now,
    )
    : [];
  const nowMs = now.getTime();
  const coversNow = (rows) => rows.some(
    (row) => Date.parse(row.startUtc) <= nowMs && nowMs < Date.parse(row.endUtc),
  );
  const planCoversNow = coversNow(planPrices);
  const integrationCoversNow = coversNow(integrationPrices);
  const planCoverage = intervalCoverageMs(planPrices, nowMs);
  const integrationCoverage = intervalCoverageMs(integrationPrices, nowMs);
  const hasIntegrationSource = importPrice.quality === "GOOD"
    && (integrationPrices.length > 0 || importPrice.value !== null);
  const selectedPriceSource = planCoversNow !== integrationCoversNow
    ? planCoversNow ? "shadow" : "integration"
    : hasIntegrationSource && integrationCoverage > planCoverage
      ? "integration"
      : planPrices.length > 0 ? "shadow" : hasIntegrationSource ? "integration" : null;
  const priceRows = selectedPriceSource === "integration" ? integrationPrices
    : selectedPriceSource === "shadow" ? planPrices : [];
  const currentPrice = priceRows.find(
    (row) => Date.parse(row.startUtc) <= nowMs && nowMs < Date.parse(row.endUtc),
  ) || null;
  const sortedPrices = priceRows
    .map((row) => finiteNumber(row.importEurPerKwh))
    .filter((value) => value !== null)
    .sort((left, right) => left - right);
  const currentPriceValue = finiteNumber(currentPrice?.importEurPerKwh);
  const cheapThreshold = sortedPrices.length
    ? sortedPrices[Math.floor((sortedPrices.length - 1) * 0.25)]
    : null;
  const expensiveThreshold = sortedPrices.length
    ? sortedPrices[Math.ceil((sortedPrices.length - 1) * 0.75)]
    : null;
  const priceZone = sortedPrices.length < 4
    || currentPriceValue === null
    || cheapThreshold === null
    || expensiveThreshold === null
    ? "INSUFFICIENT_DATA"
    : cheapThreshold >= expensiveThreshold ? "NORMAL"
      : currentPriceValue <= cheapThreshold ? "CHEAP"
        : currentPriceValue >= expensiveThreshold ? "EXPENSIVE" : "NORMAL";
  const grid = readPower(
    hass,
    config.grid_power_entity,
    now,
    staleMinutes,
    config.grid_import_positive !== false,
    true,
  );
  const battery = readPower(
    hass,
    config.battery_power_entity,
    now,
    staleMinutes,
    config.battery_charge_positive !== false,
    true,
    config.battery_freshness_entity,
  );
  const ev = readPower(hass, config.ev_power_entity, now, staleMinutes, true, true);
  const configuredHouse = readPower(hass, config.house_power_entity, now, staleMinutes, true, true);
  const pv = readPower(hass, config.pv_power_entity, now, staleMinutes, true, true);
  const heatPump = readPower(hass, config.heat_pump_power_entity, now, staleMinutes, true, true);
  const derivedHouseKw = [grid, battery, pv].every(
    (reading) => reading.quality === "GOOD" && reading.value !== null,
  )
    ? Math.round(Math.max(0, grid.value + pv.value - battery.value) * 1000) / 1000
    : null;
  const houseKw = configuredHouse.value ?? derivedHouseKw;
  const houseQuality = configuredHouse.value !== null
    ? configuredHouse.quality
    : derivedHouseKw !== null ? "GOOD" : configuredHouse.quality;
  const houseSource = configuredHouse.value !== null
    ? "MEASURED"
    : derivedHouseKw !== null ? "DERIVED" : "UNAVAILABLE";
  const summaryReading = readEntity(
    hass,
    config.validation_summary_entity,
    now,
    summaryStaleHours * 60,
  );
  const expectedBatteryAction = planInterval
    ? validationActionFromPlan(planInterval.action)
    : "INSUFFICIENT_DATA";
  const actualBatteryAction = observedBatteryAction(battery, thresholdKw);
  const evAction = observedLoadAction(ev, thresholdKw);
  const batteryOutcome = expectedBatteryAction === "INSUFFICIENT_DATA"
    || actualBatteryAction === "INSUFFICIENT_DATA"
    ? "INSUFFICIENT_DATA"
    : expectedBatteryAction === actualBatteryAction ? "MATCH"
      : expectedBatteryAction === "IDLE" ? "UNEXPECTED_ACTION" : "MISSED_OPPORTUNITY";
  const effectiveLimitKw = Math.min(peakLimitKw, smappeeLimitKw);
  const headroomKw = grid.quality === "GOOD" && grid.value !== null
    ? Math.round((effectiveLimitKw - Math.max(0, grid.value)) * 1000) / 1000
    : null;
  const collision = actualBatteryAction === "CHARGING" && evAction === "CHARGING";
  const requestedPilotStatus = String(config.pilot_status || "NOT_STARTED").toUpperCase();
  const validPilotStatus = VALIDATION_PILOT_STATUSES.includes(requestedPilotStatus);
  const pilotStatus = validPilotStatus ? requestedPilotStatus : "BLOCKED";
  const warnings = validPilotStatus
    ? []
    : [`Onbekende pilotstatus ${requestedPilotStatus}; validatie is fail-closed geblokkeerd.`];
  if (collision) {
    warnings.push("Gelijktijdig batterij- en EV-laden gedetecteerd; controleer de gedeelde netruimte.");
  }
  if (headroomKw !== null && headroomKw < 0) {
    warnings.push(`De effectieve gedeelde netgrens is met ${Math.abs(headroomKw)} kW overschreden.`);
  }
  const status = pilotStatus === "BLOCKED"
    ? "BLOCKED"
    : grid.quality !== "GOOD"
    || batteryOutcome === "INSUFFICIENT_DATA"
    || evAction === "INSUFFICIENT_DATA"
    || currentPriceValue === null
    || priceZone === "INSUFFICIENT_DATA"
    ? "INSUFFICIENT_DATA"
    : collision || (headroomKw !== null && headroomKw < 0)
      ? "SHARED_PEAK_WARNING"
      : batteryOutcome;
  return {
    generatedAt: now.toISOString(),
    pilotStatus,
    executionAllowed: false,
    warnings,
    status,
    price: {
      quality: currentPriceValue === null ? "UNAVAILABLE" : "GOOD",
      currentEurPerKwh: currentPriceValue,
      zone: priceZone,
      source: selectedPriceSource === "integration" ? "Home Assistant price entities"
        : selectedPriceSource === "shadow" ? "Shadow plan" : null,
    },
    interval: {
      planQuality: plan.quality,
      expectedBatteryAction,
      observedBatteryAction: actualBatteryAction,
      batteryOutcome,
      evAction,
      planReason: planInterval?.reason || null,
    },
    live: {
      gridKw: grid.value,
      gridQuality: grid.quality,
      batteryKw: battery.value,
      batteryQuality: battery.quality,
      batteryFreshnessSource: battery.freshnessSource,
      evKw: ev.value,
      evQuality: ev.quality,
      houseKw,
      houseQuality,
      houseSource,
      pvKw: pv.value,
      pvQuality: pv.quality,
      heatPumpKw: heatPump.value,
      heatPumpQuality: heatPump.quality,
    },
    grid: {
      dashboardLimitKw: peakLimitKw,
      smappeeLimitKw,
      effectiveLimitKw,
      headroomKw,
      collision,
    },
    summary: validationSummary(summaryReading),
  };
}

function escapeHtml(value) {
  const safe = ["string", "number", "boolean", "bigint"].includes(typeof value)
    ? String(value)
    : "";
  return safe
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatKw(value) {
  const safe = finiteNumber(value);
  return safe === null ? "—" : `${new Intl.NumberFormat("nl-BE", { maximumFractionDigits: 2 }).format(safe)} kW`;
}

function formatPercent(value) {
  const safe = finiteNumber(value);
  return safe === null ? "—" : `${new Intl.NumberFormat("nl-BE", { maximumFractionDigits: 1 }).format(safe)}%`;
}

function formatPrice(value) {
  const safe = finiteNumber(value);
  return safe === null
    ? "—"
    : new Intl.NumberFormat("nl-BE", { style: "currency", currency: "EUR", minimumFractionDigits: 3 }).format(safe);
}

function compactPrice(value) {
  const safe = finiteNumber(value);
  return safe === null ? "—" : `€${safe.toFixed(3).replace(".", ",")}`;
}

function actionLabel(action) {
  if (typeof action !== "string" || action === "") return "Geen actueel plan";
  return ACTION_LABELS[action] || action;
}

function actionTone(action) {
  if (["CHARGE_FROM_GRID", "STORE_PV_SURPLUS"].includes(action)) return "charge";
  if (action === "DISCHARGE_TO_LOAD") return "discharge";
  return "hold";
}

export function renderPriceTimeline(
  intervals,
  schedule = [],
  referenceEurPerKwh = null,
  sourceLabel = null,
  tariffVersion = null,
) {
  const referenceValue = finiteNumber(referenceEurPerKwh);
  const reference = referenceValue === null
    ? "referentie onbekend"
    : `referentie ${compactPrice(referenceValue)}/kWh`;
  const safeSourceLabel = typeof sourceLabel === "string" && sourceLabel
    ? sourceLabel
    : "Prijsbron onbekend";
  const safeTariffVersion = typeof tariffVersion === "string" ? tariffVersion : null;
  const metadata = [safeSourceLabel, safeTariffVersion, reference]
    .filter(Boolean)
    .map((value) => escapeHtml(value))
    .join(" · ");
  const displayIntervals = (Array.isArray(intervals) ? intervals : []).flatMap((row) => {
    if (!isPlainObject(row)) return [];
    const startMs = externalDateMs(safeValue(row, "startUtc"));
    const endMs = externalDateMs(safeValue(row, "endUtc"));
    const importEurPerKwh = finiteNumber(safeValue(row, "importEurPerKwh"));
    const marketEurPerMwh = finiteNumber(safeValue(row, "marketEurPerMwh"));
    const exportEurPerKwh = finiteNumber(safeValue(row, "exportEurPerKwh"));
    if (!Number.isFinite(startMs) || !Number.isFinite(endMs) || endMs <= startMs || importEurPerKwh === null) return [];
    return [{ startMs, importEurPerKwh, marketEurPerMwh, exportEurPerKwh }];
  });
  if (!displayIntervals.length) {
    return `<section class="price-timeline"><div class="section-title"><h3>Komende kwartierprijzen</h3><small>${metadata}</small></div><p class="price-empty">Nog geen toekomstige Day-Ahead-prijzen beschikbaar.</p></section>`;
  }
  const actionRows = (Array.isArray(schedule) ? schedule : []).flatMap((row) => {
    if (!isPlainObject(row)) return [];
    const startMs = externalDateMs(firstExternalValue(row, ["start_utc", "start"]));
    const action = safeValue(row, "action");
    if (!Number.isFinite(startMs) || typeof action !== "string") return [];
    return [{ startMs, action }];
  });
  const actions = new Map(uniqueRowsByStart(actionRows).map((row) => [row.startMs, row.action]));
  const formatter = new Intl.DateTimeFormat("nl-BE", {
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Europe/Brussels",
    timeZoneName: "shortOffset",
  });
  const rows = displayIntervals.map((row) => {
    const action = actions.get(row.startMs);
    const difference = referenceValue === null
      ? null
      : row.importEurPerKwh - referenceValue;
    const tone = difference === null ? "neutral" : difference <= 0 ? "cheap" : "expensive";
    return `<div class="price-quarter ${tone}"><time>${escapeHtml(formatter.format(new Date(row.startMs)))}</time><strong>${escapeHtml(compactPrice(row.importEurPerKwh))}</strong><small>markt ${escapeHtml(row.marketEurPerMwh === null ? "—" : `€${row.marketEurPerMwh.toFixed(2)}/MWh`)}</small><small>injectie ${escapeHtml(compactPrice(row.exportEurPerKwh))}</small>${action ? `<span>${escapeHtml(actionLabel(action))}</span>` : ""}</div>`;
  }).join("");
  return `<section class="price-timeline"><div class="section-title price-heading"><div><h3>Komende kwartierprijzen</h3><small>${metadata}</small></div><div class="price-nav" aria-label="Navigatie door kwartierprijzen"><button type="button" data-price-scroll-by="-1" aria-label="Eerdere kwartierprijzen" title="Eerdere kwartierprijzen">‹</button><button type="button" data-price-scroll-by="1" aria-label="Latere kwartierprijzen" title="Latere kwartierprijzen">›</button></div></div><div class="price-scroll" tabindex="0" aria-label="Komende kwartierprijzen, horizontaal scrollbaar"><div class="price-quarters">${rows}</div></div></section>`;
}

const DAILY_GRAPH_MAX_DAYS = 3;
const DAILY_GRAPH_CACHE_LIMIT = 4;
const DAILY_GRAPH_CACHE = new Map();
const LOCAL_DAY_FORMATTER = new Intl.DateTimeFormat("en-CA", {
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  timeZone: "Europe/Brussels",
});
const DAILY_GRAPH_TIME_FORMATTER = new Intl.DateTimeFormat("nl-BE", {
  hour: "2-digit",
  minute: "2-digit",
  timeZone: "Europe/Brussels",
  timeZoneName: "shortOffset",
});
const DAILY_GRAPH_DAY_FORMATTER = new Intl.DateTimeFormat("nl-BE", {
  weekday: "long",
  day: "numeric",
  month: "long",
  timeZone: "Europe/Brussels",
});
const DAILY_GRAPH_AXIS_FORMATTER = new Intl.DateTimeFormat("en-GB", {
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
  timeZone: "Europe/Brussels",
});

function localDayKey(timestamp) {
  const parts = LOCAL_DAY_FORMATTER.formatToParts(new Date(timestamp));
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${values.year}-${values.month}-${values.day}`;
}

function dailyGraphCacheKey(rows, reference) {
  const values = rows.map((row) => (
    `${row.startMs}:${row.endMs}:${row.importEurPerKwh}`
  )).join(";");
  return `${reference === null ? "null" : reference}|${values}`;
}

function cacheDailyGraph(key, html) {
  DAILY_GRAPH_CACHE.set(key, html);
  while (DAILY_GRAPH_CACHE.size > DAILY_GRAPH_CACHE_LIMIT) {
    DAILY_GRAPH_CACHE.delete(DAILY_GRAPH_CACHE.keys().next().value);
  }
  return html;
}

export function renderDailyPriceGraph(intervals, referenceEurPerKwh = null) {
  const reference = finiteNumber(referenceEurPerKwh);
  const rows = (Array.isArray(intervals) ? intervals : []).flatMap((row) => {
    if (!isPlainObject(row)) return [];
    const startMs = externalDateMs(safeValue(row, "startUtc"));
    const endMs = externalDateMs(safeValue(row, "endUtc"));
    const importEurPerKwh = finiteNumber(safeValue(row, "importEurPerKwh"));
    if (!Number.isFinite(startMs) || !Number.isFinite(endMs) || endMs <= startMs || importEurPerKwh === null) return [];
    return [{ startMs, endMs, importEurPerKwh }];
  }).sort((left, right) => left.startMs - right.startMs);
  if (!rows.length) {
    return '<section class="daily-price-graph"><div class="section-title"><h3>Kwartierprijzen per dag</h3><small>geen dagdata beschikbaar</small></div></section>';
  }
  const cacheKey = dailyGraphCacheKey(rows, reference);
  const cached = DAILY_GRAPH_CACHE.get(cacheKey);
  if (cached) {
    DAILY_GRAPH_CACHE.delete(cacheKey);
    DAILY_GRAPH_CACHE.set(cacheKey, cached);
    return cached;
  }

  const days = new Map();
  rows.forEach((row) => {
    const key = localDayKey(row.startMs);
    if (!days.has(key)) days.set(key, []);
    days.get(key).push(row);
  });
  const localTimeParts = (timestamp) => Object.fromEntries(
    DAILY_GRAPH_AXIS_FORMATTER.formatToParts(new Date(timestamp))
      .map((part) => [part.type, part.value]),
  );
  const charts = [...days.entries()].slice(-DAILY_GRAPH_MAX_DAYS).map(([day, dayRows]) => {
    const values = dayRows.map((row) => row.importEurPerKwh);
    const actualMinimum = Math.min(...values);
    const actualMaximum = Math.max(...values);
    const scaleValues = reference === null ? [0, ...values] : [0, reference, ...values];
    const minimum = Math.min(...scaleValues);
    const maximum = Math.max(...scaleValues);
    const range = maximum - minimum || 1;
    const chartHeight = 160;
    const plotTop = 8;
    const plotHeight = 132;
    const yFor = (value) => plotTop + ((maximum - value) / range) * plotHeight;
    const zeroY = yFor(0);
    const width = dayRows.length * 10;
    const bars = dayRows.map((row, index) => {
      const valueY = yFor(row.importEurPerKwh);
      const y = Math.min(valueY, zeroY);
      const height = Math.max(1, Math.abs(zeroY - valueY));
      const tone = reference === null ? "neutral" : row.importEurPerKwh <= reference ? "cheap" : "expensive";
      const label = `${DAILY_GRAPH_TIME_FORMATTER.format(new Date(row.startMs))} · ${compactPrice(row.importEurPerKwh)}/kWh`;
      return `<rect class="price-bar ${tone}" x="${index * 10 + 1}" y="${y.toFixed(2)}" width="8" height="${height.toFixed(2)}" role="img" aria-label="${escapeHtml(label)}"><title>${escapeHtml(label)}</title></rect>`;
    }).join("");
    const referenceLine = reference === null ? "" : `<line class="price-reference-line" x1="0" x2="${width}" y1="${yFor(reference).toFixed(2)}" y2="${yFor(reference).toFixed(2)}"><title>Referentie ${escapeHtml(compactPrice(reference))}/kWh</title></line>`;
    const dateLabel = DAILY_GRAPH_DAY_FORMATTER.format(new Date(dayRows[0].startMs));
    const axisMarkers = [0, 6, 12, 18].flatMap((hour) => {
      const index = dayRows.findIndex((row) => {
        const parts = localTimeParts(row.startMs);
        return Number(parts.hour) === hour && Number(parts.minute) === 0;
      });
      if (index < 0) return [];
      const position = (index / dayRows.length) * 100;
      const edgeClass = index === 0 ? " first" : "";
      return [`<span class="price-axis-marker${edgeClass}" data-axis-hour="${hour}" style="left:${position.toFixed(2)}%">${String(hour).padStart(2, "0")}:00</span>`];
    }).join("");
    const endParts = localTimeParts(dayRows.at(-1).endMs);
    const endLabel = `${endParts.hour}:${endParts.minute}`;
    const axis = `<div class="price-axis">${axisMarkers}<span class="price-axis-marker last" data-axis-hour="24" style="left:100.00%">${escapeHtml(endLabel)}</span></div>`;
    return `<article class="price-day-chart" data-day="${escapeHtml(day)}" data-quarter-count="${dayRows.length}"><div class="price-day-heading"><strong>${escapeHtml(dateLabel)}</strong><span>${dayRows.length} kwartieren · ${escapeHtml(compactPrice(actualMinimum))}–${escapeHtml(compactPrice(actualMaximum))}/kWh</span></div><svg viewBox="0 0 ${width} ${chartHeight}" preserveAspectRatio="none" role="img" aria-label="Kwartierprijzen voor ${escapeHtml(dateLabel)}">${referenceLine}<line class="price-zero-line" x1="0" x2="${width}" y1="${zeroY.toFixed(2)}" y2="${zeroY.toFixed(2)}"/>${bars}</svg>${axis}</article>`;
  }).join("");
  return cacheDailyGraph(
    cacheKey,
    `<section class="daily-price-graph"><div class="section-title"><h3>Kwartierprijzen per dag</h3><small>afnameprijs · lokale tijd</small></div><div class="price-day-list">${charts}</div></section>`,
  );
}

export function renderPriceAggregates(aggregates, referenceEurPerKwh = null) {
  const definitions = [
    ["daily", "Dag"],
    ["weekly", "Week"],
    ["monthly", "Maand"],
  ];
  const normalised = normaliseAggregates(aggregates);
  const reference = finiteNumber(referenceEurPerKwh);
  const cards = definitions.map(([key, label]) => {
    const row = normalised[key].at(-1);
    if (!row) {
      return `<div class="price-summary"><span>${label}</span><strong>—</strong><small>geen aggregaat</small></div>`;
    }
    const average = row.average_eur_per_kwh;
    const difference = reference === null ? null : average - reference;
    const suffix = row.partial_period ? "partieel" : "volledig";
    return `<div class="price-summary"><span>${label} · ${escapeHtml(row.period)}</span><strong>${escapeHtml(compactPrice(average))}</strong><small>${escapeHtml(compactPrice(difference))} vs referentie · ${suffix}</small></div>`;
  }).join("");
  return `<section class="price-aggregates">${cards}</section>`;
}

function qualityLabel(quality) {
  return {
    GOOD: "actueel",
    STALE: "verouderd",
    MISSING: "ontbreekt",
    UNAVAILABLE: "onbeschikbaar",
    INVALID: "ongeldige waarde",
    NOT_CONFIGURED: "niet ingesteld",
  }[quality] || quality;
}

function metric(label, value, detail = "") {
  return `<div class="metric"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong>${detail ? `<small>${escapeHtml(detail)}</small>` : ""}</div>`;
}

function flowItem(label, value, modifier = "") {
  return `<div class="flow-item ${modifier}"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`;
}

function qualityRows(snapshot) {
  const rows = [
    ...snapshot.quality.live,
    ...snapshot.quality.optional,
    ...snapshot.quality.requiredMissing.map((key) => ({ key, quality: "NOT_CONFIGURED" })),
  ];
  if (!rows.length) return '<span class="quality-ok">Alle geconfigureerde live inputs zijn actueel.</span>';
  return rows.map((row) => `<span class="quality-chip ${escapeHtml(row.quality.toLowerCase())}">${escapeHtml(row.key)} · ${escapeHtml(qualityLabel(row.quality))}</span>`).join("");
}

export class DynamicEnergyShadowCard extends HTMLElementBase {
  constructor() {
    super();
    this._config = { ...DEFAULT_CONFIG };
    this._hass = null;
    this._root = this.attachShadow ? this.attachShadow({ mode: "open" }) : null;
  }

  static getConfigForm() {
    return {
      schema: [
        { name: "title", selector: { text: {} } },
        { name: "grid_power_entity", required: true, selector: { entity: {} } },
        { name: "pv_power_entity", required: true, selector: { entity: {} } },
        { name: "battery_power_entity", required: true, selector: { entity: {} } },
        { name: "battery_soc_entity", required: true, selector: { entity: {} } },
        { name: "house_power_entity", selector: { entity: {} } },
        { name: "ev_power_entity", selector: { entity: {} } },
        { name: "heat_pump_power_entity", selector: { entity: {} } },
        { name: "import_price_entity", selector: { entity: {} } },
        { name: "export_price_entity", selector: { entity: {} } },
        { name: "plan_entity", selector: { entity: {} } },
        { name: "plan_attribute", selector: { text: {} } },
        { name: "price_attribute", selector: { text: {} } },
        { name: "integration_price_attribute", selector: { text: {} } },
        { name: "price_reference_eur_per_kwh", selector: { number: { min: -2, max: 5, step: 0.001, mode: "box", unit_of_measurement: "EUR/kWh" } } },
        { name: "peak_limit_kw", selector: { number: { min: 0.1, max: 30, step: 0.1, mode: "box", unit_of_measurement: "kW" } } },
        { name: "stale_after_minutes", selector: { number: { min: 1, max: 180, step: 1, mode: "box", unit_of_measurement: "min" } } },
        { name: "price_stale_after_minutes", selector: { number: { min: 1, max: 180, step: 1, mode: "box", unit_of_measurement: "min" } } },
        { name: "plan_stale_after_hours", selector: { number: { min: 1, max: 72, step: 1, mode: "box", unit_of_measurement: "h" } } },
        { name: "deviation_warning_kw", selector: { number: { min: 0.1, max: 10, step: 0.1, mode: "box", unit_of_measurement: "kW" } } },
        { name: "grid_import_positive", selector: { boolean: {} } },
        { name: "battery_charge_positive", selector: { boolean: {} } },
      ],
      computeLabel: (schema) => ({
        title: "Titel",
        grid_power_entity: "Netvermogen",
        pv_power_entity: "PV-vermogen",
        battery_power_entity: "Batterijvermogen",
        battery_soc_entity: "Batterij-SOC",
        house_power_entity: "Huisvermogen (optioneel)",
        ev_power_entity: "EV-laadvermogen (optioneel)",
        heat_pump_power_entity: "Warmtepompvermogen (optioneel)",
        import_price_entity: "Actuele afnameprijs (optioneel)",
        export_price_entity: "Actuele injectieprijs (optioneel)",
        plan_entity: "Shadow-planentity (optioneel)",
        plan_attribute: "Attribuut met kwartierplanning",
        price_attribute: "Attribuut met toekomstige prijzen",
        integration_price_attribute: "Attribuut van EPEX/Ecopower-prijsentities",
        price_reference_eur_per_kwh: "Indicatieve vergelijkingsprijs",
        peak_limit_kw: "Gezamenlijke netpiekgrens",
        stale_after_minutes: "Live data verouderd na",
        price_stale_after_minutes: "Prijsdata verouderd na",
        plan_stale_after_hours: "Plan verouderd na",
        deviation_warning_kw: "Waarschuwing bij afwijking",
        grid_import_positive: "Positief netvermogen betekent afname",
        battery_charge_positive: "Positief batterijvermogen betekent laden",
      })[schema.name] || schema.name,
    };
  }

  static getStubConfig() {
    return { ...DEFAULT_CONFIG };
  }

  static getCardSize() {
    return 8;
  }

  setConfig(config) {
    if (!config || typeof config !== "object" || Array.isArray(config)) {
      throw new Error("Ongeldige kaartconfiguratie");
    }
    this._config = { ...DEFAULT_CONFIG, ...config };
    this._renderStateRefs = null;
    this._renderMinute = null;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    const states = hass?.states || {};
    const nextRefs = SHADOW_RENDER_ENTITY_FIELDS.map((field) => {
      const entityId = this._config[field];
      return entityId ? states[entityId] || null : null;
    });
    const nextMinute = Math.floor(Date.now() / 60000);
    const relevantStateChanged = !this._renderStateRefs
      || nextRefs.some((stateObject, index) => stateObject !== this._renderStateRefs[index]);
    if (relevantStateChanged || nextMinute !== this._renderMinute) {
      this._renderStateRefs = nextRefs;
      this._renderMinute = nextMinute;
      this._render();
    }
  }

  getCardSize() {
    return 8;
  }

  _render() {
    if (!this._root) return;
    const existingPriceScroll = this._root.querySelector?.(".price-scroll");
    const activePriceDirection = this._root.activeElement?.dataset?.priceScrollBy || null;
    if (existingPriceScroll) this._priceScrollLeft = existingPriceScroll.scrollLeft;
    const snapshot = buildSnapshot(this._hass, this._config, new Date());
    const interval = snapshot.plan.interval;
    const statusClass = snapshot.status.toLowerCase().replaceAll("_", "-");
    const action = interval?.action || "NO_ACTION";
    const reason = interval?.reason || (
      snapshot.status === "DATA_GATED"
        ? "Configureer een planentity om de actuele Day-Ahead-actie te tonen."
        : "Er is geen geldig kwartierplan voor het huidige tijdstip."
    );
    const houseDetail = snapshot.live.houseSource === "DERIVED" ? "afgeleid" : "gemeten";
    const gridMode = snapshot.live.gridKw === null
      ? "geen data"
      : snapshot.live.gridKw >= 0 ? "netafname" : "injectie";
    const batteryMode = snapshot.live.batteryKw === null
      ? "geen data"
      : snapshot.live.batteryKw > 0 ? "laden" : snapshot.live.batteryKw < 0 ? "ontladen" : "rust";
    const planDetail = snapshot.plan.plannedGridImportKw === null
      ? "geen geplande netwaarde"
      : `plan ${formatKw(snapshot.plan.plannedGridImportKw)} · afwijking ${formatKw(snapshot.plan.gridDeviationKw)}`;

    this._root.innerHTML = `
      <style>
        :host {
          display: block;
          --des-accent: var(--primary-color, #315b4c);
          --des-accent-soft: color-mix(in srgb, var(--des-accent) 12%, var(--card-background-color, #fff));
          --des-ink: var(--primary-text-color, #1b211f);
          --des-muted: var(--secondary-text-color, #66706c);
          --des-border: var(--divider-color, #d9dfdc);
          --des-surface: var(--card-background-color, #fff);
          --des-work: color-mix(in srgb, var(--des-surface) 94%, var(--des-ink) 6%);
          --des-good: #2d7654;
          --des-warn: #a86512;
          --des-bad: #a53c3c;
          font-family: var(--paper-font-body1_-_font-family, var(--ha-font-family-body, system-ui, sans-serif));
          color: var(--des-ink);
        }
        ha-card { overflow: hidden; border: 1px solid var(--des-border); }
        .shell { min-width: 0; }
        .header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; padding: 20px 22px 17px; background: var(--des-accent-soft); border-bottom: 1px solid var(--des-border); }
        .eyebrow { display: block; margin-bottom: 4px; color: var(--des-muted); font-size: 11px; font-weight: 700; letter-spacing: .09em; text-transform: uppercase; }
        h2 { margin: 0; font-size: 21px; line-height: 1.2; font-weight: 650; text-wrap: pretty; }
        .status { flex: 0 0 auto; padding: 6px 9px; border: 1px solid currentColor; border-radius: 999px; font-size: 11px; font-weight: 750; letter-spacing: .04em; text-transform: uppercase; }
        .status.tracking { color: var(--des-good); }
        .status.deviation, .status.data-gated, .status.no-action, .status.setup-required { color: var(--des-warn); }
        .status.peak-risk, .status.stale-data, .status.unavailable-data { color: var(--des-bad); }
        .metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); border-bottom: 1px solid var(--des-border); }
        .metric { min-width: 0; padding: 16px 18px; border-right: 1px solid var(--des-border); }
        .metric:last-child { border-right: 0; }
        .metric span, .flow-item span { display: block; color: var(--des-muted); font-size: 11px; font-weight: 700; letter-spacing: .05em; text-transform: uppercase; }
        .metric strong { display: block; margin-top: 7px; font-family: var(--ha-font-family-code, ui-monospace, monospace); font-size: 20px; font-variant-numeric: tabular-nums; }
        .metric small { display: block; margin-top: 4px; color: var(--des-muted); font-size: 11px; }
        .price-timeline { min-width: 0; padding: 18px 20px; border-bottom: 1px solid var(--des-border); }
        .price-scroll { max-width: 100%; overflow-x: auto; overscroll-behavior-inline: contain; padding-bottom: 5px; scrollbar-width: thin; touch-action: pan-x pan-y; }
        .price-quarters { display: grid; grid-auto-flow: column; grid-auto-columns: minmax(118px, 1fr); gap: 7px; min-width: max-content; }
        .price-quarter { display: grid; gap: 5px; padding: 10px; border: 1px solid var(--des-border); border-top: 4px solid var(--des-muted); border-radius: 8px; background: var(--des-surface); scroll-snap-align: start; }
        .price-quarter.cheap { border-top-color: var(--des-good); }
        .price-quarter.expensive { border-top-color: var(--des-bad); }
        .price-quarter time, .price-quarter small { color: var(--des-muted); font-size: 10px; }
        .price-quarter strong { font-family: var(--ha-font-family-code, ui-monospace, monospace); font-size: 16px; }
        .price-quarter span { color: var(--des-accent); font-size: 10px; font-weight: 700; }
        .price-empty { margin: 0; color: var(--des-muted); font-size: 12px; }
        .price-heading > div:first-child { min-width: 0; }
        .price-heading small { display: block; margin-top: 4px; }
        .price-nav { display: flex; flex: 0 0 auto; gap: 6px; }
        .price-nav button { display: inline-grid; width: 44px; height: 44px; place-items: center; border: 1px solid var(--des-border); border-radius: 8px; background: var(--des-surface); color: var(--des-ink); font: inherit; font-size: 24px; cursor: pointer; }
        .price-nav button:focus-visible { outline: 3px solid color-mix(in srgb, var(--des-accent) 45%, transparent); outline-offset: 2px; }
        .price-nav button:disabled { cursor: default; opacity: .42; }
        .daily-price-graph { min-width: 0; padding: 18px 20px; border-bottom: 1px solid var(--des-border); }
        .price-day-list { display: grid; gap: 16px; }
        .price-day-chart { min-width: 0; padding: 12px; border: 1px solid var(--des-border); border-radius: 10px; background: var(--des-surface); }
        .price-day-heading { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin-bottom: 8px; }
        .price-day-heading strong { font-size: 13px; }
        .price-day-heading span, .price-axis { color: var(--des-muted); font-size: 10px; }
        .price-day-chart svg { display: block; width: 100%; height: 180px; overflow: visible; }
        .price-bar { fill: var(--des-muted); }
        .price-bar.cheap { fill: var(--des-good); }
        .price-bar.expensive { fill: var(--des-bad); }
        .price-reference-line { stroke: var(--des-warn); stroke-dasharray: 5 4; stroke-width: 1.5; vector-effect: non-scaling-stroke; }
        .price-zero-line { stroke: var(--des-border); stroke-width: 1; vector-effect: non-scaling-stroke; }
        .price-axis { position: relative; height: 14px; margin-top: 4px; font-variant-numeric: tabular-nums; }
        .price-axis-marker { position: absolute; top: 0; transform: translateX(-50%); white-space: nowrap; }
        .price-axis-marker.first { transform: none; }
        .price-axis-marker.last { transform: translateX(-100%); }
        .price-aggregates { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); border-bottom: 1px solid var(--des-border); }
        .price-summary { min-width: 0; padding: 12px 20px; border-right: 1px solid var(--des-border); }
        .price-summary:last-child { border-right: 0; }
        .price-summary span, .price-summary small { display: block; color: var(--des-muted); font-size: 10px; }
        .price-summary strong { display: block; margin: 5px 0; font-family: var(--ha-font-family-code, ui-monospace, monospace); font-size: 16px; }
        .body { display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(260px, .65fr); gap: 0; }
        .main { min-width: 0; padding: 18px 20px 20px; }
        .side { min-width: 0; padding: 18px; background: var(--des-work); border-left: 1px solid var(--des-border); }
        .section-title { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin-bottom: 12px; }
        h3 { margin: 0; font-size: 14px; font-weight: 700; }
        .section-title small { color: var(--des-muted); font-size: 11px; }
        .flow { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); border: 1px solid var(--des-border); border-radius: 10px; overflow: hidden; }
        .flow-item { min-width: 0; padding: 14px; border-right: 1px solid var(--des-border); }
        .flow-item:last-child { border-right: 0; }
        .flow-item strong { display: block; margin-top: 6px; font-family: var(--ha-font-family-code, ui-monospace, monospace); font-size: 16px; font-variant-numeric: tabular-nums; }
        .plan { margin-top: 16px; padding: 16px; border: 1px solid var(--des-border); border-radius: 10px; }
        .plan-top { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
        .action { display: inline-flex; align-items: center; gap: 7px; font-size: 16px; font-weight: 700; }
        .action::before { width: 9px; height: 9px; border-radius: 50%; background: var(--des-muted); content: ""; }
        .action.charge::before { background: #2f7f9b; }
        .action.discharge::before { background: var(--des-good); }
        .plan-code { color: var(--des-muted); font-family: var(--ha-font-family-code, ui-monospace, monospace); font-size: 11px; }
        .reason { margin: 10px 0 0; color: var(--des-muted); font-size: 13px; line-height: 1.5; text-wrap: pretty; }
        .plan-detail { margin-top: 12px; padding-top: 11px; border-top: 1px solid var(--des-border); color: var(--des-ink); font-family: var(--ha-font-family-code, ui-monospace, monospace); font-size: 12px; }
        .component-list { display: grid; gap: 1px; background: var(--des-border); border: 1px solid var(--des-border); border-radius: 10px; overflow: hidden; }
        .component { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 11px 12px; background: var(--des-surface); }
        .component span { color: var(--des-muted); font-size: 12px; }
        .component strong { font-family: var(--ha-font-family-code, ui-monospace, monospace); font-size: 12px; }
        .quality { display: flex; flex-wrap: wrap; gap: 7px; margin-top: 16px; }
        .quality-chip, .quality-ok { display: inline-flex; padding: 5px 7px; border: 1px solid var(--des-border); border-radius: 5px; color: var(--des-muted); font-size: 10px; }
        .quality-chip.invalid, .quality-chip.stale, .quality-chip.missing, .quality-chip.unavailable { color: var(--des-bad); border-color: color-mix(in srgb, var(--des-bad) 40%, var(--des-border)); }
        .footer { display: flex; justify-content: space-between; gap: 12px; padding: 10px 18px; border-top: 1px solid var(--des-border); color: var(--des-muted); font-size: 10px; letter-spacing: .03em; text-transform: uppercase; }
        @media (max-width: 760px) {
          .header { padding: 17px 16px 14px; }
          .metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
          .metric:nth-child(2) { border-right: 0; }
          .metric:nth-child(-n+2) { border-bottom: 1px solid var(--des-border); }
          .body { grid-template-columns: 1fr; }
          .side { border-left: 0; border-top: 1px solid var(--des-border); }
          .flow { grid-template-columns: repeat(2, minmax(0, 1fr)); }
          .flow-item:nth-child(2) { border-right: 0; }
          .flow-item:nth-child(-n+2) { border-bottom: 1px solid var(--des-border); }
          .plan-top, .footer { flex-direction: column; }
          .price-aggregates { grid-template-columns: 1fr; }
          .price-summary { border-right: 0; border-bottom: 1px solid var(--des-border); }
          .price-summary:last-child { border-bottom: 0; }
        }
        @media (max-width: 430px) {
          .header { flex-direction: column; }
          .status { align-self: flex-start; }
          .main, .side { padding: 14px; }
          .metric { padding: 13px; }
          .metric strong { font-size: 17px; }
          .price-heading, .price-day-heading { align-items: stretch; flex-direction: column; }
          .price-nav { align-self: stretch; }
          .price-nav button { flex: 1 1 0; }
          .daily-price-graph, .price-timeline { padding-inline: 14px; }
          .price-day-chart svg { height: 150px; }
        }
      </style>
      <ha-card>
        <div class="shell">
          <header class="header">
            <div><span class="eyebrow">Live observatie · geen control</span><h2>${escapeHtml(this._config.title || DEFAULT_CONFIG.title)}</h2></div>
            <span class="status ${escapeHtml(statusClass)}">${escapeHtml(snapshot.statusLabel)}</span>
          </header>
          <section class="metrics">
            ${metric("Net", formatKw(snapshot.live.gridKw), gridMode)}
            ${metric("Batterij-SOC", formatPercent(snapshot.live.socPercent), batteryMode)}
            ${metric("Vrije netruimte", formatKw(snapshot.peak.headroomKw), `grens ${formatKw(snapshot.peak.limitKw)}`)}
            ${metric("Actuele prijs", formatPrice(snapshot.live.importPriceEurPerKwh), "afname per kWh")}
          </section>
          ${renderPriceTimeline(
            snapshot.prices.intervals,
            snapshot.plan.schedule,
            snapshot.prices.referenceEurPerKwh,
            snapshot.prices.source,
            snapshot.prices.tariffVersion,
          )}
          ${renderDailyPriceGraph(snapshot.prices.dailyIntervals, snapshot.prices.referenceEurPerKwh)}
          ${renderPriceAggregates(snapshot.prices.aggregates, snapshot.prices.referenceEurPerKwh)}
          <div class="body">
            <main class="main">
              <div class="section-title"><h3>Energiestroom</h3><small>live Home Assistant-states</small></div>
              <div class="flow">
                ${flowItem("PV", formatKw(snapshot.live.pvKw))}
                ${flowItem("Woning", formatKw(snapshot.live.houseKw), houseDetail)}
                ${flowItem("Batterij", formatKw(snapshot.live.batteryKw))}
                ${flowItem("Net", formatKw(snapshot.live.gridKw))}
              </div>
              <section class="plan">
                <div class="plan-top"><div><span class="eyebrow">Huidig kwartierplan</span><span class="action ${escapeHtml(actionTone(action))}">${escapeHtml(actionLabel(action))}</span></div><code class="plan-code">${escapeHtml(snapshot.plan.mode || "READ_ONLY_SHADOW")}</code></div>
                <p class="reason">${escapeHtml(reason)}</p>
                <div class="plan-detail">${escapeHtml(planDetail)}</div>
              </section>
              <div class="quality">${qualityRows(snapshot)}</div>
            </main>
            <aside class="side">
              <div class="section-title"><h3>Componenten</h3><small>optioneel</small></div>
              <div class="component-list">
                <div class="component"><span>EV-laden</span><strong>${escapeHtml(formatKw(snapshot.live.evKw))}</strong></div>
                <div class="component"><span>Warmtepomp</span><strong>${escapeHtml(formatKw(snapshot.live.heatPumpKw))}</strong></div>
                <div class="component"><span>Injectieprijs</span><strong>${escapeHtml(formatPrice(snapshot.live.exportPriceEurPerKwh))}</strong></div>
                <div class="component"><span>Piekbenutting</span><strong>${escapeHtml(formatPercent(snapshot.peak.utilizationPercent))}</strong></div>
              </div>
            </aside>
          </div>
          <footer class="footer"><span>READ_ONLY_SHADOW</span><span>geen Home Assistant-, SMA- of Smappee-writes</span></footer>
        </div>
      </ha-card>`;
    const priceScroll = this._root.querySelector(".price-scroll");
    if (priceScroll) {
      const maximumScroll = () => Math.max(0, priceScroll.scrollWidth - priceScroll.clientWidth);
      priceScroll.scrollLeft = Math.min(this._priceScrollLeft || 0, maximumScroll());
      const scrollButtons = [...this._root.querySelectorAll("[data-price-scroll-by]")];
      const syncScrollButtons = () => {
        const currentMaximum = maximumScroll();
        scrollButtons.forEach((button) => {
          const direction = Number(button.dataset.priceScrollBy) || 0;
          button.disabled = direction < 0
            ? priceScroll.scrollLeft <= 1
            : priceScroll.scrollLeft >= currentMaximum - 1;
        });
      };
      priceScroll.addEventListener("scroll", () => {
        this._priceScrollLeft = priceScroll.scrollLeft;
        syncScrollButtons();
      }, { passive: true });
      scrollButtons.forEach((button) => {
        button.addEventListener("click", () => {
          const direction = Number(button.dataset.priceScrollBy) || 0;
          const requested = priceScroll.scrollLeft
            + direction * Math.max(240, priceScroll.clientWidth * 0.75);
          priceScroll.scrollLeft = Math.max(0, Math.min(maximumScroll(), requested));
          this._priceScrollLeft = priceScroll.scrollLeft;
          syncScrollButtons();
        });
      });
      syncScrollButtons();
      if (activePriceDirection !== null) {
        const replacement = scrollButtons.find(
          (button) => button.dataset.priceScrollBy === activePriceDirection,
        );
        replacement?.focus({ preventScroll: true });
      }
    }
  }
}

function validationActionLabel(value) {
  return {
    CHARGING: "Laden",
    DISCHARGING: "Ontladen",
    IDLE: "Geen actie",
    INSUFFICIENT_DATA: "Onvoldoende data",
  }[value] || value || "Onvoldoende data";
}

function validationStatusLabel(value) {
  return {
    BLOCKED: "Pilot geblokkeerd",
    MATCH: "Gedrag komt overeen",
    ACCEPTABLE_DEVIATION: "Aanvaardbare afwijking",
    UNEXPECTED_ACTION: "Onverwachte actie",
    MISSED_OPPORTUNITY: "Gemiste actie",
    SHARED_PEAK_WARNING: "Gedeelde piekwaarschuwing",
    INSUFFICIENT_DATA: "Onvoldoende data",
  }[value] || value || "Onvoldoende data";
}

function validationPriceZoneLabel(value) {
  return {
    CHEAP: "Goedkoop",
    NORMAL: "Normaal",
    EXPENSIVE: "Duur",
    INSUFFICIENT_DATA: "Onvoldoende data",
  }[value] || "Onvoldoende data";
}

function validationPilotStatusLabel(value) {
  return {
    NOT_STARTED: "Pilot niet gestart",
    PROTECTION_BASELINE_PENDING: "Protection baseline open",
    SMA_ONLY_PILOT: "Alleen SMA-pilot",
    SMAPPEE_ONLY_PILOT: "Alleen Smappee-pilot",
    COMBINED_OBSERVATION: "Gecombineerde observatie",
    EVIDENCE_INSUFFICIENT: "Onvoldoende bewijs",
    READY_FOR_REVIEW: "Gereed voor beoordeling",
    BLOCKED: "Geblokkeerd",
  }[value] || "Geblokkeerd";
}

function validationMetric(label, value, detail = "") {
  return `<div class="validation-metric"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong>${detail ? `<small>${escapeHtml(detail)}</small>` : ""}</div>`;
}

function formatValidationNumber(value, suffix = "") {
  const parsed = finiteNumber(value);
  return parsed === null
    ? "—"
    : `${new Intl.NumberFormat("nl-BE", { maximumFractionDigits: 2 }).format(parsed)}${suffix}`;
}

function formatValidationEur(value) {
  const parsed = finiteNumber(value);
  return parsed === null
    ? "—"
    : new Intl.NumberFormat("nl-BE", { style: "currency", currency: "EUR" }).format(parsed);
}

export function renderValidationCard(config, snapshot) {
  const summary = snapshot?.summary || { quality: "NOT_CONFIGURED" };
  const summaryTitle = summary.quality === "GOOD"
    ? `Dagscore · ${summary.localDate}`
    : "Dagscore · nog niet beschikbaar";
  const sharedTelemetryGood = [
    snapshot?.live?.gridQuality,
    snapshot?.live?.batteryQuality,
    snapshot?.live?.evQuality,
  ].every((quality) => quality === "GOOD")
    && finiteNumber(snapshot?.grid?.headroomKw) !== null;
  const sharedState = !sharedTelemetryGood
    ? "UNKNOWN"
    : snapshot.grid.headroomKw < 0 ? "EXCEEDED"
      : snapshot.grid.collision ? "COLLISION" : "CLEAR";
  const collisionText = sharedState === "UNKNOWN"
    ? "Onvoldoende actuele meetdata om gelijktijdig laden en de gedeelde netgrens betrouwbaar te beoordelen."
    : sharedState === "EXCEEDED"
      ? snapshot.grid.collision
        ? "De effectieve gedeelde netgrens is overschreden terwijl batterij en EV gelijktijdig laden."
        : "De effectieve gedeelde netgrens is overschreden zonder gelijktijdige batterij- en EV-laadactie."
      : sharedState === "COLLISION"
        ? "Gelijktijdig batterij- en EV-laden gedetecteerd; de gemeten netimport blijft binnen de effectieve grens."
        : "Geen gelijktijdige laadactie of gedeelde grensoverschrijding in dit kwartier.";
  const summaryMetrics = summary.quality === "GOOD"
    ? `
      ${validationMetric("Datadekking", formatValidationNumber(summary.coveragePercent, "%"))}
      ${validationMetric("Batterij goedkoop geladen", formatValidationNumber(summary.batteryChargeCheapKwh, " kWh"))}
      ${validationMetric("Batterij duur ontladen", formatValidationNumber(summary.batteryDischargeExpensiveKwh, " kWh"))}
      ${validationMetric("EV goedkoop geladen", formatValidationNumber(summary.evChargeCheapKwh, " kWh"))}
      ${validationMetric("EV goedkoop aandeel", formatValidationNumber(summary.evCheapSharePercent, "%"))}
      ${validationMetric("Maximale netimport", formatKw(summary.maxGridImportKw))}
      ${validationMetric("Gedeelde laadkwartieren", formatValidationNumber(summary.collisionIntervals))}
      ${validationMetric("Overeenkomstige kwartieren", formatValidationNumber(summary.matchedIntervals))}
      ${validationMetric("Afwijkende kwartieren", formatValidationNumber(summary.deviationIntervals))}
      ${validationMetric("Werkelijke kosten", formatValidationEur(summary.actualCostEur))}
      ${validationMetric("Shadow-kosten", formatValidationEur(summary.shadowCostEur))}
      ${validationMetric("Kostenverschil", formatValidationEur(summary.costDeltaEur))}`
    : validationMetric(
      "Historische validatie",
      qualityLabel(summary.quality || "NOT_CONFIGURED"),
      "Geen nulwaarden ingevuld wanneer een gevalideerde dagsamenvatting ontbreekt.",
    );
  return `
    <ha-card>
      <div class="validation-shell">
        <header class="validation-header">
          <div><span class="validation-eyebrow">Read-only gedragsvalidatie</span><h2>${escapeHtml(config.title || DEFAULT_VALIDATION_CONFIG.title)}</h2></div>
          <div class="validation-badges"><span title="${escapeHtml(snapshot?.pilotStatus || "NOT_STARTED")}">${escapeHtml(validationPilotStatusLabel(snapshot?.pilotStatus))}</span><strong class="validation-status ${escapeHtml(String(snapshot?.status || "INSUFFICIENT_DATA").toLowerCase())}">${escapeHtml(validationStatusLabel(snapshot?.status))}</strong></div>
        </header>
        <section class="validation-lock">
          <strong>Alleen observeren · er worden geen acties uitgevoerd</strong>
          <code>execution_allowed = false</code>
          <p>De kaart vergelijkt meetdata met het shadow-plan. Zij schrijft niets naar Home Assistant-apparaten, SMA, Smappee, batterij of laadpaal.</p>
        </section>
        <section class="validation-section">
          <div class="validation-section-title"><div><span class="validation-eyebrow">Huidig kwartier</span><h3>Verwacht versus werkelijk</h3></div><span>${escapeHtml(snapshot?.interval?.batteryOutcome || "INSUFFICIENT_DATA")}</span></div>
          <div class="validation-grid four">
            ${validationMetric("Verwacht batterijgedrag", validationActionLabel(snapshot?.interval?.expectedBatteryAction), snapshot?.interval?.planReason || "Geen planreden")}
            ${validationMetric(
              "Werkelijk batterijgedrag",
              validationActionLabel(snapshot?.interval?.observedBatteryAction),
              snapshot?.live?.batteryFreshnessSource === "HEARTBEAT"
                ? "actueel via heartbeat"
                : qualityLabel(snapshot?.live?.batteryQuality || "NOT_CONFIGURED"),
            )}
            ${validationMetric("Werkelijk EV-gedrag", validationActionLabel(snapshot?.interval?.evAction), qualityLabel(snapshot?.live?.evQuality || "NOT_CONFIGURED"))}
            ${validationMetric("Resultaat", validationStatusLabel(snapshot?.interval?.batteryOutcome), "Geen vendoroorzaak afgeleid")}
          </div>
          <div class="validation-grid two">
            ${validationMetric("Actuele afnameprijs", `${compactPrice(snapshot?.price?.currentEurPerKwh)}/kWh`, snapshot?.price?.source || qualityLabel(snapshot?.price?.quality || "UNAVAILABLE"))}
            ${validationMetric("Prijszone", validationPriceZoneLabel(snapshot?.price?.zone), "Relatief aan de beschikbare kwartierprijzen")}
          </div>
        </section>
        <section class="validation-section peak ${["COLLISION", "EXCEEDED"].includes(sharedState) ? "warning" : ""}">
          <div class="validation-section-title"><div><span class="validation-eyebrow">Gedeelde netruimte</span><h3>Piek- en collisionbewaking</h3></div><span>${escapeHtml(sharedState)}</span></div>
          <div class="validation-grid four">
            ${validationMetric("Netimport", formatKw(snapshot?.live?.gridKw), qualityLabel(snapshot?.live?.gridQuality || "NOT_CONFIGURED"))}
            ${validationMetric("Batterijvermogen", formatKw(snapshot?.live?.batteryKw))}
            ${validationMetric("EV-laadvermogen", formatKw(snapshot?.live?.evKw))}
            ${validationMetric("Gedeelde headroom", formatKw(snapshot?.grid?.headroomKw), `effectieve grens ${formatKw(snapshot?.grid?.effectiveLimitKw)}`)}
          </div>
          <div class="validation-grid three">
            ${validationMetric(
              "Huisvermogen",
              formatKw(snapshot?.live?.houseKw),
              snapshot?.live?.houseSource === "DERIVED"
                ? "afgeleid uit net, PV en batterij"
                : qualityLabel(snapshot?.live?.houseQuality || "NOT_CONFIGURED"),
            )}
            ${validationMetric("PV-vermogen", formatKw(snapshot?.live?.pvKw), qualityLabel(snapshot?.live?.pvQuality || "NOT_CONFIGURED"))}
            ${validationMetric("Warmtepomp", formatKw(snapshot?.live?.heatPumpKw), qualityLabel(snapshot?.live?.heatPumpQuality || "NOT_CONFIGURED"))}
          </div>
          <p class="validation-notice">${escapeHtml(collisionText)}</p>
        </section>
        <section class="validation-section summary">
          <div class="validation-section-title"><div><span class="validation-eyebrow">Bewijs over tijd</span><h3>${escapeHtml(summaryTitle)}</h3></div><span>${escapeHtml(qualityLabel(summary.quality || "NOT_CONFIGURED"))}</span></div>
          <div class="validation-grid summary-grid">${summaryMetrics}</div>
        </section>
        <footer class="validation-footer"><span>Doelarchitectuur: SMA voor batterij/PV · Smappee voor EV · niet automatisch geverifieerd</span><span>Geen uitvoermodus · geen fysieke writes</span></footer>
      </div>
    </ha-card>`;
}

export class DynamicEnergyValidationCard extends HTMLElementBase {
  constructor() {
    super();
    this._config = { ...DEFAULT_VALIDATION_CONFIG };
    this._hass = null;
    this._telemetryStates = {};
    this._telemetryRefreshTimer = null;
    this._telemetryRefreshInFlight = null;
    this._lastTelemetryRefreshMs = 0;
    this._root = this.attachShadow ? this.attachShadow({ mode: "open" }) : null;
  }

  connectedCallback() {
    this._startTelemetryRefresh();
  }

  disconnectedCallback() {
    if (this._telemetryRefreshTimer !== null) {
      globalThis.clearInterval(this._telemetryRefreshTimer);
      this._telemetryRefreshTimer = null;
    }
  }

  static getConfigForm() {
    return {
      schema: [
        { name: "title", selector: { text: {} } },
        { name: "plan_entity", required: true, selector: { entity: {} } },
        { name: "grid_power_entity", required: true, selector: { entity: {} } },
        { name: "grid_import_positive", selector: { boolean: {} } },
        { name: "battery_power_entity", required: true, selector: { entity: {} } },
        { name: "battery_charge_positive", selector: { boolean: {} } },
        { name: "battery_freshness_entity", selector: { entity: {} } },
        { name: "ev_power_entity", required: true, selector: { entity: {} } },
        { name: "house_power_entity", selector: { entity: {} } },
        { name: "pv_power_entity", selector: { entity: {} } },
        { name: "heat_pump_power_entity", selector: { entity: {} } },
        { name: "validation_summary_entity", selector: { entity: {} } },
        { name: "import_price_entity", selector: { entity: {} } },
        { name: "export_price_entity", selector: { entity: {} } },
        { name: "integration_price_attribute", selector: { text: {} } },
        { name: "price_stale_after_minutes", selector: { number: { min: 1, max: 180, step: 1, unit_of_measurement: "min" } } },
        { name: "peak_limit_kw", selector: { number: { min: 0.1, max: 30, step: 0.1, unit_of_measurement: "kW" } } },
        { name: "smappee_capacity_threshold_kw", selector: { number: { min: 0.1, max: 30, step: 0.1, unit_of_measurement: "kW" } } },
        { name: "activity_threshold_kw", selector: { number: { min: 0.01, max: 5, step: 0.01, unit_of_measurement: "kW" } } },
        { name: "data_stale_after_minutes", selector: { number: { min: 1, max: 180, step: 1, unit_of_measurement: "min" } } },
        { name: "plan_stale_after_hours", selector: { number: { min: 1, max: 72, step: 1, unit_of_measurement: "h" } } },
        { name: "summary_stale_after_hours", selector: { number: { min: 1, max: 168, step: 1, unit_of_measurement: "h" } } },
        { name: "pilot_status", selector: { select: { options: ["NOT_STARTED", "PROTECTION_BASELINE_PENDING", "SMA_ONLY_PILOT", "SMAPPEE_ONLY_PILOT", "COMBINED_OBSERVATION", "EVIDENCE_INSUFFICIENT", "READY_FOR_REVIEW", "BLOCKED"] } } },
      ],
      computeLabel: (schema) => ({
        title: "Titel",
        plan_entity: "Shadow-planentity",
        grid_power_entity: "Netvermogen",
        grid_import_positive: "Positief netvermogen betekent afname",
        battery_power_entity: "Batterijvermogen",
        battery_charge_positive: "Positief batterijvermogen betekent laden",
        battery_freshness_entity: "Batterij-heartbeat (optioneel)",
        ev_power_entity: "EV-laadvermogen",
        house_power_entity: "Huisvermogen (optioneel)",
        pv_power_entity: "PV-vermogen (optioneel)",
        heat_pump_power_entity: "Warmtepompvermogen (optioneel)",
        validation_summary_entity: "Dagelijkse validatiesamenvatting (optioneel)",
        import_price_entity: "Actuele afnameprijs (optioneel)",
        export_price_entity: "Actuele injectieprijs (optioneel)",
        integration_price_attribute: "Attribuut van EPEX/Ecopower-prijsentities",
        price_stale_after_minutes: "Prijsdata verouderd na",
        peak_limit_kw: "Gedeelde dashboardgrens",
        smappee_capacity_threshold_kw: "Smappee Maximum grid capacity",
        activity_threshold_kw: "Actief-vermogensdrempel",
        data_stale_after_minutes: "Meetdata verouderd na",
        plan_stale_after_hours: "Shadow-plan verouderd na",
        summary_stale_after_hours: "Dagscore verouderd na",
        pilot_status: "Pilotstatus",
      })[schema.name] || schema.name,
    };
  }

  static getStubConfig() {
    return { ...DEFAULT_VALIDATION_CONFIG };
  }

  static getCardSize() {
    return 7;
  }

  setConfig(config) {
    if (!isPlainObject(config)) throw new Error("Ongeldige validatiekaartconfiguratie");
    this._config = { ...DEFAULT_VALIDATION_CONFIG, ...config };
    this._render();
    this._refreshTelemetry(true);
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
    this._startTelemetryRefresh();
  }

  getCardSize() {
    return 7;
  }

  _startTelemetryRefresh() {
    if (!this._hass || typeof this._hass.callApi !== "function") return;
    this._refreshTelemetry();
    if (this._telemetryRefreshTimer === null && typeof globalThis.setInterval === "function") {
      this._telemetryRefreshTimer = globalThis.setInterval(
        () => this._refreshTelemetry(true),
        VALIDATION_TELEMETRY_REFRESH_MS,
      );
    }
  }

  async _refreshTelemetry(force = false) {
    if (!this._hass || typeof this._hass.callApi !== "function" || this._telemetryRefreshInFlight) return;
    if (!force && Date.now() - this._lastTelemetryRefreshMs < VALIDATION_TELEMETRY_REFRESH_MS) return;
    const request = fetchValidationTelemetry(this._hass, this._config);
    this._telemetryRefreshInFlight = request;
    try {
      const states = await request;
      this._lastTelemetryRefreshMs = Date.now();
      if (Object.keys(states).length > 0) {
        this._telemetryStates = states;
        this._render();
      }
    } finally {
      if (this._telemetryRefreshInFlight === request) this._telemetryRefreshInFlight = null;
    }
  }

  _render() {
    if (!this._root) return;
    this._root.innerHTML = `
      <style>
        :host { display: block; color: var(--primary-text-color, #1b211f); font-family: var(--ha-font-family-body, system-ui, sans-serif); }
        ha-card { overflow: hidden; border: 1px solid var(--divider-color, #d9dfdc); }
        .validation-header, .validation-section-title, .validation-footer { display: flex; align-items: flex-start; justify-content: space-between; gap: 14px; }
        .validation-header { padding: 20px; background: color-mix(in srgb, var(--primary-color, #315b4c) 12%, var(--card-background-color, #fff)); border-bottom: 1px solid var(--divider-color, #d9dfdc); }
        h2, h3 { margin: 0; }
        h2 { font-size: 21px; } h3 { font-size: 16px; }
        .validation-eyebrow { display: block; margin-bottom: 4px; color: var(--secondary-text-color, #66706c); font-size: 10px; font-weight: 750; letter-spacing: .08em; text-transform: uppercase; }
        .validation-badges { display: flex; flex-direction: column; align-items: flex-end; gap: 5px; }
        .validation-badges span, .validation-badges strong, .validation-section-title > span { padding: 5px 8px; border: 1px solid currentColor; border-radius: 999px; font-size: 10px; font-weight: 750; letter-spacing: .04em; text-transform: uppercase; }
        .validation-badges span { color: var(--secondary-text-color, #66706c); }
        .validation-badges strong { color: #a86512; }
        .validation-badges strong.match { color: #2d7654; }
        .validation-badges strong.blocked, .validation-badges strong.shared_peak_warning, .validation-badges strong.unexpected_action { color: #a53c3c; }
        .validation-lock { display: grid; grid-template-columns: 1fr auto; gap: 5px 12px; padding: 15px 20px; border-bottom: 1px solid var(--divider-color, #d9dfdc); }
        .validation-lock strong, .validation-lock code { color: #2d7654; font-size: 12px; }
        .validation-lock p { grid-column: 1 / -1; margin: 0; color: var(--secondary-text-color, #66706c); font-size: 11px; line-height: 1.5; }
        .validation-section { padding: 18px 20px; border-bottom: 1px solid var(--divider-color, #d9dfdc); }
        .validation-section-title > span { color: var(--secondary-text-color, #66706c); }
        .validation-section.warning { background: color-mix(in srgb, #a86512 8%, var(--card-background-color, #fff)); }
        .validation-section.warning .validation-section-title > span { color: #a53c3c; }
        .validation-grid { display: grid; margin-top: 13px; border: 1px solid var(--divider-color, #d9dfdc); border-radius: 9px; overflow: hidden; }
        .validation-grid.four { grid-template-columns: repeat(4, minmax(0, 1fr)); }
        .validation-grid.three { grid-template-columns: repeat(3, minmax(0, 1fr)); }
        .validation-grid.two { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        .summary-grid { grid-template-columns: repeat(4, minmax(0, 1fr)); }
        .validation-metric { min-width: 0; padding: 12px 13px; border-right: 1px solid var(--divider-color, #d9dfdc); border-bottom: 1px solid var(--divider-color, #d9dfdc); }
        .validation-metric span, .validation-metric small { display: block; color: var(--secondary-text-color, #66706c); font-size: 10px; }
        .validation-metric strong { display: block; margin-top: 5px; font-size: 15px; overflow-wrap: anywhere; }
        .validation-metric small { margin-top: 4px; line-height: 1.35; }
        .validation-notice { margin: 11px 0 0; color: var(--secondary-text-color, #66706c); font-size: 11px; }
        .validation-footer { padding: 13px 20px; color: var(--secondary-text-color, #66706c); font-size: 10px; }
        @media (max-width: 700px) {
          .validation-header, .validation-section-title, .validation-footer { flex-direction: column; }
          .validation-badges { align-items: flex-start; }
          .validation-grid.four, .validation-grid.three, .summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
          .validation-section { padding: 15px; }
        }
        @media (max-width: 430px) { .validation-grid.four, .validation-grid.three, .validation-grid.two, .summary-grid { grid-template-columns: 1fr; } }
      </style>
      ${renderValidationCard(
        this._config,
        buildValidationSnapshot(hassWithValidationTelemetry(this._hass, this._telemetryStates), this._config),
      )}`;
  }
}

function formatControlTime(value) {
  const timestamp = externalDateMs(value);
  if (!Number.isFinite(timestamp)) return "—";
  return new Intl.DateTimeFormat("nl-BE", {
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Europe/Brussels",
  }).format(new Date(timestamp));
}

function setupRow(label, value, detail = "") {
  return `<div class="setup-row"><span>${escapeHtml(label)}</span><em>Dashboardprofiel</em><strong>${escapeHtml(value)}</strong>${detail ? `<small>Advies · ${escapeHtml(detail)}</small>` : ""}</div>`;
}

export function renderBlockedControlConfig(config, state, message = "", dashboard = null) {
  const labels = {
    SETUP_REQUIRED: "Nog niet aangemaakt",
    OFF: "Uitgeschakeld",
    ARMED_BLOCKED: "Gewapend · fysiek geblokkeerd",
    CONFLICT: "Configuratieconflict",
  };
  const mode = state?.mode || "SETUP_REQUIRED";
  const safetyVerified = mode === "OFF" || mode === "ARMED_BLOCKED";
  const safetyTitle = safetyVerified ? "Safety lock geverifieerd" : "Safety status niet geverifieerd";
  const safetyClass = safetyVerified ? "verified" : mode === "CONFLICT" ? "conflict" : "unverified";
  const rows = Array.isArray(state?.automations) ? state.automations : [];
  const automationRows = rows.map((row) => `
    <div class="automation-row">
      <div><strong>${escapeHtml(row.id)}</strong><small>${escapeHtml(row.entity_id || "nog geen entity")}</small></div>
      <span class="automation-state">${escapeHtml(row.state || "missing")}</span>
    </div>`).join("");
  const panel = dashboard || {
    live: {},
    price: { quality: "NOT_CONFIGURED" },
    plan: { action: "NO_ACTION", quality: "NOT_CONFIGURED" },
    readiness: { mode: "DATA_BLOCKED", warnings: [], executionAllowed: false },
  };
  const warnings = Array.isArray(panel.readiness?.warnings) ? panel.readiness.warnings : [];
  const warningRows = warnings.length
    ? warnings.map((warning) => `<li>${escapeHtml(warning)}</li>`).join("")
    : "<li>Geen extra configuratiewaarschuwingen.</li>";
  const priceDetail = [panel.price?.source, panel.price?.tariffVersion]
    .filter((value) => typeof value === "string" && value)
    .join(" · ") || "Prijsbron nog niet beschikbaar";
  const forecastState = String(config.sma_forecast_charging || "OFF").toUpperCase();
  const forecastGuidance = forecastState === "ACTIVE"
    ? "Actief verklaard; gedrag nog steeds vergelijken met het shadow-plan."
    : "Forecast-based charging pas activeren na gecontroleerde pilot.";
  const currentAction = actionLabel(panel.plan?.action || "NO_ACTION");
  const readinessLabels = {
    SHADOW_READY: "Prijsdata gereed",
    SHADOW_READY_LIVE_DEGRADED: "Prijsdata gereed · live data beperkt",
    PRICE_READY_PLAN_BLOCKED: "Prijsdata gereed · plan geblokkeerd",
    DATA_BLOCKED: "Data geblokkeerd",
  };
  const smappeeTariffLabels = {
    NOT_VERIFIED: "Niet geverifieerd",
    DISABLED: "Uitgeschakeld",
    ENABLED_CONTEXT_ONLY: "Actief · alleen prijscontext",
  };
  const smappeeTariffStatus = String(
    config.smappee_dynamic_tariff_status || "NOT_VERIFIED",
  ).toUpperCase();
  return `
    <ha-card>
      <div class="control-shell">
        <header class="control-header">
          <div><span class="eyebrow">Configure · beperkte Home Assistant-writes</span><h2>${escapeHtml(config.title || DEFAULT_CONTROL_CONFIG.title)}</h2></div>
          <span class="control-status ${escapeHtml(mode.toLowerCase())}">${escapeHtml(labels[mode] || mode)}</span>
        </header>
        <section class="safety-lock ${escapeHtml(safetyClass)}">
          <strong>${safetyTitle}</strong>
          <code>execution_allowed = false</code>
          <p>Geen apparatuurcommando's worden uitgevoerd. De kaart kan uitsluitend eigen geblokkeerde automatisaties aanmaken en in- of uitschakelen; iedere actie stopt vóór een SMA-, Smappee-, batterij- of laadpaalcommando.</p>
        </section>
        <section class="control-overview">
          <div class="section-heading"><div><span class="eyebrow">Actuele besliscontext</span><h3>Prijsstrategie</h3></div><span class="readiness ${escapeHtml(panel.readiness?.mode?.toLowerCase() || "data_blocked")}">${escapeHtml(readinessLabels[panel.readiness?.mode] || "Data geblokkeerd")}</span></div>
          <div class="strategy-grid">
            ${metric("Actuele afnameprijs", `${compactPrice(panel.price?.currentEurPerKwh)}/kWh`, qualityLabel(panel.price?.quality))}
            ${metric("Volgende goedkoopste", `${compactPrice(panel.price?.cheapestEurPerKwh)}/kWh`, formatControlTime(panel.price?.cheapestStartUtc))}
            ${metric("Duurste komend kwartier", `${compactPrice(panel.price?.highestEurPerKwh)}/kWh`, formatControlTime(panel.price?.highestStartUtc))}
            ${metric("Shadow-actie · niet uitgevoerd", currentAction, panel.plan?.reason || panel.plan?.quality || "geen reden")}
          </div>
          <div class="source-line"><span>${escapeHtml(priceDetail)}</span><span>${escapeHtml(panel.price?.intervalCount || 0)} komende kwartieren</span></div>
        </section>
        <section class="live-context">
          ${metric("Batterij-SOC", formatPercent(panel.live?.batterySocPercent), qualityLabel(panel.live?.batterySocQuality || "NOT_CONFIGURED"))}
          ${metric("Netimport", formatKw(panel.live?.gridKw), `dashboardgrens ${formatKw(config.peak_limit_kw)}`)}
          ${metric("EV-laden", formatKw(panel.live?.evKw), qualityLabel(panel.live?.evQuality || "NOT_CONFIGURED"))}
          ${metric("Gepland net", formatKw(panel.plan?.plannedGridImportKw), currentAction)}
        </section>
        <section class="control-grid">
          <div><span>Planentity</span><strong>${escapeHtml(config.plan_entity)}</strong></div>
          <div><span>Evaluatie</span><strong>${escapeHtml(config.interval_minutes)} min</strong></div>
          <div><span>Netlimiet</span><strong>${escapeHtml(config.peak_limit_kw)} kW</strong></div>
          <div><span>EV-doel</span><strong>${escapeHtml(config.ev_target_soc_percent)}% · ${escapeHtml(config.ev_departure_time)}</strong></div>
        </section>
        <section class="device-guidance">
          <p class="profile-disclaimer">De kaart leest vendorinstellingen niet automatisch uit. Vergelijk dit dashboardprofiel met de actuele waarden in SMA en Smappee voordat je iets wijzigt.</p>
          <article class="device-card sma">
            <div class="device-title"><div><span class="device-kicker">Batterijcontroller</span><h3>SMA batterij · aanbevolen configuratie</h3></div><span>SMA blijft eigenaar</span></div>
            <div class="setup-list">
              ${setupRow("Controller", config.sma_controller, "Geen concurrerende Home Assistant- of Modbusregeling")}
              ${setupRow("Optimalisatiedoel", config.sma_optimization_goal, "Gebruik economische optimalisatie")}
              ${setupRow("Tarief", config.sma_tariff_type, "Controleer dat kwartierprijzen zichtbaar en actueel zijn")}
              ${setupRow("Laad-SOC dynamisch", `${escapeHtml(config.sma_grid_charge_soc_percent)}%`, "SMA-documentatie vereist 0% voor dynamisch netladen")}
              ${setupRow("Injectievergoeding", `${compactPrice(config.sma_feed_in_eur_per_kwh)}/kWh`, "Conservatieve SMA-proxy; niet contractnauwkeurig")}
              ${setupRow("Forecast charging", forecastState, forecastGuidance)}
              ${setupRow("Peak shaving", "UIT", "Niet combineren zonder afzonderlijke limiet- en ownershiptest")}
            </div>
          </article>
          <article class="device-card smappee">
            <div class="device-title"><div><span class="device-kicker">EV-controller</span><h3>Smappee EV · aanbevolen configuratie</h3></div><span>Smappee blijft eigenaar</span></div>
            <div class="setup-list">
              ${setupRow("Laadmodus", String(config.smappee_mode || "smart").replace(/^./, (letter) => letter.toUpperCase()), "Smart bewaakt de lokale netbelasting")}
              ${setupRow("Netaansluiting", config.smappee_grid_connection, "Moet exact overeenkomen met de fysieke aansluiting")}
              ${setupRow("Capaciteitsdrempel", formatKw(config.smappee_capacity_threshold_kw), "Deze lokale limiet gaat vóór de hogere dashboardgrens")}
              ${setupRow("Maximale laadstroom", `${escapeHtml(config.smappee_max_current_ampere)} A`, "Niet verhogen zonder installateursvalidatie")}
              ${setupRow("Offline laden", "UIT aanbevolen", `Huidige sitefallback ${escapeHtml(config.smappee_offline_fallback_ampere)} A; alleen inschakelen na fysieke validatie`)}
              ${setupRow("Dynamische tarieven", smappeeTariffLabels[smappeeTariffStatus] || "Niet geverifieerd", "Geen primaire prijs- of schedulerbron zonder afzonderlijke vergelijking")}
              ${setupRow("Planning", "Één scheduler", "Geen gelijktijdig Kia-, Smappee- en Home Assistant-laadschema")}
              ${setupRow("Solar-modus", "Alleen bewust kiezen", "Gebruik Solar voor PV-overschot; Smart voor net- en capaciteitsbewaking")}
            </div>
          </article>
        </section>
        <section class="ownership-policy">
          <strong>Regelarchitectuur: één actieve controller per actuator</strong>
          <p>SMA bestuurt batterij/PV, Smappee bestuurt EV-laden en Home Assistant toont, vergelijkt en beheert alleen hard-geblokkeerde dry-runautomatisaties.</p>
          <ul>${warningRows}</ul>
          <code>execution_allowed = false</code>
          <p class="no-write">Geen instelling wordt vanuit deze kaart naar SMA of Smappee geschreven.</p>
        </section>
        <section class="automation-list">${automationRows || '<p class="empty">Nog geen beheerde automatisaties gevonden.</p>'}</section>
        ${message ? `<p class="control-message" role="status">${escapeHtml(message)}</p>` : ""}
        <footer class="control-actions">
          <button type="button" data-action="create">Automatisaties aanmaken/bijwerken</button>
          <button type="button" data-action="arm">Actief · gewapend geblokkeerd</button>
          <button type="button" data-action="off" class="secondary">Uitschakelen</button>
        </footer>
      </div>
    </ha-card>`;
}

export class DynamicEnergyControlConfigCard extends HTMLElementBase {
  constructor() {
    super();
    this._config = { ...DEFAULT_CONTROL_CONFIG };
    this._hass = null;
    this._message = "";
    this._busy = false;
    this._verifiedState = null;
    this._stateRequest = 0;
    this._root = this.attachShadow ? this.attachShadow({ mode: "open" }) : null;
  }

  static getConfigForm() {
    return {
      schema: [
        { name: "title", selector: { text: {} } },
        { name: "name_prefix", selector: { text: {} } },
        { name: "plan_entity", required: true, selector: { entity: {} } },
        { name: "interval_minutes", selector: { select: { options: [5, 10, 15, 30, 60] } } },
        { name: "peak_limit_kw", selector: { number: { min: 0.1, max: 30, step: 0.1, unit_of_measurement: "kW" } } },
        { name: "battery_enabled", selector: { boolean: {} } },
        { name: "battery_reserve_soc_percent", selector: { number: { min: 0, max: 100, step: 1, unit_of_measurement: "%" } } },
        { name: "ev_enabled", selector: { boolean: {} } },
        { name: "ev_target_soc_percent", selector: { number: { min: 0, max: 100, step: 1, unit_of_measurement: "%" } } },
        { name: "ev_departure_time", selector: { time: {} } },
        { name: "battery_soc_entity", selector: { entity: {} } },
        { name: "grid_power_entity", selector: { entity: {} } },
        { name: "grid_import_positive", selector: { boolean: {} } },
        { name: "ev_power_entity", selector: { entity: {} } },
        { name: "import_price_entity", selector: { entity: {} } },
        { name: "export_price_entity", selector: { entity: {} } },
        { name: "integration_price_attribute", selector: { text: {} } },
        { name: "price_stale_after_minutes", selector: { number: { min: 1, max: 180, step: 1, unit_of_measurement: "min" } } },
        { name: "data_stale_after_minutes", selector: { number: { min: 1, max: 180, step: 1, unit_of_measurement: "min" } } },
        { name: "plan_stale_after_hours", selector: { number: { min: 1, max: 72, step: 1, unit_of_measurement: "h" } } },
        { name: "sma_controller", selector: { text: {} } },
        { name: "sma_optimization_goal", selector: { text: {} } },
        { name: "sma_tariff_type", selector: { text: {} } },
        { name: "sma_forecast_charging", selector: { select: { options: ["PILOT_PENDING", "ACTIVE", "OFF"] } } },
        { name: "sma_grid_charge_soc_percent", selector: { number: { min: 0, max: 100, step: 1, unit_of_measurement: "%" } } },
        { name: "sma_feed_in_eur_per_kwh", selector: { number: { min: -2, max: 5, step: 0.001, unit_of_measurement: "EUR/kWh" } } },
        { name: "smappee_mode", selector: { select: { options: ["standard", "smart", "solar"] } } },
        { name: "smappee_grid_connection", selector: { text: {} } },
        { name: "smappee_capacity_threshold_kw", selector: { number: { min: 0.1, max: 30, step: 0.1, unit_of_measurement: "kW" } } },
        { name: "smappee_max_current_ampere", selector: { number: { min: 6, max: 32, step: 1, unit_of_measurement: "A" } } },
        { name: "smappee_offline_fallback_ampere", selector: { number: { min: 0, max: 32, step: 1, unit_of_measurement: "A" } } },
        { name: "smappee_dynamic_tariff_status", selector: { select: { options: ["NOT_VERIFIED", "DISABLED", "ENABLED_CONTEXT_ONLY"] } } },
      ],
      computeLabel: (schema) => ({
        title: "Titel",
        name_prefix: "Naamvoorvoegsel automatisaties",
        plan_entity: "Shadow-planentity",
        interval_minutes: "Evaluatie-interval",
        peak_limit_kw: "Gedeelde netimportlimiet",
        battery_enabled: "Batterijautomatisatie bouwen",
        battery_reserve_soc_percent: "Minimale batterijreserve",
        ev_enabled: "EV-automatisatie bouwen",
        ev_target_soc_percent: "Doel-SOC EV",
        ev_departure_time: "Geplande vertrektijd",
        battery_soc_entity: "Live batterij-SOC (optioneel)",
        grid_power_entity: "Live netvermogen (optioneel)",
        grid_import_positive: "Positief netvermogen betekent afname",
        ev_power_entity: "Live EV-laadvermogen (optioneel)",
        import_price_entity: "Actuele afnameprijs (optioneel)",
        export_price_entity: "Actuele injectieprijs (optioneel)",
        integration_price_attribute: "Attribuut van EPEX/Ecopower-prijsentities",
        price_stale_after_minutes: "Prijsdata verouderd na",
        data_stale_after_minutes: "Control-data verouderd na",
        plan_stale_after_hours: "Plan en prijzen verouderd na",
        sma_controller: "SMA-controller",
        sma_optimization_goal: "SMA-optimalisatiedoel",
        sma_tariff_type: "SMA-dynamisch tarief",
        sma_forecast_charging: "SMA forecast-based charging",
        sma_grid_charge_soc_percent: "SMA laad-SOC voor dynamisch netladen",
        sma_feed_in_eur_per_kwh: "SMA injectieproxy",
        smappee_mode: "Smappee laadmodus",
        smappee_grid_connection: "Smappee netaansluiting",
        smappee_capacity_threshold_kw: "Smappee capaciteitsdrempel",
        smappee_max_current_ampere: "Smappee maximale laadstroom",
        smappee_offline_fallback_ampere: "Smappee offline fallbackstroom",
        smappee_dynamic_tariff_status: "Smappee dynamische-tarievenstatus",
      })[schema.name] || schema.name,
    };
  }

  static getStubConfig() {
    return { ...DEFAULT_CONTROL_CONFIG };
  }

  static getCardSize() {
    return 6;
  }

  setConfig(config) {
    if (!isPlainObject(config)) throw new Error("Ongeldige control-kaartconfiguratie");
    this._config = { ...DEFAULT_CONTROL_CONFIG, ...config };
    this._verifiedState = null;
    this._render();
    void this._refreshState();
  }

  set hass(hass) {
    this._hass = hass;
    this._verifiedState = null;
    this._render();
    void this._refreshState();
  }

  getCardSize() {
    return 6;
  }

  async _refreshState() {
    const request = ++this._stateRequest;
    if (!this._hass) return;
    try {
      const state = await loadBlockedAutomationState(this._hass, this._config);
      if (request !== this._stateRequest) return;
      this._verifiedState = state;
    } catch (error) {
      if (request !== this._stateRequest) return;
      this._verifiedState = { mode: "CONFLICT", automations: [] };
      this._message = `Configuratieverificatie mislukt: ${error instanceof Error ? error.message : "onbekende fout"}`;
    }
    this._render();
  }

  async _handleAction(action) {
    if (this._busy) return;
    this._busy = true;
    this._message = "Bezig met gecontroleerde Home Assistant-configuratiewijziging…";
    this._render();
    try {
      const confirmAction = typeof globalThis.confirm === "function"
        ? (prompt) => globalThis.confirm(prompt)
        : () => false;
      const result = await performBlockedControlAction(
        this._hass,
        this._config,
        action,
        confirmAction,
      );
      this._message = {
        CANCELLED: "Geen wijziging uitgevoerd.",
        SAVED: "Geblokkeerde automatisaties zijn aangemaakt of bijgewerkt.",
        UPDATED: result.mode === "ARMED_BLOCKED"
          ? "Automatisaties zijn gewapend; fysieke uitvoering blijft geblokkeerd."
          : "Beheerde automatisaties zijn uitgeschakeld.",
      }[result.status] || "Wijziging verwerkt.";
    } catch (error) {
      this._message = `Niet uitgevoerd: ${error instanceof Error ? error.message : "onbekende fout"}`;
    } finally {
      this._busy = false;
      await this._refreshState();
    }
  }

  _render() {
    if (!this._root) return;
    let state;
    try {
      state = this._verifiedState || getBlockedAutomationState(this._hass, this._config);
    } catch (error) {
      state = { mode: "CONFLICT", automations: [] };
      this._message = `Configuratiefout: ${error instanceof Error ? error.message : "onbekende fout"}`;
    }
    this._root.innerHTML = `
      <style>
        :host {
          display: block;
          --dec-accent: var(--primary-color, #315b4c);
          --dec-accent-soft: color-mix(in srgb, var(--dec-accent) 12%, var(--card-background-color, #fff));
          --dec-ink: var(--primary-text-color, #1b211f);
          --dec-muted: var(--secondary-text-color, #66706c);
          --dec-border: var(--divider-color, #d9dfdc);
          --dec-surface: var(--card-background-color, #fff);
          --dec-good: #2d7654;
          --dec-warn: #a86512;
          --dec-bad: #a53c3c;
          color: var(--dec-ink);
          font-family: var(--paper-font-body1_-_font-family, var(--ha-font-family-body, system-ui, sans-serif));
        }
        ha-card { overflow: hidden; border: 1px solid var(--dec-border); }
        .control-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; padding: 20px 22px 17px; background: var(--dec-accent-soft); border-bottom: 1px solid var(--dec-border); }
        .eyebrow { display: block; margin-bottom: 4px; color: var(--dec-muted); font-size: 11px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
        h2 { margin: 0; font-size: 21px; line-height: 1.2; font-weight: 650; }
        .control-status { flex: 0 0 auto; padding: 6px 9px; border: 1px solid currentColor; border-radius: 999px; color: var(--dec-warn); font-size: 11px; font-weight: 750; letter-spacing: .04em; text-transform: uppercase; }
        .control-status.armed_blocked { color: var(--dec-good); }
        .control-status.conflict { color: var(--dec-bad); }
        .safety-lock { display: grid; grid-template-columns: auto auto; align-items: center; gap: 5px 12px; padding: 16px 20px; border-bottom: 1px solid var(--dec-border); }
        .safety-lock strong { font-size: 14px; }
        .safety-lock code { justify-self: end; font-size: 12px; }
        .safety-lock.verified strong, .safety-lock.verified code { color: var(--dec-good); }
        .safety-lock.unverified strong, .safety-lock.unverified code { color: var(--dec-warn); }
        .safety-lock.conflict strong, .safety-lock.conflict code { color: var(--dec-bad); }
        .safety-lock p { grid-column: 1 / -1; margin: 0; color: var(--dec-muted); font-size: 12px; line-height: 1.5; }
        .control-overview { padding: 20px; border-bottom: 1px solid var(--dec-border); }
        .section-heading, .device-title, .source-line { display: flex; align-items: flex-start; justify-content: space-between; gap: 14px; }
        h3 { margin: 0; font-size: 16px; line-height: 1.25; }
        .readiness, .device-title > span { flex: 0 0 auto; padding: 5px 8px; border: 1px solid currentColor; border-radius: 999px; color: var(--dec-warn); font-size: 10px; font-weight: 750; letter-spacing: .04em; text-transform: uppercase; }
        .readiness.shadow_ready, .readiness.shadow_ready_live_degraded { color: var(--dec-good); }
        .strategy-grid, .live-context { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); margin-top: 14px; border: 1px solid var(--dec-border); border-radius: 9px; overflow: hidden; }
        .strategy-grid .metric, .live-context .metric { min-width: 0; padding: 13px 14px; border-right: 1px solid var(--dec-border); }
        .strategy-grid .metric:last-child, .live-context .metric:last-child { border-right: 0; }
        .strategy-grid .metric span, .live-context .metric span { display: block; color: var(--dec-muted); font-size: 10px; }
        .strategy-grid .metric strong, .live-context .metric strong { display: block; margin-top: 5px; font-size: 16px; overflow-wrap: anywhere; }
        .strategy-grid .metric small, .live-context .metric small { display: block; margin-top: 4px; color: var(--dec-muted); font-size: 10px; overflow-wrap: anywhere; }
        .source-line { margin-top: 10px; color: var(--dec-muted); font-size: 10px; }
        .live-context { margin: 0; border-width: 0 0 1px; border-radius: 0; }
        .control-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); border-bottom: 1px solid var(--dec-border); }
        .control-grid div { min-width: 0; padding: 14px 16px; border-right: 1px solid var(--dec-border); }
        .control-grid div:last-child { border-right: 0; }
        .control-grid span, .automation-row small { display: block; color: var(--dec-muted); font-size: 10px; }
        .control-grid strong { display: block; margin-top: 5px; overflow: hidden; font-family: var(--ha-font-family-code, ui-monospace, monospace); font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
        .device-guidance { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; padding: 20px; border-bottom: 1px solid var(--dec-border); background: color-mix(in srgb, var(--dec-surface) 94%, var(--dec-accent)); }
        .profile-disclaimer { grid-column: 1 / -1; margin: 0; padding: 11px 13px; border-left: 3px solid var(--dec-warn); background: color-mix(in srgb, var(--dec-warn) 8%, var(--dec-surface)); color: var(--dec-muted); font-size: 11px; line-height: 1.5; }
        .device-card { min-width: 0; border: 1px solid var(--dec-border); border-radius: 10px; background: var(--dec-surface); overflow: hidden; }
        .device-title { padding: 15px 16px; background: var(--dec-accent-soft); border-bottom: 1px solid var(--dec-border); }
        .device-title > span { color: var(--dec-good); }
        .device-kicker { display: block; margin-bottom: 4px; color: var(--dec-muted); font-size: 9px; font-weight: 750; letter-spacing: .08em; text-transform: uppercase; }
        .setup-list { display: grid; }
        .setup-row { display: grid; grid-template-columns: minmax(0, .8fr) auto minmax(0, 1.2fr); gap: 4px 10px; padding: 11px 14px; border-bottom: 1px solid var(--dec-border); }
        .setup-row:last-child { border-bottom: 0; }
        .setup-row span { color: var(--dec-muted); font-size: 10px; }
        .setup-row em { justify-self: end; color: var(--dec-warn); font-size: 8px; font-style: normal; font-weight: 750; letter-spacing: .05em; text-transform: uppercase; }
        .setup-row strong { grid-column: 3; min-width: 0; font-size: 12px; overflow-wrap: anywhere; }
        .setup-row small { grid-column: 3; color: var(--dec-muted); font-size: 10px; line-height: 1.4; }
        .ownership-policy { padding: 18px 20px; border-bottom: 1px solid var(--dec-border); background: color-mix(in srgb, var(--dec-warn) 8%, var(--dec-surface)); }
        .ownership-policy > strong { font-size: 14px; }
        .ownership-policy p, .ownership-policy li { color: var(--dec-muted); font-size: 11px; line-height: 1.5; }
        .ownership-policy ul { margin: 10px 0; padding-left: 18px; }
        .ownership-policy code { color: var(--dec-good); font-size: 11px; }
        .ownership-policy .no-write { margin-bottom: 0; color: var(--dec-good); font-weight: 700; }
        .automation-list { display: grid; gap: 1px; padding: 18px 20px; background: var(--dec-border); }
        .automation-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 12px; background: var(--dec-surface); }
        .automation-row strong { font-family: var(--ha-font-family-code, ui-monospace, monospace); font-size: 12px; }
        .automation-state { color: var(--dec-muted); font-family: var(--ha-font-family-code, ui-monospace, monospace); font-size: 11px; text-transform: uppercase; }
        .empty { margin: 0; padding: 12px; background: var(--dec-surface); color: var(--dec-muted); font-size: 12px; }
        .control-message { margin: 0; padding: 12px 20px; border-top: 1px solid var(--dec-border); color: var(--dec-muted); font-size: 12px; }
        .control-actions { display: flex; flex-wrap: wrap; gap: 9px; padding: 16px 20px; border-top: 1px solid var(--dec-border); }
        button { min-height: 44px; padding: 0 14px; border: 1px solid var(--dec-accent); border-radius: 7px; background: var(--dec-accent); color: var(--text-primary-color, #fff); font: inherit; font-size: 12px; font-weight: 700; cursor: pointer; }
        button.secondary { background: transparent; color: var(--dec-ink); border-color: var(--dec-border); }
        button:focus-visible { outline: 3px solid color-mix(in srgb, var(--dec-accent) 35%, transparent); outline-offset: 2px; }
        button:disabled { cursor: wait; opacity: .55; }
        @media (max-width: 700px) {
          .control-header { flex-direction: column; padding: 17px 16px 14px; }
          .control-status { align-self: flex-start; }
          .section-heading, .device-title, .source-line { flex-direction: column; }
          .readiness, .device-title > span { align-self: flex-start; }
          .strategy-grid, .live-context { grid-template-columns: repeat(2, minmax(0, 1fr)); }
          .strategy-grid .metric:nth-child(2), .live-context .metric:nth-child(2) { border-right: 0; }
          .strategy-grid .metric:nth-child(-n+2), .live-context .metric:nth-child(-n+2) { border-bottom: 1px solid var(--dec-border); }
          .device-guidance { grid-template-columns: 1fr; padding: 14px; }
          .control-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
          .control-grid div:nth-child(2) { border-right: 0; }
          .control-grid div:nth-child(-n+2) { border-bottom: 1px solid var(--dec-border); }
          .control-actions { flex-direction: column; }
          button { width: 100%; }
        }
        @media (max-width: 430px) {
          .control-overview, .ownership-policy { padding: 15px; }
          .setup-row { grid-template-columns: 1fr auto; }
          .setup-row strong, .setup-row small { grid-column: 1 / -1; }
        }
      </style>
      ${renderBlockedControlConfig(
        this._config,
        state,
        this._message,
        buildControlPanelSnapshot(this._hass, this._config),
      )}`;
    this._root.querySelectorAll("button[data-action]").forEach((button) => {
      button.disabled = this._busy;
      button.addEventListener("click", () => this._handleAction(button.dataset.action));
    });
  }
}

if (globalThis.customElements && !globalThis.customElements.get(CARD_TAG)) {
  globalThis.customElements.define("dynamic-energy-shadow-card", DynamicEnergyShadowCard);
}

if (globalThis.customElements && !globalThis.customElements.get(CONTROL_CARD_TAG)) {
  globalThis.customElements.define("dynamic-energy-control-config-card", DynamicEnergyControlConfigCard);
}

if (globalThis.customElements && !globalThis.customElements.get(VALIDATION_CARD_TAG)) {
  globalThis.customElements.define("dynamic-energy-validation-card", DynamicEnergyValidationCard);
}

if (globalThis.window) {
  globalThis.window.customCards = globalThis.window.customCards || [];
  if (!globalThis.window.customCards.some((card) => card.type === CARD_TAG)) {
    globalThis.window.customCards.push({
      type: "dynamic-energy-shadow-card",
      name: "Dynamic Energy Shadow Dashboard",
      description: "Read-only live energie- en shadow-planmonitor met visuele configuratie.",
      preview: true,
      documentationURL: "https://github.com/ju1ced/dynamic-energy-dashboard",
    });
  }
  if (!globalThis.window.customCards.some((card) => card.type === CONTROL_CARD_TAG)) {
    globalThis.window.customCards.push({
      type: "dynamic-energy-control-config-card",
      name: "Dynamic Energy Control Config",
      description: "Beheert uitsluitend namespaced ARMED_BLOCKED-automatisaties; geen actuatorwrites.",
      preview: true,
      documentationURL: "https://github.com/ju1ced/dynamic-energy-dashboard",
    });
  }
  if (!globalThis.window.customCards.some((card) => card.type === VALIDATION_CARD_TAG)) {
    globalThis.window.customCards.push({
      type: "dynamic-energy-validation-card",
      name: "Dynamic Energy Validation",
      description: "Read-only vergelijking van shadow-plan, werkelijk gedrag en gedeelde netruimte.",
      preview: true,
      documentationURL: "https://github.com/ju1ced/dynamic-energy-dashboard",
    });
  }
}
