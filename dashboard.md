
## Earth dashboard

Run with Python 3 (no extra packages needed):

```powershell
python dashboard.py
```

On Windows you can also use `py dashboard.py` if the Python launcher is configured. Open **http://127.0.0.1:8000** in your browser. Stop the server with Ctrl+C. To choose another port, run `python dashboard.py --port 8001`.

The dashboard shows all 20 Earth parameters from Table 1 in the tutorial assignment, in the original order. Each has a slider below its value. The 14 red Earth cells are disabled, including the N/A elongation angle and uncoded modulation. The six adjustable values are the two transmitter powers, transmitter and receiver loss factors, downlink frequency, and uplink/downlink frequency ratio. Reset restores the exact Earth defaults, including 221/240.

Slider changes recalculate the payload data rate, daily data, required downlink rate, uplink and downlink budgets, and margins using the helpers in `main.py`. Fixed values are also enforced by the API. This dashboard covers the Earth telecommunications case; Table 2's ADCS calculations are outside this tool's current scope.

The case table does not supply antenna efficiency or receiver noise inputs. The assumptions shown below the results specify the values used: antenna efficiency 0.6, minimum elevation 20 degrees, spacecraft/ground antenna noise temperatures 290/100 K, receiver noise figure 2 dB, cable temperature 290 K, and ideal ground pointing. The existing model uses an uncoded 32-PSK Eb/N0 approximation and simplified atmosphere/rain losses. Antenna noise stays fixed rather than modeling additional atmospheric/rain emission. These assumptions can be reviewed in `earth_model.py`; margins are estimates under that model.

The default downlink margin is -12.237 dB: the fixed camera inputs generate 23.893 Gbit/s while active, or 258.042 TB/day, requiring 1.147 Tbit/s during the 0.5-hour downlink window. One combination of adjustable fields gives a **3.376 dB Eb/N0 margin**: downlink 8.4 GHz, spacecraft transmitter 450 W, transmitter loss factor 0.90, receiver loss factor 0.90, and the original 221/240 turn-around ratio. All red table fields stay fixed. A 0.02-degree ground pointing offset would subtract 0.1728 dB from that result (the dashboard still assumes zero ground offset).

This is an energy-budget result, not a feasible hardware design: 32-PSK at that data rate requires at least 229.37 GHz of passband bandwidth even at ideal zero roll-off. No available channel bandwidth is provided. The dashboard now displays symbol rate, minimum bandwidth, and that limitation alongside the margin. The total spacecraft power check also needs amplifier electrical efficiency and other subsystem loads; RF output power alone cannot establish compliance with the 850 W budget.

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
