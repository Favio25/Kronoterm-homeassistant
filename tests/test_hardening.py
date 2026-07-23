"""Behavioral regression tests for the v1.7.0 hardening changes."""

from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path
import sys
import types
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "kronoterm"


def load_component_module(name: str):
    """Load a dependency-free component module without importing Home Assistant."""
    package_name = "kronoterm_offline_tests"
    if package_name not in sys.modules:
        package = types.ModuleType(package_name)
        package.__path__ = [str(COMPONENT)]
        sys.modules[package_name] = package

    qualified_name = f"{package_name}.{name}"
    if qualified_name in sys.modules:
        return sys.modules[qualified_name]

    spec = importlib.util.spec_from_file_location(
        qualified_name, COMPONENT / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[qualified_name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class IdentifierTests(unittest.TestCase):
    def test_two_cloud_entries_have_disjoint_energy_unique_ids(self) -> None:
        identifiers = load_component_module("identifiers")
        first = {
            identifiers.daily_energy_unique_id("entry-a", key)
            for key in identifiers.ENERGY_DATA_KEYS
        }
        first.add(identifiers.combined_energy_unique_id("entry-a"))
        second = {
            identifiers.daily_energy_unique_id("entry-b", key)
            for key in identifiers.ENERGY_DATA_KEYS
        }
        second.add(identifiers.combined_energy_unique_id("entry-b"))

        self.assertTrue(first.isdisjoint(second))
        self.assertEqual(len(first), 5)
        self.assertEqual(len(second), 5)

    def test_energy_migration_preserves_all_legacy_ids(self) -> None:
        identifiers = load_component_module("identifiers")
        migrations = identifiers.legacy_energy_unique_id_migrations("entry-a")

        self.assertEqual(len(migrations), 6)
        self.assertEqual(
            migrations["kronoterm_daily_CompHeating"],
            "entry-a_kronoterm_daily_CompHeating",
        )
        self.assertTrue(
            all(value.startswith("entry-a_kronoterm_") for value in migrations.values())
        )

    def test_cloud_config_id_does_not_expose_username(self) -> None:
        identifiers = load_component_module("identifiers")
        unique_id = identifiers.cloud_config_unique_id(
            "owner@example.com", "cloud"
        )

        self.assertNotIn("owner", unique_id)
        self.assertNotIn("example.com", unique_id)
        self.assertEqual(unique_id, identifiers.cloud_config_unique_id(
            " OWNER@example.com ", "cloud"
        ))

    def test_legacy_entry_data_gets_the_same_setup_unique_id(self) -> None:
        identifiers = load_component_module("identifiers")

        self.assertEqual(
            identifiers.config_unique_id_from_data(
                {
                    "connection_type": "cloud",
                    "username": "owner@example.com",
                    "system_type": "cloud",
                }
            ),
            identifiers.cloud_config_unique_id("owner@example.com", "cloud"),
        )
        self.assertEqual(
            identifiers.config_unique_id_from_data(
                {
                    "connection_type": "modbus",
                    "transport": "tcp",
                    "host": "10.0.0.42",
                    "port": 502,
                    "unit_id": 20,
                }
            ),
            "modbus:tcp:10.0.0.42:502:20",
        )


class EnergyHistoryTests(unittest.TestCase):
    def test_zero_only_windows_are_not_treated_as_real_history(self) -> None:
        history = load_component_module("energy_history")
        series = history.normalize_energy_series(
            {
                "heating": [0, "0.0", None],
                "dhw": [float("nan"), float("inf"), "bad"],
            },
            ("heating", "dhw"),
        )

        self.assertFalse(history.energy_window_has_data(series))
        series["dhw"][-1] = 0.25
        self.assertTrue(history.energy_window_has_data(series))

    def test_import_trims_leading_zeros_and_keeps_monotonic_totals(self) -> None:
        history = load_component_module("energy_history")
        entity_ids = {
            "heating": "sensor.heating",
            "dhw": "sensor.dhw",
            "combined": "sensor.combined",
        }
        day_values = {}
        history.merge_energy_window(
            day_values,
            date(2026, 1, 4),
            {
                "heating": [0.0, 2.0, -1.0, 4.0],
                "dhw": [0.0, 1.0, 0.5, 3.0],
            },
            entity_ids,
            ("heating", "dhw"),
        )

        trimmed = history.trim_history_to_first_energy(day_values)
        self.assertEqual(min(trimmed), date(2026, 1, 2))

        rows, totals = history.cumulative_energy_rows(
            trimmed,
            entity_ids.values(),
            date(2026, 1, 4),
        )
        self.assertEqual(
            rows["sensor.heating"],
            [(date(2026, 1, 2), 2.0), (date(2026, 1, 3), 2.0)],
        )
        self.assertEqual(totals["sensor.dhw"], 1.5)
        self.assertEqual(totals["sensor.combined"], 3.0)
        self.assertTrue(all(
            current >= previous
            for entity_rows in rows.values()
            for previous, current in zip(
                (value for _day, value in entity_rows),
                (value for _day, value in entity_rows[1:]),
            )
        ))

    def test_overlapping_cloud_windows_do_not_duplicate_days(self) -> None:
        history = load_component_module("energy_history")
        entity_ids = {"heating": "sensor.heating"}
        day_values = {}
        history.merge_energy_window(
            day_values,
            date(2026, 1, 4),
            {"heating": [3.0, 4.0]},
            entity_ids,
            ("heating",),
        )
        history.merge_energy_window(
            day_values,
            date(2026, 1, 3),
            {"heating": [1.0, 2.0, 99.0]},
            entity_ids,
            ("heating",),
        )

        self.assertEqual(sorted(day_values), [
            date(2026, 1, 1),
            date(2026, 1, 2),
            date(2026, 1, 3),
            date(2026, 1, 4),
        ])
        self.assertEqual(day_values[date(2026, 1, 3)]["sensor.heating"], 3.0)

    def test_previous_offset_is_inferred_without_double_application(self) -> None:
        history = load_component_module("energy_history")

        self.assertEqual(history.infer_previous_live_offset(100.0, 3.0), 0.0)
        self.assertEqual(history.infer_previous_live_offset(100.0, 100.0), 100.0)
        self.assertEqual(history.infer_previous_live_offset(100.0, 105.0), 100.0)
        self.assertEqual(history.infer_previous_live_offset(100.0, None), 0.0)

    def test_coordinator_offsets_live_tables_and_waits_for_recorder(self) -> None:
        source = (COMPONENT / "coordinator.py").read_text(encoding="utf-8")

        self.assertIn("recorder.async_adjust_statistics(", source)
        self.assertIn("await recorder.async_block_till_done()", source)
        self.assertIn("_previous_energy_reimport_totals", source)
        self.assertIn("EMPTY_HISTORY_STOP_DAYS", source)


class ModbusAddressTests(unittest.TestCase):
    def test_documented_addresses_are_converted_once(self) -> None:
        value_utils = load_component_module("value_utils")

        self.assertEqual(value_utils.documented_to_modbus_address(2102), 2101)
        self.assertEqual(value_utils.documented_to_modbus_address(1), 0)
        with self.assertRaises(ValueError):
            value_utils.documented_to_modbus_address(0)

    def test_config_validation_uses_runtime_framing_helpers(self) -> None:
        source = (COMPONENT / "config_flow_modbus.py").read_text(encoding="utf-8")

        self.assertIn("trace_packet=KronotermTcpPacketNormalizer()", source)
        self.assertIn("documented_to_modbus_address(DHW_CURRENT_TEMP_ADDR)", source)
        self.assertIn("finally:", source)


class LifecycleTests(unittest.TestCase):
    def test_options_are_transport_specific_and_reauth_is_supported(self) -> None:
        config_flow = (COMPONENT / "config_flow.py").read_text(encoding="utf-8")
        setup = (COMPONENT / "__init__.py").read_text(encoding="utf-8")

        self.assertIn("async_step_reauth_confirm", config_flow)
        self.assertIn("connection_type == CONNECTION_TYPE_MODBUS", config_flow)
        self.assertIn("scan_interval_seconds", config_flow)
        self.assertIn("entry.add_update_listener", setup)

    def test_diagnostics_redact_credentials_and_endpoints(self) -> None:
        diagnostics = (COMPONENT / "diagnostics.py").read_text(encoding="utf-8")

        for sensitive_key in ("host", "password", "serial_port", "token", "username"):
            self.assertIn(f'"{sensitive_key}"', diagnostics)
        self.assertIn("async_redact_data", diagnostics)
        self.assertNotIn("shared_attrs", diagnostics)


if __name__ == "__main__":
    unittest.main(verbosity=2)
