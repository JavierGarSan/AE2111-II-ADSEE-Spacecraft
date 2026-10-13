"""Earth case inputs and a pure adapter around the existing link-budget helpers."""

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
               850, 100, 2000, 1, True),
    _parameter("spacecraft_transmitter_power_w", "Transmitter power (spacecraft)",
               "W", 150, 1, 850, 1, False),
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
               15, 1, 30, 0.1, True),
    _parameter("orbit_altitude_km", "Orbit altitude", "km",
               820, 100, 2000, 1, True),
    _parameter("elongation_angle_deg",
               "Elongation angle (spacecraft–Sun line and Earth–Sun line)", "deg",
               None, 0, 180, 1, True, display="N/A"),
    _parameter("spacecraft_pointing_offset_deg", "Pointing offset angle (spacecraft)",
               "deg", 0.12, 0, 1, 0.01, True),
    _parameter("required_uplink_rate_bps", "Required uplink data rate", "bit/s",
               100_000_000, 1_000_000, 1_000_000_000, 1_000_000, True),
    _parameter("payload_swath_deg", "Payload swath width angle", "deg",
               45, 1, 90, 1, True),
    _parameter("payload_pixel_arcmin", "Payload pixel size", "arcmin",
               0.01, 0.001, 1, 0.001, True),
    _parameter("payload_bits_per_pixel", "Payload bits per pixel", "bits/pixel",
               32, 1, 64, 1, True),
    _parameter("payload_duty_cycle_percent", "Payload duty cycle", "%",
               100, 0, 100, 1, True),
    _parameter("payload_downlink_hours", "Payload downlink time", "hr/day",
               0.5, 0.1, 24, 0.1, True),
    _parameter("coding", "Modulation/coding type", "−", "uncoded", 0, 2, 1,
               True, choices=["uncoded", "coded", "ldpc"]),
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
GROUND_POINTING_OFFSET_DEG = 0.0
BITS_PER_SYMBOL = 5  # The existing required_eb_n0() model uses 32-PSK.

ASSUMPTIONS = [
    "Circular Earth orbit; spherical, non-rotating Earth; nadir line-scanning "
    "payload with no compression or packet overhead (existing model).",
    "Minimum ground-station elevation: 20 degrees.",
    "Parabolic antenna radiation efficiency: 0.6 for both antennas.",
    "Antenna noise temperature: spacecraft 290 K; ground station 100 K.",
    "Receiver noise figure: 2 dB for both receivers; cable and reference "
    "temperatures: 290 K.",
    "Ground-station pointing offset: 0 degrees; the table's 0.12-degree "
    "offset applies to the spacecraft antenna.",
    "Atmospheric and rain attenuation use the existing model's simplified "
    "frequency bands; antenna noise temperatures stay constant.",
    "The existing required Eb/N0 approximation assumes 32-PSK; the table "
    "specifies uncoded operation but does not specify the modulation order.",
    "Eb/N0 is per information bit; encoded channel rate is shown separately. "
    "The existing coded/LDPC model uses code rate 3/4 and a 10 dB coding gain.",
    "The 850 W total is an upper bound on RF output only. Amplifier DC "
    "efficiency and other subsystem loads are unspecified; spacecraft "
    "electrical power feasibility is not established.",
    "Minimum passband bandwidth is symbol rate at ideal zero pulse-shaping "
    "roll-off. Actual occupied bandwidth is larger for nonzero roll-off; "
    "available channel bandwidth is unspecified.",
]


def validate_inputs(overrides=None):
    """Merge partial input updates and enforce bounds and the fixed red cells."""
    if overrides is None:
        overrides = {}
    if not isinstance(overrides, dict):
        raise ValueError("Inputs must be an object containing case parameter values.")

    parameters = {entry["id"]: entry for entry in CASE_PARAMETERS}
    unknown = set(overrides) - set(parameters)
    if unknown:
        raise ValueError("Unknown case parameter: " + ", ".join(sorted(unknown)))

    result = {}
    for identifier, entry in parameters.items():
        value = overrides.get(identifier, entry["default"])
        if entry["locked"]:
            if value != entry["default"] or isinstance(value, bool):
                raise ValueError(f"{entry['label']} is fixed for the Earth case.")
            result[identifier] = entry["default"]
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{entry['label']} must be a number.")
        if not math.isfinite(value):
            raise ValueError(f"{entry['label']} must be finite.")
        if not entry["min"] <= value <= entry["max"]:
            raise ValueError(
                f"{entry['label']} must be between {entry['min']} and {entry['max']}."
            )
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
    required_eb_n0_db = model.required_eb_n0(inputs["required_ber"], inputs["coding"])
    available_eb_n0_db = model.energy_per_bit(
        eirp_dbw, free_space_loss_db, other_losses_db,
        receiver["g_over_t_db_per_k"], information_rate_bps,
    )
    channel_rate_bps = model.transmitted_bit_rate(information_rate_bps, inputs["coding"])
    symbol_rate_baud = channel_rate_bps / BITS_PER_SYMBOL
    return {
        "frequency_ghz": frequency_ghz,
        "information_rate_bps": information_rate_bps,
        "transmitted_rate_bps": channel_rate_bps,
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
        "carrier_to_noise_density_db_hz": available_eb_n0_db + model.n_dB(information_rate_bps),
        "required_eb_n0_db": required_eb_n0_db,
        "margin_db": model.link_margin(available_eb_n0_db, required_eb_n0_db),
    }


def calculate_earth(overrides=None):
    """Calculate both Earth links without mutating the original model globals."""
    inputs = validate_inputs(overrides)
    altitude_km = inputs["orbit_altitude_km"]
    slant_range_km = model.distance_earth_orbit(
        altitude_km, math.radians(MINIMUM_ELEVATION_DEG)
    )
    active_rate_bps = model.payload_data_rate(
        altitude_km, inputs["payload_swath_deg"], inputs["payload_pixel_arcmin"],
        inputs["payload_bits_per_pixel"], model.earthRadius, model.earth_mu,
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
    if downlink["minimum_passband_bandwidth_hz"] >= 2 * downlink_frequency_ghz * 1e9:
        warnings.append(
            "The downlink needs at least "
            f"{downlink['minimum_passband_bandwidth_hz'] / 1e9:.2f} GHz of "
            "passband bandwidth for 32-PSK at ideal zero roll-off. This "
            "exceeds twice the carrier frequency: the assumed single-carrier "
            "S/X-band link cannot carry this payload rate, even if its "
            "calculated Eb/N0 margin is positive."
        )
    return {
        "scenario": "earth",
        "inputs": inputs,
        "geometry": {
            "slant_range_km": slant_range_km,
            "minimum_elevation_deg": MINIMUM_ELEVATION_DEG,
            "uplink_frequency_ghz": uplink_frequency_ghz,
            "downlink_frequency_ghz": downlink_frequency_ghz,
        },
        "payload": {
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
        "assumptions": list(ASSUMPTIONS),
    }
