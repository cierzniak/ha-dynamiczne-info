/**
 * dynamiczne.info Lovelace card.
 *
 * A dependency-free custom card that renders the 24-hour usage hints exposed by
 * the dynamiczne.info integration's "current price" sensor (its `today` attribute:
 * a list of { hour, startsAt, buyGrossPlnPerKwh, sellGrossPlnPerKwh, consumption,
 * sell }). Each hour is coloured by its consumption advice (use / neutral /
 * limit) with a badge for sell hours; the current hour is highlighted.
 *
 * A header summarises the live state from the same sensor's `now` block
 * (current advice, next cheap/sell hour) and `today_summary` (cheap/expensive
 * hour counts), so the card answers "what now / what next" at a glance.
 *
 * Usage (Lovelace YAML):
 *   type: custom:dynamiczne-info-card
 *   entity: sensor.dynamiczne_info_energa_g11f_current_price
 *   title: dynamiczne.info - wskazówki na dziś
 */

const CARD_VERSION = "0.3.0";

const LABELS = { use: "Używaj", neutral: "Neutralnie", limit: "Ogranicz" };

const ESCAPE = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

/** Escape a value before interpolating it into an HTML string (XSS guard). */
const esc = (value) => String(value).replace(/[&<>"']/g, (c) => ESCAPE[c]);

/**
 * Build the forward-looking 24-hour window: the current hour plus the next 23,
 * drawing from `today` then `tomorrow`. Always returns exactly 24 slots; hours
 * with no data yet (e.g. tomorrow not published) are `null` so the card renders
 * a "?" placeholder instead of leaving the grid short or padded with stale past
 * hours. Returns `null` only when there is no data at all (caller shows a
 * waiting message).
 */
const next24Hours = (today, tomorrow) => {
  const all = (Array.isArray(today) ? today : []).concat(
    Array.isArray(tomorrow) ? tomorrow : [],
  );
  if (all.length === 0) return null;
  const now = Date.now();
  let start = all.findIndex((h) => {
    const t = Date.parse(h.startsAt);
    return !Number.isNaN(t) && t <= now && now < t + 3600000;
  });
  if (start < 0) start = 0; // "now" not in the data -> show from the earliest hour
  const slots = [];
  for (let i = 0; i < 24; i++) slots.push(all[start + i] || null);
  return slots;
};

/** A "?" cell for an hour whose data is not available yet. */
const EMPTY_CELL = `<div class="pf-cell pf-empty"><span class="pf-hr">?</span><span class="pf-prices"><span class="pf-buy">?</span></span></div>`;

/**
 * Render one hour cell: a large hour on the left, the buy price (and, when
 * `showSell` and a sell price are present, the sell price underneath) stacked
 * on the right. `extra` adds classes (e.g. "pf-picked"); `title` is a tooltip.
 * Loads care only about the buy price, so the scheduler card passes
 * showSell=false.
 */
const hourCell = (h, { extra = [], title = "", showSell = true } = {}) => {
  if (!h) return EMPTY_CELL;
  const advice = LABELS[h.consumption] ? h.consumption : "neutral";
  const hour = String(Number.parseInt(h.hour, 10) || 0).padStart(2, "0");
  const buy = Number.isFinite(h.buyGrossPlnPerKwh)
    ? Number(h.buyGrossPlnPerKwh).toFixed(2)
    : "";
  const sell =
    showSell && Number.isFinite(h.sellGrossPlnPerKwh)
      ? Number(h.sellGrossPlnPerKwh).toFixed(2)
      : "";
  const classes = [
    "pf-cell",
    `pf-${advice}`,
    showSell && h.sell === true ? "pf-sell" : "",
    ...extra,
  ]
    .filter(Boolean)
    .join(" ");
  const prices = sell
    ? `<span class="pf-buy">${buy}</span><span class="pf-sellpx">${sell}</span>`
    : `<span class="pf-buy">${buy}</span>`;
  const tip = title ? ` title="${title}"` : "";
  return `<div class="${classes}"${tip}>
      <span class="pf-hr">${hour}</span>
      <span class="pf-prices">${prices}</span>
    </div>`;
};

/**
 * Shared grid + cell styling, injected into both cards' <style> blocks so the
 * compact "hour | buy / sell" cell stays identical across them. Advice colours
 * (pf-use/neutral/limit) live here too because the main card's legend reuses
 * them.
 */
const CELL_CSS = `
  .pf-strip { display:grid; grid-template-columns:repeat(3,1fr); gap:4px; padding:8px 16px 16px; }
  .pf-cell { display:flex; align-items:center; justify-content:space-between; gap:6px; border-radius:6px; padding:4px 9px; border:2px solid transparent; background:rgba(var(--pf-rgb, 144,144,144), .15); color:var(--primary-text-color); }
  .pf-hr { font-weight:700; font-size:1.35rem; line-height:1; font-variant-numeric:tabular-nums; color:var(--pf, var(--primary-text-color)); }
  .pf-prices { display:flex; flex-direction:column; align-items:flex-end; line-height:1.15; }
  .pf-buy { font-size:.82rem; font-weight:600; font-variant-numeric:tabular-nums; color:var(--primary-text-color); }
  .pf-sellpx { font-size:.72rem; font-variant-numeric:tabular-nums; color:var(--info-color, #2196f3); }
  .pf-use { --pf:var(--success-color, #43a047); --pf-rgb:var(--rgb-success-color, 67,160,71); }
  .pf-neutral { --pf:var(--secondary-text-color, #9e9e9e); --pf-rgb:144,144,144; }
  .pf-limit { --pf:var(--error-color, #e53935); --pf-rgb:var(--rgb-error-color, 229,57,53); }
  .pf-sell { box-shadow:inset 0 -3px 0 var(--info-color, #2196f3); }
  .pf-picked { border-color:var(--primary-color); box-shadow:0 0 0 2px var(--primary-color) inset; }
  .pf-empty { background:rgba(var(--rgb-disabled-text-color, 189,189,189), .08); }
  .pf-empty .pf-hr, .pf-empty .pf-buy { color:var(--disabled-text-color, #9e9e9e); }`;

class DynamiczneInfoCard extends HTMLElement {
  setConfig(config) {
    if (!config || !config.entity) {
      throw new Error("Podaj 'entity' (sensor 'cena bieżąca' z dynamiczne.info).");
    }
    this._config = config;
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 3;
  }

  static getConfigElement() {
    return document.createElement("dynamiczne-info-card-editor");
  }

  static getStubConfig(hass) {
    if (hass) {
      const id = Object.keys(hass.states).find(
        (e) => e.startsWith("sensor.") && e.endsWith("_current_price"),
      );
      if (id) return { entity: id };
    }
    return { entity: "" };
  }

  _currentIndex(hours) {
    const now = Date.now();
    for (let i = 0; i < hours.length; i++) {
      const start = Date.parse(hours[i].startsAt);
      if (!Number.isNaN(start) && start <= now && now < start + 3600000) {
        return i;
      }
    }
    return -1;
  }

  _fmtHour(ref) {
    const h = ref ? Number.parseInt(ref.hour, 10) : NaN;
    return Number.isFinite(h) ? `${String(h).padStart(2, "0")}:00` : "-";
  }

  _price(value) {
    return Number.isFinite(value) ? Number(value).toFixed(2) : null;
  }

  _stat(cssClass, label, value) {
    return `<div class="pf-stat ${cssClass}">
        <span class="pf-stat-k">${esc(label)}</span>
        <span class="pf-stat-v">${esc(value)}</span>
      </div>`;
  }

  _header(nowBlock, summary, hours, nowIndex) {
    const cur =
      (nowBlock && nowBlock.hour) || (nowIndex >= 0 ? hours[nowIndex] : null);
    const chips = [];

    if (cur) {
      const advice = LABELS[cur.consumption] ? cur.consumption : "neutral";
      const price = this._price(cur.buyGrossPlnPerKwh);
      const value = `${LABELS[advice]}${price ? ` · ${price} zł` : ""}`;
      chips.push(this._stat(`pf-${advice}`, "Teraz", value));
    }

    const nextCheap = nowBlock && nowBlock.nextCheapHour;
    if (nextCheap) {
      const price = this._price(nextCheap.buyGrossPlnPerKwh);
      const value = `${this._fmtHour(nextCheap)}${price ? ` · ${price} zł` : ""}`;
      chips.push(this._stat("pf-use", "Tania od", value));
    }

    const nextSell = nowBlock && nowBlock.nextSellHour;
    if (nextSell) {
      const price = this._price(nextSell.sellGrossPlnPerKwh);
      const value = `${this._fmtHour(nextSell)}${price ? ` · ${price} zł` : ""}`;
      chips.push(this._stat("pf-sellstat", "Sprzedaj od", value));
    }

    let counts = "";
    if (summary) {
      const parts = [];
      const use = Number.parseInt(summary.useHours, 10);
      const limit = Number.parseInt(summary.limitHours, 10);
      if (Number.isFinite(use)) parts.push(`${use} tanich`);
      if (Number.isFinite(limit)) parts.push(`${limit} drogich`);
      if (parts.length) {
        counts = `<div class="pf-counts">${esc(`${parts.join(" · ")} godz. dziś`)}</div>`;
      }
    }

    if (chips.length === 0 && !counts) return "";
    return `<div class="pf-head">${chips.join("")}</div>${counts}`;
  }

  _render() {
    if (!this._hass || !this._config) return;
    const stateObj = this._hass.states[this._config.entity];
    const title = esc(this._config.title || "dynamiczne.info");

    if (!stateObj) {
      this.innerHTML = `<ha-card header="${title}"><div style="padding:16px">Brak encji <code>${esc(this._config.entity)}</code>.</div></ha-card>`;
      return;
    }

    // Forward-looking window: the current hour + the next 23, from today then
    // tomorrow. Missing hours render as "?" so the grid stays exactly 24 long.
    const slots = next24Hours(
      stateObj.attributes.today,
      stateObj.attributes.tomorrow,
    );

    if (slots === null) {
      this.innerHTML = `<ha-card header="${title}"><div style="padding:16px">Oczekiwanie na dane fixingu...</div></ha-card>`;
      return;
    }

    const hours = Array.isArray(stateObj.attributes.today)
      ? stateObj.attributes.today
      : [];
    const nowIndex = this._currentIndex(hours);
    const nowBlock =
      stateObj.attributes.now && typeof stateObj.attributes.now === "object"
        ? stateObj.attributes.now
        : null;
    const summary =
      stateObj.attributes.today_summary &&
      typeof stateObj.attributes.today_summary === "object"
        ? stateObj.attributes.today_summary
        : null;
    const header = this._header(nowBlock, summary, hours, nowIndex);
    const cells = slots
      .map((h) => {
        if (!h) return EMPTY_CELL;
        const advice = LABELS[h.consumption] ? h.consumption : "neutral";
        const hour = String(Number.parseInt(h.hour, 10) || 0).padStart(2, "0");
        const price = Number.isFinite(h.buyGrossPlnPerKwh)
          ? Number(h.buyGrossPlnPerKwh).toFixed(2)
          : "";
        const tip = esc(
          `${hour}:00 - ${LABELS[advice]}${h.sell === true ? " · Sprzedaj" : ""}${price ? ` (${price} zł/kWh)` : ""}`,
        );
        return hourCell(h, { title: tip });
      })
      .join("");

    this.innerHTML = `
      <ha-card header="${title}">
        <style>
          /* Colours come from Home Assistant theme variables so the card tracks
             the active light/dark theme; the --rgb-* fallbacks keep it readable
             if a theme omits one. Each advice class sets --pf/--pf-rgb, reused
             for the cell tint, hour colour, legend swatch and header chips. The
             compact hour grid (3 columns, "hour | buy / sell" cells) is shared
             with the scheduler card via CELL_CSS. */
          ${CELL_CSS}
          .pf-legend { display:flex; flex-wrap:wrap; gap:.7rem; padding:8px 16px 0; font-size:.84rem; color:var(--primary-text-color); }
          .pf-sw { width:.85rem; height:.85rem; border-radius:3px; display:inline-block; vertical-align:middle; margin-right:.25rem; background:var(--pf, #888); }
          .pf-sellsw { background:var(--card-background-color, transparent); box-shadow:inset 0 -3px 0 var(--info-color, #2196f3); }
          .pf-head { display:flex; flex-wrap:wrap; gap:.5rem; padding:8px 16px 0; }
          .pf-stat { display:flex; flex-direction:column; border-radius:8px; padding:6px 10px; min-width:5.5rem; background:rgba(var(--pf-rgb, 144,144,144), .15); color:var(--primary-text-color); }
          .pf-stat-k { font-size:.7rem; text-transform:uppercase; letter-spacing:.04em; color:var(--secondary-text-color); }
          .pf-stat-v { font-weight:700; font-variant-numeric:tabular-nums; font-size:.98rem; }
          .pf-sellstat { --pf:var(--info-color, #2196f3); --pf-rgb:var(--rgb-info-color, 33,150,243); box-shadow:inset 0 -3px 0 var(--info-color, #2196f3); }
          .pf-counts { padding:6px 16px 0; font-size:.82rem; color:var(--secondary-text-color); }
        </style>
        ${header}
        <div class="pf-legend">
          <span><span class="pf-sw pf-use"></span>Używaj</span>
          <span><span class="pf-sw pf-neutral"></span>Neutralnie</span>
          <span><span class="pf-sw pf-limit"></span>Ogranicz</span>
          <span><span class="pf-sw pf-sellsw"></span>Sprzedaj</span>
        </div>
        <div class="pf-strip">${cells}</div>
      </ha-card>`;
  }
}

// Guard against a double load (e.g. a stray manual resource alongside the one the
// integration registers): defining the same element twice throws and would abort
// the second module, leaving the card broken.
if (!customElements.get("dynamiczne-info-card")) {
  customElements.define("dynamiczne-info-card", DynamiczneInfoCard);

  console.info(
    `%c DYNAMICZNE-INFO-CARD %c v${CARD_VERSION} `,
    "color:#fff;background:#0a8f5b;font-weight:600;padding:2px 6px;border-radius:3px 0 0 3px",
    "color:#0a8f5b;background:#04231a;font-weight:600;padding:2px 6px;border-radius:0 3px 3px 0",
  );

  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "dynamiczne-info-card",
    name: "dynamiczne.info Card",
    description: "Godzinowe wskazówki use / limit / sell z dynamiczne.info.",
  });
}

/**
 * dynamiczne.info scheduler card.
 *
 * Interactive companion that drives one "load" (EV charger, boiler, ...): pick a
 * mode and its parameters, toggle the schedule, and see the planned hours
 * highlighted on the price grid. It resolves the load's helper entities from the
 * device registry (config `entity:` = any entity of the load, or `device:` = the
 * load device) and reads the parent tariff's "current price" sensor for the grid.
 *
 * Usage (Lovelace YAML):
 *   type: custom:dynamiczne-info-scheduler-card
 *   entity: sensor.dynamiczne_info_ladowarka_planned_start   # any entity of the load
 */

const SCHED_MODES = {
  cheapest_window: "Najtańsze okno",
  fixed: "Sztywny start",
  price_below: "Poniżej progu ceny",
  advice_use: "Godziny zalecane",
};

const UNAVAIL = ["unknown", "unavailable", ""];

/**
 * The element that truly has focus, piercing shadow roots. `document.activeElement`
 * only reports the outermost shadow host, so a native `<select>` the user has open
 * inside this card (which lives deep in Home Assistant's shadow DOM) is invisible
 * to it. Without this, the "don't clobber the field being edited" guard in
 * `set hass` never matches, every state tick re-renders, and the open dropdown is
 * destroyed before the choice registers (the click appears to "un-click itself").
 */
const deepActiveElement = () => {
  let el = document.activeElement;
  while (el && el.shadowRoot && el.shadowRoot.activeElement) {
    el = el.shadowRoot.activeElement;
  }
  return el;
};

class DynamiczneInfoSchedulerCard extends HTMLElement {
  setConfig(config) {
    // Tolerate an empty config so the visual editor preview can show a hint
    // until a load is picked, instead of throwing.
    this._config = config || {};
  }

  set hass(hass) {
    this._hass = hass;
    // Avoid clobbering a control the user is actively editing (an open <select>
    // dropdown especially). Must pierce shadow DOM: document.activeElement stops
    // at HA's outer shadow host and would never match this card's own <select>,
    // so the guard would be dead and every state tick would destroy the dropdown.
    const a = deepActiveElement();
    if (this.contains(a) && /INPUT|SELECT/.test(a.tagName)) return;
    this._render();
  }

  getCardSize() {
    return 5;
  }

  static getConfigElement() {
    return document.createElement("dynamiczne-info-scheduler-card-editor");
  }

  static getStubConfig(hass) {
    if (hass && hass.devices) {
      const dev = Object.values(hass.devices).find(
        (d) => d.model === "Load scheduler",
      );
      if (dev) return { device: dev.id };
    }
    return {};
  }

  _resolve(hass) {
    const cfg = this._config;
    let deviceId = cfg.device;
    if (!deviceId && cfg.entity && hass.entities && hass.entities[cfg.entity]) {
      deviceId = hass.entities[cfg.entity].device_id;
    }
    const ents = hass.entities ? Object.values(hass.entities) : [];
    const onDevice = deviceId
      ? ents.filter((e) => e.device_id === deviceId)
      : [];
    // Match by translation_key (stable, locale-independent); the entity_id is a
    // slug of the localised name (e.g. select.*_tryb), so suffix matching alone
    // would miss it. Keep the suffix as a fallback for older HA frontends.
    const find = (domain, key) => {
      const hit = onDevice.find(
        (e) =>
          e.entity_id.startsWith(`${domain}.`) &&
          (e.translation_key === key || e.entity_id.endsWith(`_${key}`)),
      );
      return hit ? hit.entity_id : null;
    };
    return {
      deviceId,
      schedule: cfg.schedule_entity || find("switch", "schedule"),
      mode: cfg.mode_entity || find("select", "mode"),
      ready_by: find("time", "ready_by"),
      start_at: find("time", "start_at"),
      stop_at: find("time", "stop_at"),
      duration: find("number", "duration"),
      price_ceiling: find("number", "price_ceiling"),
      run_now: find("binary_sensor", "run_now"),
      planned_start: cfg.planned_entity || find("sensor", "planned_start"),
      price: cfg.price_entity || this._findPrice(hass, deviceId),
    };
  }

  _findPrice(hass, deviceId) {
    const ents = hass.entities ? Object.values(hass.entities) : [];
    const dev = hass.devices && deviceId ? hass.devices[deviceId] : null;
    const parentId = dev && dev.via_device_id;
    if (parentId) {
      const hit = ents.find(
        (e) =>
          e.device_id === parentId &&
          (e.translation_key === "current_price" ||
            e.entity_id.endsWith("_current_price")),
      );
      if (hit) return hit.entity_id;
    }
    for (const id of Object.keys(hass.states)) {
      if (!id.startsWith("sensor.")) continue;
      const att = hass.states[id].attributes;
      if (att && Array.isArray(att.today) && att.thresholds) return id;
    }
    return null;
  }

  _state(entity) {
    return entity ? this._hass.states[entity] : null;
  }

  _timeVal(entity) {
    const s = this._state(entity);
    return s && !UNAVAIL.includes(s.state) ? s.state.slice(0, 5) : "";
  }

  _numVal(entity) {
    const s = this._state(entity);
    return s && Number.isFinite(Number(s.state)) ? s.state : "";
  }

  _fmtPlanned(iso) {
    const t = Date.parse(iso);
    if (Number.isNaN(t)) return "-";
    return new Date(t).toLocaleString([], {
      weekday: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  _timeCtl(label, entity) {
    if (!entity) return "";
    // Fixing is hourly, so minutes are meaningless: offer an hour picker
    // (00:00-23:00) instead of a HH:MM input. The empty option keeps an
    // unset/unknown time showing "--" without forcing a value.
    const curHour = this._timeVal(entity).slice(0, 2);
    const opts = [`<option value=""${curHour ? "" : " selected"}>--</option>`];
    for (let h = 0; h < 24; h++) {
      const hh = String(h).padStart(2, "0");
      opts.push(
        `<option value="${hh}"${hh === curHour ? " selected" : ""}>${hh}:00</option>`,
      );
    }
    return `<label class="pf-ctl"><span>${esc(label)}</span>
      <select class="pf-input" data-entity="${esc(entity)}" data-kind="time">${opts.join("")}</select></label>`;
  }

  _numCtl(label, entity, step, min, max) {
    if (!entity) return "";
    // For a whole-number step (e.g. duration) drop the ".0" the number entity
    // reports, so the field shows "5" not "5,0". The unit lives in the label
    // (no sub-line) so every control aligns on one baseline.
    let val = this._numVal(entity);
    if (val !== "" && Number(step) % 1 === 0) {
      val = String(Math.round(Number(val)));
    }
    return `<label class="pf-ctl"><span>${esc(label)}</span>
      <input class="pf-input" type="number" step="${esc(step)}" min="${esc(min)}" max="${esc(max)}" data-entity="${esc(entity)}" data-kind="number" value="${esc(val)}"></label>`;
  }

  _controls(mode, r) {
    if (mode === "cheapest_window") {
      // "Gotowe do" (by when the load must be done) already bounds the window,
      // so this mode has no separate stop.
      return (
        this._timeCtl("Gotowe do", r.ready_by) +
        this._numCtl("Czas (h)", r.duration, 1, 1, 12)
      );
    }
    if (mode === "fixed") {
      return this._timeCtl("Start o", r.start_at) + this._timeCtl("Stop o", r.stop_at);
    }
    if (mode === "price_below") {
      return (
        this._numCtl("Próg (zł/kWh)", r.price_ceiling, 0.05, 0, 5) +
        this._timeCtl("Stop (opc.)", r.stop_at)
      );
    }
    return this._timeCtl("Stop (opc.)", r.stop_at);
  }

  _grid(r, planned) {
    const priceObj = this._state(r.price);
    // Forward-looking window: the current hour + the next 23 (today, then
    // tomorrow), "?" where data is missing. A load only cares about the buy
    // price, so the sell price is suppressed (showSell:false).
    const slots = priceObj
      ? next24Hours(priceObj.attributes.today, priceObj.attributes.tomorrow)
      : null;
    if (slots === null) {
      return `<div class="pf-counts">Czeka na ceny fixingu...</div>`;
    }
    const sel = new Set(
      (planned && Array.isArray(planned.attributes.selected_hours)
        ? planned.attributes.selected_hours
        : []
      )
        .map((s) => Date.parse(s))
        .filter((n) => !Number.isNaN(n)),
    );
    const cells = slots
      .map((h) => {
        if (!h) return EMPTY_CELL;
        const picked = sel.has(Date.parse(h.startsAt));
        return hourCell(h, {
          extra: picked ? ["pf-picked"] : [],
          showSell: false,
        });
      })
      .join("");
    return `<div class="pf-strip">${cells}</div>`;
  }

  _render() {
    if (!this._hass || !this._config) return;
    const hass = this._hass;
    const r = this._resolve(hass);
    const title = esc(
      this._config.title ||
        (hass.devices && r.deviceId && hass.devices[r.deviceId]
          ? hass.devices[r.deviceId].name_by_user ||
            hass.devices[r.deviceId].name
          : "dynamiczne.info - odbiornik"),
    );

    if (!r.deviceId || !r.mode) {
      this.innerHTML = `<ha-card header="${title}"><div style="padding:16px">Nie znaleziono encji odbiornika. Wskaż <code>entity</code> (np. sensor zaplanowanego startu) albo <code>device</code>.</div></ha-card>`;
      return;
    }

    const modeState = this._state(r.mode);
    const mode =
      modeState && SCHED_MODES[modeState.state]
        ? modeState.state
        : "cheapest_window";
    const enabled = r.schedule
      ? this._state(r.schedule) && this._state(r.schedule).state === "on"
      : true;
    const planned = this._state(r.planned_start);
    const runNow = this._state(r.run_now);
    const running = enabled && runNow && runNow.state === "on";

    const plannedTxt =
      planned && !UNAVAIL.includes(planned.state)
        ? this._fmtPlanned(planned.state)
        : "-";
    const badge = !enabled ? "Wyłączony" : running ? "Działa teraz" : "Bezczynny";
    const badgeCls = running ? "pf-run" : "pf-idle";

    const modeOptions = Object.keys(SCHED_MODES)
      .map(
        (m) =>
          `<option value="${m}"${m === mode ? " selected" : ""}>${esc(SCHED_MODES[m])}</option>`,
      )
      .join("");
    const modeCtl = `<label class="pf-ctl"><span>Tryb</span>
        <select class="pf-input" data-entity="${esc(r.mode)}" data-kind="mode">${modeOptions}</select></label>`;
    const enableCtl = r.schedule
      ? `<label class="pf-ctl pf-enable"><input type="checkbox" data-entity="${esc(r.schedule)}" data-kind="enable"${enabled ? " checked" : ""}><span>Aktywny</span></label>`
      : "";

    this.innerHTML = `
      <ha-card header="${title}">
        <style>
          .pf-head { display:flex; flex-wrap:wrap; gap:.5rem; padding:8px 16px 0; align-items:center; }
          .pf-stat { display:flex; flex-direction:column; border-radius:8px; padding:6px 10px; min-width:6rem; background:rgba(var(--pf-rgb, 144,144,144), .15); color:var(--primary-text-color); }
          .pf-stat-k { font-size:.7rem; text-transform:uppercase; letter-spacing:.04em; color:var(--secondary-text-color); }
          .pf-stat-v { font-weight:700; font-variant-numeric:tabular-nums; font-size:.98rem; }
          .pf-badge { margin-left:auto; font-weight:700; font-size:.82rem; padding:5px 10px; border-radius:999px; }
          .pf-run { color:#fff; background:var(--success-color, #43a047); }
          .pf-idle { color:var(--secondary-text-color); background:rgba(var(--rgb-primary-text-color,120,120,120),.12); }
          .pf-sched { padding:10px 16px 2px; display:flex; flex-wrap:wrap; gap:12px; align-items:flex-end; }
          .pf-ctl { display:flex; flex-direction:column; gap:3px; font-size:.72rem; color:var(--secondary-text-color); }
          .pf-ctl > span { text-transform:uppercase; letter-spacing:.03em; }
          .pf-input { font:inherit; padding:4px 6px; border-radius:6px; border:1px solid var(--divider-color, #ccc); background:var(--card-background-color); color:var(--primary-text-color); box-sizing:border-box; min-height:32px; }
          .pf-enable { flex-direction:row; align-items:center; gap:6px; }
          ${CELL_CSS}
          .pf-counts { padding:10px 16px; font-size:.84rem; color:var(--secondary-text-color); }
        </style>
        <div class="pf-head">
          <div class="pf-stat"><span class="pf-stat-k">Zaplanowany start</span><span class="pf-stat-v">${esc(plannedTxt)}</span></div>
          <span class="pf-badge ${badgeCls}">${esc(badge)}</span>
        </div>
        <div class="pf-sched">${modeCtl}${this._controls(mode, r)}${enableCtl}</div>
        ${this._grid(r, planned)}
      </ha-card>`;

    this.querySelectorAll("[data-entity]").forEach((el) => {
      el.addEventListener("change", () => this._onChange(el));
    });
  }

  _onChange(el) {
    const entity = el.dataset.entity;
    const kind = el.dataset.kind;
    const hass = this._hass;
    // The edit is committed, so release focus. A native <select> keeps focus
    // after a pick, and while it does the `set hass` guard skips every render:
    // a new mode's controls (and the plan grid) would not appear until the user
    // clicked elsewhere *and* some later state change arrived.
    el.blur();
    if (kind === "mode") {
      hass.callService("select", "select_option", {
        entity_id: entity,
        option: el.value,
      });
    } else if (kind === "enable") {
      hass.callService("switch", el.checked ? "turn_on" : "turn_off", {
        entity_id: entity,
      });
    } else if (kind === "time") {
      if (!el.value) return;
      // The control is an hour picker ("HH"); the time entity wants HH:MM:SS.
      const time =
        el.value.length === 2
          ? `${el.value}:00:00`
          : el.value.length === 5
            ? `${el.value}:00`
            : el.value;
      hass.callService("time", "set_value", { entity_id: entity, time });
    } else if (kind === "number") {
      hass.callService("number", "set_value", {
        entity_id: entity,
        value: Number(el.value),
      });
    }
  }
}

if (!customElements.get("dynamiczne-info-scheduler-card")) {
  customElements.define("dynamiczne-info-scheduler-card", DynamiczneInfoSchedulerCard);

  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "dynamiczne-info-scheduler-card",
    name: "dynamiczne.info Scheduler Card",
    description:
      "Harmonogram odbiornika (EV, bojler) sterowany cenami dynamiczne.info.",
  });
}

/**
 * Visual config editors. HA shows these (instead of forcing the YAML editor)
 * because the cards expose static getConfigElement(). Each editor wraps a native
 * ha-form, so the user gets HA's entity/device pickers with no YAML.
 */
class DynamiczneInfoBaseCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = config || {};
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _render() {
    if (!this._hass || !this._config) return;
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.addEventListener("value-changed", (ev) => {
        ev.stopPropagation();
        this.dispatchEvent(
          new CustomEvent("config-changed", {
            detail: { config: ev.detail.value },
            bubbles: true,
            composed: true,
          }),
        );
      });
      this.appendChild(this._form);
    }
    this._form.hass = this._hass;
    this._form.schema = this.SCHEMA;
    this._form.data = this._config;
    this._form.computeLabel = (s) => this.LABELS[s.name] || s.name;
  }
}

class DynamiczneInfoCardEditor extends DynamiczneInfoBaseCardEditor {
  SCHEMA = [
    {
      name: "entity",
      required: true,
      selector: { entity: { integration: "dynamiczne_info", domain: "sensor" } },
    },
    { name: "title", selector: { text: {} } },
  ];
  LABELS = { entity: "Sensor ceny", title: "Tytuł" };
}

class DynamiczneInfoSchedulerCardEditor extends DynamiczneInfoBaseCardEditor {
  SCHEMA = [
    {
      name: "device",
      required: true,
      selector: {
        device: { integration: "dynamiczne_info", model: "Load scheduler" },
      },
    },
    { name: "title", selector: { text: {} } },
  ];
  LABELS = { device: "Odbiornik", title: "Tytuł (opcjonalnie)" };
}

if (!customElements.get("dynamiczne-info-card-editor")) {
  customElements.define("dynamiczne-info-card-editor", DynamiczneInfoCardEditor);
}
if (!customElements.get("dynamiczne-info-scheduler-card-editor")) {
  customElements.define(
    "dynamiczne-info-scheduler-card-editor",
    DynamiczneInfoSchedulerCardEditor,
  );
}
