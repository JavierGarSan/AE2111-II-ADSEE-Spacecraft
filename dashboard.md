
## Earth dashboard

Run with Python 3 (no extra packages needed):

```powershell
python dashboard.py
```

On Windows you can also use `py dashboard.py` if the Python launcher is configured. Open **http://127.0.0.1:8000** in your browser. Stop the server with Ctrl+C. To choose another port, run `python dashboard.py --port 8001`.

The dashboard shows all 20 Earth parameters from Table 1 in the tutorial assignment, in the original order. Each has a slider below its value. The 14 red Earth cells are disabled, including the N/A elongation angle and uncoded channel coding. The six adjustable values are the two transmitter powers, transmitter and receiver loss factors, downlink frequency, and uplink/downlink frequency ratio. A separate modulation selector sits directly above Results, outside the input grid, with **4-QAM** and **64-QAM**. It applies to both uplink and downlink. Reset restores the exact Earth defaults, including 221/240, and selects 4-QAM.

Slider changes recalculate the payload data rate, daily data, required downlink rate, uplink and downlink budgets, and margins using the helpers in `main.py`. Fixed values are also enforced by the API. This dashboard covers the Earth telecommunications case; Table 2's ADCS calculations are outside this tool's current scope.

The case table does not supply antenna efficiency or receiver noise inputs. The assumptions shown below the results specify the values used: antenna efficiency 0.6, minimum elevation 20 degrees, spacecraft/ground antenna noise temperatures 290/100 K, receiver noise figure 2 dB, cable temperature 290 K, and ideal ground pointing. The model uses Gray-coded square QAM in AWGN: exact uncoded BER for 4-QAM and a low-BER nearest-neighbor approximation for 64-QAM. At BER 1e-6 the required Eb/N0 is 10.530 dB for 4-QAM and 18.777 dB for 64-QAM. Symbol rate and bandwidth use 2 or 6 bits per symbol respectively. Atmospheric/rain losses are simplified, and antenna noise stays fixed rather than modeling additional atmospheric/rain emission. These assumptions can be reviewed in `earth_model.py`; margins are estimates under that model.

The default downlink margin is **+0.596 dB with 4-QAM**, or **-7.651 dB with 64-QAM**. The fixed camera inputs generate 23.893 Gbit/s while active, or 258.042 TB/day, requiring 1.147 Tbit/s during the 0.5-hour downlink window. With 4-QAM, increasing spacecraft transmitter power to 300 W gives a **3.606 dB Eb/N0 margin** at the original 2.2 GHz and loss factors. With 64-QAM, downlink 8.4 GHz, spacecraft transmitter 450 W, and transmitter/receiver loss factors 0.90 give a **7.961 dB margin**. Both examples preserve all red table fields and the 221/240 turn-around ratio. The dashboard still assumes zero ground pointing offset.

These margins are energy-budget results, not feasible hardware designs: the payload rate requires at least 573.43 GHz of passband bandwidth with 4-QAM or 191.14 GHz with 64-QAM even at ideal zero roll-off. No available channel bandwidth is provided. The dashboard displays symbol rate, minimum bandwidth, and that limitation alongside the margin. The total spacecraft power check also needs amplifier electrical efficiency and other subsystem loads; RF output power alone cannot establish compliance with the 850 W budget.

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
