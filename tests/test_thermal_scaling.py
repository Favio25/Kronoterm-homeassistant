"""Behavioral checks for SCOP-guided lifetime thermal energy scaling."""

import importlib.util
import ast
import logging
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

from test_reported_issues import COMPONENT, function_source
from test_nightly_energy import run_inline

spec = importlib.util.spec_from_file_location("thermal_scaling", COMPONENT / "thermal_scaling.py")
scaling = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scaling)


class ThermalScalingTests(unittest.TestCase):
    def test_actual_pump_and_reported_controller(self):
        for electrical, thermal, scop, expected in (
            (19782, 1442039, 7.289, 0.1),
            (19420, 1049284, 5.403, 0.1),
            (112, 608, 5.42, 1.0),
        ):
            with self.subTest(expected=expected, thermal=thermal):
                selector = scaling.ThermalScaleSelector()
                self.assertIsNone(selector.observe(electrical, thermal, scop))
                self.assertIsNone(selector.observe(electrical, thermal, scop))
                self.assertEqual(selector.observe(electrical, thermal, scop), expected)

    def test_invalid_and_unmatched_inputs_do_not_select(self):
        for sample in ((0, 608, 5.42), (1, 6, 5.42), (112, 0, 5.42),
                       (112, 608, 0), (None, 608, 5.42), (112, 608, float("nan")),
                       (112, float("inf"), 5.42), (112, 608, 2), (-112, 608, 5.42)):
            selector = scaling.ThermalScaleSelector()
            for _ in range(5):
                self.assertIsNone(selector.observe(*sample))

    def test_interrupted_evidence_restarts_confirmation(self):
        selector = scaling.ThermalScaleSelector()
        selector.observe(112, 608, 5.42)
        selector.observe(112, 608, 5.42)
        selector.observe(None, None, None)
        self.assertIsNone(selector.observe(112, 608, 5.42))
        self.assertIsNone(selector.observe(112, 608, 5.42))
        self.assertEqual(selector.observe(112, 608, 5.42), 1.0)

    def test_saved_choice_never_switches_on_reset_or_different_scop(self):
        for scale in (0.1, 1.0):
            selector = scaling.ThermalScaleSelector(scale)
            for sample in ((0, 0, 0), (112, 608, 5.42), (19782, 1442039, 7.289)):
                self.assertEqual(selector.observe(*sample), scale)
        for invalid in (True, "1.0", 10, float("nan")):
            self.assertIsNone(scaling.ThermalScaleSelector(invalid).selected)

    def coordinator(self, saved=None):
        namespace = {"Dict": dict, "Any": object,
                     "ThermalScaleSelector": scaling.ThermalScaleSelector,
                     "_LOGGER": logging.getLogger(__name__)}
        exec(function_source("modbus_coordinator.py", "_async_select_thermal_scale"), namespace)
        coordinator = SimpleNamespace(
            _thermal_scale_selector=scaling.ThermalScaleSelector(),
            _thermal_scale_loaded=False,
            _thermal_scale_store=SimpleNamespace(async_load=AsyncMock(return_value=saved),
                                                async_save=AsyncMock()),
            transport="tcp", host="test", port=502, serial_port=None, unit_id=20,
        )
        return coordinator, namespace["_async_select_thermal_scale"]

    def data(self):
        return {
            2361: {"name": "electrical_energy_heating_dhw", "raw": 112, "value": 112},
            2363: {"name": "heating_energy_heating_dhw", "raw": 608, "value": 60.8},
            2372: {"name": "scop_value", "raw": 542, "value": 5.42},
        }

    @run_inline
    async def test_coordinator_hides_pending_total_then_saves_before_publishing(self):
        coordinator, update = self.coordinator()
        for _ in range(2):
            data = self.data()
            await update(coordinator, data)
            self.assertNotIn(2363, data)
            self.assertIn(2361, data)
        coordinator._thermal_scale_store.async_save.assert_not_awaited()
        data = self.data()
        await update(coordinator, data)
        self.assertEqual(data[2363]["value"], 608)
        coordinator._thermal_scale_store.async_save.assert_awaited_once_with(
            {"scale": 1.0, "endpoint": ["tcp", "test", 502, None, 20]})
        coordinator._thermal_scale_store.async_load.assert_awaited_once()

    @run_inline
    async def test_restart_loads_only_the_same_endpoint_choice(self):
        saved = {"scale": 1.0, "endpoint": ["tcp", "test", 502, None, 20]}
        coordinator, update = self.coordinator(saved)
        data = self.data()
        await update(coordinator, data)
        self.assertEqual(data[2363]["value"], 608)
        coordinator._thermal_scale_store.async_save.assert_not_awaited()
        coordinator, update = self.coordinator(saved)
        coordinator.host = "different"
        data = self.data()
        await update(coordinator, data)
        self.assertNotIn(2363, data)

    @run_inline
    async def test_save_failure_cannot_publish_an_unpersisted_choice(self):
        coordinator, update = self.coordinator()
        for _ in range(2):
            await update(coordinator, self.data())
        coordinator._thermal_scale_store.async_save.side_effect = OSError("Disk full")
        with self.assertRaises(OSError):
            await update(coordinator, self.data())
        self.assertIsNone(coordinator._thermal_scale_selector.selected)

    @run_inline
    async def test_manual_override_needs_no_scop_and_preserves_saved_auto_choice(self):
        for multiplier in ("0.1", "1.0"):
            coordinator, update = self.coordinator()
            coordinator.thermal_scale_mode = multiplier
            data = self.data()
            del data[2372]
            await update(coordinator, data)
            self.assertAlmostEqual(data[2363]["value"], 608 * float(multiplier))
            coordinator._thermal_scale_store.async_load.assert_not_awaited()
            coordinator._thermal_scale_store.async_save.assert_not_awaited()

    def test_scaling_diagnostics_explain_pending_and_manual_states(self):
        tree = ast.parse((COMPONENT / "modbus_coordinator.py").read_text(encoding="utf-8"))
        method = next(node for node in ast.walk(tree)
                      if isinstance(node, ast.FunctionDef) and node.name == "thermal_scale_diagnostics")
        method.decorator_list = []
        namespace = {"Dict": dict, "Any": object}
        exec(compile(ast.Module(body=[method], type_ignores=[]), "diagnostics", "exec"), namespace)
        coordinator, _ = self.coordinator()
        coordinator.thermal_scale_mode = "auto"
        coordinator._thermal_scale_selector.observe(112, 608, 5.42)
        diagnostic = namespace["thermal_scale_diagnostics"](coordinator)
        self.assertEqual(diagnostic["status"], "pending")
        self.assertEqual(diagnostic["candidate"], 1.0)
        self.assertEqual(diagnostic["matching_samples"], 1)
        coordinator.thermal_scale_mode = "0.1"
        diagnostic = namespace["thermal_scale_diagnostics"](coordinator)
        self.assertEqual(diagnostic["mode"], "manual")
        self.assertEqual(diagnostic["multiplier"], 0.1)
        self.assertEqual(diagnostic["status"], "selected")
