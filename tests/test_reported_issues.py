"""Offline regression checks for the currently reported Kronoterm issues.

The fix checks run without Home Assistant credentials or access to a heat
pump. Deferred checks document behavior that must not be changed without a
representative installation or controller documentation.
"""

from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "kronoterm"


def source(name: str) -> str:
    return (COMPONENT / name).read_text(encoding="utf-8")


def function_source(filename: str, function_name: str) -> str:
    text = source(filename)
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
            return ast.get_source_segment(text, node) or ""
    raise AssertionError(f"Function {function_name!r} not found in {filename}")


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


class ReportedIssueRegressions(unittest.TestCase):
    def test_issue_51_each_cloud_entry_gets_a_private_cookie_session(self) -> None:
        """Main and DHW Cloud entries use per-entry sessions, not HA's global jar."""
        setup = function_source("__init__.py", "async_setup_entry")
        self.assertGreaterEqual(setup.count("async_create_clientsession(hass)"), 2)
        self.assertNotIn("async_get_clientsession", setup)

    def test_issue_52_config_flow_and_runtime_share_authentication(self) -> None:
        """Both call the helper that confirms BasicAuth or PHP web login."""
        validator = function_source("config_flow.py", "validate_credentials")
        runtime_login = function_source("coordinator.py", "_perform_login")
        auth_helper = function_source("cloud_auth.py", "async_authenticate_cloud")
        self.assertIn("async_authenticate_cloud", validator)
        self.assertIn("async_authenticate_cloud", runtime_login)
        self.assertIn("_async_web_login", auth_helper)
        self.assertIn("_async_handshake", auth_helper)
        self.assertIn("ConfigEntryAuthFailed", runtime_login)

    def test_cloud_debug_logs_do_not_dump_response_payloads(self) -> None:
        """Debug logging records response size without exposing device data."""
        response_handler = class_method_source(
            "coordinator.py", "KronotermBaseCoordinator", "_process_response"
        )
        self.assertIn("len(raw_text)", response_handler)
        self.assertNotIn('query_params, raw_text', response_handler)
        coordinator = source("coordinator.py")
        self.assertNotIn("Consumption raw payload", coordinator)
        self.assertNotIn("Consumption payload type=%s value=%s", coordinator)

    def test_cloud_optional_page_failures_are_isolated(self) -> None:
        """The optional page batch retains successful sibling responses."""
        updater = class_method_source("coordinator.py", "KronotermMainCoordinator", "_async_update_data")
        tree = ast.parse(updater)
        gathers = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Attribute) or node.func.attr != "gather":
                continue
            gathers.append(node)
        self.assertGreaterEqual(len(gathers), 2)
        self.assertTrue(
            all(
                any(
                    keyword.arg == "return_exceptions"
                    and isinstance(keyword.value, ast.Constant)
                    and keyword.value.value is True
                    for keyword in node.keywords
                )
                for node in gathers
            )
        )

    def test_issue_23_previous_day_resync_is_present_but_only_in_memory_guarded(self) -> None:
        """Deferred: the once-per-day guard still resets on restart."""
        coordinator = source("coordinator.py")
        init = class_method_source("coordinator.py", "KronotermMainCoordinator", "__init__")
        sync = function_source("coordinator.py", "_sync_previous_day_statistics")
        self.assertIn("self._last_stats_sync_date = None", init)
        self.assertIn("self._last_stats_sync_date == today", sync)
        self.assertNotRegex(coordinator, r"hass\.data\[[^\]]+\].*_last_stats_sync_date")

    def test_issue_54_dhw_mode_exposes_boiler_temperature_once(self) -> None:
        """DHW setup keeps the older canonical unique ID and one data path."""
        dhw_setup = function_source("sensor.py", "_async_setup_dhw_entities")
        migration = function_source("__init__.py", "async_migrate_entry")
        self.assertEqual(dhw_setup.count('"GlobalOverview", "boiler_temp"'), 1)
        self.assertIn('"dhw_current_temperature"', dhw_setup)
        self.assertNotIn('"dhw_boiler_temp"', dhw_setup)
        self.assertIn("dhw_boiler_temp", migration)
        self.assertIn("dhw_current_temperature", migration)

    def test_issue_54_display_names_distinguish_entity_roles(self) -> None:
        """English status/control and measured/climate names no longer collide."""
        translations = json.loads(
            (COMPONENT / "translations" / "en.json").read_text(encoding="utf-8")
        )["entity"]
        self.assertEqual(
            translations["binary_sensor"]["additional_source"]["name"],
            "Additional Source Status",
        )
        self.assertEqual(
            translations["switch"]["additional_source_switch"]["name"],
            "Additional Source Control",
        )
        self.assertEqual(
            translations["climate"]["loop_2_temperature"]["name"],
            "Loop 2 Thermostat",
        )
        self.assertEqual(
            translations["sensor"]["loop_2_temperature"]["name"],
            "Loop 2 Temperature",
        )
        climates = source("climate.py")
        self.assertIn('fallback_name="Loop 2 Thermostat"', climates)
        self.assertIn('fallback_name="DHW Thermostat"', climates)

    def test_issue_52_energy_labels_and_scales_match_register_meaning(self) -> None:
        """Electrical and thermal totals use the documented register pairs."""
        definitions = json.loads((COMPONENT / "kronoterm.json").read_text(encoding="utf-8"))
        registers = {item["address"]: item for item in definitions["registers"]}
        self.assertIn("Električna energija", registers[2361]["name"])
        self.assertEqual(registers[2361]["name_en"], "electrical_energy_heating_dhw")
        self.assertEqual(registers[2361]["register32_low"], 2362)
        self.assertIn("Toplotna energija", registers[2363]["name"])
        self.assertEqual(registers[2363]["name_en"], "heating_energy_heating_dhw")
        self.assertEqual(registers[2363]["register32_low"], 2364)
        self.assertEqual(registers[2363]["unit"], "x 0.1 kWh")
        self.assertEqual(registers[2371]["scale"], 0.01)
        self.assertEqual(registers[2372]["scale"], 0.001)

    def test_issue_52_value32_reader_combines_both_unsigned_words(self) -> None:
        """Live totals independently reproduce the controller's SCOP."""
        spec = importlib.util.spec_from_file_location(
            "kronoterm_value_utils", COMPONENT / "value_utils.py"
        )
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)

        electrical_kwh = module.combine_u16_words(0, 19380)
        thermal_kwh = module.combine_u16_words(16, 503) * 0.1
        self.assertEqual(electrical_kwh, 19380)
        self.assertAlmostEqual(thermal_kwh, 104907.9, places=6)
        self.assertAlmostEqual(thermal_kwh / electrical_kwh, 5.413, places=3)

        updater = class_method_source(
            "modbus_coordinator.py", "ModbusCoordinator", "_async_update_data"
        )
        self.assertIn("combine_u16_words(high_value, low_value)", updater)
        self.assertNotIn("raw_value = low_value", updater)

    def test_kronoterm_tcp_fixed_transaction_id_is_normalized(self) -> None:
        """The controller's fixed TID 20 is replaced with the active request TID."""
        spec = importlib.util.spec_from_file_location(
            "kronoterm_value_utils", COMPONENT / "value_utils.py"
        )
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)

        normalizer = module.KronotermTcpPacketNormalizer()
        request = bytes.fromhex("1a3400000006140300000001")
        response = bytes.fromhex("0014000000051403021234")
        self.assertEqual(normalizer(True, request), request)
        self.assertEqual(
            normalizer(False, response),
            bytes.fromhex("1a34000000051403021234"),
        )
        self.assertEqual(normalizer(False, b"\x00\x14"), b"\x00\x14")

    def test_deferred_issue_21_has_no_unverified_cascade_model(self) -> None:
        """Deferred: do not invent cascade behavior without representative data."""
        component_text = "\n".join(path.read_text(encoding="utf-8") for path in COMPONENT.glob("*.py"))
        self.assertIn('"hp_id"', component_text)
        self.assertIsNone(re.search(r"selected_hp|heat_pump_ids|cascade_members", component_text))


if __name__ == "__main__":
    unittest.main(verbosity=2)
