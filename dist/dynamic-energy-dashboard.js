const CARD_TAG = "dynamic-energy-shadow-card";
const DEFAULT_CONFIG = Object.freeze({
  title: "Shadow-sturing",
  plan_attribute: "schedule",
  price_attribute: "prices",
  integration_price_attribute: "data",
  price_reference_eur_per_kwh: 0.277,
  peak_limit_kw: 7,
  stale_after_minutes: 10,
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

const HTMLElementBase = globalThis.HTMLElement || class {};

export function finiteNumber(value) {
  if (value === null || value === undefined || value === "") return null;
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  if (typeof value !== "string") return null;
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

export function readEntity(hass, entityId, now = new Date(), staleMinutes = 10) {
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
  const timestamp = firstExternalValue(stateObject, ["last_updated", "last_changed"]);
  const updatedMs = externalDateMs(timestamp);
  const nowMs = now instanceof Date ? now.getTime() : NaN;
  const ageMinutes = (nowMs - updatedMs) / 60000;
  const validTimestamp = Number.isFinite(updatedMs) && Number.isFinite(ageMinutes);
  const quality = !validTimestamp ? "INVALID" : ageMinutes > staleMinutes ? "STALE" : "GOOD";
  const friendlyName = safeValue(safeAttributes(stateObject), "friendly_name");
  return {
    entityId,
    stateObject,
    value: finiteNumber(rawStateValue),
    quality,
    ageMinutes: validTimestamp ? Math.max(0, ageMinutes) : null,
    name: typeof friendlyName === "string" ? friendlyName : entityId,
  };
}

function readPower(hass, entityId, now, staleMinutes, positive = true) {
  const reading = readEntity(hass, entityId, now, staleMinutes);
  const normalised = toKilowatts(reading.stateObject);
  const quality = normalised === null && ["GOOD", "STALE"].includes(reading.quality)
    ? "INVALID"
    : reading.quality;
  return { ...reading, quality, value: normalised === null ? null : normalised * (positive ? 1 : -1) };
}

function readPercentage(hass, entityId, now, staleMinutes) {
  const reading = readEntity(hass, entityId, now, staleMinutes);
  const quality = reading.value === null && ["GOOD", "STALE"].includes(reading.quality)
    ? "INVALID"
    : reading.quality;
  return { ...reading, quality, value: reading.value === null ? null : Math.min(100, Math.max(0, reading.value)) };
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

export function getUpcomingPriceIntervals(planState, attributeName = "prices", now = new Date()) {
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
    .filter((row) => row.endMs > nowMs)
    .map(({ startMs, endMs, ...row }) => row);
}

export function getEntityPriceIntervals(
  importState,
  exportState = null,
  attributeName = "data",
  now = new Date(),
) {
  const importRows = safeValue(safeAttributes(importState), attributeName);
  if (!Array.isArray(importRows)) return [];
  const candidateExportRows = safeValue(safeAttributes(exportState), attributeName);
  const exportRows = Array.isArray(candidateExportRows) ? candidateExportRows : [];

  const parseIntegrationRows = (rows) => {
    const parsed = [];
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
      parsed.push({ startMs, endMs, price });
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
    .filter((row) => row.endMs > nowMs)
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
  const importPrice = readPrice(hass, config.import_price_entity, now, staleMinutes);
  const exportPrice = readPrice(hass, config.export_price_entity, now, staleMinutes);

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
  const planPriceIntervals = planIsFresh
    ? getUpcomingPriceIntervals(
      planReading.stateObject,
      config.price_attribute || "prices",
      now,
    )
    : [];
  const entityPriceIntervals = importPrice.quality === "GOOD"
    ? getEntityPriceIntervals(
      importPrice.stateObject,
      exportPrice.quality === "GOOD" ? exportPrice.stateObject : null,
      config.integration_price_attribute || DEFAULT_CONFIG.integration_price_attribute,
      now,
    )
    : [];
  const nowMs = now.getTime();
  const shadowCoverage = intervalCoverageMs(planPriceIntervals, nowMs);
  const integrationCoverage = intervalCoverageMs(entityPriceIntervals, nowMs);
  const hasIntegrationSource = importPrice.quality === "GOOD"
    && (entityPriceIntervals.length > 0 || importPrice.value !== null);
  const selectedPriceSource = hasIntegrationSource && integrationCoverage > shadowCoverage
    ? "integration"
    : planPriceIntervals.length > 0 ? "shadow" : hasIntegrationSource ? "integration" : null;
  const priceIntervals = selectedPriceSource === "shadow" ? planPriceIntervals
    : selectedPriceSource === "integration" ? entityPriceIntervals : [];
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
  return `<section class="price-timeline"><div class="section-title"><h3>Komende kwartierprijzen</h3><small>${metadata}</small></div><div class="price-scroll"><div class="price-quarters">${rows}</div></div></section>`;
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
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 8;
  }

  _render() {
    if (!this._root) return;
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
        .price-scroll { max-width: 100%; overflow-x: auto; padding-bottom: 5px; scrollbar-width: thin; }
        .price-quarters { display: grid; grid-auto-flow: column; grid-auto-columns: minmax(118px, 1fr); gap: 7px; min-width: max-content; }
        .price-quarter { display: grid; gap: 5px; padding: 10px; border: 1px solid var(--des-border); border-top: 4px solid var(--des-muted); border-radius: 8px; background: var(--des-surface); }
        .price-quarter.cheap { border-top-color: var(--des-good); }
        .price-quarter.expensive { border-top-color: var(--des-bad); }
        .price-quarter time, .price-quarter small { color: var(--des-muted); font-size: 10px; }
        .price-quarter strong { font-family: var(--ha-font-family-code, ui-monospace, monospace); font-size: 16px; }
        .price-quarter span { color: var(--des-accent); font-size: 10px; font-weight: 700; }
        .price-empty { margin: 0; color: var(--des-muted); font-size: 12px; }
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
  }
}

if (globalThis.customElements && !globalThis.customElements.get(CARD_TAG)) {
  globalThis.customElements.define("dynamic-energy-shadow-card", DynamicEnergyShadowCard);
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
}
