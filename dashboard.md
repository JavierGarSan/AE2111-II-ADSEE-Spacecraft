
## Spacecraft dashboard

Run with Python 3 (no extra packages needed):

```powershell
python dashboard.py
```

On Windows you can also use `py dashboard.py` if the Python launcher is configured. Open **http://127.0.0.1:8000** in your browser. Stop the server with Ctrl+C. To choose another port, run `python dashboard.py --port 8001`.

The dashboard starts with all 20 Earth parameters from Table 1 in the tutorial assignment, in their original order. Each cell has a slider and a lock button. The 14 red Earth cells start locked; every cell can be unlocked and relocked. Locks control whether the cell's slider can move. Numeric bounds and the spacecraft power constraint still apply.

The **Templates** dropdown to the right of the title loads all 20 values, the orbiting body, uncoded encoding, and the red-cell lock pattern from the supplied table:

- Case 1 - Earth LEO
- Case 2 - Moon LRO
- Case 3 - Mars Hope
- Case 4 - Mars MRO
- Case 5 - Mercury Bepi. C

Selecting a template keeps your chosen 4-QAM/64-QAM modulation. Changing its values, body, encoding or lock states shows **Custom inputs**. Every initially locked field can still be unlocked.

An **Orbiting body** selector above the grid offers Earth, Moon, Mars and Mercury. Changing this selector keeps every current input and lock state, while updating the body's gravity, radius, payload orbital speed and estimated range to a ground station on Earth. Mission values are loaded through Templates.

The **Modulation** selector immediately above Results offers 4-QAM and 64-QAM. The **Channel coding** slider in the input grid selects Uncoded or LDPC; unlock its grid cell to adjust it. Both settings apply to uplink and downlink. LDPC retains the existing model's assumed rate 3/4 and 10 dB coding gain, rather than a measured code-specific BER curve.

For both links, rate-3/4 LDPC converts information rate to transmitted rate as `R_transmitted = R_information / 0.75`; decoding gives `R_information = 0.75 * R_transmitted`. The overhead increases transmitted bit rate, symbol rate and minimum bandwidth by 33.3%, while payload generation and daily collected volume stay the same. The headline **Required downlink transmit rate** includes this overhead, with the payload information rate underneath; the budget table shows both rates for uplink and downlink. Available and required Eb/N0 are both per information bit, so the link margin uses the information rate and applies the assumed coding gain once.

**Reset inputs** keeps the selected body and restores the last loaded template's values and lock states. It selects 4-QAM and restores the template's Uncoded encoding and exact turn-around ratio (221/240 or 749/880). Power slider limits update together so transmitter RF power cannot exceed the total spacecraft power input.

Input changes recalculate the payload data rate, daily data, required downlink rate, uplink and downlink budgets, and margins using the helpers in `main.py`. The API validates types, ranges and encoding/body choices, and accepts updates to initially locked values. At 0% imaging duty cycle there is no downlink data: required rate and volume are zero, while downlink Eb/N0 and margin are not applicable. Table 2's ADCS calculations remain outside this tool's current scope.

Earth calls `main.distance_earth_orbit()` for the ground-station slant range at 20-degree elevation. Moon, Mars and Mercury call `main.distance_other_orbit()` with the selected spacecraft altitude and the same minimum elevation; angles are converted from degrees to radians before calling the helper. These shared remote calculations use the helper's tangent geometry, including spacecraft altitude and ground-station corrections. Mars and Mercury use the angle at the Sun between Earth-Sun and spacecraft-Sun lines; Mercury retains the original model's perihelion-distance approximation. If elongation remains N/A, the calculation uses a disclosed maximum-range angle of 180 degrees; unlock that cell to enter an angle. The remote model omits actual spacecraft orbital phase, exact station position, occultation and contact availability. Body constants and sources are listed in the calculation assumptions.

The case table does not supply antenna efficiency or receiver noise inputs. The assumptions shown below the results specify the values used: antenna efficiency 0.6, minimum elevation 20 degrees, spacecraft/ground antenna noise temperatures 290/100 K, receiver noise figure 2 dB, cable temperature 290 K, and ideal ground pointing. The model uses Gray-coded square QAM in AWGN: exact uncoded BER for 4-QAM and a low-BER nearest-neighbor approximation for 64-QAM. At BER 1e-6 the required Eb/N0 is 10.530 dB for 4-QAM and 18.777 dB for 64-QAM. Symbol rate and bandwidth use 2 or 6 bits per symbol respectively. Atmospheric/rain losses are simplified, and antenna noise stays fixed rather than modeling additional atmospheric/rain emission. These assumptions can be reviewed in `earth_model.py`; margins are estimates under that model.

The payload calculation follows the assignment's approximation that ground scan velocity equals orbital velocity. At 820 km altitude, `v = sqrt(mu / (R + h))` gives 7,445.164 m/s. The 0.01-arcminute pixel is 2.385283 m wide at nadir, and `45 * 60 / 0.01` gives 270,000 pixels per line. The generation rate is `pixels_per_line * (v / pixel_size) * 32`; daily volume is this rate times 86,400 seconds times the duty-cycle fraction; the downlink rate is daily volume divided by `0.5 * 3600` seconds. This gives **26.968 Gbit/s**, **291.254 TB/day**, and **1.294462 Tbit/s**. Pixels are counted by angle rather than dividing a tangent-derived full swath by a constant ground pixel width. The shared calculation's small-angle nadir pixel differs from the model's tangent conversion by less than one part in a trillion at this pixel angle.

The earlier **1.147 Tbit/s** result used the projected nadir ground-track velocity, `v * R / (R + h)`, which is 6,596.181 m/s. That is a different physical approximation; the updated calculation matches the supplied conversation and the assignment's allowed simplification of using orbital velocity as ground velocity. The projected-speed helper remains available for other uses, while the dashboard shows the orbital and assumed scan velocities.

The default downlink margin is **+0.070 dB with 4-QAM**, or **-8.177 dB with 64-QAM**. With 4-QAM, increasing spacecraft transmitter power to 300 W gives a **3.080 dB Eb/N0 margin** at the original 2.2 GHz and loss factors. With 64-QAM, downlink 8.4 GHz, spacecraft transmitter 450 W, and transmitter/receiver loss factors 0.90 give a **7.435 dB margin**. Both examples preserve all red table fields and the 221/240 turn-around ratio. The dashboard still assumes zero ground pointing offset.

These margins are energy-budget results, not feasible hardware designs: the payload rate requires at least 647.23 GHz of passband bandwidth with 4-QAM or 215.74 GHz with 64-QAM even at ideal zero roll-off. No available channel bandwidth is provided. The dashboard displays symbol rate, minimum bandwidth, and that limitation alongside the margin. The total spacecraft power check also needs amplifier electrical efficiency and other subsystem loads; RF output power alone cannot establish compliance with the 850 W budget.

Free-space and pointing helpers return positive attenuation in dB, and `energy_per_bit()` subtracts those positive losses. The receiver cable loss is included in antenna-referred noise/G/T, so it is not subtracted a second time. The CLI and dashboard use the same Earth calculation.

The UI uses plain white and grey blocks, borders, native sliders, and a budget table, with no gradients or external assets. The server listens only on this computer's loopback address.

## Existing command-line tool

```powershell
python main.py
```

## Checks

```powershell
python -m unittest discover -s tests -v
```
