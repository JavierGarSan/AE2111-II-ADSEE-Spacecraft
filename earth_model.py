"""Mission inputs and a pure adapter around the existing link-budget helpers."""

import math

import main as model


def _parameter(identifier, label, unit, default, minimum, maximum, step, locked,
               **extra):
    return {
        "id": identifier,
        "label": label,
        "unit": unit,
        "default": default,
        "min": minimum,
        "max": maximum,
        "step": step,
        "locked": locked,
        **extra,
    }


# The original order and fixed cells of Table 1, Earth mission column.
CASE_PARAMETERS = [
    _parameter("spacecraft_power_w", "Total spacecraft power", "W",
               850, 100, 10000, 1, True),
    _parameter("spacecraft_transmitter_power_w", "Transmitter power (spacecraft)",
               "W", 150, 1, 10000, 1, False),
    _parameter("ground_transmitter_power_w", "Transmitter power (ground station)",
               "W", 400, 1, 5000, 1, False),
    _parameter("transmitter_loss_factor", "Loss factor transmitter", "−",
               0.8, 0.01, 1, 0.01, False),
    _parameter("receiver_loss_factor", "Loss factor receiver", "−",
               0.7, 0.01, 1, 0.01, False),
    _parameter("downlink_frequency_ghz", "Downlink frequency", "GHz",
               2.2, 0.5, 9, 0.01, False, note="Default: S band"),
    _parameter("turnaround_ratio", "Turn around ratio (uplink/downlink frequency)",
               "−", 221 / 240, 0.8, 1.2, 0.0001, False,
               display="221/240"),
    _parameter("spacecraft_antenna_diameter_m",
               "Antenna diameter spacecraft (parabolic antenna)", "m",
               1, 0.1, 10, 0.1, True),
    _parameter("ground_antenna_diameter_m",
               "Antenna diameter ground station (parabolic antenna)", "m",
               15, 1, 70, 0.1, True),
    _parameter("orbit_altitude_km", "Orbit altitude", "km",
               820, 1, 5000, 1, True),
    _parameter("elongation_angle_deg",  
               "Elongation angle (spacecraft–Sun line and Earth–Sun line)", "deg",
               None, 0, 180, 1, True, display="N/A"),
    _parameter("spacecraft_pointing_offset_deg", "Pointing offset angle (spacecraft)",
               "deg", 0.12, 0, 1, 0.01, True),
    _parameter("required_uplink_rate_bps", "Required uplink data rate", "bit/s",
               100_000_000, 10_000, 1_000_000_000, 10_000, True),
    _parameter("payload_swath_deg", "Payload swath width angle", "deg",
               45, 0.1, 45, 0.1, True),
    _parameter("payload_pixel_arcmin", "Payload pixel size", "arcmin",
               0.01, 0.001, 1, 0.001, True),
    _parameter("payload_bits_per_pixel", "Payload bits per pixel", "bits/pixel",
               32, 1, 64, 1, True),
    _parameter("payload_duty_cycle_percent", "Payload duty cycle", "%",
               100, 0, 100, 1, True),
    _parameter("payload_downlink_hours", "Payload downlink time", "hr/day",
               0.5, 0.1, 24, 0.1, True),
    _parameter("coding", "Channel coding", "−", "uncoded", 0, 1, 1,
               True, choices=["uncoded", "ldpc"]),
    _parameter("required_ber", "Required BER", "−",
               1e-6, 1e-9, 1e-3, 1e-9, True),
]


# These quantities are absent from the case table. They are explicit model
# assumptions, separate from the transmitter and receiver cable loss factors.
ANTENNA_EFFICIENCY = 0.6
MINIMUM_ELEVATION_DEG = 20.0
SPACECRAFT_ANTENNA_NOISE_K = 290.0
GROUND_ANTENNA_NOISE_K = 100.0
RECEIVER_NOISE_FIGURE_DB = 2.0
CABLE_PHYSICAL_K = 290.0
GROUND_POINTING_OFFSET_DEG = 0.05
DEFAULT_MODULATION = "4-QAM"
MODULATION_OPTIONS = ["4-QAM", "64-QAM"]
ENCODING_OPTIONS = ["uncoded", "ldpc"]
DEFAULT_PLANET = "earth"
PLANET_OPTIONS = [
    {"id": "earth", "label": "Earth"},
    {"id": "moon", "label": "Moon"},
    {"id": "mars", "label": "Mars"},
    {"id": "venus", "label": "Venus"},
    {"id": "mercury", "label": "Mercury"},
]


def _mission_template(identifier, label, planet, row_values, locked_ids):
    """Store the supplied case table in its original row order."""
    if len(row_values) != len(CASE_PARAMETERS):
        raise ValueError("A mission template must specify every table row.")
    return {
        "id": identifier,
        "label": label,
        "planet": planet,
        "values": {entry["id"]: value for entry, value in zip(CASE_PARAMETERS, row_values)},
        "locks": {entry["id"]: entry["id"] in locked_ids for entry in CASE_PARAMETERS},
    }


DEFAULT_TEMPLATE = "case_1"
# Values and initial locks follow the user's supplied case-table image.
# Template modulation is left to the separate 4-QAM/64-QAM selector.
MISSION_TEMPLATES = [
    _mission_template("case_1", "Case 1 - Earth LEO", "earth", [
        850, 150, 400, 0.8, 0.7, 2.2, 221 / 240, 1, 15, 820, None, 0.12,
        1e8, 45, 0.01, 32, 100, 0.5, "uncoded", 1e-6,
    ], {entry["id"] for entry in CASE_PARAMETERS if entry["locked"]}),
    _mission_template("case_2", "Case 2 - Moon LRO", "moon", [
        400, 50, 1000, 0.8, 0.7, 2.4, 221 / 240, 0.3, 15, 50, None, 0.02,
        1e8, 6, 0.07, 8, 100, 1, "uncoded", 1e-6,
    ], {"spacecraft_power_w", "downlink_frequency_ghz", "turnaround_ratio",
        "orbit_altitude_km", "elongation_angle_deg", "required_uplink_rate_bps",
         "required_ber","payload_bits_per_pixel", "payload_downlink_hours","payload_pixel_arcmin"}),
    _mission_template("case_3", "Case 3 - Mars Hope", "mars", [
        1800, 400, 1000, 0.8, 0.7, 8.4, 749 / 880, 2, 34, 1000, 20, 0.1,
        1e6, 5, 0.01, 8, 50, 18, "uncoded", 1e-6,
    ], {"spacecraft_power_w", "downlink_frequency_ghz", "turnaround_ratio",
         "elongation_angle_deg",
         "required_uplink_rate_bps",
        "payload_swath_deg", "payload_duty_cycle_percent",
        "payload_downlink_hours", "required_ber","orbit_altitude_km","payload_bits_per_pixel"}),
    _mission_template("case_4", "Case 4 - Mars MRO", "mars", [
        2000, 100, 1000, 0.8, 0.7, 8.4, 749 / 880, 3, 35, 300, 150, 0.05,
        1e6, 0.5, 0.05, 8, 10, 12, "uncoded", 1e-6,
    ], {"spacecraft_power_w", "downlink_frequency_ghz", "turnaround_ratio",
        "spacecraft_antenna_diameter_m",
        "elongation_angle_deg", "required_uplink_rate_bps", "payload_pixel_arcmin",
        "required_ber","payload_bits_per_pixel", "payload_downlink_hours"}),
    _mission_template("case_5", "Case 5 - Mercury Bepi. C", "mercury", [
        1000, 200, 1000, 0.8, 0.7, 8.4, 749 / 880, 1, 35, 500, 10, 0.05,
        1e5, 10, 0.05, 8, 40, 18, "uncoded", 1e-6,
    ], {"spacecraft_power_w", "downlink_frequency_ghz", "turnaround_ratio",
        "spacecraft_antenna_diameter_m",
        "elongation_angle_deg", "required_uplink_rate_bps",
        "required_ber","payload_bits_per_pixel","ground_antenna_diameter_m"}),
]

# Radii and gravitational parameters are from NASA/JPL. Earth retains the
# original 6371 km radius so the established Earth result stays unchanged.
# Sources: https://ssd.jpl.nasa.gov/astro_par.html
# https://ssd.jpl.nasa.gov/planets/phys_par.html
# https://science.nasa.gov/moon/facts/
# https://science.nasa.gov/mars/facts/
# https://science.nasa.gov/venus/venus-facts/
# Remote ranges use rounded mean distances, rather than live ephemerides.
PLANET_CONSTANTS = {
    "earth": {"radius_km": model.earthRadius, "mu_km3_s2": model.earth_mu},
    "moon": {"radius_km": 1740.0, "mu_km3_s2": 4902.800118,
             "earth_distance_km": 384400.0},
    "mars": {"radius_km": 3389.5, "mu_km3_s2": 42828.375816,
             "sun_distance_km": 228000000.0},
    "venus": {"radius_km": 6051.8, "mu_km3_s2": 324858.592000,
              "sun_distance_km": 108000000.0},
    "mercury": {"radius_km": model.mercury_radius, "mu_km3_s2": 22031.868551,
                "sun_distance_km": model.mercury_orbit_altitude},
}

ASSUMPTIONS = [
    "Payload scan speed is approximated by circular-orbit speed, neglecting "
    "the orbital-versus-ground velocity difference as permitted by the "
    "assignment. Pixels per line use the angular swath/pixel ratio.",
    "Minimum ground-station elevation: 20 degrees.",
    "Parabolic antenna radiation efficiency: 0.6 for both antennas.",
    "Antenna noise temperature: spacecraft 290 K; ground station 100 K.",
    "Receiver noise figure: 2 dB for both receivers; cable and reference "
    "temperatures: 290 K.",
    "Ground-station pointing offset: 0 degrees; spacecraft pointing offset "
    "uses the selected cell value.",
    "Atmospheric and rain attenuation use the existing model's simplified "
    "frequency bands; antenna noise temperatures stay constant.",
    "The selected Gray-coded square QAM applies to both links in an AWGN "
    "channel. 4-QAM uses the exact BER expression; 64-QAM uses its low-BER "
    "nearest-neighbour approximation.",
    "Eb/N0 is per information bit; encoded channel rate is shown separately. "
    "The existing LDPC model uses code rate 3/4 and a 10 dB coding gain.",
    "Minimum passband bandwidth is symbol rate at ideal zero pulse-shaping "
    "roll-off. Actual occupied bandwidth is larger for nonzero roll-off; "
    "available channel bandwidth is unspecified.",
]


def validate_inputs(overrides=None):
    """Merge input updates and validate values; locks are dashboard UI state."""
    if overrides is None:
        overrides = {}
    if not isinstance(overrides, dict):
        raise ValueError("Inputs must be an object containing case parameter values.")

    parameters = {entry["id"]: entry for entry in CASE_PARAMETERS}
    unknown = set(overrides) - set(parameters) - {"modulation", "planet"}
    if unknown:
        raise ValueError("Unknown case parameter: " + ", ".join(sorted(unknown)))

    modulation = overrides.get("modulation", DEFAULT_MODULATION)
    if not isinstance(modulation, str) or modulation not in MODULATION_OPTIONS:
        raise ValueError("Modulation must be '4-QAM' or '64-QAM'.")
    planet = overrides.get("planet", DEFAULT_PLANET)
    if not isinstance(planet, str) or planet not in PLANET_CONSTANTS:
        raise ValueError("Planet must be 'earth', 'moon', 'mars', 'venus', or 'mercury'.")
    result = {"modulation": modulation, "planet": planet}
    for identifier, entry in parameters.items():
        value = overrides.get(identifier, entry["default"])
        if identifier == "coding":
            if not isinstance(value, str) or value not in ENCODING_OPTIONS:
                raise ValueError("Encoding must be 'uncoded' or 'ldpc'.")
            result[identifier] = value
            continue
        if identifier == "elongation_angle_deg" and value is None:
            result[identifier] = None
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{entry['label']} must be a number.")
        if not math.isfinite(value):
            raise ValueError(f"{entry['label']} must be finite.")
        if not entry["min"] <= value <= entry["max"]:
            raise ValueError(
                f"{entry['label']} must be between {entry['min']} and {entry['max']}."
            )
        if identifier == "payload_bits_per_pixel" and value != int(value):
            raise ValueError("Payload bits per pixel must be a whole number.")
        result[identifier] = value

    # Both frequencies must fit the existing rain-attenuation helper's domain.
    if result["downlink_frequency_ghz"] * result["turnaround_ratio"] >= 12:
        raise ValueError("Uplink frequency must be below 12 GHz.")
    if result["spacecraft_transmitter_power_w"] > result["spacecraft_power_w"]:
        raise ValueError("Spacecraft transmitter power exceeds total spacecraft power.")
    return result


def _link_budget(inputs, direction, frequency_ghz, information_rate_bps,
                 slant_range_km):
    wavelength_m = model.c / (frequency_ghz * 1e9)
    spacecraft_gain = model.antenna_gain(
        ANTENNA_EFFICIENCY, inputs["spacecraft_antenna_diameter_m"], wavelength_m
    )
    ground_gain = model.antenna_gain(
        ANTENNA_EFFICIENCY, inputs["ground_antenna_diameter_m"], wavelength_m
    )
    if direction == "downlink":
        power_w = inputs["spacecraft_transmitter_power_w"]
        transmitter_gain = spacecraft_gain
        receiver_gain = ground_gain
        antenna_noise_k = GROUND_ANTENNA_NOISE_K
    else:
        power_w = inputs["ground_transmitter_power_w"]
        transmitter_gain = ground_gain
        receiver_gain = spacecraft_gain
        antenna_noise_k = SPACECRAFT_ANTENNA_NOISE_K

    transmitter_loss_db = -model.n_dB(inputs["transmitter_loss_factor"])
    eirp_dbw = model.n_dB(power_w) + transmitter_gain - transmitter_loss_db
    # All loss helpers and budget fields use positive attenuation magnitudes.
    free_space_loss_db = model.freespaceloss(slant_range_km * 1000, wavelength_m)
    atmospheric_loss_db = model.atmospheric_attenuation_noise(frequency_ghz * 1e9)
    rain_loss_db = model.rain_attenuation_noise(frequency_ghz * 1e9)
    spacecraft_pointing_loss_db = model.pointing_angle_loss(
        frequency_ghz, inputs["spacecraft_antenna_diameter_m"],
        inputs["spacecraft_pointing_offset_deg"],        
    )
    ground_pointing_loss_db = model.pointing_angle_loss(
        frequency_ghz, inputs["ground_antenna_diameter_m"],
        GROUND_POINTING_OFFSET_DEG,
    )
    other_losses_db = (
        atmospheric_loss_db + rain_loss_db + spacecraft_pointing_loss_db
        + ground_pointing_loss_db
    )
    receiver = model.receiver_noise_and_gt(
        receiver_gain, antenna_noise_k, RECEIVER_NOISE_FIGURE_DB,
        receiver_loss_factor=inputs["receiver_loss_factor"],
        cable_physical_k=CABLE_PHYSICAL_K,
    )
    # G/T is referred to the antenna terminals, so the receive cable loss is
    # already reflected in receiver noise and must not be subtracted again.
    modulation_order = 4 if inputs["modulation"] == "4-QAM" else 64
    bits_per_symbol = int(math.log2(modulation_order))
    required_eb_n0_db = model.required_eb_n0(
        inputs["required_ber"], inputs["coding"], inputs["modulation"]
    )
    if information_rate_bps > 0:
        available_eb_n0_db = model.energy_per_bit(
            eirp_dbw, free_space_loss_db, other_losses_db,
            receiver["g_over_t_db_per_k"], information_rate_bps,
        )
        carrier_to_noise_density_db_hz = (
            available_eb_n0_db + model.n_dB(information_rate_bps)
        )
        margin_db = model.link_margin(available_eb_n0_db, required_eb_n0_db)
    else:
        # With no information bits there is no Eb/N0 or margin. C/N0 is still
        # a valid rate-independent property of the assumed radio link.
        available_eb_n0_db = None
        margin_db = None
        carrier_to_noise_density_db_hz = (
            eirp_dbw - free_space_loss_db - other_losses_db
            + receiver["g_over_t_db_per_k"] - model.n_dB(model.k_b)
        )
    channel_rate_bps = model.transmitted_bit_rate(information_rate_bps, inputs["coding"])
    symbol_rate_baud = channel_rate_bps / bits_per_symbol
    return {
        "frequency_ghz": frequency_ghz,
        "information_rate_bps": information_rate_bps,
        "transmitted_rate_bps": channel_rate_bps,
        "modulation_order": modulation_order,
        "bits_per_symbol": bits_per_symbol,
        "symbol_rate_baud": symbol_rate_baud,
        "minimum_passband_bandwidth_hz": symbol_rate_baud,
        "transmitter_power_w": power_w,
        "transmitter_gain_dbi": transmitter_gain,
        "receiver_gain_dbi": receiver_gain,
        "transmitter_loss_db": transmitter_loss_db,
        "eirp_dbw": eirp_dbw,
        "free_space_loss_db": free_space_loss_db,
        "atmospheric_loss_db": atmospheric_loss_db,
        "rain_loss_db": rain_loss_db,
        "spacecraft_pointing_loss_db": spacecraft_pointing_loss_db,
        "ground_pointing_loss_db": ground_pointing_loss_db,
        "other_losses_db": other_losses_db,
        "antenna_noise_k": antenna_noise_k,
        **receiver,
        "available_eb_n0_db": available_eb_n0_db,
        "carrier_to_noise_density_db_hz": carrier_to_noise_density_db_hz,
        "required_eb_n0_db": required_eb_n0_db,
        "margin_db": margin_db,
    }


def _range_geometry(inputs):
    """Return an Earth-station range and disclose the remote-body approximation."""
    planet = inputs["planet"]
    if planet == "earth":
        return {
            "slant_range_km": model.distance_earth_orbit(
                inputs["orbit_altitude_km"], math.radians(MINIMUM_ELEVATION_DEG)
            ),
            "range_method": "Earth ground-station slant range at 20-degree elevation",
            "effective_elongation_deg": None,
        }
    if planet == "moon":
        return {
            "slant_range_km": PLANET_CONSTANTS[planet]["earth_distance_km"],
            "range_method": "Mean Earth-Moon centre distance approximation",
            "effective_elongation_deg": None,
        }
    elongation = inputs["elongation_angle_deg"]
    effective_elongation = 180.0 if elongation is None else elongation
    sun_distance_km = PLANET_CONSTANTS[planet]["sun_distance_km"]
    # The case table's angle is between spacecraft-Sun and Earth-Sun lines:
    # it is the central angle at the Sun, not apparent elongation at Earth.
    centre_distance_km = math.sqrt(
        model.AU**2 + sun_distance_km**2
        - 2 * model.AU * sun_distance_km
        * math.cos(math.radians(effective_elongation))
    )
    return {
        "slant_range_km": centre_distance_km,
        "range_method": "Circular heliocentric orbits; Earth-body centre distance approximation",
        "effective_elongation_deg": effective_elongation,
    }


def calculate_scenario(overrides=None):
    """Calculate links for the chosen body without replacing the user's inputs."""
    inputs = validate_inputs(overrides)
    planet = inputs["planet"]
    planet_label = next(entry["label"] for entry in PLANET_OPTIONS if entry["id"] == planet)
    constants = PLANET_CONSTANTS[planet]
    altitude_km = inputs["orbit_altitude_km"]
    geometry = _range_geometry(inputs)
    slant_range_km = geometry["slant_range_km"]
    active_rate_bps = model.payload_data_rate(
        altitude_km, inputs["payload_swath_deg"], inputs["payload_pixel_arcmin"],
        inputs["payload_bits_per_pixel"], constants["radius_km"], constants["mu_km3_s2"],
    )
    scan_speed_m_s = model.orbital_speed(
        altitude_km, constants["radius_km"], constants["mu_km3_s2"]
    )
    daily_data_bits = model.daily_data_generated(
        active_rate_bps, inputs["payload_duty_cycle_percent"]
    )
    downlink_rate_bps = model.required_downlink_rate(
        daily_data_bits, inputs["payload_downlink_hours"]
    )
    downlink_frequency_ghz = inputs["downlink_frequency_ghz"]
    # Table 1 explicitly defines turnaround ratio as uplink/downlink frequency.
    uplink_frequency_ghz = downlink_frequency_ghz * inputs["turnaround_ratio"]
    uplink = _link_budget(
        inputs, "uplink", uplink_frequency_ghz,
        inputs["required_uplink_rate_bps"], slant_range_km,
    )
    downlink = _link_budget(
        inputs, "downlink", downlink_frequency_ghz,
        downlink_rate_bps, slant_range_km,
    )
    warnings = [
        "Margins check Eb/N0 only. Available channel bandwidth, modem "
        "capability and amplifier DC efficiency have not been specified."
    ]
    if planet != "earth":
        warnings.append(
            "The ground station remains on Earth. Remote range is approximated "
            "by centre-to-centre distance; spacecraft orbital phase, station "
            "position, body occultation, solar conjunction and contact "
            "availability are not calculated."
        )
    if planet in ("mars", "venus", "mercury") and inputs["elongation_angle_deg"] is None:
        warnings.append(
            "Elongation is unset. The range calculation uses a conservative "
            "180-degree angle at the Sun without changing the input. Unlock "
            "the elongation cell to set an angle. This maximum-range geometry "
            "does not establish a clear line of sight past the Sun."
        )
    if downlink_rate_bps == 0:
        warnings.append(
            "The 0% payload duty cycle generates no downlink data. Downlink "
            "Eb/N0 and margin are therefore not applicable."
        )
    if downlink["minimum_passband_bandwidth_hz"] >= 2 * downlink_frequency_ghz * 1e9:
        warnings.append(
            "The downlink needs at least "
            f"{downlink['minimum_passband_bandwidth_hz'] / 1e9:.2f} GHz of "
            f"passband bandwidth for {inputs['modulation']} at ideal zero roll-off. This "
            "exceeds twice the carrier frequency: the assumed single-carrier "
            "S/X-band link cannot carry this payload rate, even if its "
            "calculated Eb/N0 margin is positive."
        )
    return {
        "scenario": planet,
        "planet_label": planet_label,
        "modulation": inputs["modulation"],
        "encoding": inputs["coding"],
        "inputs": inputs,
        "geometry": {
            **geometry,
            "orbiting_body": planet,
            "orbiting_body_label": planet_label,
            "planet_radius_km": constants["radius_km"],
            "planet_mu_km3_s2": constants["mu_km3_s2"],
            "minimum_elevation_deg": MINIMUM_ELEVATION_DEG,
            "uplink_frequency_ghz": uplink_frequency_ghz,
            "downlink_frequency_ghz": downlink_frequency_ghz,
        },
        "payload": {
            "orbital_speed_m_s": scan_speed_m_s,
            "scan_speed_m_s": scan_speed_m_s,
            "active_rate_bps": active_rate_bps,
            "daily_data_bits": daily_data_bits,
            "daily_data_tb": daily_data_bits / 8 / 1e12,
            "required_downlink_rate_bps": downlink_rate_bps,
            "ground_pixel_size_m": model.ground_pixel_size(
                altitude_km, inputs["payload_pixel_arcmin"]
            ),
            "pixels_per_line": model.pixels_per_line(
                inputs["payload_swath_deg"], inputs["payload_pixel_arcmin"]
            ),
        },
        "uplink": uplink,
        "downlink": downlink,
        "warnings": warnings,
        "assumptions": [
            f"Circular {planet_label} orbit; spherical, non-rotating body; "
            "nadir line-scanning payload with no compression or packet overhead.",
            *ASSUMPTIONS,
            f"Selected modulation: {inputs['modulation']} "
            f"({downlink['bits_per_symbol']} bits per symbol) for both links.",
            f"Selected channel encoding: {inputs['coding']} for both links. "
            + ("Code rate is 1; coding gain is 0 dB." if inputs["coding"] == "uncoded"
               else "The existing model assumes code rate 3/4 and 10 dB coding "
                    "gain; no particular code or measured BER curve is specified."),
            f"The {inputs['spacecraft_power_w']:g} W total is an upper bound "
            "on RF output only. Amplifier DC efficiency and other subsystem "
            "loads are unspecified; electrical power feasibility is not established.",
            f"Range model: {geometry['range_method']}. The ground station is on Earth.",
            "Body gravity parameters: https://ssd.jpl.nasa.gov/astro_par.html. "
            "Planet radii: https://ssd.jpl.nasa.gov/planets/phys_par.html. "
            "Rounded lunar radius and distance: https://science.nasa.gov/moon/facts/.",
            "Circular heliocentric orbit radii are rounded mean distances: "
            "Earth 1 AU, Mars 228 million km and Venus 108 million km. "
            "Sources: https://science.nasa.gov/mars/facts/ and "
            "https://science.nasa.gov/venus/venus-facts/. The elongation input "
            "is the angle at the Sun between Earth-Sun and spacecraft-Sun lines.",
            *(["Mercury retains the original model's 2440.5 km radius and "
               "46 million km perihelion distance for the simplified range. "
               "Its gravity parameter is from JPL; this fixed distance "
               "does not model Mercury's eccentric orbit. Mercury facts: "
               "https://nssdc.gsfc.nasa.gov/planetary/factsheet/mercuryfact.html."] if planet == "mercury" else []),
        ],
    }


def calculate_earth(overrides=None):
    """Keep the CLI-compatible Earth entry point; new callers use scenario."""
    if overrides is not None and isinstance(overrides, dict):
        if overrides.get("planet", DEFAULT_PLANET) != DEFAULT_PLANET:
            raise ValueError("calculate_earth supports Earth only; use calculate_scenario.")
    return calculate_scenario(overrides)
