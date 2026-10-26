"""Offline behavior checks for issues 62 and 67."""

import json
import logging
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock

from test_nightly_energy import run_inline
from test_reported_issues import COMPONENT, function_source, source


class AlarmAndPressureTests(unittest.TestCase):
    def test_cloud_pressure_uses_measured_register(self):
        namespace = {}
        exec(source("const.py"), namespace)
        pressure = next(item for item in namespace["SENSOR_DEFINITIONS"]
                        if item.key == "heating_system_pressure")
        self.assertEqual(pressure.address, 2326)
        registers = json.loads(source("kronoterm.json"))["registers"]
        measured = next(item for item in registers if item["address"] == 2326)
        self.assertEqual(measured["name_en"], "heating_system_pressure")
        setting = next(item for item in registers if item["address"] == 2325)
        self.assertEqual(setting["name_en"], "system_pressure_setting")
        self.assertNotEqual(setting["name_en"], measured["name_en"])

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
