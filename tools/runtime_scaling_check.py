"""Run inside the Home Assistant image with /workspace mounted read-only.

Uses real HA coordinators, sensors, and storage, with all device I/O mocked.
No production configuration is mounted and no heat pump is contacted.
"""

import asyncio
import tempfile
from types import SimpleNamespace
from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from custom_components.kronoterm.modbus_coordinator import ModbusCoordinator
from custom_components.kronoterm.sensor import KronotermModbusRegSensor
from custom_components.kronoterm.button import KronotermAcknowledgeAlarmButton
from custom_components.kronoterm.config_flow import KronotermOptionsFlowHandler


def sample():
    return {
        2361: {"name": "electrical_energy_heating_dhw", "value": 112, "raw": 112},
        2363: {"name": "heating_energy_heating_dhw", "value": 60.8, "raw": 608},
        2372: {"name": "scop_value", "value": 5.42, "raw": 542},
    }


async def main():
    with tempfile.TemporaryDirectory() as directory:
        hass = HomeAssistant(directory)
        entry = SimpleNamespace(entry_id="runtime_scaling_test", data={
            "connection_type": "modbus", "host": "mock.invalid", "unit_id": 20,
        }, options={"scan_interval_seconds": 5}, pref_disable_polling=False)
        coordinator = ModbusCoordinator(hass, entry)
        sensor = KronotermModbusRegSensor(coordinator, 2363,
            "heating_energy_heating_dhw", "kWh", {})
        for poll in range(3):
            data = sample()
            await coordinator._async_select_thermal_scale(data)
            coordinator.async_set_updated_data({"main": {"ModbusReg": [
                {"address": address, **info} for address, info in data.items()]}})
            assert sensor.native_value == (None if poll < 2 else 608)
        assert coordinator.thermal_scale_diagnostics["multiplier"] == 1.0

        # A fresh Store instance must read the real on-disk saved selection.
        restarted = ModbusCoordinator(hass, entry)
        data = sample()
        await restarted._async_select_thermal_scale(data)
        assert data[2363]["value"] == 608
        assert restarted.thermal_scale_diagnostics["status"] == "selected"

        # Manual override works with no SCOP and does not replace automatic storage.
        entry.options = {"thermal_energy_multiplier": "0.1"}
        manual = ModbusCoordinator(hass, entry)
        data = sample()
        del data[2372]
        await manual._async_select_thermal_scale(data)
        assert data[2363]["value"] == 60.8
        assert manual.thermal_scale_diagnostics["mode"] == "manual"
        entry.options = {}
        automatic = ModbusCoordinator(hass, entry)
        data = sample()
        await automatic._async_select_thermal_scale(data)
        assert data[2363]["value"] == 608

        class Options(KronotermOptionsFlowHandler):
            @property
            def config_entry(self):
                return entry

        options = Options()
        options.hass = hass
        form = await options.async_step_init()
        schema = form["data_schema"]
        assert schema({"scan_interval_seconds": 5, "thermal_energy_multiplier": "1.0"})
        result = await options.async_step_init({"scan_interval_seconds": 5,
                                                "thermal_energy_multiplier": "1.0"})
        assert result["data"]["thermal_energy_multiplier"] == "1.0"

        # Exercise the actual HA ButtonEntity implementation, never a real command.
        cloud = SimpleNamespace(shared_device_info={},
            async_acknowledge_alarm=AsyncMock(return_value=True))
        button = KronotermAcknowledgeAlarmButton(cloud, entry)
        await button.async_press()
        cloud.async_acknowledge_alarm.assert_awaited_once()
        cloud.async_acknowledge_alarm.return_value = False
        try:
            await button.async_press()
        except HomeAssistantError:
            pass
        else:
            raise AssertionError("Alarm failure must surface as HomeAssistantError")
        await hass.async_block_till_done()
        await hass.async_stop()
        print("PASS: real HA sensor availability, persisted scaling, manual override, options and alarm button")


asyncio.run(main())
