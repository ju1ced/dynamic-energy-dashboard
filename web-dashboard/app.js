"use strict";

import { currentDayAheadView } from "./day-ahead-view.js";
import { buildDayCourseQuery, DEFAULT_EV_ASSUMPTIONS, renderDayCourse } from "./day-course-view.js";
import {
  ACTIVATION_CAPABILITY,
  createAutomationDraft,
  requestOperatingMode,
  serializeAutomationBundle,
  validateAutomationDraft,
} from "./control-config.js";

const state = {
  data: null,
  dayAhead: null,
  view: "overview",
  operatingMode: "monitor",
  modeMessage: "",
  automations: [],
  selectedAutomationId: null,
  dayCourse: { key: null, status: "idle", course: null, error: null },
  evAssumptions: { ...DEFAULT_EV_ASSUMPTIONS },
};
const viewNames = {
  overview: "Overzicht",
  financial: "Financieel",
  prices: "Prijzen",
  energy: "Energie",
  quality: "Datakwaliteit",
  battery: "Batterij",
  multiyear: "Meerjarig",
  scenarios: "Scenario's",
  steering: "Sturing",
  decisions: "Beslissingen",
  configuration: "Configuratie",
  daycourse: "Dagverloop",
};

const euro = new Intl.NumberFormat("nl-BE", { style: "currency", currency: "EUR", minimumFractionDigits: 2 });
const number = new Intl.NumberFormat("nl-BE", { maximumFractionDigits: 3 });
const percent = new Intl.NumberFormat("nl-BE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const monthFormat = new Intl.DateTimeFormat("nl-BE", { month: "short", year: "2-digit", timeZone: "Europe/Brussels" });
const dateTimeFormat = new Intl.DateTimeFormat("nl-BE", { dateStyle: "medium", timeStyle: "short", timeZone: "Europe/Brussels" });
const timeFormat = new Intl.DateTimeFormat("nl-BE", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Brussels" });
const euroPerKwh = new Intl.NumberFormat("nl-BE", { style: "currency", currency: "EUR", minimumFractionDigits: 4, maximumFractionDigits: 4 });

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, character => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
  })[character]);
}

function formatMonth(value) {
  return monthFormat.format(new Date(`${value}-01T12:00:00Z`)).replace(".", "");
}

function signedEuro(value) {
  const formatted = euro.format(Math.abs(value));
  return `${value > 0 ? "+" : value < 0 ? "−" : ""}${formatted}`;
}

function metric(label, value, detail, className = "") {
  return `<div class="metric"><span class="metric-label">${escapeHtml(label)}</span><strong class="metric-value ${className}">${escapeHtml(value)}</strong><span class="metric-detail">${escapeHtml(detail)}</span></div>`;
}

function lineChart(rows, valueKey, options = {}) {
  if (!rows.length) return `<div class="error-state">Geen detailreeks beschikbaar.</div>`;
  const width = 720;
  const height = 200;
  const pad = { top: 14, right: 10, bottom: 28, left: 42 };
  const values = rows.map(row => Number(row[valueKey]));
  let min = Math.min(...values, options.includeZero ? 0 : Infinity);
  let max = Math.max(...values, options.includeZero ? 0 : -Infinity);
  if (min === max) { min -= 1; max += 1; }
  const x = index => pad.left + (index / Math.max(rows.length - 1, 1)) * (width - pad.left - pad.right);
  const y = value => pad.top + ((max - value) / (max - min)) * (height - pad.top - pad.bottom);
  const points = values.map((value, index) => `${x(index).toFixed(1)},${y(value).toFixed(1)}`).join(" ");
  const area = `${pad.left},${height - pad.bottom} ${points} ${x(rows.length - 1)},${height - pad.bottom}`;
  const grid = [0, .25, .5, .75, 1].map(ratio => {
    const gy = pad.top + ratio * (height - pad.top - pad.bottom);
    const label = max - ratio * (max - min);
    return `<line class="chart-grid" x1="${pad.left}" y1="${gy}" x2="${width - pad.right}" y2="${gy}"/><text class="chart-axis" x="2" y="${gy + 3}">${escapeHtml(options.tick ? options.tick(label) : label.toFixed(0))}</text>`;
  }).join("");
  const zero = min < 0 && max > 0 ? `<line class="chart-zero" x1="${pad.left}" y1="${y(0)}" x2="${width - pad.right}" y2="${y(0)}"/>` : "";
  const lastX = x(rows.length - 1);
  const lastY = y(values[values.length - 1]);
  const endpoint = options.endpoint
    ? `<circle class="chart-dot" cx="${lastX}" cy="${lastY}" r="3.5"/><text class="chart-endpoint" text-anchor="end" x="${lastX - 7}" y="${Math.max(12, lastY - 8)}">${escapeHtml(options.endpoint(values[values.length - 1]))}</text>`
    : "";
  const labels = rows.map((row, index) => {
    if (index !== 0 && index !== rows.length - 1 && index % Math.ceil(rows.length / 6) !== 0) return "";
    const label = options.label ? options.label(row) : row.month || row.date;
    return `<text class="chart-axis" text-anchor="middle" x="${x(index)}" y="${height - 8}">${escapeHtml(label)}</text>`;
  }).join("");
  return `<div class="chart"><svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(options.aria || "Lijngrafiek")}">${grid}${zero}<polygon class="chart-area" points="${area}"/><polyline class="chart-line" points="${points}"/>${endpoint}${labels}</svg></div>`;
}

function barChart(rows, valueKey, options = {}) {
  if (!rows.length) return `<div class="error-state">Geen detailreeks beschikbaar.</div>`;
  const width = 720;
  const height = 200;
  const pad = { top: 14, right: 10, bottom: 28, left: 42 };
  const values = rows.map(row => Number(row[valueKey]));
  const min = Math.min(0, ...values);
  const max = Math.max(0, ...values);
  const range = max - min || 1;
  const innerWidth = width - pad.left - pad.right;
  const barWidth = Math.max(5, innerWidth / rows.length - 6);
  const y = value => pad.top + ((max - value) / range) * (height - pad.top - pad.bottom);
  const zeroY = y(0);
  const bars = rows.map((row, index) => {
    const value = Number(row[valueKey]);
    const bx = pad.left + (index + .5) * innerWidth / rows.length - barWidth / 2;
    const by = value >= 0 ? y(value) : zeroY;
    const bh = Math.max(1, Math.abs(y(value) - zeroY));
    const klass = value > 0 ? "chart-bar-warning" : "chart-bar-negative";
    return `<rect class="${klass}" x="${bx}" y="${by}" width="${barWidth}" height="${bh}" rx="2"><title>${escapeHtml(row.month || row.date)}: ${escapeHtml(value.toFixed(2))}</title></rect>`;
  }).join("");
  const labels = rows.map((row, index) => `<text class="chart-axis" text-anchor="middle" x="${pad.left + (index + .5) * innerWidth / rows.length}" y="${height - 8}">${escapeHtml(options.label ? options.label(row) : row.month)}</text>`).join("");
  return `<div class="chart"><svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(options.aria || "Staafgrafiek")}"><line class="chart-zero" x1="${pad.left}" y1="${zeroY}" x2="${width - pad.right}" y2="${zeroY}"/>${bars}${labels}</svg></div>`;
}

function priceComparisonChart(rows, reference) {
  if (!rows.length) return `<div class="error-state">Nog geen toekomstige Day-Ahead-kwartieren gepubliceerd.</div>`;
  const width = 720;
  const height = 230;
  const pad = { top: 14, right: 10, bottom: 34, left: 50 };
  const values = rows.map(row => Number(row.ecopower_import_eur_per_kwh_incl_vat));
  const min = Math.min(0, reference, ...values);
  const max = Math.max(reference, ...values);
  const range = max - min || 1;
  const x = index => pad.left + (index / Math.max(rows.length - 1, 1)) * (width - pad.left - pad.right);
  const y = value => pad.top + ((max - value) / range) * (height - pad.top - pad.bottom);
  const points = values.map((value, index) => `${x(index).toFixed(1)},${y(value).toFixed(1)}`).join(" ");
  const grid = [0, .25, .5, .75, 1].map(ratio => {
    const gy = pad.top + ratio * (height - pad.top - pad.bottom);
    const label = max - ratio * range;
    return `<line class="chart-grid" x1="${pad.left}" y1="${gy}" x2="${width - pad.right}" y2="${gy}"/><text class="chart-axis" x="2" y="${gy + 3}">€${label.toFixed(2)}</text>`;
  }).join("");
  const labels = rows.map((row, index) => {
    if (index !== 0 && index !== rows.length - 1 && index % Math.ceil(rows.length / 8) !== 0) return "";
    return `<text class="chart-axis" text-anchor="middle" x="${x(index)}" y="${height - 9}">${escapeHtml(timeFormat.format(new Date(row.start_local)))}</text>`;
  }).join("");
  const referenceY = y(reference);
  return `<div class="chart price-chart"><svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Ecopower Day-Ahead-prijs per kwartier tegenover de referentieprijs">${grid}<line class="chart-reference" x1="${pad.left}" y1="${referenceY}" x2="${width - pad.right}" y2="${referenceY}"/><text class="chart-reference-label" text-anchor="end" x="${width - pad.right}" y="${Math.max(11, referenceY - 6)}">referentie €0,2770/kWh</text><polyline class="chart-line" points="${points}"/>${labels}</svg></div>`;
}

function priceAggregateTable(rows, label) {
  const visible = rows.slice(-12).reverse();
  if (!visible.length) return `<div class="error-state">Geen ${escapeHtml(label.toLowerCase())} beschikbaar.</div>`;
  return `<div class="table-wrap"><table class="financial-table"><thead><tr><th>Periode</th><th>Ecopower gem.</th><th>Referentie</th><th>Verschil</th><th>Dekking</th></tr></thead><tbody>${visible.map(row => `<tr><td data-label="Periode">${escapeHtml(row.period)}</td><td data-label="Ecopower gem.">${euroPerKwh.format(row.average_eur_per_kwh_incl_vat)}/kWh</td><td data-label="Referentie">€0,2770/kWh</td><td data-label="Verschil" class="${row.difference_vs_reference_eur_per_kwh > 0 ? "positive" : "negative"}">${row.difference_vs_reference_eur_per_kwh > 0 ? "+" : ""}${euroPerKwh.format(row.difference_vs_reference_eur_per_kwh)}/kWh</td><td data-label="Dekking">${row.partial_period ? "gedeeltelijk" : "volledig"}</td></tr>`).join("")}</tbody></table></div>`;
}

function renderOverview(data) {
  const summary = data.summary;
  const recent = data.recent_energy.series;
  const maxRecent = Math.max(...Object.values(recent).map(item => item.total_kwh));
  const labels = {
    grid_import: "Netafname", grid_export: "Netinjectie", pv_generation: "PV-productie",
    battery_charge: "Batterij laden", battery_discharge: "Batterij ontladen", ev_charge: "EV-laden",
  };
  return `
    <div class="section-intro"><div><h3>Wat zegt het eerste volledige prijsjaar?</h3><p>Historische factuur versus een retrospectief dynamisch tarief, met exact dezelfde fysieke energiestromen.</p></div><span class="classification">${escapeHtml(data.classification)}</span></div>
    <div class="metric-strip">
      ${metric("Historische factuur", euro.format(summary.historical_total_eur_incl_vat), "inclusief 6% btw")}
      ${metric("Dynamische backtest", euro.format(summary.dynamic_total_eur_incl_vat), "ongewijzigd gedrag")}
      ${metric("Verschil", signedEuro(summary.difference_eur_incl_vat), `${signedEuro(summary.difference_percentage)}%`, "good")}
      ${metric("Prijsdekking", `${number.format(data.quality.price_interval_count)}/${number.format(data.quality.energy_interval_count)}`, "geen ontbrekende prijzen")}
    </div>
    <div class="content-grid">
      <section class="panel"><div class="panel-header"><h4>Cumulatief leveranciersverschil</h4><small>EUR EXCL. BTW · LAGER IS BETER</small></div>${lineChart(data.monthly, "cumulative_difference_eur_excl_vat", { includeZero: true, label: row => formatMonth(row.month), tick: value => `€${value.toFixed(0)}`, endpoint: value => signedEuro(value), aria: "Cumulatief verschil per maand" })}<div class="legend"><span>Dynamisch minus historisch</span><span class="secondary">nulreferentie</span></div></section>
      <section class="panel"><div class="panel-header"><h4>Recente energiestromen</h4><small>48 UUR · HA EXPORT</small></div><div class="bar-list">${Object.entries(recent).map(([key, item], index) => `<div class="bar-item"><div class="bar-label"><span>${escapeHtml(labels[key])}</span><strong>${number.format(item.total_kwh)} kWh</strong></div><div class="bar-track"><div class="bar-fill ${index === 2 ? "light" : index === 5 ? "blue" : ""}" style="width:${Math.max(2, item.total_kwh / maxRecent * 100)}%"></div></div></div>`).join("")}</div></section>
      <section class="panel full"><div class="panel-header"><h4>Kernconclusies</h4><small>AUDITABLE</small></div><div class="decision-list">${data.decision_log.entries.slice(0, 3).map(decisionCard).join("")}</div></section>
    </div>`;
}

function renderFinancial(data) {
  const summary = data.summary;
  return `
    <div class="section-intro"><div><h3>Shadow billing</h3><p>Alleen de contractafhankelijke leverancierscomponent werd vervangen; netkosten, heffingen en belastingen blijven gelijk aan de gevalideerde factuur.</p></div><span class="classification">RETROSPECTIEF</span></div>
    <div class="comparison">
      <div class="comparison-card"><small>Historisch · Groene Burgerstroom</small><strong>${euro.format(summary.historical_total_eur_incl_vat)}</strong><p>Leverancierscomponent excl. btw: ${euro.format(summary.historical_supplier_eur_excl_vat)}</p></div>
      <div class="comparison-card recommended"><small>Scenario A · Dynamisch</small><strong>${euro.format(summary.dynamic_total_eur_incl_vat)}</strong><p>${euro.format(Math.abs(summary.difference_eur_incl_vat))} lager in deze backtest; geen contractadvies.</p></div>
    </div>
    <div class="content-grid" style="margin-top:12px">
      <section class="panel full"><div class="panel-header"><h4>Maandelijks leveranciersverschil</h4><small>POSITIEF = DYNAMISCH DUURDER</small></div>${barChart(data.monthly, "difference_eur_excl_vat", { label: row => formatMonth(row.month).split(" ")[0], aria: "Maandelijks financieel verschil" })}</section>
      <section class="panel full"><div class="panel-header"><h4>Maanddetail</h4><small>EXCL. BTW</small></div><div class="table-wrap"><table class="financial-table"><thead><tr><th>Maand</th><th>Afname</th><th>Injectie</th><th>Historisch</th><th>Dynamisch</th><th>Verschil</th></tr></thead><tbody>${data.monthly.map(row => `<tr><td data-label="Maand">${escapeHtml(formatMonth(row.month))}</td><td data-label="Afname">${row.import_kwh == null ? "—" : `${number.format(row.import_kwh)} kWh`}</td><td data-label="Injectie">${row.export_kwh == null ? "—" : `${number.format(row.export_kwh)} kWh`}</td><td data-label="Historisch">${row.historical_supplier_eur_excl_vat == null ? "—" : euro.format(row.historical_supplier_eur_excl_vat)}</td><td data-label="Dynamisch">${row.dynamic_supplier_eur_excl_vat == null ? "—" : euro.format(row.dynamic_supplier_eur_excl_vat)}</td><td data-label="Verschil" class="${row.difference_eur_excl_vat > 0 ? "positive" : "negative"}">${signedEuro(row.difference_eur_excl_vat)}</td></tr>`).join("")}</tbody></table></div></section>
    </div>`;
}

function renderPrices(data, live) {
  const prices = data.prices;
  if (!live) {
    return `<div class="section-intro"><div><h3>Belgische Day-Ahead-prijzen</h3><p>De actuele prijsfeed is niet beschikbaar. Historische validatie blijft hieronder zichtbaar.</p></div><span class="classification">PRICE FEED UNAVAILABLE</span></div><div class="error-state">Voer <code>python3 scripts/build_current_day_ahead_prices.py --fetch</code> uit.</div><div class="content-grid" style="margin-top:12px"><section class="panel full"><div class="panel-header"><h4>Historische gemiddelde marktprijs per maand</h4><small>EUR / MWH</small></div>${lineChart(prices.monthly, "average_eur_per_mwh", { includeZero: true, label: row => formatMonth(row.month), tick: value => value.toFixed(0), aria: "Gemiddelde marktprijs per maand" })}</section></div>`;
  }
  const upcoming = live.upcoming_intervals;
  const currentDay = live.quality.stale ? null : live.aggregates.daily.find(row => row.period === upcoming[0]?.start_local.slice(0, 10));
  const minimum = upcoming.length ? Math.min(...upcoming.map(row => row.ecopower_import_eur_per_kwh_incl_vat)) : null;
  const maximum = upcoming.length ? Math.max(...upcoming.map(row => row.ecopower_import_eur_per_kwh_incl_vat)) : null;
  const belowReference = upcoming.filter(row => row.ecopower_import_eur_per_kwh_incl_vat < live.reference.eur_per_kwh_incl_vat).length;
  return `
    <div class="section-intro"><div><h3>Komende Day-Ahead-prijzen</h3><p>Belgische ENTSO-E-marktprijzen omgerekend met Ecopower Dynamische Burgerstroom. Vergelijking met de door de eigenaar gekozen indicatieve gemiddelde referentie van €0,2770/kWh.</p></div><span class="classification">INDICATIEVE VERGELIJKING · ${escapeHtml(live.quality.status)}</span></div>
    ${live.quality.stale ? '<div class="error-state"><strong>Prijsfeed is verouderd.</strong><p>Actuele kwartiermetrics zijn onderdrukt totdat een nieuwe ENTSO-E-feed beschikbaar is.</p></div>' : ""}
    <div class="metric-strip">
      ${metric("Daggemiddelde", currentDay ? `${euroPerKwh.format(currentDay.average_eur_per_kwh_incl_vat)}/kWh` : "—", "Ecopower variabel incl. GSC, WKK en 6% btw")}
      ${metric("Referentie", "€0,2770/kWh", "indicatief historisch gemiddelde")}
      ${metric("Goedkoopste kwartier", minimum == null ? "—" : `${euroPerKwh.format(minimum)}/kWh`, "komende gepubliceerde kwartieren", "good")}
      ${metric("Onder referentie", `${number.format(belowReference)}/${number.format(upcoming.length)}`, maximum == null ? "geen komende data" : `maximum ${euroPerKwh.format(maximum)}/kWh`)}
    </div>
    <div class="content-grid">
      <section class="panel full"><div class="panel-header"><h4>Ecopower-afnameprijs per kwartier</h4><small>INCL. GSC · WKK · 6% BTW · EXCL. NET/TAX/CAPACITY/SUBSCRIPTION</small></div>${priceComparisonChart(upcoming, live.reference.eur_per_kwh_incl_vat)}<div class="legend"><span>Ecopower dynamische afnameprijs</span><span class="warning">referentie €0,2770/kWh</span></div></section>
      <section class="panel full"><div class="panel-header"><h4>Vergelijking per dag</h4><small>LAATSTE 12 DAGEN · INCLUSIEF GEPUBLICEERDE TOEKOMST</small></div>${priceAggregateTable(live.aggregates.daily, "Daggegevens")}</section>
      <section class="panel full"><div class="panel-header"><h4>Vergelijking per week</h4><small>ISO-WEEK · PARTIËLE WEKEN ZICHTBAAR</small></div>${priceAggregateTable(live.aggregates.weekly, "Weekgegevens")}</section>
      <section class="panel full"><div class="panel-header"><h4>Vergelijking per maand</h4><small>PARTIËLE MAANDEN ZICHTBAAR</small></div>${priceAggregateTable(live.aggregates.monthly, "Maandgegevens")}</section>
      <section class="panel"><div class="panel-header"><h4>Formule en dekking</h4><small>${escapeHtml(live.tariff_version)}</small></div><div class="method-list"><div class="method-row"><span>ENTSO-E opgehaald</span><code>${escapeHtml(dateTimeFormat.format(new Date(live.source.retrieved_at)))}</code></div><div class="method-row"><span>Komende kwartieren</span><code>${number.format(live.coverage.upcoming_interval_count)}</code></div><div class="method-row"><span>Ontbrekende kwartieren</span><code>${number.format(live.quality.missing_quarter_count)}</code></div><div class="method-row"><span>Writes</span><code>geen · read-only</code></div></div></section>
      <section class="panel"><div class="panel-header"><h4>Vergelijkingsgrens</h4><small>GEEN FACTUURPROGNOSE</small></div><p class="panel-note">De Ecopower-kwartierprijs bevat de dynamische energiecomponent, GSC, WKK en 6% btw. Nettarieven, capaciteitstarief, accijnzen, Energiefonds en de verdeling van het maandabonnement zijn niet in deze kwartierlijn opgenomen. De €0,2770/kWh-referentie is daarom een indicatieve prijsbenchmark.</p></section>
      <section class="panel full"><div class="panel-header"><h4>Historische marktcontext</h4><small>GEVALIDEERD FACTUURJAAR · EUR/MWH</small></div>${lineChart(prices.monthly, "average_eur_per_mwh", { includeZero: true, label: row => formatMonth(row.month), tick: value => value.toFixed(0), aria: "Gemiddelde marktprijs per maand" })}</section>
    </div>`;
}

function renderEnergy(data) {
  const summary = data.summary;
  const recent = data.recent_energy.series;
  const labels = {
    grid_import: ["Netafname", "Van het net"], grid_export: ["Netinjectie", "Naar het net"], pv_generation: ["PV-productie", "Zonne-energie"],
    battery_charge: ["Batterij laden", "Opslag in"], battery_discharge: ["Batterij ontladen", "Opslag uit"], ev_charge: ["EV-laden", "Laadpaal"],
  };
  return `
    <div class="section-intro"><div><h3>Energieprofiel</h3><p>Jaarvolume uit Fluvius naast de meest recente gevalideerde Home Assistant-export. Dit scherm bevat geen live controls.</p></div><span class="classification">OBSERVATIE</span></div>
    <div class="metric-strip">
      ${metric("Jaarafname", `${number.format(summary.import_kwh)} kWh`, "Fluvius factuurjaar")}
      ${metric("Jaarinjectie", `${number.format(summary.export_kwh)} kWh`, "Fluvius factuurjaar")}
      ${metric("Zelfde gedrag", "Scenario A", "geen optimalisatie")}
      ${metric("HA-venster", "48 uur", "gevalideerde smoke-export")}
    </div>
    <div class="quality-grid">${Object.entries(recent).map(([key, item]) => `<section class="quality-card"><div class="quality-top"><h4>${escapeHtml(labels[key][0])}</h4><strong>${number.format(item.total_kwh)} kWh</strong></div><p>${escapeHtml(labels[key][1])} · ${item.quality_issue_count === 0 ? "geen kwaliteitsissues" : `${item.quality_issue_count} gemarkeerde afwijking`}</p></section>`).join("")}</div>
    <section class="panel" style="margin-top:12px"><div class="panel-header"><h4>Retentiebevinding</h4><small>HOME ASSISTANT</small></div><p style="font:10px/1.7 var(--mono);color:var(--ink-2);margin:0">${escapeHtml(data.data_retention.finding)}</p></section>`;
}

function renderQuality(data) {
  const quality = data.quality;
  const forecast_quality = data.forecast_quality;
  const dayAhead = forecast_quality.summary_by_horizon.day_ahead;
  const morning = forecast_quality.summary_by_horizon.same_day_morning;
  const coverage = quality.price_interval_count / quality.energy_interval_count * 100;
  return `
    <div class="section-intro"><div><h3>Datakwaliteit</h3><p>Beschikbaarheid, schattingen en bronreconciliatie blijven zichtbaar. Er is geen stille prijs-forward-fill toegepast.</p></div><span class="classification">TRACEABLE</span></div>
    <div class="quality-grid">
      <section class="quality-card"><div class="quality-top"><h4>Intervaldekking</h4><strong class="quality-ok">${percent.format(coverage)}%</strong></div><p>${number.format(quality.energy_interval_count)} energie- en ${number.format(quality.price_interval_count)} prijsintervallen.</p></section>
      <section class="quality-card"><div class="quality-top"><h4>Ontbrekende prijzen</h4><strong class="quality-ok">${number.format(quality.missing_price_interval_count)}</strong></div><p>Geen ontbrekende kwartieren in het volledige factuurjaar.</p></section>
      <section class="quality-card"><div class="quality-top"><h4>Geschatte energie</h4><strong class="quality-warn">${number.format(quality.estimated_interval_count)}</strong></div><p>Behoud en apart gemarkeerd; financiële sensitiviteit ${euro.format(data.estimated_interval_sensitivity_eur_excl_vat)} excl. btw.</p></section>
      <section class="quality-card"><div class="quality-top"><h4>Grid-reconciliatie</h4><strong class="quality-ok">≈ 0%</strong></div><p>Import ${percent.format(quality.grid_reconciliation_import_difference_percentage)}%; export ${percent.format(quality.grid_reconciliation_export_difference_percentage)}% verschil versus Fluvius.</p></section>
    </div>
    <div class="content-grid" style="margin-top:12px">
      <section class="panel"><div class="panel-header"><h4>Forecastkwaliteit</h4><small>SOLCAST · DAGENERGIE</small></div><div class="stat-list"><div class="stat-row"><span>Doeldagen</span><strong>${number.format(forecast_quality.quality.target_day_count)}</strong></div><div class="stat-row"><span>Bewaarde versies</span><strong>${number.format(forecast_quality.quality.forecast_version_count)}</strong></div><div class="stat-row"><span>Day-Ahead MAE</span><strong>${number.format(dayAhead.mean_absolute_error_kwh)} kWh</strong></div><div class="stat-row"><span>Day-Ahead MAPE</span><strong>${percent.format(dayAhead.mean_absolute_percentage_error)}%</strong></div><div class="stat-row"><span>Ochtend-MAE</span><strong>${number.format(morning.mean_absolute_error_kwh)} kWh</strong></div></div><p class="panel-note">Alle forecastrevisies blijven met issue time bewaard. Eén Day-Ahead-doeldag ontbreekt door de recorderretentie en is niet ingevuld.</p></section>
      <section class="panel"><div class="panel-header"><h4>Datacontract</h4><small>READ ONLY</small></div><div class="method-list"><div class="method-row"><span>Sequentie compleet</span><code>${quality.sequence_complete ? "true" : "false"}</code></div><div class="method-row"><span>Ruwe identifiers</span><code>${data.method.raw_identifiers_included ? "included" : "not included"}</code></div><div class="method-row"><span>Prijsbron</span><code>ENTSO-E A44 / A01 / Belgium</code></div><div class="method-row"><span>Loadforecast</span><code>${escapeHtml(forecast_quality.extensions.load_forecast.status)}</code></div><div class="method-row"><span>EV-forecast</span><code>${escapeHtml(forecast_quality.extensions.ev_energy_forecast.status)}</code></div><div class="method-row"><span>Generatie</span><code>${escapeHtml(dateTimeFormat.format(new Date(data.generated_at)))}</code></div></div></section>
    </div>`;
}

function renderBattery(data) {
  const battery = data.battery_simulation;
  const results = battery.central_results;
  const exportAllowed = results.perfect_foresight_export_allowed;
  const selfConsumption = results.perfect_foresight_self_consumption;
  const dayAhead = results.day_ahead_realistic;
  const coverage = battery.quality.usable_hour_count / battery.quality.source_hour_count * 100;
  return `
    <div class="section-intro"><div><h3>Offline batterijgevoeligheid</h3><p>Werkelijk gedrag vergeleken met twee perfecte bovengrenzen en een realistische Day-Ahead-heuristiek. Geen enkele simulatie stuurt de batterij aan.</p></div><span class="classification">${escapeHtml(battery.status)}</span></div>
    <div class="metric-strip">
      ${metric("Perfect zelfverbruik", signedEuro(selfConsumption.net_incremental_saving_eur), "theoretische bovengrens", "good")}
      ${metric("Perfect + export", signedEuro(exportAllowed.net_incremental_saving_eur), `${number.format(exportAllowed.battery_discharge_to_export_kwh)} kWh batterij-export`, "good")}
      ${metric("Day-Ahead realistisch", signedEuro(dayAhead.net_incremental_saving_eur), "versus werkelijk gedrag", "bad")}
      ${metric("Datadekking", `${percent.format(coverage)}%`, `${number.format(battery.quality.usable_hour_count)} bruikbare uren`)}
    </div>
    <div class="content-grid">
      <section class="panel full"><div class="panel-header"><h4>Degradatiegevoeligheid</h4><small>NETTO VERSCHIL · EUR</small></div><div class="table-wrap"><table class="financial-table"><thead><tr><th>Degradatie</th><th>Perfect + export</th><th>Perfect zelfverbruik</th><th>Day-Ahead</th></tr></thead><tbody>${battery.degradation_sensitivity.map(row => `<tr><td data-label="Degradatie">${euro.format(row.degradation_eur_per_discharged_kwh)}/kWh</td><td data-label="Perfect + export" class="${row.perfect_foresight_export_allowed_saving_eur >= 0 ? "negative" : "positive"}">${signedEuro(row.perfect_foresight_export_allowed_saving_eur)}</td><td data-label="Perfect zelfverbruik" class="${row.perfect_foresight_self_consumption_saving_eur >= 0 ? "negative" : "positive"}">${signedEuro(row.perfect_foresight_self_consumption_saving_eur)}</td><td data-label="Day-Ahead" class="${row.day_ahead_realistic_saving_eur >= 0 ? "negative" : "positive"}">${signedEuro(row.day_ahead_realistic_saving_eur)}</td></tr>`).join("")}</tbody></table></div></section>
      <section class="panel full"><div class="panel-header"><h4>Marginale waarde extra capaciteit</h4><small>5 KW VERMOGEN BLIJFT GELIJK</small></div><div class="table-wrap"><table class="financial-table"><thead><tr><th>Extra capaciteit</th><th>Perfecte jaarwaarde</th><th>10 jaar bovengrens</th><th>15 jaar bovengrens</th><th>Realistische case</th></tr></thead><tbody>${battery.additional_capacity.map(row => `<tr><td data-label="Extra capaciteit">${number.format(row.additional_usable_capacity_kwh)} kWh</td><td data-label="Perfecte jaarwaarde">${euro.format(row.perfect_self_consumption_marginal_saving_annualized_eur)}</td><td data-label="10 jaar bovengrens">${euro.format(row.perfect_self_consumption_upper_bound_installed_cost_10y_eur)}</td><td data-label="15 jaar bovengrens">${euro.format(row.perfect_self_consumption_upper_bound_installed_cost_15y_eur)}</td><td data-label="Realistische case" class="${row.realistic_investment_case_supported ? "negative" : "positive"}">${row.realistic_investment_case_supported ? "ondersteund" : "niet ondersteund"}</td></tr>`).join("")}</tbody></table></div></section>
      <section class="panel"><div class="panel-header"><h4>Verlies en gebruik</h4><small>€0,06/KWH DEGRADATIE</small></div><div class="stat-list"><div class="stat-row"><span>Perfect zelfverbruik · verlies</span><strong>${number.format(selfConsumption.conversion_loss_kwh)} kWh</strong></div><div class="stat-row"><span>Perfect zelfverbruik · cycli</span><strong>${number.format(selfConsumption.equivalent_full_cycles)}</strong></div><div class="stat-row"><span>Day-Ahead · verlies</span><strong>${number.format(dayAhead.conversion_loss_kwh)} kWh</strong></div><div class="stat-row"><span>Day-Ahead · piekeffect</span><strong>${signedEuro(dayAhead.capacity_peak_delta_eur)}</strong></div></div></section>
      <section class="panel"><div class="panel-header"><h4>Modelgrenzen</h4><small>REQUIRES TESTING</small></div><div class="method-list">${battery.limitations.map((item, index) => `<div class="method-row"><span>Beperking ${index + 1}</span><code>${escapeHtml(item)}</code></div>`).join("")}</div></section>
    </div>`;
}

function renderMultiYear(data) {
  const comparison = data.multi_year_comparison;
  const years = comparison.years;
  const trend = comparison.trend;
  const total = comparison.three_year_totals;
  const financial = comparison.three_year_financial_sensitivity;
  const largestCapacity = comparison.additional_capacity_three_year_average.at(-1);
  const signedPercent = value => `${value > 0 ? "+" : value < 0 ? "−" : ""}${percent.format(Math.abs(value))}%`;
  return `
    <div class="section-intro"><div><h3>Drie lokale energiejaren</h3><p>Fluvius-netstromen, Belgische Day-Ahead-prijzen en werkelijk batterijgedrag naast een extra virtuele batterij op het resterende netprofiel.</p></div><span class="classification">GEVALIDEERD · BEPERKINGEN</span></div>
    <div class="metric-strip">
      ${metric("Drie jaar afname", `${number.format(total.import_kwh)} kWh`, `${number.format(total.export_kwh)} kWh injectie`)}
      ${metric("Afnametrend", signedPercent(trend.first_to_last_import_change_percent), "meer afname · ongunstig", "bad")}
      ${metric("Dynamische sensitiviteit", euro.format(financial.average_dynamic_saving_eur_per_year), "gemiddeld per jaar · niet component-compleet", "good")}
      ${metric("Extra batterij 14,24 kWh", euro.format(largestCapacity.average_best_with_grid_charging_net_saving_eur_per_year), "perfecte gemiddelde jaarbovengrens", "good")}
    </div>
    <div class="content-grid">
      <section class="panel full"><div class="panel-header"><h4>Energie en financiële sensitiviteit per lokaal jaar</h4><small>CONFIGURED ALL-IN RATES · NIET COMPONENT-COMPLEET</small></div><div class="table-wrap"><table class="financial-table"><thead><tr><th>Jaar</th><th>Afname</th><th>Injectie</th><th>Gewogen prijs</th><th>Geconfigureerd historisch</th><th>Dynamische sensitiviteit</th><th>Verschil</th></tr></thead><tbody>${years.map(year => { const energy = year.energy_and_price; const finance = year.financial_sensitivity; return `<tr><td data-label="Jaar">${escapeHtml(year.analysis_year)}</td><td data-label="Afname">${number.format(energy.import_kwh)} kWh</td><td data-label="Injectie">${number.format(energy.export_kwh)} kWh</td><td data-label="Gewogen prijs">${euro.format(energy.import_weighted_market_price_eur_per_mwh)}/MWh</td><td data-label="Geconfigureerd historisch">${euro.format(finance.historical_net_variable_cost_eur)}</td><td data-label="Dynamische sensitiviteit">${euro.format(finance.dynamic_net_variable_cost_eur)}</td><td data-label="Verschil" class="${finance.dynamic_minus_historical_eur > 0 ? "positive" : "negative"}">${signedEuro(finance.dynamic_minus_historical_eur)}</td></tr>`; }).join("")}</tbody></table></div><p class="panel-note">Deze vergelijking gebruikt DSMR-configuratiewaarden, met de door de eigenaar bevestigde Home Assistant-afnameprijzen voor januari–september 2026. Vaste kosten, capaciteitstarief en historische componentversies zijn nog niet volledig gereconcilieerd.</p></section>
      <section class="panel full"><div class="panel-header"><h4>Werkelijk batterijgedrag</h4><small>SUNNY PORTAL + HOME ASSISTANT</small></div><div class="table-wrap"><table class="financial-table"><thead><tr><th>Jaar</th><th>Dekking</th><th>Geladen</th><th>Ontladen</th><th>Ratio</th><th>Cycli</th></tr></thead><tbody>${years.map(year => { const battery = year.observed_battery; return `<tr><td data-label="Jaar">${escapeHtml(year.analysis_year)}</td><td data-label="Dekking">${battery.coverage_classification === "COMPLETE_DAILY_SUNNY" ? "volledige dagdata" : "gedeeltelijk gemengd"}</td><td data-label="Geladen">${number.format(battery.charge_kwh)} kWh</td><td data-label="Ontladen">${number.format(battery.discharge_kwh)} kWh</td><td data-label="Ratio">${percent.format(battery.discharge_charge_ratio * 100)}%</td><td data-label="Cycli">${number.format(battery.equivalent_full_cycles)}</td></tr>`; }).join("")}</tbody></table></div></section>
      <section class="panel full"><div class="panel-header"><h4>Gemiddelde waarde extra opslag</h4><small>PER JAAR · PERFECT FORESIGHT</small></div><div class="table-wrap"><table class="financial-table"><thead><tr><th>Extra capaciteit</th><th>Alleen PV-overschot</th><th>Beste met netlaadoptie</th><th>Waarde netladen</th><th>Vermogen</th></tr></thead><tbody>${comparison.additional_capacity_three_year_average.map(row => `<tr><td data-label="Extra capaciteit">${number.format(row.additional_usable_capacity_kwh)} kWh</td><td data-label="Alleen PV-overschot">${euro.format(row.average_pv_surplus_only_net_saving_eur_per_year)}</td><td data-label="Beste met netlaadoptie">${euro.format(row.average_best_with_grid_charging_net_saving_eur_per_year)}</td><td data-label="Waarde netladen">${euro.format(row.average_incremental_grid_charging_value_eur_per_year)}</td><td data-label="Vermogen">5 kW</td></tr>`).join("")}</tbody></table></div></section>
      <section class="panel"><div class="panel-header"><h4>Winter en negatieve prijzen</h4><small>GEOBSERVEERD</small></div><div class="stat-list"><div class="stat-row"><span>Negatieve marktkwartieren</span><strong>${number.format(total.negative_market_interval_count)}</strong></div><div class="stat-row"><span>Laatste jaar winterafname</span><strong>${number.format(years.at(-1).energy_and_price.winter_import_kwh)} kWh</strong></div><div class="stat-row"><span>Mogelijke netlading mei-dec 2025</span><strong>${number.format(comparison.sunny_intraday_observed_dispatch.total.estimated_grid_charge_kwh)} kWh</strong></div></div></section>
      <section class="panel"><div class="panel-header"><h4>Modelgrenzen</h4><small>UPPER BOUND</small></div><div class="method-list"><div class="method-row"><span>Historische batterij</span><code>reeds in Fluvius-netprofiel</code></div><div class="method-row"><span>Netlading</span><code>perfect foresight</code></div><div class="method-row"><span>Batterij-export</span><code>uitgeschakeld</code></div><div class="method-row"><span>Fysieke writes</span><code>${comparison.physical_writes ? "uitgevoerd" : "geen"}</code></div></div></section>
    </div>`;
}

function renderScenarios(data) {
  const comparison = data.multi_year_comparison;
  const overview = comparison.scenario_overview;
  const labels = {
    OPTION: "optie",
    REQUIRES_TESTING: "testen vereist",
    INVESTMENT_CASE_REQUIRED: "investeringscase nodig",
    DATA_GATED: "data nodig",
    NOT_FEASIBLE: "niet haalbaar",
    LOW_VALUE: "lage waarde",
  };
  const optionValue = option => {
    if (option.value_eur_per_year == null) return "nog te bepalen";
    return `${euro.format(option.value_eur_per_year)}/jaar`;
  };
  const why = {
    dynamic_contract_unchanged_behavior: "Alle drie lokale jaren tonen een DSMR-gereconcilieerde tariefsensitivity zonder fysiek gedrag te wijzigen.",
    peak_neutral_winter_grid_charging: "Benut de 's winters vaak lege batterij zonder de bestaande maandpiek te verhogen.",
    battery_export: "Kan zeldzame dure kwartieren benutten nadat het huisverbruik gedekt is.",
    additional_battery_capacity: "Levert extra PV-opslag en arbitrage, maar de perfecte bovengrens blijft beperkt tegenover hardwarekost.",
  };
  const limitation = {
    dynamic_contract_unchanged_behavior: "All-in tarieven en vaste dagkosten zijn via DSMR gereconcilieerd; uitsplitsing en onafhankelijke factuurvalidatie van vaste, net-, capaciteit-, heffing- en btw-componenten blijven open.",
    peak_neutral_winter_grid_charging: "Perfect foresight op het resterende netprofiel; geen exacte redispatch van de bestaande batterij.",
    battery_export: "Controller, garantie, leverancier, meterwerking en regelgeving zijn nog niet gevalideerd.",
    additional_battery_capacity: "Geen investeringsbesluit zonder installatieprijs, levensduur en realistische forecast.",
  };
  return `
    <div class="section-intro"><div><h3>Welke scenario's zijn het onderzoeken waard?</h3><p>Beknopte besliskaart voor contract, batterij, gezamenlijke netpiek, EV en warmtepomp. Alle bedragen blijven offline simulaties; dit scherm stuurt niets aan.</p></div><span class="classification">READ ONLY · BESLISSTEUN</span></div>
    <div class="scenario-grid">
      ${overview.computed.map(option => `<article class="scenario-card"><div class="scenario-card-top"><span class="status-label ${option.status.toLowerCase().replaceAll("_", "-")}">${escapeHtml(labels[option.status] || option.status)}</span><strong>${escapeHtml(optionValue(option))}</strong></div><h4>${escapeHtml(option.title)}</h4><p>${escapeHtml(why[option.id] || option.why)}</p>${option.winter_value_eur_per_year == null ? "" : `<div class="scenario-detail"><span>Waarvan winter</span><strong>${euro.format(option.winter_value_eur_per_year)}/jaar</strong></div>`}<small>${escapeHtml(limitation[option.id] || option.limitation)}</small></article>`).join("")}
    </div>
    <div class="content-grid" style="margin-top:12px">
      <section class="panel full"><div class="panel-header"><h4>Gezamenlijke kwartierpiek: huis + warmtepomp + EV + batterijladen</h4><small>ABSOLUTE GRENS AAN AANSLUITPUNT</small></div><div class="table-wrap"><table class="financial-table"><thead><tr><th>Grens</th><th>Historische overschrijdingen</th><th>Max. overschrijding</th><th>Beste modelwaarde</th><th>Netladen gekozen</th><th>Rol</th></tr></thead><tbody>${overview.peak_caps.map(row => `<tr><td data-label="Grens">${number.format(row.cap_kw)} kW</td><td data-label="Historische overschrijdingen">${number.format(row.baseline_quarter_count_above_cap)} ${row.baseline_quarter_count_above_cap === 1 ? "kwartier" : "kwartieren"}</td><td data-label="Max. overschrijding">${number.format(row.maximum_historical_excess_kw)} kW</td><td data-label="Beste modelwaarde">${row.average_net_saving_eur_per_year == null ? "—" : `${euro.format(row.average_net_saving_eur_per_year)}/jaar`}</td><td data-label="Netladen gekozen">${row.grid_charging_selected_year_count}/3 jaren</td><td data-label="Rol">${row.cap_kw === 7 ? "strak · peak shaving" : row.cap_kw === 8 ? "middenweg · laadruimte" : "guardrail · hoge gelijktijdigheid"}</td></tr>`).join("")}</tbody></table></div><p class="panel-note">De waarde onder 7/8/10 kW komt vooral uit peak shaving en PV-opslag. Prijsbewust netladen is onder deze harde plafonds meestal niet de beste variant.</p></section>
      <section class="panel full"><div class="panel-header"><h4>Interessant, maar nog niet bewijsbaar met de huidige data</h4><small>DATA GATED</small></div><div class="scenario-grid compact">${overview.data_gated.map(option => `<article class="scenario-card muted"><span class="status-label data-gated">data nodig</span><h4>${escapeHtml(option.title)}</h4><p>Benodigd: ${escapeHtml(option.required_data)}</p></article>`).join("")}</div></section>
      <section class="panel"><div class="panel-header"><h4>Aanbevolen volgorde</h4><small>LAAG RISICO EERST</small></div><div class="method-list"><div class="method-row"><span>1</span><code>Dynamisch contract verder reconciliëren</code></div><div class="method-row"><span>2</span><code>Winterse piekneutrale batterijsturing shadow-testen</code></div><div class="method-row"><span>3</span><code>7/8/10 kW als gezamenlijke guardrail testen</code></div><div class="method-row"><span>4</span><code>EV en warmtepomp pas na datadekking toevoegen</code></div></div></section>
      <section class="panel"><div class="panel-header"><h4>Niet als eerste doen</h4><small>LAGE ZEKERHEID</small></div><div class="method-list"><div class="method-row"><span>Extra batterij</span><code>waarde te laag voor hardwarebesluit</code></div><div class="method-row"><span>Batterij-export</span><code>eerst contract en controller valideren</code></div><div class="method-row"><span>Volledige EMS</span><code>EV- en warmtepompconstraints ontbreken</code></div></div></section>
    </div>`;
}

function renderSteering(data) {
  const plan = data.shadow_controller_plan;
  const selected = plan.plans.find(row => row.id === plan.selected_policy_id);
  const actual = plan.actual_evaluations[plan.selected_policy_id];
  const counts = plan.selected_action_counts;
  const actionCount = Object.values(counts).reduce((sum, value) => sum + value, 0);
  return `
    <div class="section-intro"><div><h3>Day-Ahead shadow-controller</h3><p>Een kwartierplan voor de bestaande batterij, berekend met prijs, verwacht restprofiel en één gezamenlijke netpiek. Het plan is uitsluitend advies en stuurt niets aan.</p></div><span class="classification">${escapeHtml(plan.mode)}</span></div>
    <div class="metric-strip">
      ${metric("Geselecteerd beleid", selected.title, `${number.format(selected.cap_kw)} kW gezamenlijke grens`)}
      ${metric("Verwachte dagwaarde", signedEuro(selected.forecast_saving_eur), "na verlies en degradatie", selected.forecast_saving_eur >= 0 ? "good" : "bad")}
      ${metric("Backtest dagwaarde", signedEuro(actual.shadow_saving_eur), "plan op werkelijk restprofiel", actual.shadow_saving_eur >= 0 ? "good" : "bad")}
      ${metric("Actie-intervallen", number.format(actionCount - (counts.HOLD || 0)), `${number.format(plan.interval_count)} kwartieren totaal`)}
    </div>
    <div class="content-grid">
      <section class="panel full"><div class="panel-header"><h4>Vergelijking piekbeleid</h4><small>READ-ONLY SHADOW · GEEN SETPOINTS</small></div><div class="table-wrap"><table class="financial-table"><thead><tr><th>Beleid</th><th>Grens</th><th>Forecastwaarde</th><th>Backtestwaarde</th><th>Netladen</th><th>Ontladen</th><th>Status</th></tr></thead><tbody>${plan.plans.map(row => { const evaluation = plan.actual_evaluations[row.id]; return `<tr><td data-label="Beleid">${escapeHtml(row.title)}</td><td data-label="Grens">${number.format(row.cap_kw)} kW</td><td data-label="Forecastwaarde">${signedEuro(row.forecast_saving_eur)}</td><td data-label="Backtestwaarde">${evaluation ? signedEuro(evaluation.shadow_saving_eur) : "—"}</td><td data-label="Netladen">${number.format(row.totals.grid_charge_kwh)} kWh</td><td data-label="Ontladen">${number.format(row.totals.discharge_kwh)} kWh</td><td data-label="Status">${row.id === plan.selected_policy_id ? "geselecteerd" : "vergelijking"}</td></tr>`; }).join("")}</tbody></table></div></section>
      <section class="panel"><div class="panel-header"><h4>Voorgestelde acties</h4><small>${escapeHtml(plan.target_date)}</small></div><div class="stat-list"><div class="stat-row"><span>Netladen</span><strong>${number.format(counts.CHARGE_FROM_GRID || 0)} kwartieren</strong></div><div class="stat-row"><span>PV-overschot opslaan</span><strong>${number.format(counts.STORE_PV_SURPLUS || 0)} kwartieren</strong></div><div class="stat-row"><span>Ontladen naar huis</span><strong>${number.format(counts.DISCHARGE_TO_LOAD || 0)} kwartieren</strong></div><div class="stat-row"><span>Geen actie</span><strong>${number.format(counts.HOLD || 0)} kwartieren</strong></div></div></section>
      <section class="panel"><div class="panel-header"><h4>Veiligheidsgrenzen</h4><small>NO CONTROL</small></div><div class="method-list"><div class="method-row"><span>Home Assistant writes</span><code>${plan.home_assistant_writes ? "aan" : "uit"}</code></div><div class="method-row"><span>SMA writes</span><code>${plan.sma_writes ? "aan" : "uit"}</code></div><div class="method-row"><span>Smappee writes</span><code>${plan.smappee_writes ? "aan" : "uit"}</code></div><div class="method-row"><span>Start-SOC</span><code>${number.format(plan.battery.initial_soc_percent)}% · aangenomen voor backtest</code></div></div></section>
      <section class="panel full"><div class="panel-header"><h4>Modelgrenzen vóór activatie</h4><small>REQUIRES TESTING</small></div><div class="scenario-grid compact">${plan.forecast_limitations.map((item, index) => `<article class="scenario-card muted"><span class="status-label data-gated">beperking ${index + 1}</span><p>${escapeHtml(item)}</p></article>`).join("")}</div><p class="panel-note">De eerstvolgende stap is meerdere dagen automatisch in shadow mode bewaren en forecast versus werkelijkheid meten. Een positieve dag is geen toestemming om SMA of Smappee te wijzigen.</p></section>
    </div>`;
}

function decisionCard(decision) {
  const status = decision.outcome.status;
  const css = status.toLowerCase().replaceAll("_", "-");
  const kind = decision.entry_kind === "MEASUREMENT_CONCLUSION" ? "Werkelijke meting" : "Simulatiebesluit";
  return `<article class="decision"><div class="decision-top"><div><small>${escapeHtml(kind)} · ${escapeHtml(decision.id)}</small><h4>${escapeHtml(decision.title)}</h4></div><span class="status-label ${css}">${escapeHtml(status)}</span></div><p>${escapeHtml(decision.reason)}</p><strong>${escapeHtml(decision.outcome.summary)}</strong><div class="method-list"><div class="method-row"><span>Voorgestelde stap</span><code>${escapeHtml(decision.proposed_action.summary)}</code></div><div class="method-row"><span>Confidence</span><code>${escapeHtml(decision.confidence.level)} · ${number.format(decision.confidence.score * 100)}%</code></div><div class="method-row"><span>Bronnen</span><code>${number.format(decision.inputs.evidence_refs.length)}</code></div></div></article>`;
}

function renderDecisions(data) {
  return `
    <div class="section-intro"><div><h3>Energy Decision Log</h3><p>Formele, reproduceerbare beslisregistratie met bronverwijzingen, constraints, confidence en uitkomst. Werkelijke metingen en simulatiebesluiten blijven expliciet gescheiden.</p></div><span class="classification">READ ONLY · P2-006</span></div>
    <div class="decision-list">${data.decision_log.entries.map(decisionCard).join("")}</div>
    <section class="panel" style="margin-top:12px"><div class="panel-header"><h4>Beslisgrenzen</h4><small>ACTIEF</small></div><div class="method-list"><div class="method-row"><span>Contractwijziging</span><code>niet toegestaan</code></div><div class="method-row"><span>Home Assistant writes</span><code>niet toegestaan</code></div><div class="method-row"><span>EV / batterij control</span><code>niet toegestaan</code></div><div class="method-row"><span>Volgende financiële gate</span><code>historische contracttarieven + realistische forecast</code></div></div></section>`;
}

const AUTOMATION_STORAGE_KEY = "dynamic-energy-automation-drafts-v1";
const MODE_STORAGE_KEY = "dynamic-energy-operating-mode-v1";
const dayLabels = ["Zo", "Ma", "Di", "Wo", "Do", "Vr", "Za"];

function initialAutomation() {
  return createAutomationDraft({
    name: "Gezamenlijke goedkope kwartieren",
    target: "joint",
    max_grid_import_kw: 7,
    price_ceiling_eur_per_kwh: 0.2,
    battery_min_soc_percent: 15,
    battery_max_soc_percent: 90,
    ev_target_soc_percent: 80,
    ev_departure_time: "07:30",
    days: [1, 2, 3, 4, 5],
  });
}

function loadControlPreferences() {
  try {
    const storedDrafts = JSON.parse(localStorage.getItem(AUTOMATION_STORAGE_KEY) || "null");
    state.automations = Array.isArray(storedDrafts) && storedDrafts.length
      ? storedDrafts.map(createAutomationDraft)
      : [initialAutomation()];
    const storedMode = localStorage.getItem(MODE_STORAGE_KEY) || "monitor";
    state.operatingMode = requestOperatingMode("monitor", storedMode, ACTIVATION_CAPABILITY).mode;
  } catch (_) {
    state.automations = [initialAutomation()];
    state.operatingMode = "monitor";
  }
  state.selectedAutomationId = state.automations[0]?.id || null;
}

function saveAutomationDrafts() {
  try {
    localStorage.setItem(AUTOMATION_STORAGE_KEY, JSON.stringify(state.automations));
    state.modeMessage = "Conceptconfiguratie lokaal in deze browser opgeslagen.";
  } catch (_) {
    state.modeMessage = "Browseropslag is niet beschikbaar; de configuratie blijft alleen in deze sessie.";
  }
}

function selectedAutomation() {
  return state.automations.find(item => item.id === state.selectedAutomationId) || state.automations[0] || null;
}

function renderConfiguration() {
  const selected = selectedAutomation();
  const bundle = serializeAutomationBundle(state.automations);
  const validation = selected ? validateAutomationDraft(selected) : { valid: false, errors: ["GEEN_AUTOMATISATIE"] };
  const list = state.automations.map(item => {
    const result = validateAutomationDraft(item);
    const active = item.id === selected?.id ? " active" : "";
    return `<button type="button" class="automation-list-item${active}" data-automation-id="${escapeHtml(item.id)}"><span><strong>${escapeHtml(item.name)}</strong><small>${escapeHtml(item.target)} · prioriteit ${escapeHtml(item.priority)}</small></span><span class="automation-state ${result.valid ? "valid" : "invalid"}">${result.valid ? "GELDIG" : "NAKIJKEN"}</span></button>`;
  }).join("");
  const editor = selected ? `
    <div class="config-form" data-selected-automation="${escapeHtml(selected.id)}">
      <label class="field field-wide"><span>Naam</span><input data-config-field="name" value="${escapeHtml(selected.name)}"></label>
      <label class="field"><span>Doel</span><select data-config-field="target"><option value="joint" ${selected.target === "joint" ? "selected" : ""}>Batterij + EV</option><option value="battery" ${selected.target === "battery" ? "selected" : ""}>Alleen batterij</option><option value="ev" ${selected.target === "ev" ? "selected" : ""}>Alleen EV</option></select></label>
      <label class="field"><span>Prioriteit</span><input type="number" min="0" max="100" data-config-field="priority" value="${escapeHtml(selected.priority)}"></label>
      <label class="field"><span>Max. netimport</span><div class="input-unit"><input type="number" min="0.1" step="0.1" data-config-field="max_grid_import_kw" value="${escapeHtml(selected.max_grid_import_kw)}"><em>kW</em></div></label>
      <label class="field"><span>Max. afnameprijs</span><div class="input-unit"><input type="number" step="0.001" data-config-field="price_ceiling_eur_per_kwh" value="${escapeHtml(selected.price_ceiling_eur_per_kwh)}"><em>€/kWh</em></div></label>
      <label class="field"><span>Batterij minimum-SOC</span><div class="input-unit"><input type="number" min="0" max="100" data-config-field="battery_min_soc_percent" value="${escapeHtml(selected.battery_min_soc_percent)}"><em>%</em></div></label>
      <label class="field"><span>Batterij maximum-SOC</span><div class="input-unit"><input type="number" min="0" max="100" data-config-field="battery_max_soc_percent" value="${escapeHtml(selected.battery_max_soc_percent)}"><em>%</em></div></label>
      <label class="field"><span>EV target-SOC</span><div class="input-unit"><input type="number" min="0" max="100" data-config-field="ev_target_soc_percent" value="${escapeHtml(selected.ev_target_soc_percent)}"><em>%</em></div></label>
      <label class="field"><span>Vertrektijd</span><input type="time" data-config-field="ev_departure_time" value="${escapeHtml(selected.ev_departure_time)}"></label>
      <div class="field field-wide"><span>Actieve dagen</span><div class="day-selector">${dayLabels.map((label, day) => `<button type="button" data-automation-day="${day}" aria-pressed="${selected.days.includes(day)}">${label}</button>`).join("")}</div></div>
      <label class="toggle-field field-wide"><input type="checkbox" data-config-field="enabled" ${selected.enabled ? "checked" : ""}><span>Automatisatie meenemen in dry-run planning</span></label>
    </div>` : `<div class="error-state">Voeg een automatisatie toe om de voorwaarden te configureren.</div>`;
  return `
    <div class="section-intro"><div><h3>Sturingsconfiguratie</h3><p>Bouw batterij- en EV-automatisaties op als gevalideerde dry-runregels. De configuratie blijft lokaal in de browser en kan geen apparaat of Home Assistant wijzigen.</p></div><span class="classification">DRY-RUN · ACTIEF VERGRENDELD</span></div>
    <section class="activation-gate ${state.operatingMode}">
      <div><span class="pane-kicker">WERKINGSMODUS</span><h4>${state.operatingMode === "simulation" ? "Simulatie actief" : "Monitor actief"}</h4><p>${state.modeMessage || "De modus Actief is zichtbaar maar technisch vergrendeld totdat een afzonderlijke live-go, backendadapter en safety preflight beschikbaar zijn."}</p></div>
      <button type="button" class="activation-button" data-operating-mode="active">Actief inschakelen <span aria-hidden="true">🔒</span></button>
    </section>
    <div class="configuration-layout">
      <section class="panel automation-browser"><div class="panel-header"><h4>Automatisaties</h4><small>${state.automations.length} CONCEPT${state.automations.length === 1 ? "" : "EN"}</small></div><div class="automation-list">${list || '<div class="empty-config">Nog geen automatisaties.</div>'}</div><button type="button" class="config-button primary" id="add-automation">+ Nieuwe automatisatie</button></section>
      <section class="panel automation-editor"><div class="panel-header"><h4>Voorwaarden en grenzen</h4><small>${validation.valid ? "VALIDATIE OK" : `${validation.errors.length} FOUTEN`}</small></div>${editor}<div class="validation-summary ${validation.valid ? "valid" : "invalid"}"><strong>${validation.valid ? "Klaar voor dry-run" : "Configuratie geblokkeerd"}</strong><span>${validation.valid ? "Alle write-flags blijven false." : validation.errors.map(escapeHtml).join(" · ")}</span></div><div class="config-actions"><button type="button" class="config-button" id="delete-automation" ${selected ? "" : "disabled"}>Verwijderen</button><button type="button" class="config-button" id="export-automations">JSON exporteren</button><button type="button" class="config-button primary" id="save-automations">Concept opslaan</button></div></section>
    </div>
    <section class="panel config-contract"><div class="panel-header"><h4>Uitvoercontract</h4><small>${bundle.valid ? "SCHEMA GELDIG" : "FAIL CLOSED"}</small></div><div class="method-list"><div class="method-row"><span>Classificatie</span><code>${escapeHtml(bundle.classification)}</code></div><div class="method-row"><span>Execution allowed</span><code>false</code></div><div class="method-row"><span>Home Assistant writes</span><code>false</code></div><div class="method-row"><span>SMA writes</span><code>false</code></div><div class="method-row"><span>Smappee writes</span><code>false</code></div></div></section>`;
}

function renderContext(data, currentPrices) {
  if (state.view === "daycourse") {
    document.getElementById("context-content").innerHTML = `<div class="context-stack">
      <section class="context-section"><h3>Hoe lees je dit?</h3><ul><li>Bovenaan: de afnameprijs per kwartier. Rood ligt boven je plafond; daar laadt de EV niet.</li><li>Midden: batterij (groen) en EV (blauw) in kW.</li><li>Onderaan: wat het huis netto van het net haalt. Oranje stippellijn = je importlimiet.</li><li>"Ongestuurd" betekent: de auto laadt direct op vol vermogen bij aankomst.</li></ul></section>
      <div class="callout warning-callout"><strong>Geen live control</strong><p>Dit is een berekening op het shadow-plan. De Actief-optie blijft vergrendeld en er worden geen apparaten, Home Assistant, SMA of Smappee aangestuurd.</p></div>
      <section class="context-section"><h3>Let op</h3><p>De batterij volgt het bestaande batterijplan en houdt geen rekening met de EV. Plan en prijzen zijn de nieuwste in de shadow-pipeline; controleer de plandatum in het paneel.</p></section>
    </div>`;
    return;
  }
  const multiYear = state.view === "multiyear";
  const scenarios = state.view === "scenarios";
  const steering = state.view === "steering";
  const prices = state.view === "prices";
  const configuration = state.view === "configuration";
  const longRange = multiYear || scenarios;
  const comparison = data.multi_year_comparison;
  const callout = configuration
    ? `<div class="callout"><strong>Actief is technisch vergrendeld</strong><p>De pagina bouwt uitsluitend lokale dry-runconfiguratie. Er bestaat geen muterende backendroute of apparaatadapter.</p></div>`
    : prices && currentPrices
    ? `<div class="callout"><strong>${number.format(currentPrices.coverage.upcoming_interval_count)} komende kwartieren</strong><p>${currentPrices.quality.stale ? "De prijsfeed is verouderd; actuele kwartiermetrics zijn onderdrukt." : "De Ecopower-formule is toegepast op de laatst opgehaalde Belgische Day-Ahead-prijzen."}</p></div>`
    : steering
    ? `<div class="callout"><strong>${escapeHtml(data.shadow_controller_plan.classification)}</strong><p>De planner vergelijkt vier gedeelde piekgrenzen, maar publiceert geen uitvoercommando's.</p></div>`
    : scenarios
    ? `<div class="callout"><strong>Winterse netlading is een optie</strong><p>Gemiddeld ${euro.format(comparison.scenario_overview.computed.find(row => row.id === "peak_neutral_winter_grid_charging").value_eur_per_year)}/jaar in de perfecte piekneutrale gevoeligheid.</p></div>`
    : multiYear
    ? `<div class="callout"><strong>${percent.format(comparison.trend.first_to_last_import_change_percent)}% meer netafname</strong><p>Van het eerste naar het laatste lokale jaar, naast ${percent.format(Math.abs(comparison.trend.first_to_last_export_change_percent))}% minder injectie.</p></div>`
    : `<div class="callout"><strong>${euro.format(Math.abs(data.summary.difference_eur_incl_vat))} lager in Scenario A</strong><p>Een reproduceerbare retrospectieve backtest, geen voorspelling en geen contractadvies.</p></div>`;
  const interpretation = configuration
    ? `<section class="context-section"><h3>Activatievoorwaarden</h3><ul><li>Afzonderlijke expliciete live-go.</li><li>Gevalideerde safety supervisor en preflight.</li><li>Officieel ondersteunde SMA- en Smappee-interface.</li><li>Timeout, acknowledgement, override en lokale fallback.</li></ul></section>`
    : prices
    ? `<section class="context-section"><h3>Interpretatie</h3><ul><li>€0,2770/kWh is een indicatieve gemiddelde referentie.</li><li>De kwartierlijn bevat Ecopower energie, GSC, WKK en 6% btw.</li><li>Net-, capaciteit-, belasting- en abonnementskosten blijven apart.</li><li>Gedeeltelijke weken en maanden zijn expliciet gelabeld.</li></ul></section>`
    : steering
    ? `<section class="context-section"><h3>Interpretatie</h3><ul><li>De historische run bevat 96 kwartieren.</li><li>Het start-SOC is voor deze backtest aangenomen.</li><li>De restlastforecast bevat het bestaande batterijgedrag.</li><li>EV en warmtepomp blijven DATA_GATED.</li></ul></section>`
    : scenarios
    ? `<section class="context-section"><h3>Interpretatie</h3><ul><li>7/8/10 kW is de gezamenlijke kwartiergrens.</li><li>Batterijladen telt mee in die grens.</li><li>EV en warmtepomp zijn nog niet apart gereconstrueerd.</li><li>Resultaten zijn perfecte bovengrenzen.</li></ul></section>`
    : multiYear
    ? `<section class="context-section"><h3>Interpretatie</h3><ul><li>De vergelijking dekt drie volledige lokale jaren.</li><li>Alle 105.216 prijsintervallen zijn gekoppeld.</li><li>Zes onbeschikbare kwartieren blijven zichtbaar.</li><li>Extra opslag blijft een perfecte bovengrens.</li></ul></section>`
    : `<section class="context-section"><h3>Interpretatie</h3><ul><li>Het fysieke gedrag bleef exact gelijk.</li><li>Alle 35.040 kwartieren zijn gekoppeld.</li><li>99 geschatte kwartieren blijven zichtbaar.</li><li>De tariefformule is retrospectief toegepast.</li></ul></section>`;
  const periodStart = configuration ? data.generated_at : prices && currentPrices ? currentPrices.coverage.start_local : steering ? `${data.shadow_controller_plan.target_date}T00:00:00` : longRange ? comparison.period_start_local : data.period.start_local;
  const periodEnd = configuration ? data.generated_at : prices && currentPrices ? currentPrices.coverage.end_local : steering ? `${data.shadow_controller_plan.target_date}T23:59:59` : longRange ? comparison.period_end_local : data.period.end_local;
  const behavior = configuration ? "local dry-run configuration · active locked" : prices ? "live Day-Ahead price signal · no control" : steering ? "quarter-hour shadow plan · no control" : scenarios ? "scenario matrix · no control" : multiYear ? "residual extra battery upper bound" : "unchanged";
  document.getElementById("context-content").innerHTML = `<div class="context-stack">
    ${callout}
    ${interpretation}
    <section class="context-section"><h3>Datastatus</h3><div class="method-list"><div class="method-row"><span>Periode</span><code>${escapeHtml(periodStart.slice(0,10))} → ${escapeHtml(periodEnd.slice(0,10))}</code></div><div class="method-row"><span>Tariefversie</span><code>${escapeHtml(prices && currentPrices ? currentPrices.tariff_version : data.method.tariff_version)}</code></div><div class="method-row"><span>Gedrag</span><code>${escapeHtml(behavior)}</code></div><div class="method-row"><span>Modus</span><code>READ_ONLY</code></div></div></section>
    <div class="callout warning-callout"><strong>Geen live control</strong><p>De zichtbare Actief-optie blijft vergrendeld. Dit dashboard heeft geen write-endpoints en kan Home Assistant, SMA, Smappee, batterij of laadpaal niet wijzigen.</p></div>
    <section class="context-section"><h3>Volgende stap</h3><p>${configuration ? "De conceptregels koppelen aan het actuator-neutrale intentcontract en de safety supervisor, nog steeds zonder live writes." : steering ? "Meerdere dagelijkse plannen bewaren en forecast, dispatch, piekimpact en waarde tegen werkelijk gedrag valideren." : "Het Energy Decision Log is geformaliseerd. De volgende read-only stap is forecastkwaliteit en een realistische winterse shadow-controller."}</p></section>
  </div>`;
}

const renderers = { overview: renderOverview, financial: renderFinancial, prices: renderPrices, energy: renderEnergy, quality: renderQuality, battery: renderBattery, multiyear: renderMultiYear, scenarios: renderScenarios, steering: renderSteering, decisions: renderDecisions, configuration: renderConfiguration, daycourse: renderDayCourseView };

function render() {
  if (!state.data) return;
  const renderNow = Date.now();
  const currentPrices = state.dayAhead
    ? currentDayAheadView(state.dayAhead, renderNow)
    : null;
  document.getElementById("page-title").textContent = viewNames[state.view];
  document.getElementById("view-label").textContent = viewNames[state.view];
  const longRange = ["multiyear", "scenarios"].includes(state.view);
  const steering = state.view === "steering";
  const configuration = state.view === "configuration" || state.view === "daycourse";
  const prices = state.view === "prices" && state.dayAhead;
  const visiblePeriod = longRange
    ? state.data.multi_year_comparison
    : state.data.period;
  const periodStart = configuration ? state.data.generated_at : prices ? currentPrices.coverage.start_local : steering ? `${state.data.shadow_controller_plan.target_date}T00:00:00` : longRange ? visiblePeriod.period_start_local : visiblePeriod.start_local;
  const periodEnd = configuration ? state.data.generated_at : prices ? currentPrices.coverage.end_local : steering ? `${state.data.shadow_controller_plan.target_date}T23:59:59` : longRange ? visiblePeriod.period_end_local : visiblePeriod.end_local;
  document.getElementById("top-period").textContent = `${periodStart.slice(0, 10)} → ${periodEnd.slice(0, 10)}`;
  document.getElementById("primary-content").innerHTML = state.view === "prices"
    ? renderPrices(state.data, currentPrices)
    : renderers[state.view](state.data);
  renderContext(state.data, currentPrices);
  if (state.view === "configuration") bindConfigurationEvents();
  if (state.view === "daycourse") bindDayCourseEvents();
  document.querySelectorAll(".nav-item").forEach(button => button.classList.toggle("active", button.dataset.view === state.view));
  closeMenu();
}

const EV_ASSUMPTIONS_STORAGE_KEY = "dynamic-energy-ev-assumptions-v1";

function loadEvAssumptions() {
  try {
    const stored = JSON.parse(localStorage.getItem(EV_ASSUMPTIONS_STORAGE_KEY) || "null");
    if (stored && typeof stored === "object") {
      for (const key of Object.keys(DEFAULT_EV_ASSUMPTIONS)) {
        if (Number.isFinite(stored[key])) state.evAssumptions[key] = stored[key];
      }
    }
  } catch (_) {
    state.evAssumptions = { ...DEFAULT_EV_ASSUMPTIONS };
  }
}

function renderDayCourseView() {
  const automation = selectedAutomation();
  if (!automation) {
    return `<div class="error-state"><strong>Geen automatisatie geselecteerd.</strong><p>Maak er eerst een aan onder Configuratie.</p></div>`;
  }
  return renderDayCourse({
    status: state.dayCourse.status === "idle" ? "loading" : state.dayCourse.status,
    course: state.dayCourse.course,
    error: state.dayCourse.error,
    automation,
    assumptions: state.evAssumptions,
  });
}

async function loadDayCourse() {
  const automation = selectedAutomation();
  if (!automation) return;
  const key = buildDayCourseQuery(automation, state.evAssumptions);
  if (state.dayCourse.key === key) return;
  state.dayCourse = { key, status: "loading", course: null, error: null };
  try {
    const response = await fetch(`data/day-course.json?${key}`, { cache: "no-store" });
    const body = await response.json().catch(() => ({ status: "UNAVAILABLE", errors: [`HTTP_${response.status}`] }));
    if (state.dayCourse.key !== key) return;
    state.dayCourse = response.ok
      ? { key, status: "ready", course: body, error: null }
      : { key, status: "error", course: null, error: body };
  } catch (error) {
    if (state.dayCourse.key !== key) return;
    state.dayCourse = { key, status: "error", course: null, error: { status: "UNAVAILABLE", errors: [String(error.message || error)] } };
  }
  if (state.view === "daycourse") render();
}

function bindDayCourseEvents() {
  document.querySelectorAll("[data-ev-assumption]").forEach(input => input.addEventListener("change", () => {
    const value = Number(input.value);
    if (!input.value.trim() || !Number.isFinite(value)) return;
    state.evAssumptions[input.dataset.evAssumption] = value;
    try { localStorage.setItem(EV_ASSUMPTIONS_STORAGE_KEY, JSON.stringify(state.evAssumptions)); } catch (_) { /* optional */ }
    loadDayCourse();
    render();
  }));
  loadDayCourse();
}

function renderModeControls() {
  document.querySelectorAll("[data-operating-mode]").forEach(button => {
    button.setAttribute("aria-pressed", String(button.dataset.operatingMode === state.operatingMode));
  });
  const status = document.getElementById("operating-mode-status");
  if (status) status.textContent = state.operatingMode === "simulation" ? "SIMULATIE" : "MONITOR";
}

function selectOperatingMode(requestedMode) {
  const result = requestOperatingMode(state.operatingMode, requestedMode, ACTIVATION_CAPABILITY);
  state.operatingMode = result.mode;
  state.modeMessage = result.accepted
    ? result.mode === "simulation"
      ? "Dry-run simulatie is geselecteerd; alle uitvoer blijft niet-uitvoerbaar."
      : "Monitor is geselecteerd; automatisaties worden niet in planning meegenomen."
    : "Actief blijft vergrendeld: afzonderlijke live-go, backendadapter en safety preflight ontbreken.";
  try {
    localStorage.setItem(MODE_STORAGE_KEY, state.operatingMode);
  } catch (_) {
    // Mode remains available for the current browser session.
  }
  if (!result.accepted && requestedMode === "active") state.view = "configuration";
  if (state.data) render();
  renderModeControls();
}

function bindModeButtons(root = document) {
  root.querySelectorAll("[data-operating-mode]").forEach(button => {
    if (button.dataset.modeBound === "true") return;
    button.dataset.modeBound = "true";
    button.addEventListener("click", () => selectOperatingMode(button.dataset.operatingMode));
  });
  renderModeControls();
}

function updateSelectedAutomation(field, rawValue) {
  const selected = selectedAutomation();
  if (!selected) return;
  const numericFields = new Set([
    "priority",
    "max_grid_import_kw",
    "price_ceiling_eur_per_kwh",
    "battery_min_soc_percent",
    "battery_max_soc_percent",
    "ev_target_soc_percent",
  ]);
  const value = field === "enabled" ? Boolean(rawValue) : numericFields.has(field) ? Number(rawValue) : rawValue;
  const replacement = createAutomationDraft({ ...selected, [field]: value });
  state.automations = state.automations.map(item => item.id === selected.id ? replacement : item);
  state.selectedAutomationId = replacement.id;
  render();
}

function exportAutomationDrafts() {
  const bundle = serializeAutomationBundle(state.automations);
  const blob = new Blob([`${JSON.stringify(bundle, null, 2)}\n`], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "dynamic-energy-automation-drafts.json";
  anchor.click();
  URL.revokeObjectURL(url);
  state.modeMessage = "Niet-uitvoerbare JSON-configuratie geëxporteerd.";
  render();
}

function bindConfigurationEvents() {
  const content = document.getElementById("primary-content");
  bindModeButtons(content);
  content.querySelectorAll("[data-automation-id]").forEach(button => button.addEventListener("click", () => {
    state.selectedAutomationId = button.dataset.automationId;
    render();
  }));
  content.querySelectorAll("[data-config-field]").forEach(input => input.addEventListener("change", () => {
    updateSelectedAutomation(input.dataset.configField, input.type === "checkbox" ? input.checked : input.value);
  }));
  content.querySelectorAll("[data-automation-day]").forEach(button => button.addEventListener("click", () => {
    const selected = selectedAutomation();
    if (!selected) return;
    const day = Number(button.dataset.automationDay);
    const days = selected.days.includes(day)
      ? selected.days.filter(item => item !== day)
      : [...selected.days, day].sort();
    const replacement = createAutomationDraft({ ...selected, days });
    state.automations = state.automations.map(item => item.id === selected.id ? replacement : item);
    render();
  }));
  document.getElementById("add-automation")?.addEventListener("click", () => {
    const draft = createAutomationDraft({ name: `Automatisatie ${state.automations.length + 1}` });
    state.automations.push(draft);
    state.selectedAutomationId = draft.id;
    render();
  });
  document.getElementById("delete-automation")?.addEventListener("click", () => {
    const selected = selectedAutomation();
    if (!selected) return;
    state.automations = state.automations.filter(item => item.id !== selected.id);
    state.selectedAutomationId = state.automations[0]?.id || null;
    state.modeMessage = "Conceptautomatisatie verwijderd.";
    render();
  });
  document.getElementById("save-automations")?.addEventListener("click", () => {
    saveAutomationDrafts();
    render();
  });
  document.getElementById("export-automations")?.addEventListener("click", exportAutomationDrafts);
}

function closeMenu() {
  document.getElementById("sidebar").classList.remove("open");
  document.getElementById("scrim").classList.remove("open");
  document.getElementById("menu-button").setAttribute("aria-expanded", "false");
}

function setUiScale(value) {
  const allowed = new Set(["1", "1.12", "1.25"]);
  const scale = allowed.has(String(value)) ? String(value) : "1";
  document.documentElement.style.setProperty("--ui-scale", scale);
  document.getElementById("text-scale-label").textContent = `${Math.round(Number(scale) * 100)}%`;
  document.querySelectorAll("[data-ui-scale]").forEach(button => {
    button.setAttribute("aria-pressed", String(button.dataset.uiScale === scale));
  });
  try {
    localStorage.setItem("dynamic-energy-text-scale", scale);
  } catch (_) {
    // The control remains functional when browser storage is unavailable.
  }
}

function loadUiScale() {
  try {
    return localStorage.getItem("dynamic-energy-text-scale") || "1";
  } catch (_) {
    return "1";
  }
}

async function loadData() {
  state.dayCourse = { key: null, status: "idle", course: null, error: null };
  document.getElementById("data-status").textContent = "data laden";
  try {
    const [dashboardResponse, dayAheadResponse] = await Promise.all([
      fetch("data/dashboard-data.json", { cache: "no-store" }),
      fetch("data/day-ahead-prices.json", { cache: "no-store" }),
    ]);
    if (!dashboardResponse.ok) throw new Error(`HTTP ${dashboardResponse.status}`);
    state.data = await dashboardResponse.json();
    state.dayAhead = dayAheadResponse.ok ? await dayAheadResponse.json() : null;
    document.getElementById("data-status").textContent = `gegenereerd ${dateTimeFormat.format(new Date(state.data.generated_at))}`;
    document.getElementById("top-period").textContent = `${state.data.period.start_local.slice(0, 10)} → ${state.data.period.end_local.slice(0, 10)}`;
    render();
  } catch (error) {
    document.getElementById("primary-content").innerHTML = `<div class="error-state"><strong>Dashboarddata kon niet worden geladen.</strong><p>${escapeHtml(error.message)}</p><p>Voer eerst <code>python3 scripts/build_dashboard_data.py</code> uit.</p></div>`;
    document.getElementById("context-content").innerHTML = `<div class="error-state">Geen context beschikbaar zonder dataset.</div>`;
    document.getElementById("data-status").textContent = "datafout";
  }
}

document.querySelectorAll(".nav-item").forEach(button => button.addEventListener("click", () => {
  state.view = button.dataset.view;
  render();
}));
document.getElementById("refresh-data").addEventListener("click", loadData);
document.querySelectorAll("[data-ui-scale]").forEach(button => button.addEventListener("click", () => {
  setUiScale(button.dataset.uiScale);
}));
document.getElementById("menu-button").addEventListener("click", () => {
  const open = !document.getElementById("sidebar").classList.contains("open");
  document.getElementById("sidebar").classList.toggle("open", open);
  document.getElementById("scrim").classList.toggle("open", open);
  document.getElementById("menu-button").setAttribute("aria-expanded", String(open));
});
document.getElementById("scrim").addEventListener("click", closeMenu);
window.addEventListener("keydown", event => { if (event.key === "Escape") closeMenu(); });

loadControlPreferences();
loadEvAssumptions();
setUiScale(loadUiScale());
bindModeButtons();
loadData();
