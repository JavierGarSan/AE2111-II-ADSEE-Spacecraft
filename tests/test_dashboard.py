"""Integration checks for mission selection, editable inputs and the local API."""

import json
import math
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from dashboard import DashboardHandler
from earth_model import (
    CASE_PARAMETERS, DEFAULT_MODULATION, DEFAULT_PLANET, ENCODING_OPTIONS,
    MODULATION_OPTIONS, PLANET_OPTIONS, calculate_earth, calculate_scenario,
    DEFAULT_TEMPLATE, MISSION_TEMPLATES,
)
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
        self.assertEqual(result["inputs"]["planet"], DEFAULT_PLANET)
        self.assertAlmostEqual(result["uplink"]["frequency_ghz"], 2.2 * 221 / 240)
        self.assertAlmostEqual(result["payload"]["required_downlink_rate_bps"], result["payload"]["daily_data_bits"] / 1800)
        for direction in ("uplink", "downlink"):
            budget = result[direction]
            self.assertGreater(budget["free_space_loss_db"], 0)
            self.assertTrue(all(math.isfinite(v) for v in budget.values()
                                if isinstance(v, (int, float))))
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

    def test_initially_locked_values_can_be_changed_after_unlocking(self):
        for parameter in CASE_PARAMETERS:
            if not parameter["locked"]:
                continue
            identifier = parameter["id"]
            if "choices" in parameter:
                changed = "ldpc"
            elif identifier == "spacecraft_power_w":
                changed = parameter["max"]
            elif identifier == "elongation_angle_deg":
                changed = 45
            else:
                changed = parameter["min"]
            with self.subTest(parameter=parameter["id"]):
                result = calculate_scenario({identifier: changed})
                self.assertEqual(result["inputs"][identifier], changed)
                json.dumps(result, allow_nan=False)

    def test_all_numeric_parameter_bounds_are_accepted(self):
        for parameter in CASE_PARAMETERS:
            if "choices" in parameter:
                continue
            for bound in ("min", "max"):
                with self.subTest(parameter=parameter["id"], bound=bound):
                    overrides = {parameter["id"]: parameter[bound]}
                    # The total RF power constraint must also hold when its
                    # inputs are set to independently valid slider endpoints.
                    if parameter["id"] == "spacecraft_power_w":
                        overrides["spacecraft_transmitter_power_w"] = 1
                    elif parameter["id"] == "spacecraft_transmitter_power_w":
                        overrides["spacecraft_power_w"] = 10000
                    result = calculate_scenario(overrides)
                    self.assertEqual(result["inputs"][parameter["id"]], parameter[bound])
                    json.dumps(result, allow_nan=False)

    def test_numeric_parameter_types_and_bounds_are_validated(self):
        for parameter in CASE_PARAMETERS:
            if "choices" in parameter:
                continue
            invalid_values = (
                parameter["min"] - parameter["step"],
                parameter["max"] + parameter["step"],
                True, "1", float("nan"), float("inf"),
            )
            for value in invalid_values:
                with self.subTest(parameter=parameter["id"], value=value):
                    with self.assertRaises(ValueError):
                        calculate_scenario({parameter["id"]: value})
        with self.assertRaises(ValueError):
            calculate_scenario({"payload_bits_per_pixel": 32.5})

    def test_zero_imaging_duty_cycle_has_no_downlink_eb_n0(self):
        result = calculate_scenario({"payload_duty_cycle_percent": 0})
        self.assertEqual(result["payload"]["daily_data_bits"], 0)
        self.assertEqual(result["payload"]["required_downlink_rate_bps"], 0)
        downlink = result["downlink"]
        for field in ("information_rate_bps", "transmitted_rate_bps", "symbol_rate_baud"):
            self.assertEqual(downlink[field], 0)
        self.assertIsNone(downlink["available_eb_n0_db"])
        self.assertIsNone(downlink["margin_db"])
        self.assertTrue(math.isfinite(downlink["carrier_to_noise_density_db_hz"]))
        self.assertTrue(math.isfinite(result["uplink"]["margin_db"]))
        json.dumps(result, allow_nan=False)

    def test_encoding_changes_channel_rate_and_assumed_coding_gain(self):
        uncoded = calculate_scenario({"coding": "uncoded"})
        for encoding in (option for option in ENCODING_OPTIONS if option != "uncoded"):
            with self.subTest(encoding=encoding):
                encoded = calculate_scenario({"coding": encoding})
                self.assertEqual(encoded["inputs"]["coding"], encoding)
                self.assertEqual(encoded["payload"], uncoded["payload"])
                self.assertEqual(encoded["geometry"], uncoded["geometry"])
                for direction in ("uplink", "downlink"):
                    budget = encoded[direction]
                    original = uncoded[direction]
                    self.assertEqual(budget["information_rate_bps"], original["information_rate_bps"])
                    self.assertAlmostEqual(budget["transmitted_rate_bps"] / original["transmitted_rate_bps"], 4 / 3)
                    self.assertAlmostEqual(budget["symbol_rate_baud"] / original["symbol_rate_baud"], 4 / 3)
                    self.assertEqual(budget["available_eb_n0_db"], original["available_eb_n0_db"])
                    self.assertAlmostEqual(original["required_eb_n0_db"] - budget["required_eb_n0_db"], 10)
                    self.assertAlmostEqual(budget["margin_db"] - original["margin_db"], 10)

    def test_planet_selection_preserves_inputs_and_changes_geometry(self):
        baseline = calculate_scenario({
            "orbit_altitude_km": 1000,
            "payload_swath_deg": 30,
            "payload_bits_per_pixel": 16,
            "payload_duty_cycle_percent": 25,
            "spacecraft_transmitter_power_w": 300,
            "modulation": "64-QAM", "coding": "ldpc",
        })
        for planet in PLANET_OPTIONS:
            with self.subTest(planet=planet["id"]):
                overrides = {**baseline["inputs"], "planet": planet["id"]}
                selected = calculate_scenario(overrides)
                self.assertEqual(selected["inputs"], overrides)
                self.assertEqual(selected["scenario"], planet["id"])
                self.assertEqual(selected["planet_label"], planet["label"])
                geometry = selected["geometry"]
                self.assertEqual(geometry["orbiting_body"], planet["id"])
                expected_speed = math.sqrt(
                    geometry["planet_mu_km3_s2"] /
                    (geometry["planet_radius_km"] + overrides["orbit_altitude_km"])
                ) * 1000
                self.assertAlmostEqual(selected["payload"]["scan_speed_m_s"], expected_speed)
                if planet["id"] != "earth":
                    self.assertNotEqual(geometry["slant_range_km"], baseline["geometry"]["slant_range_km"])
                    self.assertNotEqual(selected["payload"]["active_rate_bps"], baseline["payload"]["active_rate_bps"])
                json.dumps(selected, allow_nan=False)

    def test_elongation_changes_interplanetary_range_without_setting_inputs(self):
        for planet in ("mars", "venus", "mercury"):
            with self.subTest(planet=planet):
                unspecified = calculate_scenario({"planet": planet})
                closest = calculate_scenario({"planet": planet, "elongation_angle_deg": 0})
                farthest = calculate_scenario({"planet": planet, "elongation_angle_deg": 180})
                self.assertIsNone(unspecified["inputs"]["elongation_angle_deg"])
                self.assertEqual(unspecified["geometry"]["effective_elongation_deg"], 180)
                self.assertEqual(unspecified["geometry"]["slant_range_km"], farthest["geometry"]["slant_range_km"])
                self.assertLess(closest["geometry"]["slant_range_km"], farthest["geometry"]["slant_range_km"])
                self.assertGreater(closest["downlink"]["margin_db"], farthest["downlink"]["margin_db"])

    def test_all_planet_modulation_encoding_combinations_are_serializable(self):
        self.assertEqual({entry["id"] for entry in PLANET_OPTIONS}, {"earth", "moon", "mars", "venus", "mercury"})
        self.assertEqual(set(ENCODING_OPTIONS), {"uncoded", "ldpc"})
        for planet in PLANET_OPTIONS:
            for modulation in MODULATION_OPTIONS:
                for encoding in ENCODING_OPTIONS:
                    with self.subTest(planet=planet["id"], modulation=modulation, encoding=encoding):
                        result = calculate_scenario({
                            "planet": planet["id"], "modulation": modulation,
                            "coding": encoding,
                        })
                        self.assertEqual(result["inputs"]["planet"], planet["id"])
                        self.assertEqual(result["modulation"], modulation)
                        self.assertEqual(result["inputs"]["coding"], encoding)
                        for direction in ("uplink", "downlink"):
                            self.assertTrue(math.isfinite(result[direction]["margin_db"]))
                        json.dumps(result, allow_nan=False)

    def test_all_mission_templates_load_and_recalculate(self):
        expected = [
            ("Case 1 - Earth LEO", "earth", 820, 45, 1e8, 14),
            ("Case 2 - Moon LRO", "moon", 50, 6, 1e8, 8),
            ("Case 3 - Mars Hope", "mars", 1000, 5, 1e6, 12),
            ("Case 4 - Mars MRO", "mars", 300, 0.5, 1e6, 9),
            ("Case 5 - Mercury Bepi. C", "mercury", 500, 10, 1e5, 13),
        ]
        self.assertEqual(len(MISSION_TEMPLATES), 5)
        ids = {parameter["id"] for parameter in CASE_PARAMETERS}
        for template, (label, planet, altitude, swath, uplink_rate, locked_count) in zip(MISSION_TEMPLATES, expected):
            with self.subTest(template=template["id"]):
                self.assertEqual(template["label"], label)
                self.assertEqual(template["planet"], planet)
                self.assertEqual(set(template["values"]), ids)
                self.assertEqual(set(template["locks"]), ids)
                self.assertEqual(sum(template["locks"].values()), locked_count)
                self.assertEqual(template["values"]["orbit_altitude_km"], altitude)
                self.assertEqual(template["values"]["payload_swath_deg"], swath)
                self.assertEqual(template["values"]["required_uplink_rate_bps"], uplink_rate)
                for modulation in MODULATION_OPTIONS:
                    inputs = {**template["values"], "planet": planet, "modulation": modulation}
                    result = calculate_scenario(inputs)
                    self.assertEqual(result["inputs"], inputs)
                    self.assertTrue(math.isfinite(result["downlink"]["margin_db"]))
                    json.dumps(result, allow_nan=False)

    def test_template_lock_settings_follow_the_coloured_cells(self):
        templates = {entry["id"]: entry for entry in MISSION_TEMPLATES}
        # These differ between columns and catch incorrectly reused Earth locks.
        self.assertFalse(templates["case_2"]["locks"]["spacecraft_antenna_diameter_m"])
        self.assertTrue(templates["case_2"]["locks"]["downlink_frequency_ghz"])
        self.assertFalse(templates["case_3"]["locks"]["ground_antenna_diameter_m"])
        self.assertTrue(templates["case_4"]["locks"]["ground_antenna_diameter_m"])
        self.assertFalse(templates["case_4"]["locks"]["payload_swath_deg"])
        self.assertTrue(templates["case_5"]["locks"]["payload_bits_per_pixel"])
        for template in MISSION_TEMPLATES[1:]:
            self.assertFalse(template["locks"]["coding"])
        for template in MISSION_TEMPLATES:
            self.assertEqual(template["values"]["turnaround_ratio"],
                             221 / 240 if template["planet"] in ("earth", "moon") else 749 / 880)


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
            self.assertEqual(config["planets"], PLANET_OPTIONS)
            self.assertEqual(config["default_planet"], DEFAULT_PLANET)
            self.assertEqual(config["encodings"], ENCODING_OPTIONS)
            self.assertEqual(config["default_encoding"], "uncoded")
            self.assertEqual(config["templates"], MISSION_TEMPLATES)
            self.assertEqual(config["default_template"], DEFAULT_TEMPLATE)

    def test_template_switches_through_api(self):
        for template in MISSION_TEMPLATES:
            with self.subTest(template=template["label"]):
                inputs = {**template["values"], "planet": template["planet"], "modulation": "64-QAM"}
                with self.post(inputs) as response:
                    result = json.load(response)
                self.assertEqual(result["inputs"], inputs)
                self.assertEqual(result["scenario"], template["planet"])
                self.assertGreater(result["payload"]["required_downlink_rate_bps"], 0)

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

    def test_planet_encoding_and_unlocked_input_updates_through_api(self):
        for planet in PLANET_OPTIONS:
            with self.subTest(planet=planet["id"]):
                inputs = {
                    "planet": planet["id"], "coding": "ldpc",
                    "orbit_altitude_km": 1000,
                    "ground_antenna_diameter_m": 20,
                    "payload_bits_per_pixel": 16,
                }
                with self.post(inputs) as response:
                    selected = json.load(response)
                self.assertEqual(selected["scenario"], planet["id"])
                for key, value in inputs.items():
                    self.assertEqual(selected["inputs"][key], value)
                self.assertAlmostEqual(selected["downlink"]["transmitted_rate_bps"],
                                       selected["payload"]["required_downlink_rate_bps"] / 0.75)
        with self.post({}) as response:
            reset = json.load(response)
        self.assertEqual(reset["scenario"], "earth")
        self.assertEqual(reset["inputs"]["coding"], "uncoded")
        self.assertEqual(reset["inputs"]["orbit_altitude_km"], 820)

    def test_zero_duty_cycle_returns_json_null_instead_of_invalid_numbers(self):
        with self.post({"payload_duty_cycle_percent": 0}) as response:
            result = json.load(response)
        self.assertIsNone(result["downlink"]["margin_db"])
        self.assertIsNone(result["downlink"]["available_eb_n0_db"])
        self.assertEqual(result["payload"]["required_downlink_rate_bps"], 0)

    def test_slider_update_and_reset(self):
        with self.post({"spacecraft_transmitter_power_w": 300}) as response:
            changed = json.load(response)
        with self.post({}) as response:
            reset = json.load(response)
        self.assertEqual(reset["inputs"]["spacecraft_transmitter_power_w"], 150)
        self.assertAlmostEqual(changed["downlink"]["margin_db"] - reset["downlink"]["margin_db"], 10 * math.log10(2))

    def test_bad_inputs_are_rejected_with_json_errors(self):
        for data in (
            {"orbit_altitude_km": 0}, {"orbit_altitude_km": "1000"},
            {"coding": "reed-solomon"}, {"coding": None},
            {"coding": "coded"},
            {"coding": 1}, {"coding": ["coded"]},
            {"planet": "jupiter"}, {"planet": None},
            {"planet": 1}, {"planet": ["moon"]},
            {"payload_bits_per_pixel": 32.5},
            {"payload_duty_cycle_percent": -1},
            {"elongation_angle_deg": float("inf")},
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
