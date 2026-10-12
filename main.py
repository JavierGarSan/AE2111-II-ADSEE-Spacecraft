import math
from statistics import NormalDist

print("Hello cruel world")

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
earthRadius = 6371 # km
earth_mu = 398600.435507 # km^3/s^2; https://ssd.jpl.nasa.gov/astro_par.html
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
    Cross-track pixels are counted by angle, since ground footprints grow toward the swath edges. 
    """
    if bits_per_pixel <= 0:
        raise ValueError("Bits per pixel must be positive.")
    speed_m_s = ground_track_speed(altitude_km, planet_radius_km, mu_km3_s2)
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

def n_dB(value):
    return 10 * math.log10(value/1)
def dB_n(value):
    return 10**(value/10*1)

def antenna_gain(radiation_efficiency, antenna_diameter, wavelength): # return in dB
    return 10 * math.log10(radiation_efficiency * (math.pi*antenna_diameter/wavelength)**2)


def freespaceloss(distance, wavelength):    # return in dB
    return -20 * math.log10(4*math.pi*distance/wavelength) 

def pointing_angle_loss(frequency_ghz,offset_antenna_diameter_m, pointing_offset_deg):
    # Return the pointing loss of one parabolic antenna in dB.
    # This needs to be called twice.
    if frequency_ghz <= 0 or offset_antenna_diameter_m <= 0:
        raise ValueError("Frequency and both antenna diameters must be positive.")
    offset_half_power_angle_deg = 21 / (frequency_ghz * offset_antenna_diameter_m)
    offset_loss_db = -12 * (pointing_offset_deg / offset_half_power_angle_deg)**2
    return  offset_loss_db

def energy_per_bit(EIRP, free_space_loss, All_other_losses, G_over_T, bitrate): # input in dB
    return EIRP - free_space_loss - All_other_losses + G_over_T - 10 * math.log10(k_b * bitrate)

def distance_earth_orbit(satellite_altitude, minimum_elevation_angle):
    global earthRadius
    return earthRadius * (math.sqrt(((earthRadius + satellite_altitude)/earthRadius)**2 - math.cos(minimum_elevation_angle)**2) - math.sin(minimum_elevation_angle))

def distance_other_orbit(orbit_altitude_orbiting_body, satellite_altitude, elongation_angle): #No reason for this.   
    return 

def required_eb_n0(ber, coding):
    """Required Eb/N0 per information bit, in dB, for 32-PSK."""

    coding = coding.lower()
    if coding not in ("uncoded", "coded", "ldpc"):
        raise ValueError("Choose 'uncoded', 'coded', or 'ldpc'.")
    if not math.isfinite(ber) or not 0 < ber <= 1e-3:
        raise ValueError("Use a BER between 0 and 1e-3.")

    bits_per_symbol = 5
    q_inverse = -NormalDist().inv_cdf(
        ber * bits_per_symbol / 2
    )

    eb_n0_linear = q_inverse**2 / (
        2 * bits_per_symbol * math.sin(math.pi / 32)**2
    )
    required_db = 10 * math.log10(eb_n0_linear)

    coding_gain_db = 0.0 if coding == "uncoded" else 10.0
    return required_db - coding_gain_db

def transmitted_bit_rate(information_rate_bps, coding="uncoded"):
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

def link_margin(available_eb_n0_db, required_eb_n0_db):
    """Return available minus required Eb/N0, in dB."""

    if not all(
        math.isfinite(value)
        for value in (available_eb_n0_db, required_eb_n0_db)
    ):
        raise ValueError("Both Eb/N0 values must be finite.")

    return available_eb_n0_db - required_eb_n0_db

payload_dr = payload_data_rate(orbit_altitude, pl_swath_width_angle, pl_pixel_size, pl_bits_per_pixel, planet_radius_km=earthRadius, mu_km3_s2=earth_mu)
data_generated_per_day = daily_data_generated(payload_dr, pl_duty_cycle)
required_downlink_dr = required_downlink_rate(data_generated_per_day, pl_downlink_t)

print(f"Payload data rate while active: {payload_dr:.3e} bit/s")
print(f"Data generated per day: {data_generated_per_day:.3e} bits ({data_generated_per_day / 8 / 10**12:.3f} TB)")
print(f"Required downlink data rate: {required_downlink_dr:.3e} bit/s")

wavelength_downlink = c/(downlink_f*10**9)
transmitter_gain = antenna_gain(radiation_efficiency=loss_factor_transmitter, antenna_diameter=antenna_diameter_sc, wavelength=wavelength_downlink)
print("transmitter_gain: ", transmitter_gain)
eirp = n_dB(transmitter_P_sc * dB_n(transmitter_gain)* loss_factor_transmitter)
print(f"eirp = {eirp}")

