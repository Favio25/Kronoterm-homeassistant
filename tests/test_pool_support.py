"""Offline regression checks for Modbus pool heat-loop support."""

from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import textwrap
from typing import Any, Dict
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "kronoterm"


def source(name: str) -> str:
    return (COMPONENT / name).read_text(encoding="utf-8")


def class_method_source(filename: str, class_name: str, method_name: str) -> str:
    text = source(filename)
    tree = ast.parse(text)
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != class_name:
            continue
        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == method_name:
                return ast.get_source_segment(text, child) or ""
    raise AssertionError(f"Method {class_name}.{method_name} not found in {filename}")


def load_value_utils():
    spec = importlib.util.spec_from_file_location(
        "kronoterm_value_utils", COMPONENT / "value_utils.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class DummyLogger:
    def debug(self, *args: Any, **kwargs: Any) -> None:
        pass


def pool_flag_for_registers(registers: dict[int, Any]) -> bool:
    """Execute ModbusCoordinator._update_feature_flags against test registers."""
    value_utils = load_value_utils()
    method = class_method_source(
        "modbus_coordinator.py", "ModbusCoordinator", "_update_feature_flags"
    )
    control_method = class_method_source(
        "modbus_coordinator.py", "ModbusCoordinator", "_is_enabled_control"
    )
    class_source = "class Subject:\n"
    class_source += textwrap.indent(control_method, "    ")
    class_source += "\n"
    class_source += textwrap.indent(method, "    ")
    namespace = {
        "Any": Any,
        "Dict": Dict,
        "_LOGGER": DummyLogger(),
        "is_pool_setpoint_available": value_utils.is_pool_setpoint_available,
        "is_pool_temperature_available": value_utils.is_pool_temperature_available,
    }
    exec(class_source, namespace)
    namespace["Subject"]._is_enabled_control = staticmethod(
        namespace["Subject"]._is_enabled_control
    )
    subject = namespace["Subject"]()
    data = {
        address: {"value": value, "raw": value}
        for address, value in registers.items()
    }
    subject._update_feature_flags(data)
    return subject.pool_installed


def modbus_pool_current_temperature(value: Any) -> float | None:
    """Execute KronotermModbusPoolClimate.current_temperature for one register."""
    value_utils = load_value_utils()
    method = class_method_source(
        "climate.py", "KronotermModbusPoolClimate", "current_temperature"
    )
    class_source = """class Subject:
    def __init__(self, value):
        self._value = value
        self._current_temp_address = 2109

    def _get_register_value(self, address):
        return self._value

"""
    class_source += textwrap.indent(method, "    ")
    namespace = {
        "is_pool_temperature_available": value_utils.is_pool_temperature_available,
    }
    exec(class_source, namespace)
    current_temperature = namespace["Subject"](value).current_temperature
    if callable(current_temperature):
        return current_temperature()
    return current_temperature


POOL_REGISTERS = {
    2079: "pool_setpoint",
    2080: "pool_current_setpoint",
    2081: "pool_operation_mode",
    2086: "pool_eco_offset",
    2087: "pool_comfort_offset",
    2109: "pool_temperature",
}


class PoolLoopSupport(unittest.TestCase):
    def test_modbus_coordinator_detects_pool_installed(self) -> None:
        """pool_installed is derived from live pool readings/controls."""
        self.assertTrue(pool_flag_for_registers({2109: 12.5}))
        self.assertTrue(pool_flag_for_registers({2080: 25.0}))
        self.assertTrue(pool_flag_for_registers({2020: 1}))
        self.assertTrue(pool_flag_for_registers({2081: 2}))

    def test_modbus_pool_detection_ignores_unavailable_sentinels(self) -> None:
        """Unavailable pool readings must not create phantom pool entities."""
        for value in (None, -60.0, -40.0, 0.0, "unknown"):
            with self.subTest(value=value):
                self.assertFalse(pool_flag_for_registers({2109: value}))

    def test_modbus_pool_climate_hides_unavailable_temperatures(self) -> None:
        """The pool climate does not expose controller sentinel values."""
        for value in (None, -60.0, -40.0, 0.0, "unknown"):
            with self.subTest(value=value):
                self.assertIsNone(modbus_pool_current_temperature(value))
        self.assertEqual(modbus_pool_current_temperature(12.5), 12.5)

    def test_modbus_offset_write_maps_pool_page_ten(self) -> None:
        """Pool eco/comfort offsets write to their page-10 registers."""
        offset = class_method_source(
            "modbus_writes.py", "ModbusWriteMixin", "async_set_offset"
        )
        self.assertIn('(10, "circle_eco_offset"): 2086', offset)
        self.assertIn('(10, "circle_comfort_offset"): 2087', offset)

    def test_modbus_setpoint_and_mode_write_maps_pool_page_ten(self) -> None:
        """Pool setpoint and operation mode resolve to their page-10 registers."""
        setpoint = class_method_source(
            "modbus_writes.py", "ModbusWriteMixin", "async_set_temperature"
        )
        self.assertIn("10: 2079", setpoint)
        mode = class_method_source(
            "modbus_writes.py", "ModbusWriteMixin", "async_set_loop_mode_by_page"
        )
        self.assertIn("10: 2081", mode)

    def test_modbus_pool_climate_class_wires_the_right_registers(self) -> None:
        """The pool climate reads temperature/setpoint and writes the pool setpoint."""
        climate = source("climate.py")
        self.assertIn("class KronotermModbusPoolClimate", climate)
        cls = climate[climate.index("class KronotermModbusPoolClimate"):]
        for token in (
            'translation_key="pool_temperature"',
            "current_temp_address=2109",
            "target_temp_address=2080",
            "write_temp_address=2079",
            "operation_mode_address=2081",
            "supports_cooling=False",
            "enable_preset=True",
        ):
            self.assertIn(token, cls, token)

    def test_modbus_pool_climate_registered_behind_install_flag(self) -> None:
        """The pool climate is only created when the pool is installed."""
        climate = source("climate.py")
        self.assertIn("KronotermModbusPoolClimate(entry, coordinator)", climate)
        self.assertIn('getattr(coordinator, "pool_installed", False)', climate)

    def test_pool_offset_numbers_defined_for_page_ten(self) -> None:
        """The eco/comfort offset numbers stay wired to the pool install flag."""
        number = source("number.py")
        self.assertIn(
            'OffsetConfig("pool_eco_offset", 10, 2086, "circle_eco_offset", -10.0, 0.0, "pool_installed")',
            number,
        )
        self.assertIn(
            'OffsetConfig("pool_comfort_offset", 10, 2087, "circle_comfort_offset", 0.0, 10.0, "pool_installed")',
            number,
        )

    def test_pool_registers_present_in_both_maps(self) -> None:
        """Both controller maps expose the pool registers with the expected names."""
        for filename in ("kronoterm.json", "kronoterm_tt3000.json"):
            registers = {item["address"]: item for item in json.loads(source(filename))["registers"]}
            for address, name_en in POOL_REGISTERS.items():
                self.assertIn(address, registers, f"{address} missing from {filename}")
                self.assertEqual(registers[address]["name_en"], name_en)

    def test_pool_climate_and_sensor_names_stay_distinct(self) -> None:
        """The pool climate name does not collide with the pool sensor name."""
        for locale in ("en", "de", "it", "sl"):
            climate = json.loads(source(f"translations/{locale}.json"))["entity"]["climate"]
            self.assertIn("pool_temperature", climate)
        english = json.loads(source("translations/en.json"))["entity"]
        self.assertEqual(english["climate"]["pool_temperature"]["name"], "Pool Thermostat")
        self.assertEqual(english["sensor"]["pool_temperature"]["name"], "Pool Temperature")

    def test_cloud_pool_page_is_wired(self) -> None:
        """The Cloud pool GET/SET pages and page->query mapping exist."""
        const = source("const.py")
        self.assertIn('"pool": {"TopPage": "1", "Subpage": "10"}', const)
        self.assertIn('"pool": {"TopPage": "1", "Subpage": "10", "Action": "1"}', const)
        self.assertIn('10: "pool"', const)

    def test_cloud_coordinator_fetches_pool_page(self) -> None:
        """The main Cloud coordinator fetches the pool page each update."""
        updater = class_method_source(
            "coordinator.py", "KronotermMainCoordinator", "_async_update_data"
        )
        self.assertIn('"pool"', updater)

    def test_cloud_pool_climate_reads_pool_fields(self) -> None:
        """The Cloud pool climate reads pool_temp and is created when installed."""
        climate = source("climate.py")
        self.assertIn("class KronotermPoolClimate(KronotermJsonClimate)", climate)
        self.assertIn('data_key="pool"', climate)
        self.assertIn('current_temp_json_key="pool_temp"', climate)
        self.assertIn("KronotermPoolClimate(entry, coordinator)", climate)


if __name__ == "__main__":
    unittest.main(verbosity=2)
