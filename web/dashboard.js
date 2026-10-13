"use strict";

const controls = document.querySelector("#parameters");
const statusText = document.querySelector("#status");
const errorText = document.querySelector("#error");
const resetButton = document.querySelector("#reset");
const modulationSelector = document.querySelector("#modulation");
let defaultModulation;
let parameters = [];
let values = {};
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
  if (value === null || value === undefined) return "--";
  if (value !== 0 && (Math.abs(value) >= 1000000 || Math.abs(value) < 0.001)) {
    return value.toExponential(2);
  }
  return value.toLocaleString("en-GB", { maximumFractionDigits: digits });
}

function inputText(parameter, value) {
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

function createControls() {
  controls.replaceChildren();
  for (const parameter of parameters) {
    const card = document.createElement("div");
    card.className = `parameter${parameter.locked ? " fixed" : ""}`;
    const label = document.createElement("label");
    label.htmlFor = `slider-${parameter.id}`;
    label.textContent = parameter.label;

    const line = document.createElement("div");
    line.className = "value-line";
    const output = document.createElement("output");
    output.id = `value-${parameter.id}`;
    output.htmlFor = `slider-${parameter.id}`;
    const note = document.createElement("span");
    note.className = "control-note";
    note.id = `note-${parameter.id}`;
    note.textContent = parameter.locked ? "Fixed" : "Adjustable";
    line.append(output, note);

    const slider = document.createElement("input");
    slider.type = "range";
    slider.id = `slider-${parameter.id}`;
    slider.min = parameter.min;
    slider.max = parameter.max;
    slider.step = parameter.step;
    slider.disabled = parameter.locked;
    slider.setAttribute("aria-describedby", note.id);
    slider.value = parameter.choices ? parameter.choices.indexOf(parameter.default) : (parameter.default ?? 0);
    slider.addEventListener("input", () => {
      values[parameter.id] = parameter.choices ? parameter.choices[Number(slider.value)] : Number(slider.value);
      setOutput(parameter);
      scheduleRecalculation();
    });

    const limits = document.createElement("div");
    limits.className = "range-limits";
    if (parameter.locked) {
      limits.textContent = "Red cell in the assignment";
    } else {
      const min = document.createElement("span");
      const max = document.createElement("span");
      min.textContent = numberText(parameter.min, 4);
      max.textContent = numberText(parameter.max, 4);
      limits.append(min, max);
    }
    card.append(label, line, slider, limits);
    controls.append(card);
    setOutput(parameter);
  }
}

function displayResults(result) {
  for (const direction of ["uplink", "downlink"]) {
    const margin = result[direction].margin_db;
    document.querySelector(`#${direction}-margin`).textContent = `${numberText(margin, 2)} dB`;
    document.querySelector(`#${direction}-verdict`).textContent = margin >= 3 ? "At least 3 dB Eb/N0 margin" : margin >= 0 ? "Less than 3 dB Eb/N0 margin" : "Below required Eb/N0";
  }
  document.querySelector("#downlink-rate").textContent = `${numberText(result.payload.required_downlink_rate_bps)} bit/s`;
  document.querySelector("#daily-data").textContent = `${numberText(result.payload.daily_data_tb, 2)} TB`;
  document.querySelector("#active-rate").textContent = `Active camera: ${numberText(result.payload.active_rate_bps)} bit/s`;
  document.querySelector("#geometry").textContent = `Slant range: ${numberText(result.geometry.slant_range_km, 2)} km at ${result.geometry.minimum_elevation_deg} deg minimum elevation. Ground pixel size: ${numberText(result.payload.ground_pixel_size_m, 2)} m.`;

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
      cell.textContent = `${numberText(result[direction][key], 3)} ${unit}`;
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
  const retry = parameters.length ? "change a slider or modulation, or reset to retry" : "reload this page to retry";
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
    statusText.textContent = `Results updated for the Earth case (${result.modulation}).`;
  } catch (error) {
    if (error.name !== "AbortError" && currentRequest === requestNumber) displayError(error);
  }
}

modulationSelector.addEventListener("change", () => {
  values.modulation = modulationSelector.value;
  scheduleRecalculation();
});

resetButton.addEventListener("click", () => {
  clearTimeout(timer);
  values = Object.fromEntries(parameters.map(parameter => [parameter.id, parameter.default]));
  values.modulation = defaultModulation;
  modulationSelector.value = defaultModulation;
  createControls();
  statusText.textContent = "Recalculating Earth defaults...";
  recalculate();
});

async function initialize() {
  try {
    const response = await fetch("/api/config");
    if (!response.ok) throw new Error("Could not load the Earth inputs.");
    const config = await response.json();
    parameters = config.parameters;
    defaultModulation = config.default_modulation;
    modulationSelector.replaceChildren();
    for (const modulation of config.modulations) {
      const option = document.createElement("option");
      option.value = modulation;
      option.textContent = modulation;
      modulationSelector.append(option);
    }
    modulationSelector.value = defaultModulation;
    values = Object.fromEntries(parameters.map(parameter => [parameter.id, parameter.default]));
    values.modulation = defaultModulation;
    createControls();
    resetButton.disabled = false;
    modulationSelector.disabled = false;
    await recalculate();
  } catch (error) {
    displayError(error);
  }
}

initialize();
