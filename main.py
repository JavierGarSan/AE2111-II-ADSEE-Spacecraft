import math

print("Hello cruel world")

# So this entire thing is just gonna be 𝑆𝑁𝑅 = 𝐸𝐼𝑅𝑃 − 𝐿_(𝐹𝑟𝑒𝑒 𝑆𝑝𝑎𝑐𝑒) + 𝐺/𝑇 − 10 𝑙𝑜𝑔10 𝑘_B D_𝑟 (𝑑𝐵)
# The final output provided by the tool shall be the link margin of the mission under consideration (for both the uplink and the downlink communication)

#Important to note that we dont know the downlink bitrate and we need to use. This needs to be calculated based on the camera abroad the satellite.
 
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
    return -20 * math.log10(4*math.pi()*distance/wavelength) 


#Assumptions - NOT IN FILE.
earthRadius = 6371 #km
c = 299792458 # m/s

# Parameters from missions to enter:
transmitter_P_sc = 150 # W
transmitter_P_gs = 400 # W
loss_factor_transmitter = 0.8 # -
loss_factor_receiver = 0.7 # -
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


print(c/(downlink_f*10**9)/turnaround_ratio)
transmitter_gain = antenna_gain(radiation_efficiency=1/loss_factor_transmitter, antenna_diameter=antenna_diameter_sc, wavelength=c/(downlink_f*10**9)/turnaround_ratio)
print("transmitter_gain: ", transmitter_gain)
eirp = n_dB(transmitter_P_sc * dB_n(transmitter_gain) / loss_factor_transmitter)
print(f"eirp = {eirp}")