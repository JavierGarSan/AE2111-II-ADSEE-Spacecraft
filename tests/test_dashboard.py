"""Integration checks for the dashboard's Earth case and local API."""

import json
import math
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from dashboard import DashboardHandler
from earth_model import CASE_PARAMETERS, DEFAULT_MODULATION, MODULATION_OPTIONS, calculate_earth
import main as model


EDITABLE = {
    "spacecraft_transmitter_power_w", "ground_transmitter_power_w",
    "transmitter_loss_factor", "receiver_loss_factor",
    "downlink_frequency_ghz", "turnaround_ratio",
}


class EarthCaseTests(unittest.TestCase):
    def test_default_payload_units_and_range(self):
        result = calculate_earth()
        self.assertEqual(result["payload"]["pixels_per_line"], 270000)
        self.assertAlmostEqual(result["payload"]["ground_pixel_size_m"], 2.385283311060599)
        self.assertAlmostEqual(result["payload"]["active_rate_bps"] / 1e9, 26.967954883078625)
        self.assertAlmostEqual(result["payload"]["daily_data_tb"], 291.25391273724915)
        self.assertAlmostEqual(result["payload"]["required_downlink_rate_bps"] / 1e12, 1.294461834387774)
        self.assertAlmostEqual(result["geometry"]["slant_range_km"], 1804.5717272642773)
        self.assertAlmostEqual(model.distance_earth_orbit(820, math.pi / 2), 820)
        horizon_range = math.sqrt((model.earthRadius + 820) ** 2 - model.earthRadius ** 2)
        self.assertAlmostEqual(model.distance_earth_orbit(820, 0), horizon_range)

    def test_payload_scan_uses_assignment_orbital_velocity_approximation(self):
        # Independent reference: the assignment allows ground velocity to be
        # approximated by orbital velocity, rather than the slower nadir track.
        altitude_m = 820_000
        earth_radius_km = 6371
        mu_km3_s2 = 398600.435507
        orbital_speed = math.sqrt(mu_km3_s2 / (earth_radius_km + 820)) * 1000
        pixel_angle = 0.01 / 60 * math.pi / 180
        pixel_size = 2 * altitude_m * math.tan(pixel_angle / 2)
        pixels_per_line = 45 * 60 / 0.01
        expected_generation_rate = pixels_per_line * orbital_speed / pixel_size * 32
        result = calculate_earth()
        payload = result["payload"]
        self.assertAlmostEqual(payload["orbital_speed_m_s"], orbital_speed)
        self.assertAlmostEqual(payload["scan_speed_m_s"], orbital_speed)
        self.assertAlmostEqual(payload["active_rate_bps"] / expected_generation_rate, 1)
        self.assertAlmostEqual(
            payload["required_downlink_rate_bps"] / expected_generation_rate,
            24 / 0.5,
        )
        # Preserve the physically projected speed helper for other uses; using
        # it for this payload would reproduce the old 1.147 Tbit/s result.
        projected_speed = orbital_speed * earth_radius_km / (earth_radius_km + 820)
        self.assertAlmostEqual(model.ground_track_speed(820, earth_radius_km, mu_km3_s2), projected_speed)
        self.assertGreater(payload["scan_speed_m_s"], projected_speed)

    def test_friis_in_linear_units_matches_downlink(self):
        result = calculate_earth()
        inputs = result["inputs"]
        budget = result["downlink"]
        wavelength = model.c / (inputs["downlink_frequency_ghz"] * 1e9)
        range_m = result["geometry"]["slant_range_km"] * 1000
        transmit_gain = 0.6 * (math.pi * inputs["spacecraft_antenna_diameter_m"] / wavelength) ** 2
        receive_gain = 0.6 * (math.pi * inputs["ground_antenna_diameter_m"] / wavelength) ** 2
        received_w = inputs["spacecraft_transmitter_power_w"] * inputs["transmitter_loss_factor"] * transmit_gain * receive_gain * (wavelength / (4 * math.pi * range_m)) ** 2
        received_w *= 10 ** (-budget["other_losses_db"] / 10)
        receiver_factor = 10 ** (2 / 10)
        temperature_k = 100 + 290 * (1 / inputs["receiver_loss_factor"] - 1) + 290 * (receiver_factor - 1) / inputs["receiver_loss_factor"]
        eb_n0 = received_w / (1.380649e-23 * temperature_k * result["payload"]["required_downlink_rate_bps"])
        self.assertAlmostEqual(10 * math.log10(eb_n0), budget["available_eb_n0_db"])

    def test_three_db_configuration_and_bandwidth_limit(self):
        result = calculate_earth({
            "modulation": "64-QAM",
            "spacecraft_transmitter_power_w": 450,
            "downlink_frequency_ghz": 8.4,
            "transmitter_loss_factor": 0.9,
            "receiver_loss_factor": 0.9,
        })
        self.assertGreater(result["downlink"]["margin_db"], 3)
        self.assertAlmostEqual(result["downlink"]["margin_db"], 7.435438950328299)
        self.assertAlmostEqual(result["uplink"]["frequency_ghz"], 7.735)
        self.assertAlmostEqual(result["downlink"]["symbol_rate_baud"] / 1e9, 215.743639064629)
        self.assertTrue(any("cannot carry" in warning for warning in result["warnings"]))
        # The same settings retain 3 dB with a small, nonzero ground offset.
        loss_db = model.pointing_angle_loss(8.4, 15, 0.02)
        self.assertAlmostEqual(loss_db, 0.1728)
        self.assertGreater(result["downlink"]["margin_db"] - loss_db, 3)

    def test_modulation_updates_threshold_and_bandwidth_for_both_links(self):
        qam4 = calculate_earth({"modulation": "4-QAM"})
        qam64 = calculate_earth({"modulation": "64-QAM"})
        self.assertEqual(calculate_earth()["modulation"], DEFAULT_MODULATION)
        self.assertEqual(qam4["payload"], qam64["payload"])
        self.assertEqual(qam4["geometry"], qam64["geometry"])
        for direction in ("uplink", "downlink"):
            self.assertEqual(qam4[direction]["bits_per_symbol"], 2)
            self.assertEqual(qam64[direction]["bits_per_symbol"], 6)
            self.assertAlmostEqual(qam4[direction]["required_eb_n0_db"], 10.529831699571446)
            self.assertAlmostEqual(qam64[direction]["required_eb_n0_db"], 18.777249982940724)
            self.assertEqual(qam4[direction]["available_eb_n0_db"], qam64[direction]["available_eb_n0_db"])
            self.assertGreater(qam4[direction]["margin_db"], qam64[direction]["margin_db"])
            self.assertAlmostEqual(qam64[direction]["symbol_rate_baud"], qam4[direction]["symbol_rate_baud"] / 3)
            self.assertEqual(qam64[direction]["minimum_passband_bandwidth_hz"], qam64[direction]["symbol_rate_baud"])
        self.assertTrue(any("64-QAM" in warning for warning in qam64["warnings"]))

    def test_defaults_and_red_cells_match_earth_table(self):
        self.assertEqual(len(CASE_PARAMETERS), 20)
        self.assertEqual({p["id"] for p in CASE_PARAMETERS if not p["locked"]}, EDITABLE)
        result = calculate_earth()
        self.assertEqual(result["inputs"]["elongation_angle_deg"], None)
        self.assertEqual(result["inputs"]["coding"], "uncoded")
        self.assertAlmostEqual(result["uplink"]["frequency_ghz"], 2.2 * 221 / 240)
        self.assertAlmostEqual(result["payload"]["required_downlink_rate_bps"], result["payload"]["daily_data_bits"] / 1800)
        for direction in ("uplink", "downlink"):
            budget = result[direction]
            self.assertGreater(budget["free_space_loss_db"], 0)
            self.assertTrue(all(math.isfinite(v) for v in budget.values()))
            self.assertAlmostEqual(budget["margin_db"], budget["available_eb_n0_db"] - budget["required_eb_n0_db"])

    def test_power_change_affects_correct_direction(self):
        original = calculate_earth()
        for key, affected, unaffected in (
            ("spacecraft_transmitter_power_w", "downlink", "uplink"),
            ("ground_transmitter_power_w", "uplink", "downlink"),
        ):
            with self.subTest(parameter=key):
                changed = calculate_earth({key: original["inputs"][key] * 2})
                self.assertAlmostEqual(changed[affected]["margin_db"] - original[affected]["margin_db"], 10 * math.log10(2))
                self.assertEqual(changed[unaffected], original[unaffected])
                self.assertEqual(changed["payload"], original["payload"])

    def test_loss_factors_and_frequency_change_budgets(self):
        original = calculate_earth()
        transmitter = calculate_earth({"transmitter_loss_factor": 0.4})
        receiver = calculate_earth({"receiver_loss_factor": 0.5})
        frequency = calculate_earth({"downlink_frequency_ghz": 8.4, "turnaround_ratio": 1.1})
        for direction in ("uplink", "downlink"):
            self.assertAlmostEqual(transmitter[direction]["margin_db"] - original[direction]["margin_db"], -10 * math.log10(2))
            self.assertGreater(receiver[direction]["system_noise_k"], original[direction]["system_noise_k"])
            self.assertLess(receiver[direction]["margin_db"], original[direction]["margin_db"])
        self.assertAlmostEqual(frequency["uplink"]["frequency_ghz"], 8.4 * 1.1)
        self.assertNotEqual(frequency["downlink"]["margin_db"], original["downlink"]["margin_db"])

    def test_fixed_values_cannot_be_overridden(self):
        for parameter in CASE_PARAMETERS:
            if not parameter["locked"]:
                continue
            default = parameter["default"]
            changed = (default * 2) if isinstance(default, (int, float)) else "changed"
            with self.subTest(parameter=parameter["id"]):
                with self.assertRaisesRegex(ValueError, "fixed"):
                    calculate_earth({parameter["id"]: changed})

    def test_all_editable_bounds_produce_finite_results(self):
        for parameter in CASE_PARAMETERS:
            if parameter["locked"]:
                continue
            for bound in ("min", "max"):
                with self.subTest(parameter=parameter["id"], bound=bound):
                    result = calculate_earth({parameter["id"]: parameter[bound]})
                    json.dumps(result, allow_nan=False)


class QuietDashboardHandler(DashboardHandler):
    def log_message(self, format, *args):
        pass


class LinkHelperTests(unittest.TestCase):
    def test_losses_are_positive_and_half_beamwidth_is_three_db(self):
        self.assertGreater(model.freespaceloss(1e6, 0.1), 0)
        self.assertEqual(model.pointing_angle_loss(8.4, 15, 0), 0)
        full_beamwidth_deg = 21 / (8.4 * 15)
        self.assertAlmostEqual(model.pointing_angle_loss(8.4, 15, full_beamwidth_deg / 2), 3)

    def test_invalid_physical_link_inputs_are_rejected(self):
        for args in ((0, 0.1), (1e6, 0), (float("nan"), 0.1), (1, float("inf"))):
            with self.subTest(args=args), self.assertRaises(ValueError):
                model.freespaceloss(*args)
        for args in ((0, 15, 0.01), (8.4, -1, 0.01), (8.4, 15, -0.01), (8.4, 15, float("nan"))):
            with self.subTest(args=args), self.assertRaises(ValueError):
                model.pointing_angle_loss(*args)
        for args in ((45, -164, 0.15, 22, 1e8), (45, 164, -1, 22, 1e8), (45, 164, 0.15, 22, 0), (float("inf"), 164, 0.15, 22, 1e8)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                model.energy_per_bit(*args)

    def test_noise_reference_and_ber_inverse(self):
        ideal = model.receiver_noise_and_gt(20, 100, 0, receiver_loss_factor=1)
        self.assertEqual(ideal["system_noise_k"], 100)
        self.assertEqual(ideal["g_over_t_db_per_k"], 0)
        lossy = model.receiver_noise_and_gt(20, 100, 0, receiver_loss_factor=0.5)
        self.assertEqual(lossy["system_noise_k"], 390)
        # Independent forward BER expressions check the threshold inversion.
        for modulation, factor, scale in (("4-QAM", 1, 1), ("64-QAM", 7 / 12, 1 / 7)):
            with self.subTest(modulation=modulation):
                required_linear = 10 ** (model.required_eb_n0(1e-6, "uncoded", modulation) / 10)
                ber = factor * 0.5 * math.erfc(math.sqrt(scale * required_linear))
                self.assertAlmostEqual(ber / 1e-6, 1)
        with self.assertRaisesRegex(ValueError, "4-QAM"):
            model.required_eb_n0(1e-6, "uncoded", "16-QAM")


class DashboardApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), QuietDashboardHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def post(self, data):
        request = Request(self.base_url + "/api/calculate", json.dumps(data).encode(), {"Content-Type": "application/json"})
        return urlopen(request, timeout=5)

    def test_static_assets_and_config_are_served(self):
        for path, media_type in (("/", "text/html"), ("/dashboard.js", "text/javascript"), ("/dashboard.css", "text/css")):
            with self.subTest(path=path), urlopen(self.base_url + path, timeout=5) as response:
                self.assertEqual(response.status, 200)
                self.assertIn(media_type, response.headers["Content-Type"])
                self.assertTrue(response.read())
        with urlopen(self.base_url + "/api/config", timeout=5) as response:
            config = json.load(response)
            self.assertEqual(config["parameters"], CASE_PARAMETERS)
            self.assertEqual(config["modulations"], MODULATION_OPTIONS)
            self.assertEqual(config["default_modulation"], "4-QAM")

    def test_modulation_selection_and_reset_through_api(self):
        with self.post({"modulation": "64-QAM"}) as response:
            changed = json.load(response)
        self.assertEqual(changed["inputs"]["modulation"], "64-QAM")
        self.assertEqual(changed["modulation"], "64-QAM")
        self.assertEqual(changed["downlink"]["bits_per_symbol"], 6)
        with self.post({}) as response:
            reset = json.load(response)
        self.assertEqual(reset["modulation"], "4-QAM")
        self.assertEqual(reset["downlink"]["bits_per_symbol"], 2)

    def test_slider_update_and_reset(self):
        with self.post({"spacecraft_transmitter_power_w": 300}) as response:
            changed = json.load(response)
        with self.post({}) as response:
            reset = json.load(response)
        self.assertEqual(reset["inputs"]["spacecraft_transmitter_power_w"], 150)
        self.assertAlmostEqual(changed["downlink"]["margin_db"] - reset["downlink"]["margin_db"], 10 * math.log10(2))

    def test_bad_inputs_are_rejected_with_json_errors(self):
        for data in (
            {"orbit_altitude_km": 1000}, {"coding": "coded"},
            {"ground_transmitter_power_w": 0},
            {"spacecraft_transmitter_power_w": 851},
            {"receiver_loss_factor": float("nan")},
            {"transmitter_loss_factor": True}, {"unknown": 10}, [],
            {"modulation": "16-QAM"}, {"modulation": None},
            {"modulation": 64}, {"modulation": ["64-QAM"]},
        ):
            with self.subTest(data=data):
                with self.assertRaises(HTTPError) as caught:
                    self.post(data)
                error = caught.exception
                self.assertEqual(error.code, 400)
                self.assertIn("error", json.load(error))
                error.close()

    def test_arbitrary_workspace_files_are_not_served(self):
        for path in ("/main.py", "/../main.py", "/.git/config"):
            with self.subTest(path=path):
                with self.assertRaises(HTTPError) as caught:
                    urlopen(self.base_url + path, timeout=5)
                self.assertEqual(caught.exception.code, 404)
                caught.exception.close()


if __name__ == "__main__":
    unittest.main()
