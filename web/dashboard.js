"use strict";

const controls = document.querySelector("#parameters");
const statusText = document.querySelector("#status");
const errorText = document.querySelector("#error");
const resetButton = document.querySelector("#reset");
const modulationSelector = document.querySelector("#modulation");
const encodingSelector = document.querySelector("#encoding");
const planetSelector = document.querySelector("#planet");
const templateSelector = document.querySelector("#templates");
let defaultModulation;
let defaultEncoding;
let planets = [];
let templates = [];
let baselineTemplate;
let parameters = [];
let values = {};
let locks = {};
let timer;
let requestNumber = 0;
let activeRequest;

function scheduleRecalculation() {
  statusText.textContent = "Recalculating...";
  // Invalidate any older response as soon as an input changes.
  requestNumber += 1;
  activeRequest?.abort();
  clearTimeout(timer);
  timer = setTimeout(recalculate, 120);
}

function numberText(value, digits = 3) {
  if (value === null || value === undefined || !Number.isFinite(value)) return "--";
  if (value !== 0 && (Math.abs(value) >= 1000000 || Math.abs(value) < 0.001)) {
    return value.toExponential(2);
  }
  return value.toLocaleString("en-GB", { maximumFractionDigits: digits });
}

function encodingText(encoding) {
  return { uncoded: "Uncoded", ldpc: "LDPC (rate 3/4)" }[encoding] || encoding;
}

function selectedPlanetLabel() {
  return planets.find(planet => planet.id === values.planet)?.label || "Earth";
}

function updatePlanetHeading() {
  const label = selectedPlanetLabel();
  document.title = `Spacecraft homework - ${label} orbit`;
  document.querySelector("#scenario-heading").textContent = `AE2111-II homework tool / ${label} orbit`;
  controls.setAttribute("aria-label", `${label} orbit parameters`);
}

function inputText(parameter, value) {
  if (parameter.id === "turnaround_ratio" && value === 749 / 880) return "749/880";
  if (parameter.display && value === parameter.default) return parameter.display;
  if (value === null) return "N/A";
  if (typeof value === "string") return value;
  return numberText(value, parameter.id === "turnaround_ratio" ? 6 : 4);
}

function setOutput(parameter) {
  const output = document.querySelector(`#value-${parameter.id}`);
  const text = inputText(parameter, values[parameter.id]);
  output.textContent = `${text}${parameter.unit && text !== "N/A" ? ` ${parameter.unit}` : ""}`;
  document.querySelector(`#slider-${parameter.id}`).setAttribute("aria-valuetext", output.textContent);
}

function setSliderValue(parameter) {
  const slider = document.querySelector(`#slider-${parameter.id}`);
  slider.value = parameter.choices ? parameter.choices.indexOf(values[parameter.id]) : (values[parameter.id] ?? 0);
  setOutput(parameter);
}

function setLock(parameter) {
  const locked = locks[parameter.id];
  document.querySelector(`#card-${parameter.id}`).classList.toggle("fixed", locked);
  document.querySelector(`#slider-${parameter.id}`).disabled = locked;
  document.querySelector(`#note-${parameter.id}`).textContent = locked ? "Locked" : "Adjustable";
  const button = document.querySelector(`#lock-${parameter.id}`);
  const label = `${locked ? "Unlock" : "Lock"} ${parameter.label}`;
  button.setAttribute("aria-pressed", String(locked));
  button.setAttribute("aria-label", label);
  button.title = label;
  button.querySelector("path").setAttribute("d", locked ? "M8 11V7a4 4 0 0 1 8 0v4" : "M8 11V7a4 4 0 0 1 8 0");
}

function updateTemplateSelection() {
  const matches = baselineTemplate && values.planet === baselineTemplate.planet &&
    parameters.every(parameter => values[parameter.id] === baselineTemplate.values[parameter.id] &&
      locks[parameter.id] === baselineTemplate.locks[parameter.id]);
  templateSelector.value = matches ? baselineTemplate.id : "";
}

function applyTemplate(template) {
  clearTimeout(timer);
  baselineTemplate = template;
  // The table supplies channel coding, while modulation remains a user choice.
  const modulation = values.modulation ?? defaultModulation;
  values = { ...template.values, planet: template.planet, modulation };
  locks = { ...template.locks };
  planetSelector.value = values.planet;
  modulationSelector.value = values.modulation;
  encodingSelector.value = values.coding;
  createControls();
  updatePlanetHeading();
  updateTemplateSelection();
}

function updatePowerBounds() {
  for (const id of ["spacecraft_power_w", "spacecraft_transmitter_power_w"]) {
    const parameter = parameters.find(entry => entry.id === id);
    const slider = document.querySelector(`#slider-${id}`);
    const minimum = id === "spacecraft_power_w" ? Math.max(parameter.min, values.spacecraft_transmitter_power_w) : parameter.min;
    const maximum = id === "spacecraft_transmitter_power_w" ? Math.min(parameter.max, values.spacecraft_power_w) : parameter.max;
    slider.min = minimum;
    slider.max = maximum;
    document.querySelector(`#minimum-${id}`).textContent = numberText(minimum, 4);
    document.querySelector(`#maximum-${id}`).textContent = numberText(maximum, 4);
  }
}

function createControls() {
  controls.replaceChildren();
  for (const parameter of parameters) {
    const card = document.createElement("div");
    card.id = `card-${parameter.id}`;
    card.className = "parameter";
    const heading = document.createElement("div");
    heading.className = "parameter-heading";
    const label = document.createElement("label");
    label.htmlFor = `slider-${parameter.id}`;
    label.textContent = parameter.label;
    const lockButton = document.createElement("button");
    lockButton.type = "button";
    lockButton.id = `lock-${parameter.id}`;
    lockButton.className = "lock-button";
    const icon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    icon.setAttribute("viewBox", "0 0 24 24");
    icon.setAttribute("aria-hidden", "true");
    const shackle = document.createElementNS("http://www.w3.org/2000/svg", "path");
    const lockBody = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    lockBody.setAttribute("x", "5");
    lockBody.setAttribute("y", "11");
    lockBody.setAttribute("width", "14");
    lockBody.setAttribute("height", "10");
    lockBody.setAttribute("rx", "1");
    icon.append(shackle, lockBody);
    lockButton.append(icon);
    lockButton.addEventListener("click", () => {
      locks[parameter.id] = !locks[parameter.id];
      setLock(parameter);
      updateTemplateSelection();
    });
    heading.append(label, lockButton);

    const line = document.createElement("div");
    line.className = "value-line";
    const output = document.createElement("output");
    output.id = `value-${parameter.id}`;
    output.htmlFor = `slider-${parameter.id}`;
    const note = document.createElement("span");
    note.className = "control-note";
    note.id = `note-${parameter.id}`;
    line.append(output, note);

    const slider = document.createElement("input");
    slider.type = "range";
    slider.id = `slider-${parameter.id}`;
    slider.min = parameter.min;
    slider.max = parameter.max;
    slider.step = parameter.step;
    slider.setAttribute("aria-describedby", note.id);
    slider.addEventListener("input", () => {
      values[parameter.id] = parameter.choices ? parameter.choices[Number(slider.value)] : Number(slider.value);
      setOutput(parameter);
      if (parameter.id === "coding") encodingSelector.value = values.coding;
      if (["spacecraft_power_w", "spacecraft_transmitter_power_w"].includes(parameter.id)) updatePowerBounds();
      updateTemplateSelection();
      scheduleRecalculation();
    });

    const limits = document.createElement("div");
    limits.className = "range-limits";
    const min = document.createElement("span");
    const max = document.createElement("span");
    min.id = `minimum-${parameter.id}`;
    max.id = `maximum-${parameter.id}`;
    min.textContent = parameter.choices ? parameter.choices[0] : numberText(parameter.min, 4);
    max.textContent = parameter.choices ? parameter.choices[parameter.choices.length - 1].toUpperCase() : numberText(parameter.max, 4);
    limits.append(min, max);
    card.append(heading, line, slider, limits);
    controls.append(card);
    setSliderValue(parameter);
    setLock(parameter);
  }
  updatePowerBounds();
}

function displayResults(result) {
  for (const direction of ["uplink", "downlink"]) {
    const margin = result[direction].margin_db;
    document.querySelector(`#${direction}-margin`).textContent = margin === null ? "--" : `${numberText(margin, 2)} dB`;
    document.querySelector(`#${direction}-verdict`).textContent = margin === null ? "No downlink data" : margin >= 3 ? "At least 3 dB Eb/N0 margin" : margin >= 0 ? "Less than 3 dB Eb/N0 margin" : "Below required Eb/N0";
  }
  document.querySelector("#downlink-rate").textContent = `${numberText(result.downlink.transmitted_rate_bps)} bit/s`;
  document.querySelector("#downlink-information-rate").textContent = `Payload information: ${numberText(result.downlink.information_rate_bps)} bit/s`;
  document.querySelector("#daily-data").textContent = `${numberText(result.payload.daily_data_tb, 2)} TB`;
  document.querySelector("#active-rate").textContent = `Active camera: ${numberText(result.payload.active_rate_bps)} bit/s`;
  const body = result.planet_label || selectedPlanetLabel();
  const elevation = result.scenario === "earth" ? ` at ${numberText(result.geometry.minimum_elevation_deg)} deg minimum elevation` : "";
  const elongation = ["mars", "venus", "mercury"].includes(result.scenario) ? ` Elongation: ${numberText(result.geometry.effective_elongation_deg)} deg.` : "";
  document.querySelector("#geometry").textContent = `${body} orbit. Ground-station range: ${numberText(result.geometry.slant_range_km, 2)} km${elevation}.${elongation} Ground pixel size: ${numberText(result.payload.ground_pixel_size_m, 2)} m. Payload scan speed: ${numberText(result.payload.scan_speed_m_s, 2)} m/s (orbital-speed approximation).`;

  const rows = [
    ["Frequency", "frequency_ghz", "GHz"],
    ["Information data rate", "information_rate_bps", "bit/s"],
    ["Transmitted data rate", "transmitted_rate_bps", "bit/s"],
    [`Symbol rate (${result.modulation})`, "symbol_rate_baud", "baud"],
    ["Minimum passband bandwidth (zero roll-off)", "minimum_passband_bandwidth_hz", "Hz"],
    ["Transmitter power", "transmitter_power_w", "W"],
    ["Transmitter antenna gain", "transmitter_gain_dbi", "dBi"],
    ["Receiver antenna gain", "receiver_gain_dbi", "dBi"],
    ["Transmitter loss", "transmitter_loss_db", "dB"],
    ["EIRP", "eirp_dbw", "dBW"],
    ["Free-space loss", "free_space_loss_db", "dB"],
    ["Atmospheric loss", "atmospheric_loss_db", "dB"],
    ["Rain loss", "rain_loss_db", "dB"],
    ["Spacecraft pointing loss", "spacecraft_pointing_loss_db", "dB"],
    ["Ground pointing loss", "ground_pointing_loss_db", "dB"],
    ["System noise temperature", "system_noise_k", "K"],
    ["Receiver G/T", "g_over_t_db_per_k", "dB/K"],
    ["Carrier-to-noise density C/N0", "carrier_to_noise_density_db_hz", "dB Hz"],
    ["Available Eb/N0", "available_eb_n0_db", "dB"],
    ["Required Eb/N0", "required_eb_n0_db", "dB"],
    ["Link margin", "margin_db", "dB"]
  ];
  const budget = document.querySelector("#budget");
  budget.replaceChildren();
  for (const [label, key, unit] of rows) {
    const row = document.createElement("tr");
    const heading = document.createElement("th");
    heading.scope = "row";
    heading.textContent = label;
    row.append(heading);
    for (const direction of ["uplink", "downlink"]) {
      const cell = document.createElement("td");
      const value = result[direction][key];
      cell.textContent = value === null || value === undefined ? "--" : `${numberText(value, 3)} ${unit}`;
      row.append(cell);
    }
    budget.append(row);
  }
  const assumptions = document.querySelector("#assumptions");
  assumptions.replaceChildren();
  for (const text of result.assumptions) {
    const item = document.createElement("li");
    item.textContent = text;
    assumptions.append(item);
  }
  const warnings = document.querySelector("#model-warnings");
  warnings.replaceChildren();
  for (const text of result.warnings) {
    const item = document.createElement("li");
    item.textContent = text;
    warnings.append(item);
  }
  document.querySelector("#model-notes").hidden = result.warnings.length === 0;
}

function displayError(error) {
  const retry = parameters.length ? "change an input or reset to retry" : "reload this page to retry";
  errorText.textContent = `${error.message} Check that dashboard.py is still running, then ${retry}.`;
  errorText.hidden = false;
  statusText.textContent = "Results could not be updated. Any visible results are from the previous calculation.";
}

async function recalculate() {
  const currentRequest = ++requestNumber;
  activeRequest?.abort();
  activeRequest = new AbortController();
  try {
    const response = await fetch("/api/calculate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(values),
      signal: activeRequest.signal
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Calculation failed.");
    if (currentRequest !== requestNumber) return;
    displayResults(result);
    errorText.hidden = true;
    statusText.textContent = `Results updated for ${result.planet_label || selectedPlanetLabel()} orbit (${result.modulation}, ${encodingText(result.inputs.coding)}).`;
  } catch (error) {
    if (error.name !== "AbortError" && currentRequest === requestNumber) displayError(error);
  }
}

modulationSelector.addEventListener("change", () => {
  values.modulation = modulationSelector.value;
  scheduleRecalculation();
});

encodingSelector.addEventListener("change", () => {
  values.coding = encodingSelector.value;
  setSliderValue(parameters.find(parameter => parameter.id === "coding"));
  updateTemplateSelection();
  scheduleRecalculation();
});

planetSelector.addEventListener("change", () => {
  values.planet = planetSelector.value;
  updatePlanetHeading();
  updateTemplateSelection();
  scheduleRecalculation();
});

templateSelector.addEventListener("change", () => {
  const template = templates.find(entry => entry.id === templateSelector.value);
  if (!template) return;
  applyTemplate(template);
  scheduleRecalculation();
});

resetButton.addEventListener("click", () => {
  clearTimeout(timer);
  const planet = values.planet;
  values = baselineTemplate ? { ...baselineTemplate.values } : Object.fromEntries(parameters.map(parameter => [parameter.id, parameter.default]));
  values.planet = planet;
  values.modulation = defaultModulation;
  values.coding = baselineTemplate?.values.coding ?? defaultEncoding;
  locks = baselineTemplate ? { ...baselineTemplate.locks } : Object.fromEntries(parameters.map(parameter => [parameter.id, parameter.locked]));
  modulationSelector.value = defaultModulation;
  encodingSelector.value = values.coding;
  createControls();
  updateTemplateSelection();
  statusText.textContent = "Recalculating default inputs...";
  recalculate();
});

async function initialize() {
  try {
    const response = await fetch("/api/config");
    if (!response.ok) throw new Error("Could not load the inputs.");
    const config = await response.json();
    parameters = config.parameters;
    defaultModulation = config.default_modulation;
    defaultEncoding = config.default_encoding;
    planets = config.planets;
    templates = config.templates;
    templateSelector.replaceChildren();
    const customOption = document.createElement("option");
    customOption.value = "";
    customOption.textContent = "Custom inputs";
    templateSelector.append(customOption);
    for (const template of templates) {
      const option = document.createElement("option");
      option.value = template.id;
      option.textContent = template.label;
      templateSelector.append(option);
    }
    modulationSelector.replaceChildren();
    for (const modulation of config.modulations) {
      const option = document.createElement("option");
      option.value = modulation;
      option.textContent = modulation;
      modulationSelector.append(option);
    }
    modulationSelector.value = defaultModulation;
    encodingSelector.replaceChildren();
    for (const encoding of config.encodings) {
      const option = document.createElement("option");
      option.value = encoding;
      option.textContent = encodingText(encoding);
      encodingSelector.append(option);
    }
    encodingSelector.value = defaultEncoding;
    planetSelector.replaceChildren();
    for (const planet of planets) {
      const option = document.createElement("option");
      option.value = planet.id;
      option.textContent = planet.label;
      planetSelector.append(option);
    }
    planetSelector.value = config.default_planet;
    values = Object.fromEntries(parameters.map(parameter => [parameter.id, parameter.default]));
    values.planet = config.default_planet;
    values.modulation = defaultModulation;
    values.coding = defaultEncoding;
    locks = Object.fromEntries(parameters.map(parameter => [parameter.id, parameter.locked]));
    applyTemplate(templates.find(template => template.id === config.default_template));
    resetButton.disabled = false;
    modulationSelector.disabled = false;
    encodingSelector.disabled = false;
    planetSelector.disabled = false;
    templateSelector.disabled = false;
    await recalculate();
  } catch (error) {
    displayError(error);
  }
}

initialize();
