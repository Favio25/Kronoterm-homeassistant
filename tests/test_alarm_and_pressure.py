"""Offline behavior checks for issues 62 and 67."""

from functools import partial
import json
import logging
import re
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock

from test_nightly_energy import run_inline
from test_reported_issues import COMPONENT, class_method_source, function_source, source


class AlarmAndPressureTests(unittest.TestCase):
    def test_cloud_register_definitions_keep_setting_and_measurement_apart(self):
        namespace = {}
        exec(source("const.py"), namespace)
        keys = {item.key for item in namespace["SENSOR_DEFINITIONS"]}
        # The Cloud payload only exposes the alarm limit as a register.
        self.assertIn("system_pressure_setting", keys)
        self.assertNotIn("heating_system_pressure", keys)
        registers = json.loads(source("kronoterm.json"))["registers"]
        measured = next(item for item in registers if item["address"] == 2326)
        self.assertEqual(measured["name_en"], "heating_system_pressure")
        setting = next(item for item in registers if item["address"] == 2325)
        self.assertEqual(setting["name_en"], "system_pressure_setting")
        self.assertNotEqual(setting["name_en"], measured["name_en"])

    @staticmethod
    def _pressure_sensor(data):
        """Build a stand-in for KronotermCloudPressureSensor bound to `data`."""
        namespace = {"re": re}
        for method in ("_current_function_value", "_fallback_value", "native_value"):
            exec(
                class_method_source("sensor.py", "KronotermCloudPressureSensor", method),
                namespace,
            )
        sensor = SimpleNamespace(
            coordinator=SimpleNamespace(data=data),
            _field="heating_system_pressure",
            _fallback_address=2326,
            _PAGE_KEYS=("system_data", "main", "shortcuts", "main_settings", "info"),
        )
        for name, func in namespace.items():
            if callable(func) and name.startswith(("_", "native")):
                setattr(sensor, name, partial(func, sensor))
        return sensor

    def test_cloud_pressure_prefers_current_function_data(self):
        """The alarm limit in ModbusReg must never win over the live reading."""
        data = {
            "main": {"ModbusReg": [
                {"address": 2325, "value": "1.3"},
                {"address": 2326, "value": "1.3"},
            ]},
            "info": {"CurrentFunctionData": [{
                "heating_system_pressure": "2.5",
                "heating_source_pressure": "1.2",
            }]},
        }
        self.assertEqual(self._pressure_sensor(data).native_value(), 2.5)

    def test_cloud_pressure_falls_back_to_register_and_tolerates_gaps(self):
        register_only = {"main": {"ModbusReg": [{"address": 2326, "value": "2.1"}]}}
        self.assertEqual(self._pressure_sensor(register_only).native_value(), 2.1)
        self.assertIsNone(self._pressure_sensor({}).native_value())
        self.assertIsNone(self._pressure_sensor(None).native_value())
        empty_block = {"info": {"CurrentFunctionData": []}}
        self.assertIsNone(self._pressure_sensor(empty_block).native_value())

    def test_cloud_info_page_refreshes_every_cycle(self):
        """CurrentFunctionData is only live if the info page is re-fetched."""
        update = class_method_source(
            "coordinator.py", "KronotermMainCoordinator", "_async_update_data"
        )
        page_block = update.split("page_keys = (")[1].split("\n            )")[0]
        self.assertIn('"info"', page_block)
        self.assertIn('if data.get("info") is None', update)

    @run_inline
    async def test_alarm_action_posts_supplied_query_and_refreshes(self):
        constants = {}
        exec(source("const.py"), constants)
        namespace = {"_LOGGER": logging.getLogger(__name__), "UpdateFailed": RuntimeError}
        for name in ("async_acknowledge_alarm", "_send_set_request"):
            exec(function_source("coordinator.py", name), namespace)
        coordinator = SimpleNamespace(
            api_queries_set=constants["API_QUERIES_SET"],
            _request_with_retries=AsyncMock(return_value={"result": "success"}),
            async_request_refresh=AsyncMock(),
        )
        coordinator._send_set_request = lambda key, form: namespace["_send_set_request"](coordinator, key, form)
        self.assertTrue(await namespace["async_acknowledge_alarm"](coordinator))
        coordinator._request_with_retries.assert_awaited_once_with(
            "POST", {"TopPage": "1", "Subpage": "11", "Action": "3"}, [])
        coordinator.async_request_refresh.assert_awaited_once()
        coordinator._request_with_retries.return_value = {"result": "error"}
        self.assertFalse(await namespace["async_acknowledge_alarm"](coordinator))
        self.assertEqual(coordinator.async_request_refresh.await_count, 1)

    @run_inline
    async def test_button_surfaces_failure(self):
        namespace = {"HomeAssistantError": RuntimeError}
        exec(function_source("button.py", "async_press"), namespace)  # Alarm class is first.
        button = SimpleNamespace(coordinator=SimpleNamespace(
            async_acknowledge_alarm=AsyncMock(return_value=False)))
        with self.assertRaisesRegex(RuntimeError, "acknowledgement failed"):
            await namespace["async_press"](button)
        button.coordinator.async_acknowledge_alarm.return_value = True
        await namespace["async_press"](button)

    @run_inline
    async def test_buttons_are_only_registered_for_main_cloud(self):
        namespace = {"_LOGGER": logging.getLogger(__name__), "DOMAIN": "kronoterm",
                     "HomeAssistant": object, "ConfigEntry": object, "AddEntitiesCallback": object,
                     "KronotermReimportEnergyButton": Mock(return_value="reimport"),
                     "KronotermAcknowledgeAlarmButton": Mock(return_value="alarm")}
        exec(function_source("button.py", "async_setup_entry"), namespace)
        entry = SimpleNamespace(entry_id="test")
        for mode in ("cloud", "modbus", "dhw"):
            add = Mock()
            hass = SimpleNamespace(data={"kronoterm": {"test": SimpleNamespace(system_type=mode)}})
            await namespace["async_setup_entry"](hass, entry, add)
            if mode == "cloud":
                add.assert_called_once_with(["reimport", "alarm"])
            else:
                add.assert_not_called()

    def test_alarm_translation_exists_in_all_languages(self):
        for path in [COMPONENT / "strings.json", *(COMPONENT / "translations").glob("*.json")]:
            with self.subTest(path=path.name):
                data = json.loads(path.read_text(encoding="utf-8"))
                self.assertTrue(data["entity"]["button"]["acknowledge_alarm"]["name"])
