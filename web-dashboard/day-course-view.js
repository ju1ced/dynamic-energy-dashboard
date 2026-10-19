"use strict";

export const DEFAULT_EV_ASSUMPTIONS = Object.freeze({
  ev_start_soc_percent: 20,
  ev_capacity_kwh: 60,
  ev_max_charge_kw: 7.4,
});

const euro = new Intl.NumberFormat("nl-BE", { style: "currency", currency: "EUR", minimumFractionDigits: 2 });
const kw = new Intl.NumberFormat("nl-BE", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const kwh = new Intl.NumberFormat("nl-BE", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const rate = new Intl.NumberFormat("nl-BE", { minimumFractionDigits: 3, maximumFractionDigits: 3 });

const WARNING_TEXT = {
  PRICE_CEILING_BLOCKS_TARGET: "Het prijsplafond is te laag: de auto haalt het doel niet.",
  LIMIT_OR_WINDOW_BLOCKS_TARGET: "De importlimiet of het tijdvenster tot vertrek laat te weinig laadruimte: de auto haalt het doel niet.",
  AUTOMATION_NOT_ACTIVE_ON_TARGET_DAY: "Deze automatisatie is niet actief op de dag van dit plan: de EV wordt niet ingepland.",
  EV_TARGET_ALREADY_REACHED: "De start-SOC ligt al op of boven het doel: er is niets te laden.",
};

const ERROR_TEXT = {
  PLAN_UNAVAILABLE: "Er is geen leesbaar shadow-plan beschikbaar.",
  INVALID_PARAMETERS: "Een of meer instellingen zijn ongeldig.",
};

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, character => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[character]);
}

function finite(value, fallback) {
  const number = typeof value === "number" ? value : Number.NaN;
  return Number.isFinite(number) ? number : fallback;
}

export function buildDayCourseQuery(automation, assumptions = DEFAULT_EV_ASSUMPTIONS) {
  const params = new URLSearchParams();
  const evEnabled = automation.enabled !== false && automation.target !== "battery";
  params.set("max_grid_import_kw", String(automation.max_grid_import_kw));
  params.set("price_ceiling_eur_per_kwh", String(automation.price_ceiling_eur_per_kwh));
  params.set("ev_enabled", String(evEnabled));
  params.set("ev_target_soc_percent", String(automation.ev_target_soc_percent));
  params.set("ev_departure_time", String(automation.ev_departure_time));
  params.set("active_days", automation.days.join(","));
  for (const key of Object.keys(DEFAULT_EV_ASSUMPTIONS)) {
    params.set(key, String(finite(Number(assumptions[key]), DEFAULT_EV_ASSUMPTIONS[key])));
  }
  return params.toString();
}

// Merge consecutive EV-charging quarters into readable blocks.
export function chargingBlocks(intervals) {
  const blocks = [];
  for (const row of intervals) {
    if (!(row.ev_kw > 0)) continue;
    const previous = blocks[blocks.length - 1];
    const startMs = Date.parse(row.start_utc);
    if (previous && previous.endMs === startMs) {
      previous.endMs = startMs + row.duration_hours * 3600000;
      previous.kwh += row.ev_kw * row.duration_hours;
      previous.peak = Math.max(previous.peak, row.ev_kw);
      previous.endLocal = row.start_local;
      previous.endDuration = row.duration_hours;
    } else {
      blocks.push({
        startLocal: row.start_local,
        endLocal: row.start_local,
        endDuration: row.duration_hours,
        endMs: startMs + row.duration_hours * 3600000,
        kwh: row.ev_kw * row.duration_hours,
        peak: row.ev_kw,
        reason: row.ev_reason,
      });
    }
  }
  return blocks;
}

function clock(local) {
  return String(local).slice(11, 16);
}

function endClock(block) {
  const [hours, minutes] = clock(block.endLocal).split(":").map(Number);
  const total = hours * 60 + minutes + Math.round(block.endDuration * 60);
  return `${String(Math.floor(total / 60) % 24).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
}

export function dayCourseChart(course) {
  const rows = course.intervals;
  const params = course.parameters;
  const width = 960;
  const left = 46;
  const right = 8;
  const columnWidth = (width - left - right) / rows.length;
  const x = index => left + index * columnWidth;
  const panels = {
    price: { top: 18, height: 96 },
    power: { top: 150, height: 110 },
    grid: { top: 296, height: 96 },
  };
  const maxPrice = Math.max(...rows.map(row => row.import_rate_eur_per_kwh), params.price_ceiling_eur_per_kwh, 0.01) * 1.1;
  const priceY = value => panels.price.top + panels.price.height * (1 - value / maxPrice);
  const maxPower = Math.max(1, ...rows.map(row => Math.abs(row.battery_kw)), ...rows.map(row => row.ev_kw)) * 1.1;
  const powerMid = panels.power.top + panels.power.height / 2;
  const powerY = value => powerMid - (value / maxPower) * (panels.power.height / 2);
  const maxGrid = Math.max(params.max_grid_import_kw * 1.15, ...rows.map(row => row.grid_net_kw)) ;
  const minGrid = Math.min(0, ...rows.map(row => row.grid_net_kw));
  const gridY = value => panels.grid.top + panels.grid.height * (1 - (value - minGrid) / (maxGrid - minGrid));

  const departureIndex = rows.findIndex(row => clock(row.start_local) >= params.ev_departure_time);
  const departureX = departureIndex < 0 ? null : x(departureIndex);

  const priceBars = rows.map((row, index) => {
    const above = row.import_rate_eur_per_kwh > params.price_ceiling_eur_per_kwh + 1e-9;
    const top = priceY(row.import_rate_eur_per_kwh);
    return `<rect class="dc-price ${above ? "above" : "below"}" x="${x(index).toFixed(2)}" y="${top.toFixed(2)}" width="${(columnWidth - 0.6).toFixed(2)}" height="${(panels.price.top + panels.price.height - top).toFixed(2)}"/>`;
  }).join("");
  const powerBars = rows.map((row, index) => {
    const half = (columnWidth - 0.6) / 2;
    const battery = Math.abs(row.battery_kw) > 1e-6
      ? `<rect class="dc-battery ${row.battery_kw > 0 ? "charge" : "discharge"}" x="${x(index).toFixed(2)}" y="${Math.min(powerY(row.battery_kw), powerMid).toFixed(2)}" width="${half.toFixed(2)}" height="${Math.abs(powerY(row.battery_kw) - powerMid).toFixed(2)}"/>`
      : "";
    const ev = row.ev_kw > 1e-6
      ? `<rect class="dc-ev" x="${(x(index) + half).toFixed(2)}" y="${powerY(row.ev_kw).toFixed(2)}" width="${half.toFixed(2)}" height="${(powerMid - powerY(row.ev_kw)).toFixed(2)}"/>`
      : "";
    return battery + ev;
  }).join("");
  const gridBars = rows.map((row, index) => {
    const zero = gridY(0);
    const top = gridY(row.grid_net_kw);
    return `<rect class="dc-grid ${row.over_limit ? "over" : row.grid_net_kw < 0 ? "export" : "import"}" x="${x(index).toFixed(2)}" y="${Math.min(top, zero).toFixed(2)}" width="${(columnWidth - 0.6).toFixed(2)}" height="${Math.abs(zero - top).toFixed(2)}"/>`;
  }).join("");
  const hover = rows.map((row, index) => {
    const lines = [
      `${clock(row.start_local)} · ${rate.format(row.import_rate_eur_per_kwh)} €/kWh`,
      `Batterij: ${row.battery_action} ${kw.format(Math.abs(row.battery_kw))} kW — ${row.battery_reason}`,
      `EV: ${kw.format(row.ev_kw)} kW — ${row.ev_reason}`,
      `Net: ${kw.format(row.grid_net_kw)} kW${row.over_limit ? " (boven limiet)" : ""}`,
    ];
    return `<rect class="dc-hover" x="${x(index).toFixed(2)}" y="${panels.price.top}" width="${columnWidth.toFixed(2)}" height="${panels.grid.top + panels.grid.height - panels.price.top}"><title>${escapeHtml(lines.join("\n"))}</title></rect>`;
  }).join("");
  const hourLabels = rows.map((row, index) => (
    clock(row.start_local).endsWith(":00") && Number(clock(row.start_local).slice(0, 2)) % 3 === 0
      ? `<text class="dc-axis" text-anchor="middle" x="${(x(index) + columnWidth / 2).toFixed(1)}" y="${panels.grid.top + panels.grid.height + 16}">${clock(row.start_local)}</text>`
      : ""
  )).join("");
  const line = (className, y, label) => `<line class="${className}" x1="${left}" x2="${width - right}" y1="${y.toFixed(2)}" y2="${y.toFixed(2)}"/><text class="dc-axis ${className}-label" x="${width - right}" y="${(y - 3).toFixed(2)}" text-anchor="end">${escapeHtml(label)}</text>`;
  const departure = departureX === null ? "" : `<line class="dc-departure" x1="${departureX.toFixed(2)}" x2="${departureX.toFixed(2)}" y1="${panels.price.top}" y2="${panels.grid.top + panels.grid.height}"/><text class="dc-axis" x="${(departureX + 3).toFixed(2)}" y="${panels.price.top + 8}">vertrek ${escapeHtml(params.ev_departure_time)}</text>`;
  const panelTitle = (label, panel) => `<text class="dc-panel-title" x="${left}" y="${panel.top - 6}">${escapeHtml(label)}</text>`;
  return `<div class="dc-chart"><svg viewBox="0 0 ${width} 424" role="img" aria-label="Dagverloop: prijs, batterij en EV, netimport per kwartier">
    ${panelTitle("Afnameprijs per kWh — rood = boven je plafond", panels.price)}
    ${priceBars}${line("dc-ceiling", priceY(params.price_ceiling_eur_per_kwh), `plafond ${rate.format(params.price_ceiling_eur_per_kwh)}`)}
    ${panelTitle("Vermogen — groen = batterij (omhoog laden, omlaag ontladen), blauw = EV", panels.power)}
    <line class="dc-zero" x1="${left}" x2="${width - right}" y1="${powerMid}" y2="${powerMid}"/>${powerBars}
    <text class="dc-axis" x="2" y="${powerY(maxPower / 1.1) + 3}">${kw.format(maxPower / 1.1)} kW</text><text class="dc-axis" x="2" y="${powerY(-maxPower / 1.1) + 3}">−${kw.format(maxPower / 1.1)}</text>
    ${panelTitle("Netto van/naar het net — rood = boven je importlimiet, groen = export", panels.grid)}
    <line class="dc-zero" x1="${left}" x2="${width - right}" y1="${gridY(0).toFixed(2)}" y2="${gridY(0).toFixed(2)}"/>${gridBars}${line("dc-limit", gridY(params.max_grid_import_kw), `limiet ${kw.format(params.max_grid_import_kw)} kW`)}
    ${departure}${hourLabels}${hover}
  </svg></div>`;
}

function metric(label, value, detail, className = "") {
  return `<div class="metric"><span class="metric-label">${escapeHtml(label)}</span><span class="metric-value ${className}">${escapeHtml(value)}</span><span class="metric-detail">${escapeHtml(detail)}</span></div>`;
}

function field(name, label, value, unit, attributes = "") {
  return `<label class="field"><span>${escapeHtml(label)}</span><div class="input-unit"><input type="number" ${attributes} data-ev-assumption="${name}" value="${escapeHtml(value)}"><em>${escapeHtml(unit)}</em></div></label>`;
}

export function renderDayCourse(model) {
  const { status, course, error, automation, assumptions } = model;
  const intro = `<div class="section-intro"><div><h3>Dagverloop: hoe zou deze dag lopen?</h3><p>Voor één dag, per kwartier: de batterij volgt het shadow-plan, de EV laadt in de goedkoopste kwartieren onder je prijsplafond en binnen je gezamenlijke importlimiet. Je regels uit Configuratie sturen dit aan. Er wordt niets aangestuurd.</p></div><span class="classification">DRY-RUN · GEEN STURING</span></div>`;
  const assumptionForm = `<section class="panel full"><div class="panel-header"><h4>Aannames voor de auto</h4><small>${escapeHtml(automation.name)}</small></div>
    <div class="config-form">
      ${field("ev_start_soc_percent", "SOC bij aankomst", assumptions.ev_start_soc_percent, "%", 'min="0" max="100" step="1"')}
      ${field("ev_capacity_kwh", "Accucapaciteit", assumptions.ev_capacity_kwh, "kWh", 'min="1" max="200" step="1"')}
      ${field("ev_max_charge_kw", "Max. laadvermogen", assumptions.ev_max_charge_kw, "kW", 'min="1" max="22" step="0.1"')}
    </div>
    <p class="panel-note">Doel-SOC, vertrektijd, prijsplafond, importlimiet en actieve dagen komen uit de geselecteerde automatisatie (${escapeHtml(automation.target === "battery" ? "alleen batterij: EV uit" : "batterij + EV")}).</p></section>`;

  if (status === "loading") {
    return `${intro}<div class="loading-state"><span></span><p>Dagverloop berekenen…</p></div>${assumptionForm}`;
  }
  if (status === "error") {
    const detail = (error?.errors || []).map(code => ERROR_TEXT[code] || code).join(" · ") || ERROR_TEXT[error?.status] || "Onbekende fout";
    return `${intro}<div class="error-state"><strong>Dagverloop niet beschikbaar.</strong><p>${escapeHtml(detail)}</p><p>Draai de dashboardserver via <code>scripts/serve_dashboard.py</code>; een statische bestandsserver heeft dit endpoint niet.</p></div>${assumptionForm}`;
  }

  const summary = course.summary;
  const reached = summary.ev_target_reached;
  const warnings = course.warnings.map(code => `<div class="callout warning-callout"><p>${escapeHtml(WARNING_TEXT[code] || code)}</p></div>`).join("");
  const blocks = chargingBlocks(course.intervals);
  const blockRows = blocks.length
    ? blocks.map(block => `<tr><td data-label="Van–tot">${clock(block.startLocal)}–${endClock(block)}</td><td data-label="Vermogen (piek)">${kw.format(block.peak)} kW</td><td data-label="Energie">${kwh.format(block.kwh)} kWh</td><td data-label="Reden">${escapeHtml(block.reason)}</td></tr>`).join("")
    : `<tr><td colspan="4">De EV laadt deze dag niet.</td></tr>`;
  const ceilingHint = summary.required_price_ceiling_eur_per_kwh === null
    ? ""
    : `<div class="stat-row"><span>Plafond nodig voor het doel</span><strong>${rate.format(summary.required_price_ceiling_eur_per_kwh)} €/kWh</strong></div>`;
  const evCostLabel = summary.ev_saving_vs_unmanaged_eur >= 0 ? "bespaard" : "duurder";

  return `${intro}
    <div class="metric-strip">
      ${metric("Auto klaar bij vertrek", reached ? "Ja" : course.parameters.ev_enabled ? "Nee" : "—", `${kwh.format(summary.ev_planned_kwh)} van ${kwh.format(summary.ev_needed_kwh)} kWh · einde ${kwh.format(summary.ev_end_soc_percent)}%`, reached ? "good" : course.parameters.ev_enabled ? "bad" : "")}
      ${metric("EV-kost (gestuurd)", euro.format(summary.ev_cost_eur), `ongestuurd ${euro.format(summary.ev_cost_unmanaged_eur)} · ${euro.format(Math.abs(summary.ev_saving_vs_unmanaged_eur))} ${evCostLabel}`, summary.ev_saving_vs_unmanaged_eur >= 0 ? "good" : "bad")}
      ${metric("Piek netimport", `${kw.format(summary.peak_grid_import_kw)} kW`, `ongestuurd ${kw.format(summary.peak_grid_import_unmanaged_kw)} kW · limiet ${kw.format(course.parameters.max_grid_import_kw)}`, summary.over_limit_intervals ? "bad" : "good")}
      ${metric("Kwartieren boven limiet", String(summary.over_limit_intervals), `ongestuurd ${summary.over_limit_intervals_unmanaged}`, summary.over_limit_intervals ? "bad" : "good")}
    </div>
    ${warnings}
    <section class="panel full"><div class="panel-header"><h4>Plan van ${escapeHtml(course.plan.target_date)}</h4><small>${course.plan.interval_count} KWARTIEREN · BELGISCHE TIJD</small></div>${dayCourseChart(course)}<p class="panel-note">Beweeg over een kwartier voor de reden. Het onderliggende shadow-plan is gegenereerd op ${escapeHtml(String(course.plan.generated_at).slice(0, 16).replace("T", " "))} UTC.</p></section>
    <div class="content-grid">
      <section class="panel"><div class="panel-header"><h4>Laadmomenten EV</h4><small>${blocks.length} BLOK${blocks.length === 1 ? "" : "KEN"}</small></div><div class="table-wrap"><table class="financial-table"><thead><tr><th>Van–tot</th><th>Vermogen (piek)</th><th>Energie</th><th>Reden</th></tr></thead><tbody>${blockRows}</tbody></table></div></section>
      <section class="panel"><div class="panel-header"><h4>Kosten van de dag</h4><small>INDICATIEF</small></div><div class="stat-list">
        <div class="stat-row"><span>Zonder sturing</span><strong>${euro.format(summary.cost_no_control_eur)}</strong></div>
        <div class="stat-row"><span>Met batterij</span><strong>${euro.format(summary.cost_battery_only_eur)}</strong></div>
        <div class="stat-row"><span>Met batterij + EV</span><strong>${euro.format(summary.cost_with_ev_eur)}</strong></div>
        <div class="stat-row"><span>Geblokkeerd door plafond</span><strong>${summary.ev_blocked_intervals.CEILING} kwartieren</strong></div>
        <div class="stat-row"><span>Geblokkeerd door importlimiet</span><strong>${summary.ev_blocked_intervals.LIMIT} kwartieren</strong></div>
        ${ceilingHint}
      </div></section>
    </div>
    ${assumptionForm}
    <section class="panel full"><div class="panel-header"><h4>Aannames en grenzen van dit model</h4><small>LEES DIT VOOR JE CIJFERS VERTROUWT</small></div><ul class="plain-list">${course.assumptions.map(item => `<li>${escapeHtml(item)}</li>`).join("")}</ul></section>`;
}
