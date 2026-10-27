"""Review-only runtime checks for PR 70; no live device requests."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from custom_components.kronoterm.const import API_QUERIES_GET
from custom_components.kronoterm.coordinator import KronotermMainCoordinator
from custom_components.kronoterm.sensor import KronotermCloudPressureSensor


async def main():
    coordinator = object.__new__(KronotermMainCoordinator)
    coordinator.config_entry = SimpleNamespace(entry_id="pressure_review")
    coordinator._session_valid = True
    coordinator.api_queries_get = API_QUERIES_GET
    coordinator.data = {}
    coordinator._fetch_consumption = AsyncMock(return_value={})
    coordinator._sync_previous_day_statistics = AsyncMock()
    pressure = "2.5"
    fail_info = False

    async def request(method, query):
        assert method == "GET"
        if query == API_QUERIES_GET["info"]:
            if fail_info:
                raise RuntimeError("Simulated info failure")
            return {"CurrentFunctionData": [{"heating_system_pressure": pressure}]}
        return {"ModbusReg": [{"address": 2325, "value": 1.3}]}

    coordinator._request_with_retries = AsyncMock(side_effect=request)
    sensor = KronotermCloudPressureSensor(coordinator, {})
    assert sensor.unique_id == "pressure_review_kronoterm_heating_system_pressure"
    coordinator.data = await coordinator._async_update_data()
    assert sensor.native_value == 2.5
    pressure = "2.7 bar"
    coordinator.data = await coordinator._async_update_data()
    assert sensor.native_value == 2.7
    fail_info = True
    coordinator.data = await coordinator._async_update_data()
    assert sensor.native_value == 2.7
    coordinator.data = {"main": {"ModbusReg": [{"address": 2326, "value": "2.1"}]}}
    assert sensor.native_value == 2.1
    coordinator.data = {"main": {"ModbusReg": [{"address": 2325, "value": "1.3"}]}}
    assert sensor.native_value is None
    coordinator.data = None
    assert sensor.native_value is None
    print("PASS: actual HA pressure sensor identity, measured value, repeated refresh, failed-page cache, 2326 fallback, no threshold fallback")


asyncio.run(main())
