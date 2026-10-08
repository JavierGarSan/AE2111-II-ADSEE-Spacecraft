import math

print("Hello cruel world")

print("Hello cruel world")
# So this entire thing is just gonna be 𝑆𝑁𝑅 = 𝐸𝐼𝑅𝑃 − 𝐿_(𝐹𝑟𝑒𝑒 𝑆𝑝𝑎𝑐𝑒) + 𝐺/𝑇 − 10 𝑙𝑜𝑔10 𝑘_B D_𝑟 (𝑑𝐵)
# The final output provided by the tool shall be the link margin of the mission under consideration (for both the uplink and the downlink communication)

# Parameters from missions to enter:
transmitter_P_sc = 150 # W
transmitter_P_gs = 400 # W
Loss_factor_transmitter = 0.8 # -
Loss_factor_receiver = 0.7 # -
downlink_f = 2.2 # GHz
turnaround_ratio = 221/240 # -
antenna_diameter_sc = 1 # m
antenna_diameter_gc = 15 # m
orbit_altitude = 820 # km
elongation_angle = 0 # deg
pointing_offset_angle = 0.12 # deg
required_uplink_dr = 10**8 # bit/s
pl_swath_width_angle = 45 # deg
pl_pixel_size = 0.01 # arcmin
pl_bits_per_pixel = 32 # -
pl_duty_cycle = 100 # %
pl_downlink_t = 0.5 # hr/day
modulation_type = "uncoded"
ber_required = 10**-6 # -




def freespaceloss(distance, wavelength):
    return -20 * math.log10(4*math.pi()*distance/wavelength) 








