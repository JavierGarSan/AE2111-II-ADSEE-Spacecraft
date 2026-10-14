import math
from statistics import NormalDist

# So this entire thing is just gonna be 𝑆𝑁𝑅 = 𝐸𝐼𝑅𝑃 − 𝐿_(𝐹𝑟𝑒𝑒 𝑆𝑝𝑎𝑐𝑒) + 𝐺/𝑇 − 10 𝑙𝑜𝑔10 𝑘_B D_𝑟 (𝑑𝐵)
# The final output provided by the tool shall be the link margin of the mission under consideration (for both the uplink and the downlink communication)

#Important to note that we dont know the downlink bitrate and we need to use. This needs to be calculated based on the camera abroad the satellite.
# Payload data calculation inputs (from the mission table).
orbit_altitude = 820 # km above Earth's surface
pl_swath_width_angle = 45 # deg; full cross-track field of view
pl_pixel_size = 0.01 # arcmin; angular size of a square pixel
pl_bits_per_pixel = 32 # bits per pixel, total across any channels
pl_duty_cycle = 100 # % of each day spent collecting data
pl_downlink_t = 0.5 # hr/day; available time to transmit the daily data

# Physical assumptions: circular orbit and a spherical, non-rotating Earth.
AU = 149597870.7    # km
earthRadius = 6371 # km
earth_mu = 398600.435507 # km^3/s^2; https://ssd.jpl.nasa.gov/astro_par.html
moon_orbit_altitude = 384400 # km https://science.nasa.gov/moon/facts/#h-size-and-distance
moon_radius = 1740 # km  same link
mars_orbit_altitude = 228 * 10**6 # km https://science.nasa.gov/mars/facts/#h-size-and-distance
mars_radius = 3390 # km  same link
mercury_orbit_altitude = 46 *10**6 # km https://nssdc.gsfc.nasa.gov/planetary/factsheet/mercuryfact.html (at perihelion)
mercury_radius = 2440.5 # km  same link
seconds_per_day = 24 * 60 * 60

#Assumptions - NOT IN FILE.
c = 299792458 # m/s
k_b = 1.380649 * 10**(-23)
signalnoise_ratio = 3 #dB


# Parameters from missions to enter:
required_uplink_dr = 10**8 # bit/s
transmitter_P_sc = 150 # W
transmitter_P_gs = 400 # W
loss_factor_transmitter = 0.8 # -
loss_factor_receiver = 0.7 # -
downlink_f = 2.2 # GHz
turnaround_ratio = 221/240 # -
antenna_diameter_sc = 1 # m
antenna_diameter_gc = 15 # m
pointing_offset_angle = 0.12 # deg
modulation_type = "uncoded"
ber_required = 10**-6 # -


def orbital_period(altitude_km, planet_radius_km, mu_km3_s2):
    """Return the circular-orbit period in seconds."""
    if altitude_km <= 0 or planet_radius_km <= 0 or mu_km3_s2 <= 0:
        raise ValueError("Altitude, radius and gravitational parameter must be positive.")
    orbit_radius_km = planet_radius_km + altitude_km
    return 2 * math.pi * math.sqrt(orbit_radius_km**3 / mu_km3_s2)


def orbital_speed(altitude_km, planet_radius_km, mu_km3_s2):
    """Return circular-orbit speed in m/s, with distances in km and mu in km^3/s^2."""
    if not all(
        math.isfinite(value) and value > 0
        for value in (altitude_km, planet_radius_km, mu_km3_s2)
    ):
        raise ValueError("Altitude, radius and gravitational parameter must be finite and positive.")
    return math.sqrt(mu_km3_s2 / (planet_radius_km + altitude_km)) * 1000


def ground_track_speed(altitude_km, planet_radius_km, mu_km3_s2):
    """Return the nadir ground-track speed in m/s, ignoring planets rotation."""
    period_s = orbital_period(altitude_km, planet_radius_km, mu_km3_s2)
    return 2 * math.pi * planet_radius_km * 1000 / period_s


def ground_pixel_size(altitude_km, pixel_size_arcmin):
    """Return a nadir pixel's approximate ground size in m (local flat surface)."""
    if altitude_km <= 0 or not 0 < pixel_size_arcmin < 180 * 60:
        raise ValueError("Altitude must be positive and pixel angle must be between 0 and 180 degrees.")
    pixel_angle_rad = math.radians(pixel_size_arcmin / 60)
    return 2 * altitude_km * 1000 * math.tan(pixel_angle_rad / 2)


def pixels_per_line(swath_width_angle_deg, pixel_size_arcmin):
    """Return the number of angular pixels covering the full cross-track swath."""
    if not 0 < swath_width_angle_deg < 180 or pixel_size_arcmin <= 0:
        raise ValueError("Swath angle must be between 0 and 180 degrees and pixel size must be positive.")
    return math.ceil(swath_width_angle_deg * 60 / pixel_size_arcmin)


def payload_data_rate(altitude_km, swath_width_angle_deg, pixel_size_arcmin,
                      bits_per_pixel, planet_radius_km, mu_km3_s2):
    """Estimate raw bits/s while a nadir pushbroom camera is active.

    Assumes square angular pixels and one image row per along-track pixel.
    Uses orbital speed as the ground scan speed, following the assignment's
    permitted simplification and the referenced data-rate calculation.
    Cross-track pixels are counted by angle, since ground footprints grow toward the swath edges. 
    """
    if bits_per_pixel <= 0:
        raise ValueError("Bits per pixel must be positive.")
    speed_m_s = orbital_speed(altitude_km, planet_radius_km, mu_km3_s2)
    pixel_size_m = ground_pixel_size(altitude_km, pixel_size_arcmin)
    line_rate_hz = speed_m_s / pixel_size_m
    return pixels_per_line(swath_width_angle_deg, pixel_size_arcmin) * line_rate_hz * bits_per_pixel


def daily_data_generated(data_rate_bps, duty_cycle_percent):
    """Return raw bits collected in 24 hours; duty cycle is a percentage (0-100)."""
    if data_rate_bps < 0 or not 0 <= duty_cycle_percent <= 100:
        raise ValueError("Data rate must be nonnegative and duty cycle must be between 0 and 100 percent.")
    return data_rate_bps * seconds_per_day * duty_cycle_percent / 100


def required_downlink_rate(daily_data_bits, downlink_hours_per_day):
    """Return the minimum payload bit/s needed to transmit one day's data."""
    if daily_data_bits < 0 or not 0 < downlink_hours_per_day <= 24:
        raise ValueError("Daily data must be nonnegative and downlink time must be between 0 and 24 hours.")
    return daily_data_bits / (downlink_hours_per_day * 60 * 60)

 
#
# Data Input:  Packet Engine > Code Engine > Modulator > Mixer > Power Amplifier 
#                                                                            free space loss
# Data Output: Packet Engine < Code Engine < Demodulator < Mixer < LNA     < ----/

#Assumption: emin will always be 20º
def atmospheric_attenuation_noise(frequency): #We assume minimum operating elevation of 20º
    if frequency>10e9:
        return 0.75 #dB
    if frequency>5e9:
        return 0.2 #dB
    elif frequency>0:
        return 0.15 #dB
    raise ValueError("Frequency can't be negative")

def n_dB(value):
    return 10 * math.log10(value/1)
def dB_n(value):
    return 10**(value/10*1)

def antenna_gain(radiation_efficiency, antenna_diameter, wavelength): # return in dB
    return 10 * math.log10(radiation_efficiency * (math.pi*antenna_diameter/wavelength)**2)

def freespaceloss(distance, wavelength):
    """Return free-space attenuation in dB; distance and wavelength are metres.

    Loss magnitudes are positive in the link-budget convention. The Friis
    far-field model does not apply where its calculated attenuation is negative.
    """
    if not all(math.isfinite(value) and value > 0 for value in (distance, wavelength)):
        raise ValueError("Distance and wavelength must be finite and positive.")
    loss_db = 20 * math.log10(4 * math.pi * distance / wavelength)
    if loss_db < 0:
        raise ValueError("Distance is too small for the free-space loss model.")
    return loss_db

def pointing_angle_loss(frequency_ghz,offset_antenna_diameter_m, pointing_offset_deg):
    """Return nonnegative parabolic-antenna pointing attenuation in dB.

    Frequency is in GHz, diameter in metres, and offset in degrees. The
    approximate full half-power beamwidth is 21 / (frequency * diameter) degrees.
    Call separately for the transmitting and receiving antennas.
    """
    if not all(
        math.isfinite(value) and value > 0
        for value in (frequency_ghz, offset_antenna_diameter_m)
    ):
        raise ValueError("Frequency and antenna diameter must be finite and positive.")
    if not math.isfinite(pointing_offset_deg) or pointing_offset_deg < 0:
        raise ValueError("Pointing offset must be finite and nonnegative.")
    offset_half_power_angle_deg = 21 / (frequency_ghz * offset_antenna_diameter_m)
    offset_loss_db = 12 * (pointing_offset_deg / offset_half_power_angle_deg)**2
    return  offset_loss_db

def energy_per_bit(EIRP, free_space_loss, All_other_losses, G_over_T, bitrate):
    """Return Eb/N0 in dB for a positive information bitrate in bit/s.

    EIRP is in dBW, G/T in dB/K, and both attenuation arguments are
    nonnegative loss magnitudes in dB.
    """
    if not all(
        math.isfinite(value)
        for value in (EIRP, free_space_loss, All_other_losses, G_over_T, bitrate)
    ):
        raise ValueError("Link-budget inputs must be finite.")
    if bitrate <= 0:
        raise ValueError("Bitrate must be positive.")
    if free_space_loss < 0 or All_other_losses < 0:
        raise ValueError("Loss magnitudes must be nonnegative.")
    return EIRP - free_space_loss - All_other_losses + G_over_T - 10 * math.log10(k_b * bitrate)

def distance_earth_orbit(satellite_altitude, minimum_elevation_angle): # input in km, output in km
    global earthRadius
    return earthRadius * (math.sqrt(((earthRadius + satellite_altitude)/earthRadius)**2 - math.cos(minimum_elevation_angle)**2) - math.sin(minimum_elevation_angle))

def distance_other_orbit(orbiting_body, satellite_altitude, minimum_elevation_angle, elongation_angle): # remember input angles in radians, input in km, output in km
    if not isinstance(orbiting_body, str):
        raise ValueError("Input orbiting body is not string")
    orbiting_body = orbiting_body.lower()
    if orbiting_body == "moon":
        dist_satellite_to_surface_body = math.sqrt((satellite_altitude+moon_radius)**2 - moon_radius**2)
        distance_to_moon = distance_earth_orbit(moon_orbit_altitude, minimum_elevation_angle)
        dist_gs_to_surface_body = math.sqrt(distance_to_moon**2 - moon_radius**2)
        distance = dist_satellite_to_surface_body + dist_gs_to_surface_body

    elif orbiting_body == "mars":
        dist_earth_to_body = math.sqrt(AU**2 + mars_orbit_altitude**2 - 2 * AU * mars_orbit_altitude * math.cos(elongation_angle))
        dist_earth_to_surface_body = math.sqrt(dist_earth_to_body**2 - mars_radius**2)
        dist_satellite_to_surface_body = math.sqrt((satellite_altitude+mars_radius)**2 - mars_radius**2)
        gs_dist = math.sin(minimum_elevation_angle) * earthRadius
        distance = dist_earth_to_surface_body + dist_satellite_to_surface_body - gs_dist

    elif orbiting_body == "mercury":
        dist_earth_to_body = math.sqrt(AU**2 + mercury_orbit_altitude**2 - 2 * AU * mercury_orbit_altitude * math.cos(elongation_angle))
        dist_earth_to_surface_body = math.sqrt(dist_earth_to_body**2 - mercury_radius**2)
        dist_satellite_to_surface_body = math.sqrt((satellite_altitude+mercury_radius)**2 - mercury_radius**2)
        gs_dist = math.sin(minimum_elevation_angle) * earthRadius
        distance = dist_earth_to_surface_body + dist_satellite_to_surface_body - gs_dist
    else:
        raise ValueError("Input orbiting body is not supported")
    return distance
#print(f"distance to mars would be: {distance_other_orbit("mars", 300, math.pi/6, 150/180*math.pi)}")

def required_eb_n0(ber, coding, modulation="4-QAM"):
    """Required Eb/N0 per information bit for Gray-coded square QAM in AWGN.

    For M = 4 and k = log2(M), BER = Q(sqrt(2 * Eb/N0)) is exact.
    For M = 64, use the low-BER nearest-neighbour approximation:
    BER ~= (4/k) * (1 - 1/sqrt(M)) * Q(sqrt(3*k*Eb/N0/(M-1))).
    This is the leading term of the square-QAM BER expression documented at
    https://www.mathworks.com/help/comm/ug/analytical-expressions-used-in-berawgn-function-and-bit-error-rate-analysis-app.html

    The existing coded/LDPC options retain their assumed 10 dB coding gain;
    they do not model a particular code's measured BER performance.
    """

    coding = coding.lower()
    if coding not in ("uncoded", "coded", "ldpc"):
        raise ValueError("Choose 'uncoded', 'coded', or 'ldpc'.")
    if not math.isfinite(ber) or not 0 < ber <= 1e-3:
        raise ValueError("Use a BER between 0 and 1e-3.")
    if modulation not in ("4-QAM", "64-QAM"):
        raise ValueError("Choose '4-QAM' or '64-QAM'.")

    modulation_order = 4 if modulation == "4-QAM" else 64
    bits_per_symbol = math.log2(modulation_order)
    ber_coefficient = 4 / bits_per_symbol * (1 - 1 / math.sqrt(modulation_order))
    q_inverse = -NormalDist().inv_cdf(ber / ber_coefficient)

    eb_n0_linear = q_inverse**2 * (modulation_order - 1) / (3 * bits_per_symbol)
    required_db = 10 * math.log10(eb_n0_linear)

    coding_gain_db = 0.0 if coding == "uncoded" else 10.0
    return required_db - coding_gain_db

def transmitted_bit_rate(information_rate_bps, coding="uncoded"):
    """Return channel bit/s, including coding overhead, for either link.

    Rate-3/4 LDPC sends four channel bits per three information bits:
    R_channel = R_information / (3/4). Decoding recovers information at
    R_information = R_channel * (3/4). Payload generation is unchanged.
    """
    if information_rate_bps < 0:
        raise ValueError("Information rate must be nonnegative.")

    coding = coding.lower()
    if coding == "uncoded":
        return information_rate_bps
    if coding in ("coded", "ldpc"):
        return information_rate_bps / (3 / 4)

    raise ValueError("Choose 'uncoded', 'coded', or 'ldpc'.")

def receiver_noise_and_gt(
    antenna_gain_dbi,
    antenna_noise_k,
    receiver_noise_figure_db,
    receiver_loss_factor=0.7,
    cable_physical_k=290.0,
    reference_k=290.0,
):
    """Calculate noise temperatures referred to the antenna terminals."""

    values = (
        antenna_gain_dbi, antenna_noise_k, receiver_noise_figure_db,
        receiver_loss_factor, cable_physical_k, reference_k,
    )
    if not all(math.isfinite(value) for value in values):
        raise ValueError("Inputs must be finite.")
    if not 0 < receiver_loss_factor <= 1:
        raise ValueError("Receiver loss factor must be in (0, 1].")
    if antenna_noise_k < 0 or cable_physical_k < 0 or reference_k <= 0:
        raise ValueError("Invalid temperature.")
    if receiver_noise_figure_db < 0:
        raise ValueError("Receiver noise figure must be nonnegative.")

    noise_factor = 10 ** (receiver_noise_figure_db / 10)

    # Receiver noise at the receiver's own input.
    receiver_noise_k = reference_k * (noise_factor - 1)

    # Refer cable and receiver noise back to the antenna terminals.
    cable_noise_k = cable_physical_k * (1 / receiver_loss_factor - 1)
    receiver_referred_k = receiver_noise_k / receiver_loss_factor

    system_noise_k = (
        antenna_noise_k + cable_noise_k + receiver_referred_k
    )
    if system_noise_k <= 0:
        raise ValueError("System noise temperature must be positive.")

    return {
        "receiver_noise_k": receiver_noise_k,
        "cable_noise_referred_k": cable_noise_k,
        "receiver_noise_referred_k": receiver_referred_k,
        "system_noise_k": system_noise_k,
        "g_over_t_db_per_k": (
            antenna_gain_dbi - 10 * math.log10(system_noise_k)
        ),
    }

def rain_attenuation_noise(frequency): #in dB, super simplified
    if (frequency>(5*(10**9))) and frequency<(12*(10**9)):
        return 2.86
    elif (frequency<=(5*(10**9))):
        return 0
    raise ValueError("The frequency isnt represented the program (only below 12 GHz)")

def link_margin(available_eb_n0_db, required_eb_n0_db):
    """Return available minus required Eb/N0, in dB."""

    if not all(
        math.isfinite(value)
        for value in (available_eb_n0_db, required_eb_n0_db)
    ):
        raise ValueError("Both Eb/N0 values must be finite.")

    return available_eb_n0_db - required_eb_n0_db

if __name__ == "__main__":
    # Use the same defaults and assumptions as the web dashboard. Import here
    # because earth_model imports this module's calculation helpers.
    from earth_model import calculate_earth

    result = calculate_earth()
    payload = result["payload"]
    print(f"Payload data rate while active: {payload['active_rate_bps']:.3e} bit/s")
    print(
        f"Data generated per day: {payload['daily_data_bits']:.3e} bits "
        f"({payload['daily_data_tb']:.3f} TB)"
    )
    print(f"Required downlink data rate: {payload['required_downlink_rate_bps']:.3e} bit/s")
    print(f"Earth slant range: {result['geometry']['slant_range_km']:.3f} km")
    for direction in ("uplink", "downlink"):
        budget = result[direction]
        print(
            f"{direction.capitalize()}: {budget['frequency_ghz']:.6f} GHz, "
            f"EIRP {budget['eirp_dbw']:.3f} dBW, "
            f"available Eb/N0 {budget['available_eb_n0_db']:.3f} dB, "
            f"required Eb/N0 {budget['required_eb_n0_db']:.3f} dB, "
            f"margin {budget['margin_db']:.3f} dB"
        )

