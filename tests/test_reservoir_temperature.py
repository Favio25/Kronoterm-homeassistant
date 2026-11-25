"""Execute Cloud reservoir climate behavior without Home Assistant or device I/O."""

import ast
import __future__
from enum import IntFlag
from types import SimpleNamespace
import unittest

from test_pool_support import load_value_utils
from test_reported_issues import COMPONENT


class ClimateFeatures(IntFlag):
    TARGET_TEMPERATURE = 1
    PRESET_MODE = 2


class ClimateParent:
    def __init__(self, *, entry, coordinator, **kwargs):
        self.coordinator = coordinator


def reservoir_climate(payload):
    """Run both real JSON/reservoir classes, stubbing only the HA parent."""
    path = COMPONENT / "climate.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    classes = ast.Module(body=[node for node in tree.body
                              if isinstance(node, ast.ClassDef)
                              and node.name in {"KronotermJsonClimate", "KronotermReservoirClimate"}],
                         type_ignores=[])
    namespace = {
        "KronotermBaseClimate": ClimateParent,
        "ClimateEntityFeature": ClimateFeatures,
        "is_measured_temperature_plausible": load_value_utils().is_measured_temperature_plausible,
    }
    exec(compile(classes, str(path), "exec", flags=__future__.annotations.compiler_flag), namespace)
    return namespace["KronotermReservoirClimate"](
        None, SimpleNamespace(data={"reservoir": payload})
    )


class ReservoirTemperatureTests(unittest.TestCase):
    def test_measured_temperature_is_independent_of_calculated_and_user_setpoints(self):
        for calculated in ("36.2", "500.0"):
            with self.subTest(calculated=calculated):
                entity = reservoir_climate({
                    "TemperaturesAndConfig": {"reservoir_temp": "23.2"},
                    "HeatingCircleData": {"circle_calc_temp": calculated, "circle_temp": "40.0"},
                })
                self.assertEqual(entity.current_temperature, 23.2)
                self.assertEqual(entity.target_temperature, 40.0)

    def test_captured_live_response_has_no_measured_reservoir_temperature(self):
        # Reduced from the read-only Cloud/Modbus capture on 2026-11-20:
        # 42.1 matched calculated-setpoint register 2034; 2101 was 37.4.
        entity = reservoir_climate({
            "TemperaturesAndConfig": {"reservoir_temp": "-60.0", "reservoir_installed": 0},
            "HeatingCircleData": {"circle_calc_temp": "42.1", "circle_temp": "50.1"},
        })
        self.assertIsNone(entity.current_temperature)
        self.assertEqual(entity.target_temperature, 50.1)

    def test_missing_measurement_never_falls_back_to_a_setpoint(self):
        for section in ({}, {"TemperaturesAndConfig": {}}):
            with self.subTest(section=section):
                entity = reservoir_climate({
                    **section,
                    "HeatingCircleData": {"circle_calc_temp": "36.2", "circle_temp": "40.0"},
                })
                self.assertIsNone(entity.current_temperature)

    def test_invalid_measured_values_are_unavailable(self):
        for value in (None, "", "unknown", "unavailable", "N/A", "-60.0", -60,
                      "500", "500.0", 500, "nan", "inf", "-inf"):
            with self.subTest(value=value):
                entity = reservoir_climate({
                    "TemperaturesAndConfig": {"reservoir_temp": value},
                    "HeatingCircleData": {"circle_calc_temp": "36.2"},
                })
                self.assertIsNone(entity.current_temperature)

    def test_numeric_measurement_is_accepted(self):
        entity = reservoir_climate({"TemperaturesAndConfig": {"reservoir_temp": 29.5}})
        self.assertEqual(entity.current_temperature, 29.5)


if __name__ == "__main__":
    unittest.main()
