const CARD_TAG = "dynamic-energy-shadow-card";
const DEFAULT_CONFIG = Object.freeze({
  title: "Shadow-sturing",
  plan_attribute: "schedule",
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
  const parsed = Number(String(value).replace(",", "."));
  return Number.isFinite(parsed) ? parsed : null;
}

export function toKilowatts(stateObject) {
  if (!stateObject) return null;
  const value = finiteNumber(stateObject.state);
  if (value === null) return null;
  const unit = String(stateObject.attributes?.unit_of_measurement || "").trim();
  if (["W", "watt", "watts"].includes(unit)) return value / 1000;
  if (["MW", "megawatt", "megawatts"].includes(unit)) return value * 1000;
  return value;
}

export function toEuroPerKwh(stateObject) {
  if (!stateObject) return null;
  const value = finiteNumber(stateObject.state);
  if (value === null) return null;
  const unit = String(stateObject.attributes?.unit_of_measurement || "")
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
  const stateObject = hass?.states?.[entityId];
  if (!stateObject) {
    return { entityId, stateObject: null, value: null, quality: "MISSING" };
  }
  const rawState = String(stateObject.state ?? "").toLowerCase();
  if (["unknown", "unavailable", "none", "null", ""].includes(rawState)) {
    return { entityId, stateObject, value: null, quality: "UNAVAILABLE" };
  }
  const updatedAt = new Date(stateObject.last_updated || stateObject.last_changed || 0);
  const ageMinutes = (now.getTime() - updatedAt.getTime()) / 60000;
  const quality = Number.isFinite(ageMinutes) && ageMinutes > staleMinutes ? "STALE" : "GOOD";
  return {
    entityId,
    stateObject,
    value: finiteNumber(stateObject.state),
    quality,
    ageMinutes: Number.isFinite(ageMinutes) ? Math.max(0, ageMinutes) : null,
    name: stateObject.attributes?.friendly_name || entityId,
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
  const schedule = planState.attributes?.[attributeName];
  if (!Array.isArray(schedule)) return null;
  const nowMs = now.getTime();
  return schedule.find((row) => {
    const startMs = Date.parse(row.start_utc || row.start || row.start_local || "");
    if (!Number.isFinite(startMs)) return false;
    const endMs = row.end_utc
      ? Date.parse(row.end_utc)
      : startMs + finiteNumber(row.duration_hours || 0.25) * 3600000;
    return Number.isFinite(endMs) && startMs <= nowMs && nowMs < endMs;
  }) || null;
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
  const planInterval = getCurrentPlanInterval(
    planReading.stateObject,
    config.plan_attribute || DEFAULT_CONFIG.plan_attribute,
    now,
  );
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
  } else if (["MISSING", "UNAVAILABLE", "STALE"].includes(planReading.quality)) {
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
      importPriceEurPerKwh: importPrice.value,
      exportPriceEurPerKwh: exportPrice.value,
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
      plannedGridImportKw,
      gridDeviationKw,
    },
    quality: {
      requiredMissing,
      live: liveQuality,
      optional: optionalQuality,
    },
  };
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatKw(value) {
  return value === null ? "—" : `${new Intl.NumberFormat("nl-BE", { maximumFractionDigits: 2 }).format(value)} kW`;
}

function formatPercent(value) {
  return value === null ? "—" : `${new Intl.NumberFormat("nl-BE", { maximumFractionDigits: 1 }).format(value)}%`;
}

function formatPrice(value) {
  return value === null
    ? "—"
    : new Intl.NumberFormat("nl-BE", { style: "currency", currency: "EUR", minimumFractionDigits: 3 }).format(value);
}

function actionLabel(action) {
  return ACTION_LABELS[action] || action || "Geen actueel plan";
}

function actionTone(action) {
  if (["CHARGE_FROM_GRID", "STORE_PV_SURPLUS"].includes(action)) return "charge";
  if (action === "DISCHARGE_TO_LOAD") return "discharge";
  return "hold";
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
